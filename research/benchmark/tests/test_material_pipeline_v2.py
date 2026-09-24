import copy
from pathlib import Path
import tempfile
import unittest
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import ProtocolError, read_json, write_json
from mrhbench.material_pipeline import prepare_material_job, validate_job, validate_package, validate_environment, prepare_review, stage_repair_candidate
from mrhbench.material_batch import run_batch


class MaterialPipelineTests(unittest.TestCase):
    def setUp(self):
        self.job = read_json(ROOT / "materials/pilot_v2/jobs/ssa.json")

    def test_real_source_only_staging_hashes_and_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "fresh"
            result = prepare_material_job(self.job, ROOT.parents[1], dest, ROOT / "prompts")
            self.assertFalse(result["model_invoked"])
            self.assertGreater(result["published_bytes"], 1000)
            self.assertFalse((dest / "AGENTS.md").exists())
            self.assertFalse((dest / "submission.json").exists())
            self.assertFalse((dest / "output").exists())
            with self.assertRaises(ProtocolError):
                prepare_material_job(self.job, ROOT.parents[1], dest, ROOT / "prompts")

    def test_source_mutation_and_gpu_rejected(self):
        for key, val in (("gpu", True), ("wall_seconds", 0)):
            job = copy.deepcopy(self.job)
            job["environment_candidate"][key] = val
            with self.assertRaises(ProtocolError):
                validate_job(job, ROOT.parents[1])
        job = copy.deepcopy(self.job)
        job["sources"][0]["sha256"] = "0" * 64
        with self.assertRaises(ProtocolError):
            validate_job(job, ROOT.parents[1])

    def test_no_self_approval(self):
        with self.assertRaises(ProtocolError):
            validate_package({"schema_version": "material-package-1", "status": "accepted"}, ROOT, [])

    def test_cannot_expose_target_to_idea(self):
        p = {"schema_version": "material-package-1", "status": "candidate", "paper_id": "p",
             "facts": [{"fact_id": "f", "kind": "maintainer_scope", "statement": "target method",
                        "allowed_stages": ["IDEA"], "discloses_target_contribution": True}],
             "coverage": [{"task_type": t, "status": "deferred", "reason": "test"} for t in
                          ["LIT", "IDEA", "EXP", "WRITE_CONTENT", "WRITE_EVIDENCE"]],
             "tasks": [{"task_id": "t", "task_type": "IDEA", "paper_id": "p", "split": "development",
                        "input_fact_ids": ["f"]}]}
        with self.assertRaisesRegex(ProtocolError, "Target contribution"):
            validate_package(p, ROOT, [])

    def test_failed_native_receipt_resume_does_not_reinvoke(self):
        class Failing:
            count = 0
            def run(self, **kwargs):
                self.count += 1
                raise RuntimeError("injected transport failure")
        caller = Failing()
        with tempfile.TemporaryDirectory() as tmp:
            args = dict(workspace=ROOT.parents[1], batch_root=Path(tmp)/"batch", templates=ROOT/"prompts",
                        constructor=caller, reviewer=caller)
            first = run_batch([self.job], **args)
            second = run_batch([self.job], **args)
            self.assertEqual(first, second)
            self.assertEqual(caller.count, 1)
            self.assertEqual(first["jobs"][0]["status"], "failed_needs_attribution")

    def test_package_limits_differ(self):
        iv = read_json(ROOT / "materials/pilot_v2/jobs/iv.json")
        self.assertNotEqual(self.job["environment_candidate"]["wall_seconds"], iv["environment_candidate"]["wall_seconds"])
        self.assertFalse(iv["environment_candidate"]["runtime_verified"])

    def test_generated_environment_not_input_only_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/"environment/image").mkdir(parents=True)
            (root/"environment/image/Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf8")
            (root/"environment/smoke.py").write_text("assert 1 + 1 == 2\n", encoding="utf8")
            env = {"gpu": False, "network": "none", "runtime_verified": False, "dependencies": [],
                   "scientific_rationale": "CPU smoke", "resources": {"cpus": 1, "memory_mb": 100,
                   "disk_mb": 100, "pids_limit": 10, "wall_seconds": 60}}
            self.assertFalse(validate_environment(env, root)["runtime_verified"])
            for key, value in (("gpu", True), ("network", "host"), ("runtime_verified", True)):
                bad = dict(env, **{key: value})
                with self.assertRaises(ProtocolError):
                    validate_environment(bad, root)
            (root/"environment/image/answer.json").write_text("{}")
            with self.assertRaisesRegex(ProtocolError, "dependency definitions"):
                validate_environment(env, root)

    def test_reviewer_refuses_constructor_modified_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/"constructor"
            prepare_material_job(self.job, ROOT.parents[1], dest, ROOT/"prompts")
            source = next((dest/"sources").iterdir())
            source.write_bytes(b"modified original")
            with self.assertRaisesRegex(ProtocolError, "altered original"):
                prepare_review(dest, Path(tmp)/"review", ROOT/"prompts")

    def _valid_private_package(self, root):
        (root/"environment/image").mkdir(parents=True)
        (root/"environment/image/Dockerfile").write_text("FROM python:3.12-slim\n")
        (root/"environment/smoke.py").write_text("assert True\n")
        return {"schema_version": "material-package-1", "status": "candidate", "paper_id": "p",
            "facts": [{"fact_id": "private-result", "kind": "source_result", "statement": "withheld result",
                "allowed_stages": [], "discloses_target_contribution": True,
                "evidence": [{"source_id": "s", "source_sha256": "HASH", "locator": "Table 1"}]}],
            "coverage": [{"task_type": t, "status": "candidate" if t == "EXP" else "deferred", "reason": "fixture"}
                for t in ["LIT", "IDEA", "EXP", "WRITE_CONTENT", "WRITE_EVIDENCE"]],
            "tasks": [{"task_id": "t", "task_type": "EXP", "paper_id": "p", "split": "development",
                "input_fact_ids": [], "private_fact_ids": ["private-result"], "private_source_ids": ["s"],
                "input_contract": {"description": "self-contained fixture"}, "output_contract": {"required": ["result"]},
                "verification_plan": {"status": "pending"}, "assets": []}],
            "environment": {"gpu": False, "network": "none", "runtime_verified": False, "dependencies": [],
                "scientific_rationale": "fixture", "resources": {"cpus": 1, "memory_mb": 100, "disk_mb": 100,
                "pids_limit": 10, "wall_seconds": 60}}}

    def test_private_only_empty_allowed_stages_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = self._valid_private_package(root)
            refs = [{"source_id": "s", "sha256": "HASH"}]
            result = validate_package(p, root, refs)
            self.assertEqual(result["structural_gate"], "passed")
            p["tasks"][0]["input_fact_ids"] = ["private-result"]
            with self.assertRaisesRegex(ProtocolError, "Stage-ineligible"):
                validate_package(p, root, refs)

    def test_asset_paths_are_output_relative_never_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = self._valid_private_package(root)
            for bad in ("output/assets/task.md", "sources/000-paper.source"):
                p["tasks"][0]["assets"] = [{"path": bad, "sha256": "HASH", "visibility": "private"}]
                with self.assertRaisesRegex(ProtocolError, "relative to output"):
                    validate_package(p, root, [{"source_id": "s", "sha256": "HASH"}])

    def test_explicit_repair_copies_only_candidate_not_prior_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            prior = Path(tmp)/"old"
            (prior/"constructor/output/assets").mkdir(parents=True)
            original = prior/"constructor/output/assets/task.txt"
            original.write_text("old generated task")
            (prior/"constructor/events.jsonl").write_text("PRIVATE_REASONING")
            write_json(prior/"receipt.json", {"status": "failed_needs_attribution", "error": {"message": "bad path"}})
            new = Path(tmp)/"new"
            new.mkdir()
            result = stage_repair_candidate(prior, new)
            self.assertEqual(original.read_text(), "old generated task")
            self.assertEqual((new/"previous_candidate/assets/task.txt").read_text(), original.read_text())
            self.assertFalse((new/"previous_candidate/events.jsonl").exists())
            self.assertEqual(result["prior_error"]["message"], "bad path")
            self.assertFalse((new/"output").exists())

    def test_repair_cannot_reuse_old_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ProtocolError, "new batch"):
                run_batch([self.job], workspace=ROOT.parents[1], batch_root=Path(tmp), templates=ROOT/"prompts",
                          constructor=None, reviewer=None, repair_from=Path(tmp))

if __name__ == "__main__":
    unittest.main()
