"""Aggregate the full cost of a run directory from the shared call ledger (0 model calls).

Every ledgered call whose artifact directory lies under --run is included: executor calls
(OpenAI-compatible wrapper; trajectory = http_request_body.json + http_response_body.json per
call), judge/builder/factory calls (Claude native; trajectory = events.jsonl stream), grouped by
role and by task directory. Tokens are normalised to uncached input / cache write / cache read /
output. The dollar figure is an ESTIMATE at list API prices for claude-opus-5-5 (input $4, output
$20 per MTok; cache write 1.25x, cache read 0.1x input); the subscription is not metered per call.
"""
import argparse
import json
from pathlib import Path

from mrhbench.io import read_json, write_json, utc_now

ROOT = Path(__file__).resolve().parent
PRICE = {"input": 4.0, "output": 20.0, "cache_write": 5.0, "cache_read": 0.4}  # USD per MTok, opus-5-5 list price


def tokens(attempt):
    u = attempt.get("usage") or {}
    meta = attempt.get("metadata") or {}
    cached = int(u.get("cached_input_tokens") or 0)
    write = int(u.get("cache_write_input_tokens") or 0)
    if str(meta.get("transport", "")).startswith("openai_chat_completions"):
        # Wrapper prompt_tokens include cache reads and writes.
        uncached = int(u.get("uncached_input_tokens", int(u.get("input_tokens") or 0) - cached - write))
    else:
        uncached = int(u.get("input_tokens") or 0)
    out = int(u.get("output_tokens") or 0)
    # Primary raw counts: every input token sent (all cache classes) and every output token.
    return {"input_tokens_total": uncached + write + cached, "output_tokens": out,
            "uncached_input": uncached, "cache_write": write, "cache_read": cached, "output": out}


def trajectory(attempt):
    d = Path(attempt.get("artifact_directory") or "")
    if (d / "events.jsonl").is_file():
        return {"kind": "claude_stream", "files": [str(d / "events.jsonl")]}
    files = [str(d / n) for n in ("request.json", "http_request_body.json", "http_response_body.json", "result.json") if (d / n).is_file()]
    return {"kind": "http_exchange" if files else "missing", "files": files}


def dollars(t):
    return (t["uncached_input"] * PRICE["input"] + t["output"] * PRICE["output"] + t["cache_write"] * PRICE["cache_write"]
            + t["cache_read"] * PRICE["cache_read"]) / 1e6


def add(bucket, t, wall, usage_missing):
    for k, v in t.items():
        bucket[k] = bucket.get(k, 0) + v
    bucket["calls"] = bucket.get("calls", 0) + 1
    bucket["wall_seconds"] = round(bucket.get("wall_seconds", 0) + (wall or 0), 3)
    bucket["calls_without_usage"] = bucket.get("calls_without_usage", 0) + usage_missing


def report(run: Path, ledger_path: Path):
    run = run.resolve()
    rows, by_role, by_task, total = [], {}, {}, {}
    for a in read_json(ledger_path)["attempts"]:
        d = a.get("artifact_directory")
        if not d:
            continue
        try:
            rel = Path(d).resolve().relative_to(run)
        except ValueError:
            continue
        t = tokens(a)
        missing = int(a.get("usage") is None)
        task = rel.parts[0] if rel.parts else "."
        rows.append({"call_id": a["id"], "role": a["role"], "status": a["status"], "model": a.get("model"), "task": task,
                     "wall_seconds": a.get("wall_seconds"), "tokens": t, "usage_recorded": not missing,
                     "estimated_usd": round(dollars(t), 4), "trajectory": trajectory(a)})
        for bucket in (by_role.setdefault(a["role"], {}), by_task.setdefault(task, {}).setdefault(a["role"], {}), total):
            add(bucket, t, a.get("wall_seconds"), missing)
    for bucket in [total, *by_role.values(), *(r for v in by_task.values() for r in v.values())]:
        bucket["estimated_usd"] = round(dollars({k: bucket.get(k, 0) for k in ("uncached_input", "cache_write", "cache_read", "output")}), 4)
        bucket["_primary"] = "input_tokens_total and output_tokens are the raw measurements; the cache split and USD are secondary"
    return {"schema_version": "run-cost-report-1", "generated_at": utc_now(), "run": str(run), "ledger": str(ledger_path),
            "price_basis": "ESTIMATE at claude-opus-5-5 list API prices; subscription calls are not metered per call", "price_per_mtok_usd": PRICE,
            "missing_usage_is_not_zero": True, "total": total, "by_role": by_role, "by_task": by_task, "calls": rows}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--ledger", type=Path, default=ROOT / "audit/development_call_ledger.json")
    p.add_argument("--out", type=Path, help="Default: <run>/cost_report.json")
    a = p.parse_args()
    r = report(a.run, a.ledger)
    write_json(a.out or a.run / "cost_report.json", r)
    print(json.dumps({"total": r["total"], "by_role": r["by_role"]}, indent=1))


if __name__ == "__main__":
    main()
