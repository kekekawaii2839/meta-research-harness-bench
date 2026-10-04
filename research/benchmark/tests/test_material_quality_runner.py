import json
import tempfile
import unittest
from pathlib import Path
from mrhbench.io import ProtocolError, file_hash, read_json, write_json
from mrhbench.material_quality_runner import QualityBoundRunner


class QualityRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.policy = self.root / "shared.md"
        self.policy.write_text("All six checks; task-specific rules.", encoding="utf-8")
        self.ws = self.root / "role"
        self.ws.mkdir()
        write_json(self.ws / "request.json", {"paper_id": "P"})
        out = self.ws / "output"
        out.mkdir()
        (out / "task.md").write_text("Neutral", encoding="utf-8")
        write_json(out / "package.json", {"facts": [{"fact_id": "F", "kind": "source_fact",
            "statement": "condition", "allowed_stages": ["EXP"]}],
            "environment": {"resources": {"cpus": 2}}, "tasks": [{"task_id": "T",
            "task_type": "EXP", "input_fact_ids": ["F"], "input_contract": {},
            "output_contract": {}, "assets": [{"path": "task.md", "visibility": "public",
            "sha256": file_hash(out / "task.md")}]}]})

    def runner(self, callback):
        class Inner:
            def run(inner, **kwargs):
                callback(kwargs)
                return {"call_id": 1}
        return QualityBoundRunner(Inner(), policy_path=self.policy, project_id="P", round_no=2)

    def emit(self, kwargs, *, identity="P", unknown=False):
        ws = kwargs["workspace"]
        c = read_json(ws / "quality_contract.json")
        ids = list(c["public_inventory"])
        check = {"status": "unknown" if unknown else "clear",
            "rationale": "synthetic fixture only", "evidence": [{"surface_id": ids[0],
                "locator": "fixture", "observation": "synthetic"}]}
        checks = {k: {**check, **({"scope": "entire_bound_public_inventory"} if k in (
            "identity", "author_scale", "target_implementation") else {
            "scope": "selected_surfaces", "inspected_surface_ids": ids})} for k in c["checks"]}
        write_json(ws / "quality_coverage.json", {"contract_sha256": c["contract_sha256"],
            "policy_sha256": c["policy_sha256"], "checks": checks})
        write_json(ws / "review.json", {"schema_version": "material-review-1",
            "paper_id": identity, "decision": "pass_with_pending_runtime"})

    def test_success_keeps_native_return_and_writes_nonsemantic_receipt(self):
        result = self.runner(self.emit).run(workspace=self.ws, prompt="review", role="material_reviewer")
        self.assertEqual(result, {"call_id": 1})
        self.assertIn("not_established", read_json(self.ws / "quality_controller_validation.json")["scientific_acceptance"])

    def test_conflicting_policy_stops_before_call(self):
        (self.ws / "policy.md").write_text("old", encoding="utf-8")
        with self.assertRaises(ProtocolError):
            self.runner(lambda k: self.fail("called")).run(workspace=self.ws, prompt="", role="material_reviewer")

    def test_unknown_cannot_pass(self):
        with self.assertRaises(ProtocolError):
            self.runner(lambda k: self.emit(k, unknown=True)).run(workspace=self.ws, prompt="", role="material_reviewer")

    def test_wrong_identity_not_normalized(self):
        with self.assertRaises(Exception):
            self.runner(lambda k: self.emit(k, identity="P/job")).run(workspace=self.ws, prompt="", role="material_reviewer")
        self.assertEqual(read_json(self.ws / "review.json")["paper_id"], "P/job")

    def test_modified_candidate_rejected(self):
        def mutate(k):
            self.emit(k)
            (self.ws / "output/task.md").write_text("changed", encoding="utf-8")
        with self.assertRaises(ProtocolError):
            self.runner(mutate).run(workspace=self.ws, prompt="", role="material_reviewer")

    def test_constructor_reads_policy_without_self_acceptance(self):
        def ctor(k):
            self.assertIn("quality_policy.md", k["prompt"])
            self.assertFalse((self.ws / "quality_coverage.schema.json").exists())
        self.runner(ctor).run(workspace=self.ws, prompt="", role="constructor")
        self.assertFalse((self.ws / "quality_controller_validation.json").exists())

    def test_adjudicator_exact_id_and_round_schema(self):
        write_json(self.ws / "review_adjudication.schema.json", {"type": "object",
            "required": ["project_id", "round", "action"], "properties": {
                "project_id": {"type": "string"}, "round": {"type": "integer"},
                "action": {"enum": ["pass", "drop"]}}})
        def adjud(k):
            self.emit(k)
            write_json(self.ws / "review_adjudication.json", {
                "project_id": "P", "round": 2, "action": "pass"})
        result = self.runner(adjud).run(workspace=self.ws, prompt="", role="adjudicator")
        self.assertEqual(result["call_id"], 1)

    def test_missing_sidecar_is_not_success(self):
        def missing(k):
            write_json(self.ws / "review.json", {"schema_version": "material-review-1",
                "paper_id": "P", "decision": "pass_with_pending_runtime"})
        with self.assertRaises(FileNotFoundError):
            self.runner(missing).run(workspace=self.ws, prompt="", role="material_reviewer")

    def test_extra_action_cannot_hide_reviewer_unknown_pass(self):
        def spoof(k):
            self.emit(k, unknown=True)
            output = read_json(self.ws / "review.json")
            output["action"] = "drop"
            write_json(self.ws / "review.json", output)
        with self.assertRaises(ProtocolError):
            self.runner(spoof).run(workspace=self.ws, prompt="", role="material_reviewer")
