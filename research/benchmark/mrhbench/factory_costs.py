"""Token consumption audit of material factory roots (0 model calls).

Every ledgered call whose artifact directory lies under a factory root is attributed through the workspace
recorded in its request.json: papers/<pid>/[units/<TYPE>/]<stage>[.failed-N]/... Failed calls (429, timeout,
errors) and calls inside set-aside attempts are therefore attributed too. The primary measurements are the raw
input_tokens_total (every input token sent, all cache classes) and output_tokens; cache split and prices are
left to later processing (user decision 2026-09-26).

Waste = tokens of calls whose result was not used: failed calls, and completed calls inside a set-aside attempt,
unless a later attempt reused that attempt's output (reviewer-only resume or v4 continuation).
"""
from __future__ import annotations

import statistics
from pathlib import Path

from .io import read_json, utc_now

PRIMARY = ("input_tokens_total", "output_tokens")


def call_tokens(attempt):
    """Raw input (all cache classes) and output tokens; None when the provider reported no usage."""
    u = attempt.get("usage")
    if u is None:
        return None
    meta = attempt.get("metadata") or {}
    cached, write = int(u.get("cached_input_tokens") or 0), int(u.get("cache_write_input_tokens") or 0)
    if str(meta.get("transport", "")).startswith("openai_chat_completions"):
        uncached = int(u.get("uncached_input_tokens", int(u.get("input_tokens") or 0) - cached - write))
    else:
        uncached = int(u.get("input_tokens") or 0)
    return {"input_tokens_total": uncached + write + cached, "output_tokens": int(u.get("output_tokens") or 0)}


def locate(workspace: Path, root: Path):
    """(paper, unit, stage, attempt_dir) for a workspace under a factory root."""
    try:
        parts = workspace.resolve().relative_to(root.resolve()).parts
    except ValueError:
        return None, None, "outside_root", None
    if not parts:
        return None, None, "root", None
    if parts[0] != "papers" or len(parts) < 3:
        return None, None, parts[0], None
    pid, rest, base = parts[1], list(parts[2:]), root.resolve() / "papers" / parts[1]
    unit = None
    if rest[0] == "units" and len(rest) >= 3:
        unit, rest, base = rest[1], rest[2:], base / "units" / rest[1]
    return pid, unit, rest[0], base / rest[0]


def _receipt_reuse(root: Path):
    """Attempt paths (resolved) whose output a later attempt reused."""
    reused = set()
    for receipt in root.glob("papers/**/receipt.json"):
        try:
            r = read_json(receipt)
        except (ValueError, OSError):
            continue
        if r.get("resumed_from"):
            reused.add(str(Path(r["resumed_from"]).resolve().parent))  # prior batch dir
        src = r.get("repair_source")
        if src and ".failed-" in Path(src).name:
            reused.add(str(Path(src).resolve()))  # v4 continuation from a set-aside attempt
    return reused


def _compiled_tasks(root: Path, pid):
    n = 0
    for path in list((root / "papers" / pid).glob("compiled/compiled_tasks.json")) + list(
            (root / "papers" / pid).glob("units/*/compiled/compiled_tasks.json")):
        n += len(read_json(path))
    return n


def _add(bucket, t, attempt):
    bucket["calls"] = bucket.get("calls", 0) + 1
    if t is None:
        bucket["calls_without_usage"] = bucket.get("calls_without_usage", 0) + 1
        t = {k: 0 for k in PRIMARY}
    for k in PRIMARY:
        bucket[k] = bucket.get(k, 0) + t[k]
    bucket["wall_seconds"] = round(bucket.get("wall_seconds", 0) + (attempt.get("wall_seconds") or 0), 1)


def audit_root(root: Path, attempts, label=None):
    root = Path(root).resolve()
    reused = _receipt_reuse(root)
    rows = []
    for a in attempts:
        d = a.get("artifact_directory")
        if not d:
            continue
        try:
            Path(d).resolve().relative_to(root)
        except ValueError:
            continue
        req = Path(d) / "request.json"
        workspace = Path(read_json(req)["workspace"]) if req.is_file() else None
        pid, unit, stage, attempt_dir = locate(workspace, root) if workspace else (None, None, "unknown_workspace", None)
        set_aside = ".failed-" in stage
        stage_base = stage.split(".failed-")[0]
        was_reused = attempt_dir is not None and str(attempt_dir) in reused
        completed = a.get("status") == "completed"
        wasted = (not completed or set_aside) and not was_reused
        rows.append({"call_id": a["id"], "role": a["role"], "status": a["status"], "paper": pid, "unit": unit,
                     "stage": stage_base, "set_aside_attempt": set_aside, "reused_later": was_reused, "wasted": wasted,
                     "tokens": call_tokens(a), "wall_seconds": a.get("wall_seconds"),
                     "num_turns": (a.get("metadata") or {}).get("num_turns"), "artifact_directory": d})
    total, wasted, by_stage, by_paper, by_unit = {}, {}, {}, {}, {}
    for r in rows:
        a = {"wall_seconds": r["wall_seconds"]}
        _add(total, r["tokens"], a)
        if r["wasted"]:
            _add(wasted, r["tokens"], a)
        key = r["stage"] if r["stage"] == "triage" else "%s/%s" % (r["stage"], r["role"])
        _add(by_stage.setdefault(key, {}), r["tokens"], a)
        if r["paper"]:
            _add(by_paper.setdefault(r["paper"], {}), r["tokens"], a)
            if r["wasted"]:
                _add(by_paper[r["paper"]].setdefault("wasted", {}), r["tokens"], a)
            if r["unit"]:
                _add(by_unit.setdefault("%s/%s" % (r["paper"], r["unit"]), {}), r["tokens"], a)
    for pid, b in by_paper.items():
        b["compiled_tasks"] = _compiled_tasks(root, pid)
    construction = [r for r in rows if r["paper"]]
    paper_total = {}
    for r in construction:
        _add(paper_total, r["tokens"], {"wall_seconds": r["wall_seconds"]})
    n_tasks = sum(b["compiled_tasks"] for b in by_paper.values())
    ctor = [r for r in rows if r["role"] == "constructor" and r["status"] == "completed" and r["tokens"]]
    summary = {
        "papers_touched": len(by_paper), "compiled_tasks": n_tasks,
        "construction_calls": paper_total.get("calls", 0),
        "construction_input_tokens": paper_total.get("input_tokens_total", 0),
        "construction_output_tokens": paper_total.get("output_tokens", 0),
        "input_tokens_per_compiled_task": round(paper_total.get("input_tokens_total", 0) / n_tasks) if n_tasks else None,
        "output_tokens_per_compiled_task": round(paper_total.get("output_tokens", 0) / n_tasks) if n_tasks else None,
        "wasted_input_share": round(wasted.get("input_tokens_total", 0) / total["input_tokens_total"], 3) if total.get("input_tokens_total") else None,
        "constructor_completed_calls": len(ctor),
        "constructor_median_input": statistics.median(r["tokens"]["input_tokens_total"] for r in ctor) if ctor else None,
        "constructor_median_output": statistics.median(r["tokens"]["output_tokens"] for r in ctor) if ctor else None,
        "constructor_median_turns": statistics.median(r["num_turns"] for r in ctor if r["num_turns"] is not None) if ctor else None,
    }
    return {"label": label or root.name, "root": str(root), "summary": summary, "total": total, "wasted": wasted,
            "by_stage_role": dict(sorted(by_stage.items())), "by_paper": dict(sorted(by_paper.items())),
            "by_unit": dict(sorted(by_unit.items())), "calls": rows}


def audit(roots, ledger_path: Path):
    attempts = read_json(ledger_path)["attempts"]
    reports = [audit_root(Path(path), attempts, label) for label, path in roots]
    return {"combined": combine(reports), "schema_version": "factory-cost-audit-1", "generated_at": utc_now(), "ledger": str(ledger_path),
            "primary_measurements": list(PRIMARY),
            "note": "Raw input_tokens_total (all cache classes) and output_tokens; cache split and USD are later processing. "
                    "Construction figures exclude scout triage. A paper migrated between roots is counted in each root it used.",
            "roots": reports}


def combine(reports):
    """Per paper across roots (a paper migrated between roots keeps all its calls; tasks = the most any root compiled)."""
    papers = {}
    for r in reports:
        for pid, b in r["by_paper"].items():
            c = papers.setdefault(pid, {"calls": 0, "input_tokens_total": 0, "output_tokens": 0, "wasted_input_tokens": 0,
                                        "compiled_tasks": 0, "roots": []})
            c["calls"] += b["calls"]
            c["input_tokens_total"] += b.get("input_tokens_total", 0)
            c["output_tokens"] += b.get("output_tokens", 0)
            c["wasted_input_tokens"] += (b.get("wasted") or {}).get("input_tokens_total", 0)
            c["compiled_tasks"] = max(c["compiled_tasks"], b["compiled_tasks"])
            c["roots"].append(r["label"])
    tot = {k: sum(c[k] for c in papers.values()) for k in ("calls", "input_tokens_total", "output_tokens", "wasted_input_tokens", "compiled_tasks")}
    n = tot["compiled_tasks"]
    return {"label": "+".join(r["label"] for r in reports), "papers": len(papers), **tot,
            "input_tokens_per_compiled_task": round(tot["input_tokens_total"] / n) if n else None,
            "output_tokens_per_compiled_task": round(tot["output_tokens"] / n) if n else None,
            "wasted_input_share": round(tot["wasted_input_tokens"] / tot["input_tokens_total"], 3) if tot["input_tokens_total"] else None,
            "by_paper": dict(sorted(papers.items()))}


def markdown(report):
    lines = ["# Factory token audit", "", "Primary measurements: total input tokens (all cache classes) and output tokens.", "",
             "| root | papers | compiled tasks | construction calls | input tokens | output tokens | input / task | output / task | wasted input share | constructor median input | median output | median turns |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in report["roots"]:
        s = r["summary"]
        f = lambda v: "-" if v is None else ("{:,}".format(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v))
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["label"], s["papers_touched"], s["compiled_tasks"], s["construction_calls"], f(s["construction_input_tokens"]),
            f(s["construction_output_tokens"]), f(s["input_tokens_per_compiled_task"]), f(s["output_tokens_per_compiled_task"]),
            f(s["wasted_input_share"]), f(s["constructor_median_input"]), f(s["constructor_median_output"]), f(s["constructor_median_turns"])))
    c = report["combined"]
    lines += ["", "## Combined per paper (%s)" % c["label"], "",
              "%d papers, %d construction calls, %s input / %s output tokens, %d compiled tasks; per compiled task %s input / %s output; "
              "wasted input share %s." % (c["papers"], c["calls"], "{:,}".format(c["input_tokens_total"]), "{:,}".format(c["output_tokens"]),
                                          c["compiled_tasks"], "{:,}".format(c["input_tokens_per_compiled_task"] or 0),
                                          "{:,}".format(c["output_tokens_per_compiled_task"] or 0), c["wasted_input_share"]),
              "", "| paper | roots | calls | input | output | wasted input | compiled tasks |", "|---|---|---|---|---|---|---|"]
    for pid, b in c["by_paper"].items():
        lines.append("| %s | %s | %d | {:,} | {:,} | {:,} | %d |".format(b["input_tokens_total"], b["output_tokens"], b["wasted_input_tokens"])
                     % (pid, ",".join(b["roots"]), b["calls"], b["compiled_tasks"]))
    for r in report["roots"]:
        lines += ["", "## %s: by stage and role" % r["label"], "", "| stage/role | calls | input | output |", "|---|---|---|---|"]
        for k, b in r["by_stage_role"].items():
            lines.append("| %s | %d | {:,} | {:,} |".format(b.get("input_tokens_total", 0), b.get("output_tokens", 0)) % (k, b["calls"]))
    return "\n".join(lines) + "\n"
