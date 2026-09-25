import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"scripts/prepare"))
from prepare_development_budget_variant import prepare
from mrhbench.io import ProtocolError,read_json,file_hash


class BudgetVariantTests(unittest.TestCase):
    def test_versioned_model_budget_only(self):
        source=ROOT/'materials/pilot_v3/compiled_candidates_v7/ssa/ssa-write-evidence-utk-v6'
        original=file_hash(source/'task.json')
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/'variant'
            report=prepare(source,output,12)
            new=read_json(output/'task.json')
            self.assertEqual(new['task_id'],new['public']['task_id'])
            self.assertEqual(new['public']['resources']['execution_budget']['model_calls'],12)
            self.assertTrue(report['assets_unchanged'])
            self.assertTrue(report['scientific_input_unchanged'])
            self.assertTrue(report['container_resources_unchanged'])
            self.assertEqual(file_hash(source/'task.json'),original)
            with self.assertRaises(ProtocolError):prepare(source,output,12)

    def test_invalid_call_count_before_writes(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'out'
            with self.assertRaises(ProtocolError):prepare(Path(td)/'source',out,True)
            self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
