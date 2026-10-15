"""Judge acceptance runs on finished P11 tasks (1 judge call per task; executor NOT re-run; original judgment kept).

--judge v38    -> judge v3.8 into <run>/rejudge-v38/
--judge v36    -> judge v3.6 repeat (noise baseline) into <run>/rejudge-v36-repeat/
Both use exactly the evidence records the original v3.6 judgment received (<run>/evidence.json).
Usage: rejudge_v38.py --judge v38|v36 --summary <json> [--dry-run] <unit_dir>@<release>=<run_dir> [...]
"""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import platform_patches  # noqa: F401
import pilot_v5  # noqa: F401  (judge v3.6 policy layers)
from pilot_v5 import sc, read_json, write_json, LEDGER
from mrhbench.io import ProtocolError


def one(judge, unit_spec, run_dir, roles_path, dry_run):
    unit_dir, release = unit_spec.split("@", 1)
    sub = ""
    if "#" in str(run_dir):  # <run_dir>#<subdir>: evidence and baseline judgment of a v3.6 rejudge in that subdir
        run_dir, sub = str(run_dir).split("#", 1)
    unit_dir, run_dir = Path(unit_dir), Path(run_dir)
    base = run_dir / sub if sub else run_dir
    tag = {"v310": "rejudge-v310", "v39": "rejudge-v39", "v38": "rejudge-v38", "v36": "rejudge-v36-repeat"}[judge] + ("-dryrun" if dry_run else "")
    dest = run_dir / tag
    if not (base / "evidence.json").is_file() or dest.exists():
        raise ProtocolError("needs a judged run and a new destination: " + str(dest))
    package = next(p for p in (unit_dir / release / "compiled").iterdir() if p.name.startswith("task-"))
    task = sc.load_task(package / "task.json")
    if read_json(run_dir / "public/task.json")["task_id"] != task["task_id"]:
        raise ProtocolError("release does not match the run's task")
    records = read_json(base / "evidence.json")
    dest.mkdir()
    roles = read_json(Path(roles_path))
    j = roles["judge"]
    from mrhbench.claude_transport import ClaudeNativeRunner
    runner = ClaudeNativeRunner(binary=Path(roles["claude_binary_default"]), model=j["model"], reasoning_effort=j["effort"],
                                ledger=sc.CallLedger(LEDGER), audit_root=dest / "judge_calls", timeout_seconds=j.get("timeout_seconds", 600))
    inv = sc.output_inventory_for_run(task["task_type"], run_dir / "execution")
    if judge in ("v38", "v39", "v310"):
        import judge_v38
        mod = judge_v38
        if judge == "v39":
            import judge_v39
            mod = judge_v39
        if judge == "v310":
            import judge_v310
            judge_v310.CHECKS_SPEC = read_json(unit_dir / "checks.json")["checks"]
            mod = judge_v310
        version = mod.VERSION
        call = lambda: mod.run_native_judge(runner=runner, task_id=task["task_id"], task_type=task["task_type"], records=records,
                                                   output=dest / "judge", python_binary=Path(sys.executable),
                                                   controller_output_inventory=inv, run_dir=run_dir / "execution", dry_run=dry_run)
    else:
        version = pilot_v5.judge_v35.VERSION
        if dry_run:
            call = lambda: {"status": "dry_run"}
        else:
            call = lambda: sc.run_native_judge(runner=runner, task_id=task["task_id"], task_type=task["task_type"], records=records,
                                               output=dest / "judge", python_binary=Path(sys.executable), controller_output_inventory=inv)
    write_json(dest / "rejudge_note.json", {"judge_version": version, "purpose": "judge v3.8 acceptance (v36 = noise-baseline repeat)",
                                            "evidence": str(base / "evidence.json"), "baseline_judgment": str(base / "judge_run_result.json"), "original_judgment_kept": True,
                                            "retry_of_execution": False, "dry_run": dry_run})
    try:
        res = call()
    except Exception as exc:
        res = {"status": "judge_attempt_failed", "error_type": type(exc).__name__, "message": str(exc)[:500]}
    write_json(dest / "judge_run_result.json", res)
    old = read_json(base / "judge_run_result.json")
    return {"run": run_dir.name, "judge": judge, "status": res.get("status"), "quality": res.get("quality"), "quality_v36_original": old.get("quality"),
            "dims": res.get("dimension_scores"), "candidate_quality": res.get("candidate_quality"), "gates": res.get("gates"),
            "prompt_chars": res.get("prompt_chars"), "message": res.get("message")}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pairs", nargs="+")
    ap.add_argument("--judge", choices=["v310", "v39", "v38", "v36"], required=True)
    ap.add_argument("--roles", default=r"D:/mrhbench-local-pilot/factory-v5-driver/config/role_transport_sonnet46low_executor.json")
    ap.add_argument("--summary", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows, start = [], read_json(LEDGER)["used_attempts"]
    for pair in a.pairs:
        unit, run = pair.split("=", 1)
        since = read_json(LEDGER)["attempts"][start:]
        if not a.dry_run and any("provider_rate_limit" in json.dumps(x) or "HTTP 429" in json.dumps(x) for x in since):
            rows.append({"run": run, "judge": a.judge, "status": "not_started_after_rate_limit"})
        else:
            try:
                rows.append(one(a.judge, unit, run, a.roles, a.dry_run))
            except Exception as exc:
                rows.append({"run": run, "judge": a.judge, "status": "stage_failed", "error": "%s: %s" % (type(exc).__name__, str(exc)[:500])})
        write_json(Path(a.summary), {"rows": rows, "dry_run": a.dry_run})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
