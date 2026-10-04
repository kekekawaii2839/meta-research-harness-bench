import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.efficiency_metrics import compare_pair, summarize_calls, trace_metrics
from mrhbench.io import ProtocolError, write_json


class EfficiencyMetricsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_cache_added_once_failures_count_missing_not_zero(self):
        ledger = self.root / "ledger.json"
        rows = [{"id": 1, "status": "failed", "artifact_directory": str(self.root),
                 "wall_seconds": 5, "usage": {"input_tokens": 2,
                 "cache_write_input_tokens": 3, "cached_input_tokens": 10, "output_tokens": 7}}]
        write_json(ledger, {"attempts": rows})
        out = summarize_calls(ledger, [1])
        self.assertEqual(out["total_input_tokens"], 15)
        self.assertEqual(out["failure_count"], 1)
        rows.append({"id": 2, "status": "reserved", "artifact_directory": str(self.root)})
        write_json(ledger, {"attempts": rows})
        out = summarize_calls(ledger, [1, 2])
        self.assertIsNone(out["total_input_tokens"])
        self.assertIsNone(out["model_session_seconds"])
        self.assertEqual(out["observed_usage_subtotals"]["output_tokens"], 7)
        with self.assertRaises(ProtocolError):
            summarize_calls(ledger, [1, 1])

    def test_trace_deduplicates_message_blocks_and_counts_utf8(self):
        path = self.root / "events.jsonl"
        block = {"type": "tool_use", "id": "t1", "name": "Write", "input": {"content": "中文"}}
        event = {"type": "assistant", "message": {"id": "m1", "content": [block]}}
        path.write_text((json.dumps(event) + "\n") * 2, encoding="utf8")
        out = trace_metrics(path)
        self.assertEqual(out["tool_calls"], 1)
        self.assertEqual(out["assistant_messages"], 1)
        self.assertEqual(out["write_content_utf8_bytes_requested"], 6)
        self.assertFalse(trace_metrics(self.root / "missing")["available"])

    def test_target_not_automatic_quality_pass(self):
        old = {"total_input_tokens": 100, "output_tokens": 100, "model_session_seconds": 100}
        new = {"total_input_tokens": 100, "output_tokens": 60, "model_session_seconds": 60}
        out = compare_pair(old, new)
        self.assertTrue(out["engineering_target_met"])
        self.assertEqual(out["scientific_quality"], "requires_independent_audit")
        new["total_input_tokens"] = None
        self.assertIsNone(compare_pair(old, new)["engineering_target_met"])


if __name__ == "__main__":
    unittest.main()
