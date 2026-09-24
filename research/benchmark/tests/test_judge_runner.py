"""Scripted transport exercises control flow only; never a judge quality result."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import ProtocolError, read_json
from mrhbench.judge_runner import evidence_record, run_judge
from mrhbench.scoring import DIMENSIONS


class ScriptedClient:
    def __init__(self):
        self.requests = []

    def complete(self, request, **kwargs):
        self.requests.append(request)
        if len(self.requests) == 1:
            body = {"reads": [{"evidence_id": r["evidence_id"], "start_line": 1, "end_line": 1} for r in request["input"]["evidence_inventory"]]}
            action = {"kind": "read_evidence", "payload_json": json.dumps(body)}
        elif kwargs["role"] == "feedback":
            action = {"kind": "final", "payload_json": json.dumps({"issues": [], "limitations": ["Scripted test, not actual model feedback"]})}
        else:
            refs = [r["receipt_id"] for r in request["history"][-1]["tool_results"]]
            body = {"status": "scored", "dimensions": {d: {"score": 2, "rationale": "Synthetic control-flow fixture", "refs": refs} for d in DIMENSIONS["WRITE_CONTENT"]},
                    "checks": [], "serious_issues": [], "uncertainty": ["synthetic"], "failure_reason": None}
            action = {"kind": "final", "payload_json": json.dumps(body)}
        return {"response": action, "call_id": len(self.requests), "audit_directory": "synthetic-unit-test-not-a-live-model"}


class JudgeRunnerTests(unittest.TestCase):
    def test_read_before_grade_and_separate_public_feedback(self):
        records = [evidence_record("task", "task", "task"), evidence_record("submission", "submission", "submission"),
                   evidence_record("reference", "reference", "PRIVATE_REFERENCE_CANARY", visibility="private")]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scoring = ScriptedClient()
            result = run_judge(client=scoring, task_id="fixture", task_type="WRITE_CONTENT", records=records, output=root/"score")
            self.assertEqual(result["model_steps"], 2)
            self.assertEqual(scoring.requests[0]["remaining_evidence_text_chars"], 120000)
            self.assertLess(scoring.requests[1]["remaining_evidence_text_chars"], 120000)
            self.assertEqual(result["acceptance_status"], "awaiting_manual_trajectory_review")
            feedback = ScriptedClient()
            run_judge(client=feedback, task_id="fixture", task_type="WRITE_CONTENT", records=records, output=root/"feedback", mode="feedback", dimension_scores=result["dimension_scores"])
            self.assertNotIn("PRIVATE_REFERENCE_CANARY", json.dumps(feedback.requests))
            self.assertNotIn("PRIVATE_REFERENCE_CANARY", (root/"feedback/evidence.json").read_text())
            with self.assertRaises(ProtocolError):
                run_judge(client=scoring, task_id="fixture", task_type="WRITE_CONTENT", records=records, output=root/"score")

    def test_step_limit_is_judge_failure_not_scientific_zero(self):
        records = [evidence_record("task", "task", "task")]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/"limited"
            with self.assertRaises(ProtocolError):
                run_judge(client=ScriptedClient(), task_id="fixture", task_type="WRITE_CONTENT", records=records, output=out, max_steps=1)
            failure = read_json(out/"failure.json")
            self.assertEqual(failure["status"], "judge_failure")
            self.assertIsNone(failure["scientific_quality"])


if __name__ == "__main__":
    unittest.main()
