"""Finish a P11 pilot task whose execution completed but whose post-execution step crashed in the controller
(e.g. 2026-10-04 UnicodeDecodeError on a binary public asset, fixed in platform_patches item 7). Same steps as
pilot_v5.run_task after execution: evidence -> controller checks -> platform failure summary -> judge (1 model call).
The executor is NOT re-run. Usage: finish_pilot_judge.py <unit_dir>@<release> <task output dir> <roles.json>"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import platform_patches  # noqa: F401  (must precede mrhbench imports)
import pilot_v5
from pilot_v5 import sc, judge_v35, run_checks, read_json, write_json, LEDGER
unit_s, out_s, roles_path = sys.argv[1], sys.argv[2], sys.argv[3]
unit_dir, release = unit_s.split("@", 1)
unit_dir, output = Path(unit_dir), Path(out_s)
if (output / "judge_run_result.json").exists() or (output / "evidence.json").exists() or not (output / "execution/submission.json").is_file():
    raise SystemExit("needs a completed execution without evidence/judgment")
package = next(p for p in (unit_dir / release / "compiled").iterdir() if p.name.startswith("task-"))
task = sc.load_task(package / "task.json"); view = read_json(output / "public/task.json")
assert view["task_id"] == task["task_id"]
if task["task_type"] == "LIT":
    raise SystemExit("LIT needs the live literature service trace; not supported here")
records = sc.evidence_for_run(task, package, output / "public", output / "execution")
import output_checks as _oc
_oc.LIBRARY_ROOT = None
checks = run_checks(read_json(unit_dir / "checks.json")["checks"], output / "execution/artifacts", output / "public", image_id=view["resources"]["image_id"])
write_json(output / "output_checks.json", checks, exclusive=True)
records.append(sc.evidence_record("controller-output-checks", "program_check", json.dumps(checks, ensure_ascii=False, indent=1)))
records.append(judge_v35.summary_record(sc, output / "execution"))
write_json(output / "evidence.json", records)
write_json(output / "finish_note.json", {"reason": sys.argv[4] if len(sys.argv) > 4 else "post-execution controller step crashed (binary public asset decode); fixed in platform_patches item 7; executor not re-run",
                                         "platform_patches": platform_patches.APPLIED, "judge_version": judge_v35.VERSION})
roles = read_json(Path(roles_path)); j = roles["judge"]
from mrhbench.claude_transport import ClaudeNativeRunner
runner = ClaudeNativeRunner(binary=Path(roles["claude_binary_default"]), model=j["model"], reasoning_effort=j["effort"], ledger=sc.CallLedger(LEDGER),
                            audit_root=output / "judge_calls", timeout_seconds=j.get("timeout_seconds", 600))
try:
    judge = sc.run_native_judge(runner=runner, task_id=task["task_id"], task_type=task["task_type"], records=records,
                                output=output / "judge", python_binary=Path(sys.executable),
                                controller_output_inventory=sc.output_inventory_for_run(task["task_type"], output / "execution"))
except Exception as exc:
    judge = {"status": "judge_attempt_failed", "error_type": type(exc).__name__, "message": str(exc)[:500]}
write_json(output / "judge_run_result.json", judge)
print(json.dumps({"status": judge.get("status"), "quality": judge.get("quality"), "hard_failed": checks["hard_failed"], "flags": checks["flags_raised"]}))
