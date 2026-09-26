"""Factory token audit: attribution by workspace, waste and reuse (synthetic ledger, no model calls)."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.factory_costs import audit, locate, markdown  # noqa: E402
from mrhbench.io import write_json  # noqa: E402


class FactoryCostAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "factory"
        self.attempts = []

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, role, workspace, status="completed", usage=(100, 10)):
        n = len(self.attempts) + 1
        d = self.root / "native_calls" / role / ("native-%d" % n)
        ws = self.root / workspace
        ws.mkdir(parents=True, exist_ok=True)
        write_json(d / "request.json", {"workspace": str(ws), "prompt": "p"})
        self.attempts.append({"id": n, "role": role, "status": status, "artifact_directory": str(d), "wall_seconds": 1.0,
                              "usage": None if usage is None else {"input_tokens": usage[0], "cached_input_tokens": 5,
                                                                    "cache_write_input_tokens": 1, "output_tokens": usage[1]},
                              "metadata": {"transport": "claude_code_native_agent", "num_turns": 3}})

    def run_audit(self):
        ledger = Path(self.tmp.name) / "ledger.json"
        write_json(ledger, {"attempts": self.attempts})
        return audit([("v4", str(self.root))], ledger)

    def test_attribution_waste_and_reuse(self):
        pid = "iclr2025-x"
        self.call("scout", "triage/batch-000")
        self.call("source_auditor", "papers/%s/source_audit" % pid)
        # a truncated constructor whose partial output a v4 continuation reused
        self.call("constructor", "papers/%s/units/EXP/construct.failed-1/%s__EXP/constructor" % (pid, pid), status="failed")
        # a 429 with no usage and no reuse
        self.call("constructor", "papers/%s/units/LIT/construct.failed-1/%s__LIT/constructor" % (pid, pid), status="failed", usage=None)
        self.call("constructor", "papers/%s/units/EXP/construct/%s__EXP/constructor" % (pid, pid))
        write_json(self.root / "papers" / pid / "units/EXP/construct" / (pid + "__EXP") / "receipt.json",
                   {"repair_source": str(self.root / "papers" / pid / "units/EXP/construct.failed-1")})
        write_json(self.root / "papers" / pid / "units/EXP/compiled/compiled_tasks.json", [{"task_id": "a"}, {"task_id": "b"}])
        report = self.run_audit()
        r = report["roots"][0]
        rows = {c["call_id"]: c for c in r["calls"]}
        self.assertEqual((rows[3]["unit"], rows[3]["stage"], rows[3]["set_aside_attempt"], rows[3]["reused_later"], rows[3]["wasted"]),
                         ("EXP", "construct", True, True, False))
        self.assertTrue(rows[4]["wasted"])
        self.assertIsNone(rows[4]["tokens"])
        self.assertEqual(r["total"]["input_tokens_total"], 4 * 106)  # uncached + cache write + cache read; missing usage not zero-filled as data
        self.assertEqual(r["total"]["calls_without_usage"], 1)
        self.assertEqual(r["summary"]["compiled_tasks"], 2)
        self.assertEqual(r["summary"]["construction_calls"], 4)  # triage excluded
        self.assertEqual(r["summary"]["input_tokens_per_compiled_task"], 3 * 106 // 2)
        self.assertEqual(r["by_stage_role"]["triage"]["calls"], 1)
        self.assertEqual(report["combined"]["compiled_tasks"], 2)
        self.assertIn("| v4 |", markdown(report))

    def test_locate(self):
        root = Path(self.tmp.name)
        self.assertEqual(locate(root / "papers/p/units/IDEA/repair/j/reviewer", root)[:3], ("p", "IDEA", "repair"))
        self.assertEqual(locate(root / "papers/p/adjudication", root)[:3], ("p", None, "adjudication"))
        self.assertEqual(locate(Path(self.tmp.name).parent, root)[2], "outside_root")


if __name__ == "__main__":
    unittest.main()
