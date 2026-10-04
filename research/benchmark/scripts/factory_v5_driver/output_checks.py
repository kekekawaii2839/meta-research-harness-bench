"""Lightweight controller-side deterministic checks of a solver's submission (no model calls).

A task declares its checks in checks.json (list). Six check types only:
  exists       {"files": [...], "any_of": [[glob, ...], ...]}   (each any_of group needs >= 1 match)
  json_schema  {"file": ..., "schema_asset": ...}                  (schema from the task's public assets)
  word_count   {"file": ..., "min": n, "max": n, "strip_math": bool}
  regex_all    {"file": ..., "patterns": {"label": "regex", ...}}  (every pattern must match, case-insensitive)
  regex_none   {"file": ..., "patterns": {...}}                    (a match is reported for the judge to confirm)
  ids_in       {"file": ..., "path": "a.*.b", "allowed_regex": ..., "allowed_asset": ...}
               every value at the JSON path must be among the ids the regex finds in the named public asset
  table_values {"file": ..., "path": "plotted_values", "table_asset": csv, "key_column": "row_id",
                "id_field": "row_id", "field_field": "field", "value_field": "value_shown"}
               every JSON row's shown value must equal the named CSV cell (numeric compare to 2 d.p., else exact)
  claimed_paths {"pointers": ["content.deliverables.*.path", ...]}
               every path the submission manifest (../submission.json next to the artifacts) names at those JSON
               pointers must exist among the collected artifacts; a path that is a released input is reported
               separately (an input is not an output). Leading /work/ is ignored.
  locators_resolve {}  LIT: cited anchor locators exist in the cited library document (locator_check.py)
  rerun        {"workdir": "submission", "command": [...], "compare": [globs], "compare_flag": [globs], "timeout": s}
               re-executes the solver's generation command in a FRESH task-image container (no network, non-root,
               read-only public inputs, a copy of the workdir); "compare" files must regenerate byte-identically
               (hard), "compare_flag" differences are only reported. Originals are never modified.
Each check carries "severity": "hard" (requirement failed) or "flag" (for judge confirmation). Results are
platform evidence for the judge; nothing here computes or overrides a score. Submission code is never run.
"""
from pathlib import Path
import json
import re

import jsonschema

TYPES = {"exists", "json_schema", "word_count", "regex_all", "regex_none", "ids_in", "table_values", "rerun", "claimed_paths",
         "locators_resolve"}
LIBRARY_ROOT = None  # set by the pilot for LIT tasks (controller shared library); locators_resolve is n/a without it


def _read(root, rel):
    p = (Path(root) / rel).resolve()
    if not p.is_relative_to(Path(root).resolve()):
        raise ValueError("path escapes root: " + rel)
    return p


def _walk(value, parts):
    if not parts:
        yield value
        return
    head, rest = parts[0], parts[1:]
    if head == "*":
        items = value if isinstance(value, list) else (value.values() if isinstance(value, dict) else [])
        for v in items:
            yield from _walk(v, rest)
    elif isinstance(value, dict) and head in value:
        yield from _walk(value[head], rest)


def _prose(text):
    """Prose words: displayed ($$...$$) AND inline ($...$, \(...\)) math removed, then whitespace tokens."""
    text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.S)
    text = re.sub(r"\\\[.*?\\\]", " ", text, flags=re.S)
    text = re.sub(r"(?<!\\)\$[^$\n]+?(?<!\\)\$", " ", text)
    text = re.sub(r"\\\(.*?\\\)", " ", text, flags=re.S)
    return len(re.findall(r"\S+", text))


def _rerun(check, out_root, public_root, image_id):
    import hashlib, shutil, subprocess, tempfile, uuid
    if not image_id:
        return False, {"error": "no task image id supplied to the checker"}
    src = _read(out_root, check["workdir"])
    if not src.is_dir():
        return False, {"error": "workdir missing: " + check["workdir"]}
    tmp = Path(tempfile.mkdtemp(prefix="rerun-"))
    work = tmp / "work"
    shutil.copytree(src, work / check["workdir"])
    def digest(root, pats):
        out = {}
        for pat in pats:
            for f in sorted(Path(root).glob(pat)):
                out[f.relative_to(root).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
        return out
    before = digest(out_root, check.get("compare", []) + check.get("compare_flag", []))
    for rel in before:  # remove outputs so they must be regenerated
        (work / rel).unlink(missing_ok=True)
    name = "mrh-rerun-" + uuid.uuid4().hex[:12]
    argv = ["docker", "run", "--rm", "--name", name, "--network", "none", "--user", "10001:10001", "--cpus", "1",
            "--memory", "2g", "--pids-limit", "128", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "-e", "MRH_PUBLIC_ROOT=/inputs/public", "-e", "HOME=/tmp", "-e", "MPLCONFIGDIR=/tmp",
            "-v", str(Path(public_root).resolve()) + ":/inputs/public:ro",
            "-v", str(work) + ":/work", "-w", "/work/" + check["workdir"], image_id] + check["command"]
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=check.get("timeout", 300))
        code, err = proc.returncode, proc.stderr.decode("utf8", "replace")[-1500:]
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        code, err = "timeout", ""
    after = digest(work, check.get("compare", []) + check.get("compare_flag", []))
    hard = [k for k in digest(out_root, check.get("compare", [])) if after.get(k) != before[k]]
    soft = [k for k in digest(out_root, check.get("compare_flag", [])) if after.get(k) != before[k]]
    shutil.rmtree(tmp, ignore_errors=True)
    detail = {"exit_code": code, "stderr_tail": err, "regenerated_differs_hard": hard, "regenerated_differs_flag": soft,
              "compared": sorted(before), "note": "solver code executed only inside a fresh isolated task-image container"}
    return code == 0 and not hard, detail


def run_one(check, out_root, public_root, image_id=None):
    kind = check["type"]
    res = {"id": check["id"], "type": kind, "severity": check["severity"], "requirement": check.get("requirement", "")}
    try:
        if kind == "exists":
            missing = [f for f in check.get("files", []) if not _read(out_root, f).is_file()]
            groups = [g for g in check.get("any_of", []) if not any(p.is_file() for pat in g for p in Path(out_root).glob(pat))]
            res.update(passed=not missing and not groups, detail={"missing": missing, "unsatisfied_any_of": groups})
        elif kind == "json_schema":
            data = json.loads(_read(out_root, check["file"]).read_text(encoding="utf8"))
            schema = json.loads(_read(public_root, check["schema_asset"]).read_text(encoding="utf8"))
            if check.get("schema_files_key"):  # multi-file schema: {"files": {name: {...}}, "$defs": {...}}
                schema = {**{k: v for k, v in schema.items() if k in ("$schema", "$defs", "definitions")},
                          **schema["files"][check["schema_files_key"]]}
            errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
            res.update(passed=not errors, detail={"errors": [("/".join(map(str, e.path)) or "$") + ": " + e.message[:300] for e in errors[:20]]})
        elif kind == "word_count":
            text = _read(out_root, check["file"]).read_text(encoding="utf8")
            n = _prose(text) if check.get("strip_math") else len(re.findall(r"\S+", text))
            res.update(passed=check["min"] <= n <= check["max"], detail={"words": n, "min": check["min"], "max": check["max"],
                       "all_whitespace_tokens": len(re.findall(r"\S+", text)),
                       "counting": ("whitespace tokens after removing displayed and inline math" if check.get("strip_math")
                                    else "whitespace tokens"),
                       "note": "word counts depend on convention; treat near-boundary results as approximate"})
        elif kind in ("regex_all", "regex_none"):
            text = _read(out_root, check["file"]).read_text(encoding="utf8")
            hits = {k: [m.group(0)[:80] for m in re.finditer(p, text, flags=re.I)][:5] for k, p in check["patterns"].items()}
            if kind == "regex_all":
                missing = [k for k, v in hits.items() if not v]
                res.update(passed=not missing, detail={"missing": missing})
            else:
                found = {k: v for k, v in hits.items() if v}
                res.update(passed=not found, detail={"matches": found})
        elif kind == "ids_in":
            data = json.loads(_read(out_root, check["file"]).read_text(encoding="utf8"))
            allowed = set(re.findall(check["allowed_regex"], _read(public_root, check["allowed_asset"]).read_text(encoding="utf8")))
            used = [v for v in _walk(data, check["path"].split(".")) if isinstance(v, str)]
            bad = sorted(set(used) - allowed)
            res.update(passed=bool(used) and not bad, detail={"checked": len(used), "unknown_ids": bad[:50], "allowed_count": len(allowed)})
        elif kind == "table_values":
            import csv
            data = json.loads(_read(out_root, check["file"]).read_text(encoding="utf8"))
            with _read(public_root, check["table_asset"]).open(encoding="utf8", newline="") as f:
                table = {r[check["key_column"]]: r for r in csv.DictReader(f)}
            bad, n = [], 0
            for row in _walk(data, check["path"].split(".") + ["*"]):
                if not isinstance(row, dict):
                    continue
                n += 1
                rid, field, shown = row.get(check["id_field"]), row.get(check["field_field"]), str(row.get(check["value_field"], ""))
                cell = (table.get(rid) or {}).get(field)
                if cell is None:
                    bad.append({"row": rid, "field": field, "shown": shown, "expected": None})
                    continue
                try:
                    ok = round(float(shown), 2) == round(float(cell), 2)
                except ValueError:
                    ok = shown.strip() == cell.strip()
                if not ok:
                    bad.append({"row": rid, "field": field, "shown": shown, "expected": cell})
            res.update(passed=n > 0 and not bad, detail={"checked": n, "mismatches": bad[:30], "mismatch_count": len(bad)})
        elif kind == "claimed_paths":
            sub = json.loads((Path(out_root).parent / "submission.json").read_text(encoding="utf8"))
            claimed = []
            for ptr in check["pointers"]:
                claimed += [v for v in _walk(sub, ptr.split(".")) if isinstance(v, str) and v.strip()]
            missing, inputs, present = [], [], []
            for c in dict.fromkeys(claimed):
                rel = c.strip()[len("/work/"):] if c.strip().startswith("/work/") else c.strip()
                rel = rel.split("#")[0].split(":")[0] if not Path(out_root, rel).exists() else rel
                try:
                    if rel and _read(out_root, rel).exists():
                        present.append(c)
                        continue
                except ValueError:
                    pass
                pub = rel[len("/inputs/public/"):] if rel.startswith("/inputs/public/") else rel
                try:
                    is_input = bool(pub) and _read(public_root, pub).exists()
                except ValueError:
                    is_input = False
                (inputs if is_input else missing).append(c)
            res.update(passed=(not missing and not inputs) if claimed else None,
                       detail={"claimed": len(claimed), "present": len(present), "missing_from_artifacts": missing[:50],
                               "released_inputs_claimed_as_outputs": inputs[:50],
                               "note": "claims taken from the solver's submission manifest; the judge decides the consequence"})
        elif kind == "locators_resolve":
            if LIBRARY_ROOT is None:
                res.update(passed=None, detail={"not_applicable": "no library configured for this run"})
            else:
                from locator_check import check as _loc
                ok, detail = _loc(out_root, public_root, LIBRARY_ROOT)
                res.update(passed=ok, detail=detail)
        elif kind == "rerun":
            ok, detail = _rerun(check, out_root, public_root, image_id)
            res.update(passed=ok, detail=detail)
        else:
            raise ValueError("unknown check type " + kind)
    except FileNotFoundError as exc:
        name = Path(exc.filename or "").name
        if kind in ("regex_none", "word_count"):
            # nothing to scan; the missing deliverable itself is reported by the exists check
            res.update(passed=None, detail={"not_applicable": "file not found: " + name})
        else:
            res.update(passed=False, detail={"error": "file not found: " + name})
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        res.update(passed=False, detail={"error": "unparseable: " + str(exc)[:200]})
    return res


def validate_spec(spec):
    ids = [c["id"] for c in spec]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate check ids")
    for c in spec:
        if c.get("type") not in TYPES or c.get("severity") not in ("hard", "flag"):
            raise ValueError("bad check " + str(c.get("id")))
        for pat in (c.get("patterns") or {}).values():
            re.compile(pat)


def run_checks(spec, out_root, public_root, image_id=None):
    validate_spec(spec)
    results = [run_one(c, out_root, public_root, image_id) for c in spec]
    return {"schema_version": "output-checks-1", "results": results,
            "hard_failed": [r["id"] for r in results if r["severity"] == "hard" and r["passed"] is False],
            "flags_raised": [r["id"] for r in results if r["severity"] == "flag" and r["passed"] is False],
            "not_applicable": [r["id"] for r in results if r["passed"] is None],
            "note": "Controller deterministic checks on collected outputs. Submission code was not executed. "
                    "Not a score: the judge applies the rubric anchors; flags require judge confirmation."}
