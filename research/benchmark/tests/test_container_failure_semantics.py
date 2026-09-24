import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.container_executor import _record_incomplete_execution, run_container_harness
from mrhbench.io import ProtocolError, write_json
from mrhbench.artifact_policy import make_collection_policy


class FailureSemanticsTests(unittest.TestCase):
    def test_unknown_not_empty_and_existing_receipts_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "broker").mkdir()
            receipt = root / "broker/rpc-00001.json"
            receipt.write_text('{"observed":"marker existed"}')
            broker = SimpleNamespace(budget=SimpleNamespace(checkpoint=lambda: {"used": {"tool": 1}}))
            _record_incomplete_execution(root, broker, TimeoutError("deadline"))
            record = json.loads((root / "failure.json").read_text())
            self.assertFalse(record["missing_capture_proves_no_solver_output"])
            self.assertFalse(record["artifact_completeness_verified"])
            self.assertFalse(record["automatic_zero"])
            self.assertIsNone(record["quality_score"])
            self.assertEqual(record["preserved_controller_evidence"][0]["path"], "broker/rpc-00001.json")
            self.assertTrue(receipt.is_file())
            self.assertFalse((root / "artifact_inventory.json").exists())

    def test_audit_write_failure_does_not_replace_primary(self):
        with tempfile.TemporaryDirectory() as tmp:
            exc = TimeoutError("primary")
            broker = SimpleNamespace(budget=SimpleNamespace(checkpoint=lambda: {}))
            with patch("mrhbench.container_executor.write_json", side_effect=OSError("disk unavailable")):
                _record_incomplete_execution(Path(tmp), broker, exc)
            self.assertEqual(str(exc), "primary")

    def test_run_preserves_primary_when_audit_and_cleanup_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); public = root / "public"; public.mkdir()
            harness = root / "harness.py"; harness.write_text("def run(*args): pass")
            resources = {"cpus": 1, "memory_mb": 64, "disk_mb": 4, "pids_limit": 16, "wall_seconds": 10}
            write_json(public / "task.json", {"resources": {"container": resources, "execution_budget": {"model_calls": 1, "tool_calls": 1, "wall_seconds": 10}, "image_id": "sha256:" + "a"*64,
                'artifact_collection': make_collection_policy(max_total_bytes=1000,max_entries=10)}, "asset_manifest": [], "tools": []})
            class BrokenSession:
                def __init__(self, **kwargs): self.resources = kwargs["resources"]
                def start(self): raise ProtocolError("primary start failure")
                def close(self): raise OSError("cleanup failure")
            with patch("mrhbench.container_executor.ContainerSession", BrokenSession), patch("mrhbench.container_executor._record_incomplete_execution", side_effect=OSError("audit failure")):
                with self.assertRaisesRegex(ProtocolError, "primary start failure"):
                    run_container_harness(harness=harness, public_root=public, image_id="sha256:"+"a"*64, provider=None, output=root/"run", max_artifact_bytes=1000, max_artifact_files=10)
            cleanup = json.loads((root/"run/cleanup_failure.json").read_text())
            self.assertFalse(cleanup["cleanup_verified"])
            self.assertTrue(cleanup["primary_failure_preserved"])


if __name__ == "__main__": unittest.main()
