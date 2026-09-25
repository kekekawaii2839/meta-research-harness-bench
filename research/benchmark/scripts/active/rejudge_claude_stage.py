"""Re-judge an already executed development stage with the current Claude judge (no re-execution).

Used when the execution itself is valid but the judgment failed for judge/platform reasons
(e.g. a malformed judge output or an image delivered downscaled). Evidence is rebuilt from the
frozen stage directory with the current controller evidence builder; the original judge
directory is never modified. One attempt, no retry.
"""
import argparse
import json
import sys
from pathlib import Path

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.claude_transport import ClaudeNativeRunner
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, file_hash, read_json, write_json
from mrhbench.literature_judge_evidence import build_literature_judge_evidence
from mrhbench.materials import load_task
from mrhbench.native_judge import CLAUDE_VERSION, run_native_judge
from mrhbench.stage_controller import evidence_for_run, output_inventory_for_run

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=Path, required=True, help="Existing stage output directory")
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--label", required=True, help="New judge subdirectory name, e.g. judge_v33")
    p.add_argument("--reason", required=True)
    p.add_argument("--roles", type=Path, default=ROOT / "config/role_transport_claude_v1.json")
    a = p.parse_args()
    stage, package = a.stage.resolve(), a.package.resolve()
    out = stage / a.label
    if out.exists():
        raise ProtocolError("Re-judge output must be new")
    task = load_task(package / "task.json")
    if not (stage / "execution/submission.json").is_file():
        raise ProtocolError("No completed execution to re-judge")
    records = evidence_for_run(task, package, stage / "public", stage / "execution")
    if task["private"].get("corpus_configuration"):
        raise ProtocolError("LIT re-judge needs the frozen literature service; not supported here")
    roles = read_json(a.roles)
    judge = roles["judge"]
    runner = ClaudeNativeRunner(binary=Path(roles["claude_binary_default"]), model=judge["model"], reasoning_effort=judge["effort"],
                                ledger=CallLedger(ROOT / "audit/development_call_ledger.json"), audit_root=stage / (a.label + "_calls"),
                                timeout_seconds=judge.get("timeout_seconds", 600))
    write_json(stage / (a.label + "_request.json"), {"reason": a.reason, "judge_version": CLAUDE_VERSION,
               "native_judge_sha256": file_hash(ROOT / "mrhbench/native_judge.py"), "evidence_records": len(records),
               "previous_judge_directories_untouched": True, "retry": False}, exclusive=True)
    try:
        result = run_native_judge(runner=runner, task_id=task["task_id"], task_type=task["task_type"], records=records, output=out,
                                  python_binary=Path(sys.executable),
                                  controller_output_inventory=output_inventory_for_run(task["task_type"], stage / "execution"))
        summary = {"status": result.get("status"), "quality": result.get("quality"), "dimension_scores": result.get("dimension_scores")}
    except Exception as exc:
        summary = {"status": "judge_attempt_failed", "error_type": type(exc).__name__, "message": str(exc)[:500]}
    write_json(stage / (a.label + "_result.json"), summary, exclusive=True)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
