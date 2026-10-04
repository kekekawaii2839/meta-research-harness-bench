import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_material_adapter as adapter_fixture
from mrhbench.io import ProtocolError, read_json, write_json, file_hash, digest
from mrhbench.material_public_identity import allocate_map, project_candidate, remap_task_keys
from mrhbench.material_identity_release import compile_identity_release


class IdentityReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        original, args = adapter_fixture.MaterialAdapterTests().fixture(self.root)
        p = read_json(original / 'package.json')
        p['paper_id'] = 'source-paper-HIDDEN'
        p['tasks'][0].update(task_id='source-task-HIDDEN', paper_id=p['paper_id'])
        write_json(original / 'package.json', p)
        self.mapping = allocate_map(original, self.root / 'private/map.json')
        self.source = self.root / 'projected'
        project_candidate(original, self.source, self.mapping, receipt_path=self.root / 'private/receipt.json')
        self.package = read_json(self.source / 'package.json')
        self.tid = self.package['tasks'][0]['task_id']
        # Explicit synthetic record: test controller binding, never real runtime evidence.
        rt = {'schema_version': 'factory-runtime-1', 'status': 'passed', 'reasons': [],
              'package_slug': 'fixture', 'package_json_sha256': file_hash(self.source / 'package.json'),
              'package_digest': digest(self.package), 'image': {'id': 'sha256:'+'a'*64}}
        self.args = dict(runtime_record=rt, package_slug='fixture', source_manifest=[],
            execution_budgets=remap_task_keys({'source-task-HIDDEN': args['execution_budgets']['t']}, self.mapping),
            artifact_collections=remap_task_keys({'source-task-HIDDEN': args['artifact_collections']['t']}, self.mapping))

    def run_release(self, **overrides):
        return compile_identity_release(self.source, self.root/'staging', self.mapping, **(self.args | overrides))

    def test_real_compiler_export_keeps_all_acceptance_pending(self):
        before = file_hash(self.source/'package.json')
        r = self.run_release()
        self.assertFalse(r['solver_admitted'])
        self.assertFalse(r['formal_accepted'])
        release = Path(r['releases'][0]['release_root'])
        v = read_json(release/'task.json')
        self.assertEqual(v['task_id'], self.tid)
        self.assertIn('Fixed scope', v['prompt'])
        self.assertNotIn('source-paper-HIDDEN', (release/'task.json').read_text())
        self.assertFalse((release/'private').exists())
        compiled = read_json(self.root/'staging/compiled'/self.tid/'task.json')
        self.assertTrue(all(g['status']=='pending' for g in compiled['gates'].values()))
        self.assertIsNone(compiled['private']['reviewer'])
        self.assertEqual(file_hash(self.source/'package.json'),before)
        with self.assertRaises(ProtocolError): self.run_release()

    def test_old_runtime_hash_rejected_without_output(self):
        rt = copy.deepcopy(self.args['runtime_record']); rt['package_json_sha256']='0'*64
        with self.assertRaisesRegex(ProtocolError,'changed'): self.run_release(runtime_record=rt)
        self.assertFalse((self.root/'staging').exists())

    def test_no_default_or_legacy_budget_fallback(self):
        for budgets in [{}, {'source-task-HIDDEN': {'model_calls': 1}}, {self.tid: {'model_calls': 1}}]:
            with self.assertRaises(ProtocolError): self.run_release(execution_budgets=budgets)
        budgets = copy.deepcopy(self.args['execution_budgets']);budgets[self.tid]['wall_seconds']=301
        with self.assertRaises(ProtocolError): self.run_release(execution_budgets=budgets)
        with self.assertRaises(ProtocolError): self.run_release(artifact_collections={self.tid:{}})
        self.assertFalse((self.root/'staging').exists())

    def test_new_controller_text_checked_in_actual_release(self):
        with patch('mrhbench.factory_runtime.controller_notes', return_value='source-paper-HIDDEN'):
            with self.assertRaisesRegex(ProtocolError,'private identity'): self.run_release()
        # Retain failed private diagnostic staging, never publish success receipt.
        self.assertFalse((self.root/'staging/identity_release_record.json').exists())


if __name__ == '__main__': unittest.main()
