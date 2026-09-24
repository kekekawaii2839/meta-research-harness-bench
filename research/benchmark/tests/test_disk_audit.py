import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.disk_audit import tree_usage, comparison, snapshot
from unittest.mock import patch


class DiskAuditTests(unittest.TestCase):
    def test_lengths_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a").write_bytes(b"123")
            (root / "nested").mkdir()
            (root / "nested/b").write_bytes(b"12")
            self.assertEqual(tree_usage(root)["logical_bytes"], 5)
            self.assertIsNone(tree_usage(root / "missing")["logical_bytes"])

    def test_partial_delta_not_zero(self):
        a = {"phase": "before", "directories": {"x": {"status": "partial", "logical_bytes": 3}}}
        b = {"phase": "after", "directories": {"x": {"status": "available", "logical_bytes": 7}}}
        self.assertIsNone(comparison(a, b)["directories"]["x"]["logical_bytes_delta"])

    def test_cli_missing(self):
        with tempfile.TemporaryDirectory() as d, patch("mrhbench.disk_audit.shutil.which", return_value=None):
            r = snapshot(Path(d), phase="test")
            self.assertEqual(r["docker"]["status"], "unavailable")
            self.assertIsNone(r["docker"]["usage_bytes"])


if __name__ == "__main__":
    unittest.main()
