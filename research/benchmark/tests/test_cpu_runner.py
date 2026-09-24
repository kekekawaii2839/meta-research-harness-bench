"""Reviewed CPU adapter software tests; these are not research experiments."""
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.cpu_runner import ReviewedCPURunner
from mrhbench.io import ProtocolError, read_json, write_json


class CPUTests(unittest.TestCase):
    def test_reviewed_fixture_runs_and_binds_real_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/"inputs").mkdir(); (root/"artifacts").mkdir()
            (root/"inputs/fact.txt").write_text("fixture")
            # The fixed source below is reviewed inline; auto approval in this
            # test does NOT authorize dynamic/model-generated code elsewhere.
            (root/"artifacts/main.py").write_text("from pathlib import Path\nassert Path('inputs/fact.txt').read_text() == 'fixture'\nPath('answer.txt').write_text('real CPU fixture output')\nprint('fixture ran')\nprint(Path.cwd())\n")
            def approve_fixture():
                for _ in range(100):
                    found = list((root/"jobs").glob("*/request.json"))
                    if found:
                        request = read_json(found[0])
                        write_json(found[0].with_name("approval.json"), {"decision":"approve_cpu_only", "snapshot_hash":request["snapshot_hash"], "reviewer":"unit-test fixed source", "review_note":"Fixed inline pathlib fixture only, not a scientific run or dynamic model code."})
                        return
                    time.sleep(.05)
            thread = threading.Thread(target=approve_fixture);thread.start()
            runner = ReviewedCPURunner(python=Path(sys.executable), audit_root=root/"jobs", input_root=root/"inputs", artifacts=root/"artifacts", approval_wait_seconds=10)
            result = runner.run(script="main.py", timeout_seconds=10)
            thread.join()
            self.assertEqual(result["exit_code"],0)
            self.assertIn("fixture ran",result["stdout"])
            self.assertNotIn(str(root),result["stdout"])
            self.assertIn("<task-workspace>",result["stdout"])
            self.assertEqual((root/"artifacts/answer.txt").read_text(),"real CPU fixture output")
            self.assertFalse(result["formal_isolation_verified"])
            self.assertFalse(result["gpu_execution"])

    def test_no_approval_means_no_execution_and_formal_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/"inputs").mkdir();(root/"artifacts").mkdir()
            (root/"artifacts/main.py").write_text("raise RuntimeError('MUST NOT RUN')")
            kwargs=dict(python=Path(sys.executable),audit_root=root/"jobs",input_root=root/"inputs",artifacts=root/"artifacts",approval_wait_seconds=1)
            with self.assertRaises(ProtocolError): ReviewedCPURunner(**kwargs,formal=True)
            with self.assertRaises(ProtocolError): ReviewedCPURunner(**kwargs).run(script="main.py")
            row=read_json(next((root/"jobs").glob("*/result.json")))
            self.assertFalse(row["executed"])

    def test_task_deadline_prevents_wait_and_execution(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/"inputs").mkdir();(root/"artifacts").mkdir()
            (root/"artifacts/main.py").write_text("raise RuntimeError('MUST NOT RUN')")
            runner=ReviewedCPURunner(python=Path(sys.executable),audit_root=root/"jobs",input_root=root/"inputs",artifacts=root/"artifacts")
            with self.assertRaises(ProtocolError):
                runner.run(script="main.py",deadline_monotonic=time.monotonic()-1)
            self.assertFalse(read_json(next((root/"jobs").glob("*/result.json")))["executed"])


if __name__=="__main__": unittest.main()
