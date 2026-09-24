"""Offline SDK tests, never evidence of model scientific quality."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.io import ProtocolError, TraceLog, file_hash
from mrhbench.sdk import Budget, ExecutorClient, TaskTools, validate_submission


class SDKTests(unittest.TestCase):
    def tools(self, path):
        source = path/"inputs"
        source.mkdir()
        (source/"fact.txt").write_text("public fact", encoding="utf-8")
        budget = Budget(model_calls=2, tool_calls=20, wall_seconds=10)
        view = {"tools": ["artifact_read_write"], "asset_manifest": [{"asset_id": "fact", "path": "fact.txt", "sha256": file_hash(source/"fact.txt")}]}
        return TaskTools(view=view, input_root=source, output_root=path/"out", budget=budget, trace=TraceLog(path/"trace.jsonl"))

    def test_assets_artifacts_gpu_and_private_capabilities(self):
        with tempfile.TemporaryDirectory() as d:
            t = self.tools(Path(d))
            self.assertEqual(t.call("asset.read", {"asset_id": "fact"})["text"], "public fact")
            for name, args in [("asset.read", {"asset_id": "private"}), ("artifact.write_text", {"path": "../escape", "text": "x"}),
                               ("cpu_python_execution", {}), ("gpu.execute", {}), ("literature.search", {"query": "x"})]:
                with self.assertRaises(ProtocolError):
                    t.call(name, args)
            a = t.call("artifact.write_text", {"path": "nested/a.txt", "text": "answer"})
            value = {"status": "completed", "content": {}, "artifacts": [a], "omissions": []}
            validate_submission(value, t)
            (t.output_root/"nested/a.txt").write_text("changed")
            with self.assertRaises(ProtocolError):
                validate_submission(value, t)

    def test_asset_mutation_and_fresh_state(self):
        with tempfile.TemporaryDirectory() as d:
            t = self.tools(Path(d))
            (t.input_root/"fact.txt").write_text("changed")
            with self.assertRaises(ProtocolError):
                t.call("asset.read", {"asset_id": "fact"})
            with self.assertRaises(ProtocolError):
                TaskTools(view=t.view, input_root=t.input_root, output_root=t.output_root, budget=t.budget, trace=t.trace)

    def test_budget_counts_failed_requests_and_cancel(self):
        b = Budget(model_calls=1, tool_calls=1, wall_seconds=5)
        b.consume("model")
        with self.assertRaises(ProtocolError): b.consume("model")
        b.cancelled = True
        with self.assertRaises(ProtocolError): b.consume("tool")

    def test_executor_role_and_metadata_are_bound(self):
        class Provider:
            def complete(self, request, **kwargs):
                self.role = kwargs["role"]
                self.timeout = kwargs["timeout_seconds"]
                return {"response": {"a": 1}, "call_id": 3, "usage": {}, "audit_directory": "PRIVATE_PATH"}
        with tempfile.TemporaryDirectory() as d:
            p = Provider()
            c = ExecutorClient(p, Budget(model_calls=1, tool_calls=1, wall_seconds=5), TraceLog(Path(d)/"trace.jsonl"))
            answer = c.complete({}, output_schema={})
            self.assertEqual(p.role, "executor")
            self.assertGreater(p.timeout, 0)
            self.assertLessEqual(p.timeout, 5)
            self.assertNotIn("audit_directory", answer)
            with self.assertRaises(TypeError): c.complete({}, output_schema={}, role="judge")


if __name__ == "__main__": unittest.main()
