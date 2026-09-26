"""Per-task resource limits inside one package (user decision 2026-09-26)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.io import ProtocolError  # noqa: E402
from mrhbench.material_adapter import task_container  # noqa: E402

PKG = {"cpus": 4, "memory_mb": 4096, "disk_mb": 2048, "pids_limit": 256, "wall_seconds": 2400}


def task(**res):
    return {"input_contract": {"resources": res}}


class PerTaskResourceTests(unittest.TestCase):
    def test_smaller_limits_override_package_and_unset_keys_inherit(self):
        self.assertEqual(task_container(task(cpus=1, memory_mb=1024, wall_seconds=900, gpu=False, network="none"), PKG),
                         {**PKG, "cpus": 1, "memory_mb": 1024, "wall_seconds": 900})

    def test_no_restatement_uses_package(self):
        self.assertEqual(task_container({"input_contract": {}}, PKG), PKG)

    def test_exceeding_package_or_invalid_values_rejected(self):
        for bad in ({"cpus": 8}, {"wall_seconds": 0}, {"memory_mb": True}, {"disk_mb": "512"}):
            with self.subTest(bad=bad), self.assertRaises(ProtocolError):
                task_container(task(**bad), PKG)

    def test_conflicting_restatements_rejected(self):
        t = {"input_contract": {"resources": {"cpus": 1}, "resource_requirements": {"cpus": 2}}}
        with self.assertRaises(ProtocolError):
            task_container(t, PKG)


if __name__ == "__main__":
    unittest.main()
