import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, read_json, write_json
from mrhbench.providers import parse_codex_events, CodexJSONTransport


class ProviderContractTests(unittest.TestCase):
    def test_rollout_rejections_finalize_ledger_without_masking_failure(self):
        for capture, expected, message in [({'status':'unavailable'},'failed','rollout missing'),
                 ({'status':'captured','observed_tools':['synthetic_native_tool']},'rejected_native_tool_activity','native tool activity')]:
            with self.subTest(capture=capture), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);path=root/'ledger.json'
                write_json(path,{'authorized_maximum':1,'used_attempts':0,'attempts':[]});ledger=CallLedger(path)
                transport=CodexJSONTransport(binary=Path(sys.executable),model='gpt-5.6-sol',reasoning_effort='medium',ledger=ledger,audit_root=root/'audit')
                proc=SimpleNamespace(returncode=0,stdout=json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}}),stderr='')
                with patch('mrhbench.providers.run_process_tree',return_value=proc) as worker, patch('mrhbench.native_codex.capture_session_rollout',return_value=capture):
                    with self.assertRaisesRegex(ProtocolError,message):
                        transport.complete({},output_schema={'type':'object','properties':{},'additionalProperties':False},role='probe')
                    self.assertEqual(worker.call_count,1)
                attempt=read_json(path)['attempts'][0]
                self.assertEqual(attempt['status'],expected)
                self.assertEqual(attempt['metadata']['error_type'],'ProtocolError')
                self.assertFalse(attempt['metadata']['automatic_outer_retry'])

    def test_ledger_reserves_before_call_counts_failure_and_no_zero_imputation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"ledger.json"
            write_json(path, {"authorized_maximum": 2, "used_attempts": 0, "attempts": []})
            ledger = CallLedger(path)
            a = ledger.reserve(role="judge", model="gpt-5.6-sol", effort="medium", request_hash="test-fixture", artifact_directory="fixture")
            self.assertEqual(read_json(path)["used_attempts"], 1)
            ledger.finish(a, status="failed", wall_seconds=1, usage=None, metadata={"fixture": True})
            b = ledger.reserve(role="judge", model="gpt-5.6-sol", effort="medium", request_hash="test-fixture2", artifact_directory="fixture")
            ledger.finish(b, status="completed", wall_seconds=2, usage={"input_tokens": 10, "output_tokens": 5}, metadata={"fixture": True})
            s = ledger.summary()
            self.assertEqual(s["used_runs_including_failures"], 2)
            self.assertIsNone(s["dollar_cost"])
            self.assertEqual(s["roles"]["judge"]["runs_without_usage"], 1)
            self.assertEqual(s["roles"]["judge"]["usage_observed"]["input_tokens"], 10)
            with self.assertRaises(ProtocolError):
                ledger.reserve(role="judge", model="gpt-5.6-sol", effort="medium", request_hash="3", artifact_directory="fixture")
            with self.assertRaises(ProtocolError):
                ledger.finish(a, status="completed", wall_seconds=3, usage={}, metadata={})

    def test_cli_native_actions_fail_closed_and_usage_is_observed(self):
        events = [{"type": "thread.started", "thread_id": "fixture"},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": '{"ok":true}'}},
                  {"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 2}}]
        result = parse_codex_events("\n".join(json.dumps(x) for x in events))
        self.assertEqual(result["completed_turns"], 1)
        self.assertEqual(result["native_activity"], [])
        self.assertEqual(result["usage"]["input_tokens"], 5)
        events.insert(1, {"type": "item.started", "item": {"type": "command_execution", "command": "no actual command in unit test"}})
        self.assertTrue(parse_codex_events("\n".join(json.dumps(x) for x in events))["native_activity"])
        with self.assertRaises(ProtocolError):
            parse_codex_events("not json")

    def test_unaccepted_cli_transport_not_allowed_for_formal_executor(self):
        with self.assertRaises(ProtocolError):
            CodexJSONTransport(binary=Path(sys.executable), model="gpt-5.6-sol", reasoning_effort="medium", ledger=None, audit_root=ROOT, development=False)

    def test_known_startup_warning_is_not_native_tool_but_unknown_error_fails(self):
        warning = {"type": "item.completed", "item": {"type": "error", "message": "Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`."}}
        result = parse_codex_events(json.dumps(warning))
        self.assertFalse(result["failed"])
        self.assertFalse(result["native_activity"])
        self.assertEqual(len(result["startup_warnings"]), 1)
        warning["item"]["message"] = "Unexpected runtime failure"
        self.assertTrue(parse_codex_events(json.dumps(warning))["failed"])


if __name__ == "__main__":
    unittest.main()
