import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.executor_broker import ExecutorBroker, worker_path
from mrhbench.io import ProtocolError
from mrhbench.container_runtime import ArtifactHashError


class Session:
    resources = {"cpus": 1, "memory_mb": 128, "disk_mb": 32, "pids_limit": 32, "wall_seconds": 60}
    def __init__(self): self.files = {}
    def write(self, p, data): self.files[p] = data
    def read(self, p, max_bytes):
        data = self.files[p]
        if len(data) > max_bytes: raise ProtocolError("too large")
        return data
    def hash_file(self,p,*,max_bytes):
        data=self.files[p]
        if len(data)>max_bytes:raise ArtifactHashError('byte_limit_exceeded')
        return {'path':p,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    def exec(self, argv, timeout): return {"argv": argv, "timeout": timeout}


class Trace:
    def append(self, *args): pass


class Provider:
    def __init__(self): self.calls = []
    def complete(self, request, **kwargs):
        self.calls.append(kwargs)
        return {"response": {}, "call_id": 1, "usage": None}


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.session, self.provider = Session(), Provider()
        self.view = {"resources": {"container": Session.resources, "execution_budget": {"model_calls": 1,"tool_calls": 5,"wall_seconds": 60}},
                     "asset_manifest": [], "tools": ["artifact_read_write", "artifact_image_view", "cpu_python_execution"]}
        self.broker = ExecutorBroker(view=self.view, session=self.session, provider=self.provider, trace=Trace(), audit_root=Path(self.tmp.name)/"rpc")
    def tearDown(self): self.tmp.cleanup()
    def rpc(self, op, args):
        return self.broker.dispatch({"sequence": self.broker.next_sequence, "operation": op, "arguments": args})
    def test_paths(self):
        for path in ["../x", "/tmp/a", "a/../b", "a//b", "C:/x", "a\\x", ".broker/request.json"]:
            with self.assertRaises(ProtocolError): worker_path(path)
    def test_fixed_role_and_budget(self):
        self.assertFalse(self.rpc("complete", {"request": {}, "output_schema": {}, "role": "judge"})["ok"])
        self.assertTrue(self.rpc("complete", {"request": {}, "output_schema": {}})["ok"])
        self.assertFalse(self.rpc("complete", {"request": {}, "output_schema": {}})["ok"])
        self.assertEqual(self.provider.calls[0]["role"], "executor")
        self.assertEqual(len(self.provider.calls), 1)
    def test_artifact_and_replay(self):
        result = self.rpc("tool", {"name": "artifact.write_text", "arguments": {"path": "x.py", "text": "print(1)"}})
        self.assertTrue(result["ok"])
        self.broker.verify_artifacts([result["value"]])
        with self.assertRaises(ProtocolError): self.broker.dispatch({"sequence": 1, "operation": "remaining", "arguments": {}})
    def test_image_pixels(self):
        self.session.files["/work/figure.png"] = b"\x89PNG\r\n\x1a\nTEST"
        result = self.rpc("tool", {"name": "artifact.view_image", "arguments": {"path": "figure.png"}})
        self.assertTrue(result["ok"])
        self.rpc("complete", {"request": {}, "output_schema": {}, "image_ids": [result["value"]["image_id"]]})
        self.assertEqual(self.provider.calls[0]["images"][0].read_bytes(), self.session.files["/work/figure.png"])
    def test_large_artifact_hash_uses_stream_api_not_read(self):
        from unittest.mock import patch
        self.session.files['/work/large']=b'x'*(25*1024*1024)
        expected=hashlib.sha256(self.session.files['/work/large']).hexdigest()
        with patch.object(self.session,'read',side_effect=AssertionError('content read forbidden')):
            receipt=self.broker.verify_artifacts([{'path':'large','sha256':expected}])
        self.assertEqual(receipt['total_bytes'],25*1024*1024)
        with self.assertRaises(ArtifactHashError) as e:self.broker.verify_artifacts([{'path':'large','sha256':'0'*64}])
        self.assertEqual(e.exception.code,'hash_mismatch')
    def test_cumulative_published_disk_not_per_file(self):
        self.session.files['/work/a']=b'a'*(17*1024*1024)
        self.session.files['/work/b']=b'b'*(17*1024*1024)
        rows=[{'path':p,'sha256':hashlib.sha256(self.session.files['/work/'+p]).hexdigest()} for p in ['a','b']]
        with self.assertRaises(ArtifactHashError) as e:self.broker.verify_artifacts(rows)
        self.assertEqual(e.exception.code,'byte_limit_exceeded')
    def test_published_collection_is_tighter_necessary_bound(self):
        from mrhbench.artifact_policy import make_collection_policy
        self.broker.view['resources']['artifact_collection']=make_collection_policy(max_total_bytes=2,max_entries=1)
        self.session.files['/work/a']=b'abc'
        with self.assertRaises(ArtifactHashError) as e:
            self.broker.verify_artifacts([{'path':'a','sha256':hashlib.sha256(b'abc').hexdigest()}])
        self.assertEqual(e.exception.code,'byte_limit_exceeded')
        with self.assertRaises(ArtifactHashError) as e:
            self.broker.verify_artifacts([{'path':p,'sha256':'0'*64} for p in ['a','b']])
        self.assertEqual(e.exception.code,'declared_entry_limit_exceeded')
    def test_typed_public_error_categories(self):
        from mrhbench.io import ProviderRefusal
        bad = self.rpc("complete", {"request": {}, "output_schema": {}, "role": "judge"})
        self.assertEqual(bad["category"], "invalid_request")
        class Refusing(Provider):
            def complete(self, request, **kwargs): raise ProviderRefusal("private provider detail req_123")
        self.broker.client._provider = Refusing()
        refused = self.rpc("complete", {"request": {}, "output_schema": {}})
        self.assertEqual(refused["category"], "provider_refusal")
        self.assertNotIn("req_123", str(refused))
        self.assertNotIn("exhausted", refused["message"])
        exhausted = self.rpc("complete", {"request": {}, "output_schema": {}})
        self.assertEqual(exhausted["category"], "budget_exhausted")
        tool = self.rpc("tool", {"name": "asset.read", "arguments": {"asset_id": "nope"}})
        self.assertEqual(tool["category"], "tool_error")
        from mrhbench.executor_broker import PUBLIC_ERROR_MESSAGES
        # Interface v4 rule: only budget_exhausted may mention the budget at all.
        for category, message in PUBLIC_ERROR_MESSAGES.items():
            self.assertTrue(message.startswith(category + ":"))
            if category != "budget_exhausted":
                self.assertNotIn("budget", message.lower())

    def test_mismatch_and_error_redaction(self):
        self.view["resources"]["execution_budget"]["wall_seconds"] = 61
        with self.assertRaises(ProtocolError): ExecutorBroker(view=self.view, session=self.session, provider=self.provider, trace=Trace(), audit_root=Path(self.tmp.name)/"bad")
        result = self.rpc("tool", {"name": "asset.read", "arguments": {"asset_id": "private-host-secret"}})
        self.assertFalse(result["ok"])
        self.assertNotIn("private-host-secret", str(result))


if __name__ == "__main__": unittest.main()
