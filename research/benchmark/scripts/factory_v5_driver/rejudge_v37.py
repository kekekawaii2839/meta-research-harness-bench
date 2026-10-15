"""Re-judge finished P11 runs with judge v3.7 into <run>/rejudge-v37/ (1 judge call per task; executor NOT re-run).

Inputs are exactly the evidence records the original v3.6 judge received (<run>/evidence.json, including its
controller checks and platform-failure summary), so the comparison isolates the v3.7 evidence-access changes.
The original judgment is kept. Usage:
  rejudge_v37.py [--dry-run] [--tag rejudge-v37] <unit_dir>@<release>=<run_dir> [...]
"""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import platform_patches  # noqa: F401  (must precede mrhbench imports)
import pilot_v5  # noqa: F401  (judge v3.6 policy layers)
from pilot_v5 import sc, read_json, write_json, LEDGER
import judge_v37
from mrhbench.io import ProtocolError


def rejudge(unit_spec, run_dir, roles_path, tag, dry_run):
    unit_dir, release = unit_spec.split("@", 1)
    unit_dir, run_dir = Path(unit_dir), Path(run_dir)
    dest = run_dir / tag
    if not (run_dir / "execution/submission.json").is_file() or not (run_dir / "evidence.json").is_file():
        raise ProtocolError("needs a completed, judged execution")
    if dest.exists():
        raise ProtocolError("destination exists: " + str(dest))
    package = next(p for p in (unit_dir / release / "compiled").iterdir() if p.name.startswith("task-"))
    task = sc.load_task(package / "task.json")
    if read_json(run_dir / "public/task.json")["task_id"] != task["task_id"]:
        raise ProtocolError("release does not match the run's task")
    records = read_json(run_dir / "evidence.json")
    dest.mkdir()
    write_json(dest / "rejudge_note.json", {"judge_version": judge_v37.VERSION, "reason": "judge v3.7 acceptance: same evidence as the original "
                                            "v3.6 judgment, v3.7 evidence access (listing/catalog/search, 24000-char pages, merged timeline, "
                                            "LIT citation bundle)", "original_judgment_kept": str(run_dir / "judge_run_result.json"),
                                            "retry_of_execution": False, "dry_run": dry_run})
    roles = read_json(Path(roles_path))
    j = roles["judge"]
    from mrhbench.claude_transport import ClaudeNativeRunner
    runner = ClaudeNativeRunner(binary=Path(roles["claude_binary_default"]), model=j["model"], reasoning_effort=j["effort"],
                                ledger=sc.CallLedger(LEDGER), audit_root=dest / "judge_calls", timeout_seconds=j.get("timeout_seconds", 600))
    try:
        judge = judge_v37.run_native_judge(runner=runner, task_id=task["task_id"], task_type=task["task_type"], records=records,
                                           output=dest / "judge", python_binary=Path(sys.executable),
                                           controller_output_inventory=sc.output_inventory_for_run(task["task_type"], run_dir / "execution"),
                                           run_dir=run_dir / "execution", dry_run=dry_run)
    except Exception as exc:
        judge = {"status": "judge_attempt_failed", "error_type": type(exc).__name__, "message": str(exc)[:500]}
    write_json(dest / "judge_run_result.json", judge)
    old = read_json(run_dir / "judge_run_result.json")
    return {"run": run_dir.name, "task_type": task["task_type"], "status": judge.get("status"), "quality_v37": judge.get("quality"),
            "quality_v36": old.get("quality"), "dims_v37": judge.get("dimension_scores"), "dims_v36": old.get("dimension_scores"),
            **({k: judge.get(k) for k in ("prompt_chars", "records", "listed", "library_documents", "listed_library_documents",
                                          "solver_touched", "solver_cited", "guidance_named", "message")})}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pairs", nargs="+")
    ap.add_argument("--roles", default=r"D:/mrhbench-local-pilot/factory-v5-driver/config/role_transport_sonnet46low_executor.json")
    ap.add_argument("--tag", default="rejudge-v37")
    ap.add_argument("--summary", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows = []
    start = read_json(LEDGER)["used_attempts"]
    for pair in a.pairs:
        unit, run = pair.split("=", 1)
        since = read_json(LEDGER)["attempts"][start:]
        if not a.dry_run and any("provider_rate_limit" in json.dumps(x) or "HTTP 429" in json.dumps(x) for x in since):
            rows.append({"run": run, "status": "not_started_after_rate_limit"})
        else:
            try:
                rows.append(rejudge(unit, run, a.roles, a.tag, a.dry_run))
            except Exception as exc:
                rows.append({"run": run, "status": "stage_failed", "error": "%s: %s" % (type(exc).__name__, str(exc)[:500])})
        write_json(Path(a.summary), {"rows": rows, "judge_version": judge_v37.VERSION, "dry_run": a.dry_run}) if True else None
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
