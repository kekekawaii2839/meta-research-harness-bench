import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.bounded_ledger import BoundedCallLedger
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, read_json, write_json


class BoundedLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "ledger.json"
        write_json(self.path, {"attempts": [], "used_attempts": 0,
                               "authorized_maximum": 100})

    def ledger(self, arm="old", stop_at=4, maximum=3):
        return BoundedCallLedger(self.path, baseline=0, stop_at=stop_at,
                                 experiment_root=self.root / "trial",
                                 arm_root=self.root / "trial" / arm,
                                 arm_maximum=maximum)

    def reserve(self, ledger, directory=None):
        return ledger.reserve(role="constructor", model="frozen", effort="medium",
                              request_hash="hash", artifact_directory=str(
                                  directory or ledger.arm_root / "calls" / "1"))

    def finish(self, ledger, call_id, failure=None):
        ledger.finish(call_id, status="failed" if failure else "completed",
                      wall_seconds=1, usage=None,
                      metadata={"failure_class": failure} if failure else {})

    def test_arm_budget_survives_restart_and_counts_failures(self):
        ledger = self.ledger(maximum=1)
        self.finish(ledger, self.reserve(ledger), "other_failure")
        with self.assertRaises(ProtocolError):
            self.reserve(self.ledger(maximum=1))
        self.assertEqual(read_json(self.path)["authorized_maximum"], 100)
        self.assertEqual(self.reserve(self.ledger("new")), 2)

    def test_global_experiment_boundary(self):
        ledger = self.ledger(stop_at=1)
        self.finish(ledger, self.reserve(ledger))
        with self.assertRaises(ProtocolError):
            self.reserve(self.ledger("new", stop_at=1))
        self.assertEqual(read_json(self.path)["used_attempts"], 1)

    def test_first_429_blocks_other_arm_and_restart(self):
        ledger = self.ledger()
        self.finish(ledger, self.reserve(ledger), "provider_rate_limit")
        with self.assertRaises(ProtocolError):
            self.reserve(self.ledger("new"))

    def test_uncertain_attempt_and_outside_directory(self):
        ledger = self.ledger()
        with self.assertRaises(ProtocolError):
            self.reserve(ledger, self.root / "trial" / "old-sibling")
        self.reserve(ledger)
        with self.assertRaises(ProtocolError):
            self.reserve(self.ledger("new"))

    def test_atomic_parallel_reservation_only_one_starts(self):
        def attempt(arm):
            try:
                return self.reserve(self.ledger(arm))
            except ProtocolError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ("old", "new")))
        self.assertEqual(sorted(x for x in results if x is not None), [1])

    def test_invalid_budgets_and_roots(self):
        for stop in (0, True, -1):
            with self.assertRaises(ProtocolError):
                self.ledger(stop_at=stop)
        with self.assertRaises(ProtocolError):
            self.ledger(arm="../outside")

    def test_base_ledger_unchanged(self):
        ledger = CallLedger(self.path)
        self.assertEqual(ledger.reserve(role="probe", model="m", effort="medium",
                                      request_hash="h", artifact_directory="any"), 1)


if __name__ == "__main__":
    unittest.main()
