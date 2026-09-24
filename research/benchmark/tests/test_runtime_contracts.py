import base64
import os
import concurrent.futures
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.io import ProtocolError, TraceLog, write_json, read_json
from mrhbench.costs import CallLedger
from mrhbench.sdk import Budget, ExecutorClient, TaskTools
from mrhbench.runtime_contracts import run_process_tree, failure_record, capability_preflight
from mrhbench.native_codex import NativeCodexRunner, capture_session_rollout


class RuntimeTests(unittest.TestCase):
    def test_budget_requires_published_contract_and_rejects_mismatch(self):
        config = {"model_calls": 3, "tool_calls": 5, "wall_seconds": 17}
        b = Budget.from_task({"resources": {"execution_budget": config}})
        self.assertEqual(b.remaining()["tool_calls"], 5)
        with self.assertRaises(ProtocolError): Budget.from_task({"resources": {}})
        with self.assertRaises(ProtocolError): Budget.from_task({"resources": {"execution_budget": config}}, overrides={**config, "wall_seconds": 2400})

    def test_restore_preserves_failed_attempts_and_downtime(self):
        b = Budget(model_calls=3, tool_calls=5, wall_seconds=10)
        b.consume("model"); state = b.checkpoint()
        restored = Budget.restore(state)
        self.assertEqual(restored.used, {"model": 1, "tool": 0})
        self.assertLessEqual(restored.remaining()["wall_seconds"], b.wall_limit)
        state["started_at"] -= 100; state["expires_at"] -= 100
        expired = Budget.restore(state)
        with self.assertRaises(ProtocolError): expired.consume("tool")

    def test_parallel_ledger_has_no_lost_or_duplicate_attempts(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"ledger.json"; write_json(p, {"authorized_maximum": 20, "used_attempts": 0, "attempts": []})
            def job(i):
                ledger = CallLedger(p)
                call = ledger.reserve(role="constructor", model="fixture", effort="medium", request_hash=str(i), artifact_directory=d)
                ledger.finish(call, status="failed", wall_seconds=.1, usage=None, metadata={})
                return call
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                ids = list(pool.map(job, range(12)))
            self.assertEqual(sorted(ids), list(range(1,13)))
            self.assertTrue(all(a["status"] == "failed" for a in read_json(p)["attempts"]))

    def test_process_tree_timeout_stops_descendant_marker(self):
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d)/"escaped.txt"
            child = "import time; from pathlib import Path; time.sleep(1.5); Path(" + repr(str(marker)) + ").write_text('escaped')"
            parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); time.sleep(20)"
            with self.assertRaises(subprocess.TimeoutExpired):
                run_process_tree([sys.executable, "-c", parent], timeout=.5, capture_output=True)
            time.sleep(1.6)
            self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == 'nt','Windows kill-on-close Job Object check')
    def test_finished_parent_cannot_leave_background_child(self):
        with tempfile.TemporaryDirectory() as d:
            marker=Path(d)/'orphan.txt'
            child="import time; from pathlib import Path; time.sleep(1); Path("+repr(str(marker))+").write_text('escaped')"
            parent="import subprocess,sys; subprocess.Popen([sys.executable,'-c',"+repr(child)+"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
            result=run_process_tree([sys.executable,'-c',parent],timeout=5,capture_output=True)
            self.assertEqual(result.returncode,0)
            time.sleep(1.2)
            self.assertFalse(marker.exists())

    def test_failure_no_automatic_score_and_missing_probe_blocks(self):
        for category in ("material", "platform", "judge", "agent", "unresolved"):
            row = failure_record(category=category, phase="test", reason="fixed fixture", evidence=["fixture log"])
            self.assertIsNone(row["quality_score"])
        self.assertFalse(capability_preflight(["view_image"], {})["ready"])
        self.assertFalse(capability_preflight(["cpu"], {"cpu":lambda:{"passed":True}})["ready"])
        self.assertTrue(capability_preflight(["cpu"], {"cpu":lambda:{"passed":True,"evidence":{"exit_code":0}}})["ready"])

    def test_images_are_explicit_bytes_not_path_claims(self):
        class Provider:
            def complete(self, request, **kwargs):
                self.images = kwargs["images"]
                return {"response":{},"call_id":1,"usage":{}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/"inputs").mkdir(); registry={}; trace=TraceLog(root/"trace.jsonl")
            budget=Budget(model_calls=2,tool_calls=3,wall_seconds=10)
            tools=TaskTools(view={"tools":["artifact_image_view"],"asset_manifest":[]},input_root=root/"inputs",output_root=root/"out",budget=budget,trace=trace,image_registry=registry)
            png=root/"out/image.png"
            png.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='))
            image=tools.call("artifact.view_image",{"path":"image.png"})
            provider=Provider(); client=ExecutorClient(provider,budget,trace,image_registry=registry)
            client.complete({},output_schema={},image_ids=[image["image_id"]])
            self.assertEqual(provider.images,[png])
            png.write_bytes(b'changed')
            with self.assertRaises(ProtocolError): client.complete({},output_schema={},image_ids=[image["image_id"]])

    def test_native_command_explicit_profile_and_tool_surface(self):
        runner=NativeCodexRunner(binary=Path(sys.executable),model="fixture",reasoning_effort="medium",ledger=None,audit_root=Path.cwd())
        args=runner.command(Path.cwd(),Path.cwd()/"response.json")
        self.assertIn('--no-daemon',args)
        self.assertIn('default_permissions=":workspace"',args)
        self.assertIn('--ignore-user-config',args)
        self.assertEqual(args[args.index('view_image')-1],'--enable')
        self.assertNotIn('--ephemeral',args)

    def test_rollout_capture_exact_identity_redaction_and_absence(self):
        import json
        session='12345678-1234-1234-1234-123456789abc'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); home=root/'home'; sessions=home/'sessions'/'2026'/'09'/'23'; sessions.mkdir(parents=True)
            audit=root/'audit'; audit.mkdir()
            unrelated=sessions/'rollout-unrelated.jsonl'; unrelated.write_text('MUST NOT READ INVALID JSON')
            events=[{'type':'thread.started','thread_id':session}]
            self.assertEqual(capture_session_rollout(events,audit_directory=audit,codex_home=home)['status'],'unavailable')
            source=sessions/f'rollout-{session}.jsonl'
            rows=[{'type':'session_meta','payload':{'id':session}}, {'type':'response_item','payload':{'type':'function_call','name':'view_image','call_id':'x'}}, {'type':'test','payload':{'access_token':'secret_token_value','text':'secret_fixture_123456'}}]
            source.write_text('\n'.join(json.dumps(r) for r in rows),encoding='utf8')
            report=capture_session_rollout(events,audit_directory=audit,codex_home=home,secret_values=['secret_fixture_123456'])
            content=Path(report['path']).read_text()
            self.assertEqual(report['status'],'captured')
            self.assertNotIn('secret_token_value',content); self.assertNotIn('secret_fixture_123456',content)
            self.assertEqual(report['observed_tools'][0]['name'],'view_image')
            self.assertFalse(report['complete_trajectory_verified'])

    def test_rollout_identity_mismatch_is_not_accepted(self):
        import json
        session='12345678-1234-1234-1234-123456789abc'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'sessions').mkdir()
            (root/'sessions'/f'rollout-{session}.jsonl').write_text(json.dumps({'type':'session_meta','payload':{'id':'other'}}))
            result=capture_session_rollout([{'type':'thread.started','thread_id':session}],audit_directory=root,codex_home=root)
            self.assertEqual(result['reason'],'rollout_identity_mismatch')


if __name__ == '__main__': unittest.main()
