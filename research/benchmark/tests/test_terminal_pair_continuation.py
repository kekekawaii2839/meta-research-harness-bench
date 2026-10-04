import runpy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import ProtocolError, write_json

validate = runpy.run_path(str(ROOT / "scripts/active/continue_efficiency_terminal_pair.py"))["validate_known_terminal"]


class TerminalContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = {"case_id": "diffusion_science_code_repair", "order": ["incremental", "old"],
                     "job_path": str(self.root / "job.json")}
        self.cases = {"cases": [{}, self.case]}
        self.manifest = {"ledger_path": str(self.root / "ledger.json"),
                         "rounds": {self.case["case_id"]: 2}, "allowed_actions": ["pass", "drop"]}
        self.prior = self.root / "arms" / self.case["case_id"] / "incremental"
        self.result = {"status": "failed_needs_attribution", "error": {
            "type": "ProtocolError", "message": "Adjudication identity/round/action invalid"},
            "cost": {"call_ids": [600, 601, 602]}}
        write_json(self.prior / "result.json", self.result)
        self.ledger = {"used_attempts": 602, "attempts": [{"status": "completed"} for _ in range(602)]}
        write_json(self.root / "ledger.json", self.ledger)
        write_json(self.root / "job.json", {"paper_id": "p", "job_id": "j"})
        self.adj = {"project_id": "p/j", "round": 2, "action": "pass", "finding_decisions": [],
                    "excluded_task_ids": [], "repair_notes": []}
        write_json(self.prior / "adjudicator/review_adjudication.json", self.adj)
        write_json(self.prior / "adjudicator/review.json", {"findings": []})
        write_json(self.prior / "adjudicator/output/package.json", {"tasks": [{"task_id": "t"}]})

    def test_known_terminal_preserves_original_failure_bytes(self):
        before = (self.prior / "result.json").read_bytes()
        self.assertEqual(validate(self.root, self.manifest, self.cases), self.prior)
        self.assertEqual(before, (self.prior / "result.json").read_bytes())

    def test_reserved_or_other_failure_not_eligible(self):
        self.ledger["attempts"][-1]["status"] = "reserved"
        write_json(self.root / "ledger.json", self.ledger)
        with self.assertRaises(ProtocolError):
            validate(self.root, self.manifest, self.cases)
        self.result["error"]["message"] = "unknown operation"
        write_json(self.prior / "result.json", self.result)
        with self.assertRaises(ProtocolError):
            validate(self.root, self.manifest, self.cases)

    def test_other_contract_error_not_silently_repaired(self):
        self.adj["round"] = 99
        write_json(self.prior / "adjudicator/review_adjudication.json", self.adj)
        with self.assertRaises(ProtocolError):
            validate(self.root, self.manifest, self.cases)


if __name__ == "__main__":
    unittest.main()
