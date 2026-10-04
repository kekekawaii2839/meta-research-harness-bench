"""Synthetic incremental batch integration: no paid calls or Docker."""
from pathlib import Path
import tempfile
import unittest

import test_material_input_integrity as fixtures
ROOT = fixtures.ROOT
from mrhbench.io import read_json, write_json, ProtocolError
from mrhbench.material_batch import run_batch


class IncrementalBatchTests(unittest.TestCase):
    def exercise(self, tmp, *, tamper=False):
        root = Path(tmp)
        fixtures.MaterialInputIntegrityTests().run_case(root)
        prior = root / "batch/fixture/constructor"
        job = read_json(prior / "request.json")
        job["schema_version"] = "material-job-1"
        for source in job["sources"]:
            source["local_path"] = source.pop("path")
        class Constructor:
            def run(self, *, workspace, prompt, **kwargs):
                assert "INCREMENTAL REPAIR CONTRACT" in prompt
                assert (workspace / "output/environment/smoke.py").is_file()
                p = read_json(workspace / "output/package.json")
                p["facts"][0]["statement"] = "Corrected fixture"
                write_json(workspace / "output/package.json", p)
                return {"status": "completed"}
        class Reviewer:
            calls = 0
            def run(self, *, workspace, prompt, **kwargs):
                self.calls += 1
                assert "INDEPENDENT INCREMENTAL REVIEW CONTRACT" in prompt
                assert (workspace / "repair_context/repair_request.json").is_file()
                assert read_json(workspace / "output/package.json")["facts"][0]["statement"] == "Corrected fixture"
                if tamper:
                    (workspace / "repair_context/repair_request.json").write_text("{}")
                write_json(workspace / "review.json", {"schema_version": "material-review-1", "paper_id": "p",
                                                       "decision": "pass_with_pending_runtime"})
                return {"status": "completed"}
        reviewer = Reviewer()
        opts = dict(workspace=prior, batch_root=root / "incremental", templates=ROOT / "prompts",
                    constructor=Constructor(), reviewer=reviewer, repair_from=root / "batch",
                    repair_notes={"fixture": ["Correct fixture statement."]}, incremental_repair=True)
        result = run_batch([job], **opts)
        return job, opts, result

    def test_seed_diff_review_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            job, opts, result = self.exercise(tmp)
            row = result["jobs"][0]
            self.assertEqual(row["status"], "pass_with_pending_runtime")
            self.assertTrue(row["incremental_repair"])
            self.assertEqual(len(row["efficiency_prompt_hashes"]), 2)
            self.assertEqual(run_batch([job], **opts), result)
            self.assertEqual(opts["reviewer"].calls, 1)
            opts["incremental_repair"] = False
            with self.assertRaises(ProtocolError): run_batch([job], **opts)

    def test_incremental_context_is_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, result = self.exercise(tmp, tamper=True)
            self.assertIn("Reviewer altered", result["jobs"][0]["error"]["message"])

    def test_prior_required_before_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ProtocolError):
                run_batch([], workspace=Path(tmp), batch_root=Path(tmp)/"b", templates=ROOT/"prompts",
                          constructor=None, reviewer=None, incremental_repair=True)


if __name__ == "__main__":
    unittest.main()
