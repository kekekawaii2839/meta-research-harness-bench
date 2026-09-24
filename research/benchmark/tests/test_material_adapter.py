import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import ProtocolError, file_hash, read_json, write_json
from mrhbench.material_adapter import compile_package
from mrhbench.material_pipeline import stage_repair_candidate
from mrhbench.materials import export_task
from mrhbench.artifact_policy import make_collection_policy


class MaterialAdapterTests(unittest.TestCase):
    def fixture(self, root):
        out = root / "source"
        (out / "environment/image").mkdir(parents=True)
        (out / "environment/image/Dockerfile").write_text("FROM python:3.12-slim\n")
        (out / "environment/smoke.py").write_text("print('smoke')\n")
        (out / "assets").mkdir()
        (out / "assets/start.txt").write_text("Public fixed inputs")
        asset = {"path": "assets/start.txt", "sha256": file_hash(out / "assets/start.txt"), "visibility": "public"}
        p = {"schema_version": "material-package-1", "status": "candidate", "paper_id": "p",
            "facts": [{"fact_id": "f", "kind": "maintainer_scope", "statement": "Fixed scope", "evidence": [],
                       "allowed_stages": ["EXP"], "discloses_target_contribution": True},
                      {"fact_id": "secret", "kind": "maintainer_scope", "statement": "CANARY_PRIVATE", "evidence": [],
                       "allowed_stages": [], "discloses_target_contribution": True}],
            "coverage": [{"task_type": t, "status": "candidate" if t == "EXP" else "deferred", "reason": "fixture"}
                         for t in ("LIT", "IDEA", "EXP", "WRITE_CONTENT", "WRITE_EVIDENCE")],
            "tasks": [{"task_id": "t", "task_type": "EXP", "paper_id": "p", "split": "development",
                       "input_fact_ids": ["f"], "private_fact_ids": ["secret"], "assets": [asset],
                       "input_contract": {"files": [asset]}, "output_contract": {"require": "real evidence"},
                       "verification_plan": {"private": "CANARY_PRIVATE"}}],
            "environment": {"gpu": False, "network": "none", "runtime_verified": False, "dependencies": [],
                            "scientific_rationale": "Small CPU experiment", "resources": {"cpus": 1,
                            "memory_mb": 256, "disk_mb": 32, "pids_limit": 32, "wall_seconds": 300}}}
        write_json(out / "package.json", p)
        return out, dict(request={"sources": []}, execution_budgets={"t": {
            "model_calls": 3, "tool_calls": 20, "wall_seconds": 300}}, image_id="sha256:" + "a" * 64,
            public_rubrics={"EXP": {"version": "test"}},
            artifact_collections={'t': make_collection_policy(max_total_bytes=1024*1024,max_entries=100)})

    def test_compiles_public_private_without_gate_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); out, args = self.fixture(root)
            before = file_hash(out / "package.json")
            result = compile_package(out, destination=root / "compiled", **args)
            self.assertFalse(result["formal_accepted"])
            task = read_json(root / "compiled/t/task.json")
            self.assertTrue(all(g["status"] == "pending" for g in task["gates"].values()))
            self.assertEqual(task["public"]["resources"]["container"]["wall_seconds"], 300)
            self.assertEqual(task['public']['resources']['artifact_collection'], args['artifact_collections']['t'])
            self.assertIn("hypothesis_evidence_map", task["public"]["output_contract"]["required"])
            export_task(task, root / "compiled/t", root / "release", audience="development_executor")
            self.assertNotIn("CANARY_PRIVATE", ''.join(p.read_text() for p in (root / "release").rglob('*') if p.is_file()))
            self.assertEqual(file_hash(out / "package.json"), before)
            with self.assertRaises(ProtocolError):
                compile_package(out, destination=root / "compiled", **args)

    def test_reject_missing_budget_mutable_image_and_wall_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); out, args = self.fixture(root)
            for replacement in ({"execution_budgets": {}}, {"image_id": "python:latest"},
                                {"execution_budgets": {"t": {"model_calls": 3, "tool_calls": 20, "wall_seconds": 301}}}):
                with self.assertRaises(ProtocolError):
                    compile_package(out, destination=root / "compiled", **(args | replacement))
                self.assertFalse((root / "compiled").exists())

    def test_adjudicated_notes_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); old = root / "prior/constructor/output"
            old.mkdir(parents=True); (old / "package.json").write_text("{}")
            destination = root / "next"; destination.mkdir()
            result = stage_repair_candidate(root / "prior", destination,
                                            adjudicated_notes=["Do not force experimental grids"])
            self.assertEqual(result["maintainer_adjudicated_notes"], ["Do not force experimental grids"])

    def test_visual_preview_is_explicit_controller_rule_not_source_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); out, args = self.fixture(root)
            package = read_json(out / "package.json")
            package["tasks"][0]["task_type"] = "WRITE_EVIDENCE"
            package["facts"][0]["allowed_stages"] = ["WRITE_EVIDENCE"]
            write_json(out / "package.json", package)
            before = file_hash(out / "package.json")
            args["public_rubrics"] = {"WRITE_EVIDENCE": {"version": "test"}}
            compile_package(out, destination=root / "compiled", require_visual_png_preview=True, **args)
            task = read_json(root / "compiled/t/task.json")
            self.assertIn("same-content PNG preview", task["public"]["prompt"])
            self.assertIn("native PNG", task["private"]["controller_visual_preview_rule"])
            self.assertEqual(file_hash(out / "package.json"), before)


if __name__ == "__main__":
    unittest.main()
