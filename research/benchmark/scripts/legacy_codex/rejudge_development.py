"""Explicit new judge/feedback run on saved development evidence, no solver rerun."""
import argparse
from pathlib import Path

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.costs import CallLedger
from mrhbench.io import read_json
from mrhbench.judge_runner import run_judge
from mrhbench.providers import CodexJSONTransport


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--codex-binary", type=Path, required=True)
    p.add_argument("--records", type=Path, required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--task-type", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--feedback-from", type=Path)
    p.add_argument("--max-evidence-chars", type=int, default=120000)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    cfg = read_json(root/"config/development.json")["judge"]
    client = CodexJSONTransport(binary=args.codex_binary, model=cfg["model"], reasoning_effort=cfg["reasoning_effort"],
                              ledger=CallLedger(root/"audit/development_call_ledger.json"), audit_root=root/"audit/model_calls")
    grades = read_json(args.feedback_from)["dimension_scores"] if args.feedback_from else None
    result = run_judge(client=client, task_id=args.task_id, task_type=args.task_type, records=read_json(args.records), output=args.output,
                      mode="feedback" if args.feedback_from else "score", dimension_scores=grades, max_steps=5,
                      max_text_chars=args.max_evidence_chars)
    print({"status": result.get("status", "feedback_generated"), "acceptance": result["acceptance_status"], "output": str(args.output)})
