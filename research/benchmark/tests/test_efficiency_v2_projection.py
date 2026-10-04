import copy
import hashlib
import json
import runpy
import tempfile
import unittest
from pathlib import Path

project = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/active/prepare_efficiency_v2_cases.py'))['project']
from mrhbench.material_pipeline import validate_job, prepare_material_job


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ws = self.root / 'historical'
        self.ws.mkdir()
        self.out = self.root / 'new'
        self.candidate = self.ws / 'candidate'
        self.candidate.mkdir()
        def put(p, value):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
            return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        self.put = put
        asset = put(self.candidate / 'assets/a.txt', b'unchanged\r\nscientific facts')
        put(self.candidate / 'assets/excluded.txt', b'other task')
        put(self.candidate / 'environment/image/Dockerfile', b'FROM example')
        put(self.candidate / 'environment/smoke.py', b'print("requires all stages; must repair")')
        source = put(self.ws / 'source.txt', b'original source')
        a = {'path': 'assets/a.txt', 'sha256': asset['sha256'], 'visibility': 'public'}
        self.pkg = {'paper_id': 'p', 'tasks': [{'task_id': 't', 'task_type': 'IDEA', 'assets': [a], 'input_contract': {'files': [a]}, 'input_fact_ids': ['f'], 'private_fact_ids': ['private'], 'private_source_ids': ['s']}, {'task_id': 'other', 'task_type': 'EXP'}], 'facts': [{'fact_id': 'f', 'statement': 'unchanged', 'evidence': [{'source_id': 's'}]}, {'fact_id': 'private'}, {'fact_id': 'excluded'}], 'environment': {'dockerfile': 'environment/image/Dockerfile', 'smoke_test': 'environment/smoke.py', 'resources': {'cpus': 2}}, 'coverage': []}
        job = {'schema_version': 'material-job-1', 'first_disclosure': {'date': '2020-01-01'}, 'environment_candidate': {'gpu': False, 'network': 'none', 'scientific_rationale': 'synthetic test', 'cpus': 1, 'memory_mb': 100, 'disk_mb': 100, 'pids_limit': 10, 'wall_seconds': 30}, 'job_id': 'j', 'paper_id': 'p', 'requested_task_types': ['IDEA', 'EXP'], 'sources': [{'source_id': 's', 'url': 'https://example.invalid/source', 'version': 'v1', 'role': 'source', 'local_path': 'source.txt', 'sha256': source['sha256']}], 'scope_request': 'original instructions'}
        self.case = {'workspace': str(self.ws), 'job': put(self.ws/'job.json', job), 'prior_package': put(self.candidate/'package.json', self.pkg), 'prior_review': put(self.ws/'review.json', {'decision': 'revise'}), 'prior_adjudication_and_notes': put(self.ws/'adj.json', {'repair_notes': ['original scientific note', 'other stage note']}), 'recommended_task_id': 't', 'recommended_single_task_type': 'IDEA', 'source_inventory': [source], 'proposed_retained_notes_scope': ['one selected stage']}

    def test_exact_assets_facts_notes_environment(self):
        project(self.case, self.out)
        p = self.out/'prior/j/constructor/output'
        self.assertEqual((p/'assets/a.txt').read_bytes(), (self.candidate/'assets/a.txt').read_bytes())
        self.assertEqual((p/'environment/smoke.py').read_bytes(), (self.candidate/'environment/smoke.py').read_bytes())
        self.assertFalse((p/'assets/excluded.txt').exists())
        pkg = json.loads((p/'package.json').read_text())
        self.assertEqual(pkg['tasks'], self.pkg['tasks'][:1])
        self.assertEqual(pkg['facts'], self.pkg['facts'][:2])
        self.assertEqual(pkg['environment'], self.pkg['environment'])
        self.assertEqual(len(pkg['coverage']), 5)
        self.assertIn('NOT a claim', pkg['coverage'][2]['reason'])
        notes = json.loads((self.out/'repair_notes.json').read_text())
        self.assertEqual(notes[2:], ['original scientific note', 'other stage note'])
        self.assertIn('CONTROLLER-INDUCED', notes[0])
        job = json.loads((self.out/'job.json').read_text())
        self.assertEqual(job['requested_task_types'], ['IDEA'])
        self.assertFalse(Path(job['sources'][0]['local_path']).is_absolute())
        validate_job(job, self.out)
        templates = self.root/'templates'
        templates.mkdir()
        (templates/'material_constructor.txt').write_text('test prompt')
        (templates/'material_package.schema.json').write_text('{}')
        prepare_material_job(job, self.out, self.root/'published', templates)
        self.assertEqual((self.root/'published/sources/000-000-source.txt').read_bytes(), b'original source')

    def test_existing_destination_rejected(self):
        self.out.mkdir()
        with self.assertRaises(ValueError): project(self.case, self.out)

    def test_traversal_rejected_before_write(self):
        self.pkg['tasks'][0]['assets'][0]['path'] = '../source.txt'
        self.case['prior_package'] = self.put(self.candidate/'package.json', self.pkg)
        with self.assertRaises(ValueError): project(self.case, self.out)
        self.assertFalse(self.out.exists())

    def test_source_whitelist_fail_closed(self):
        self.case['source_inventory'] = []
        with self.assertRaises(ValueError): project(self.case, self.out)
        self.assertFalse(self.out.exists())

    def test_tamper_rejected(self):
        (self.candidate/'assets/a.txt').write_text('tampered')
        with self.assertRaises(ValueError): project(self.case, self.out)

    def test_missing_fact_rejected(self):
        self.pkg['facts'] = []
        self.case['prior_package'] = self.put(self.candidate/'package.json', self.pkg)
        with self.assertRaises(ValueError): project(self.case, self.out)

    def test_prepop_selected_exact_bytes(self):
        data = (self.candidate/'assets/a.txt').read_bytes()
        source = self.put(self.ws/'prepop.txt', data)
        self.case['source_inventory'].append(source)
        job = json.loads((self.ws/'job.json').read_text())
        job['prepopulated_output_files'] = [{'from': 'prepop.txt', 'to': 'assets/a.txt', 'sha256': source['sha256']}]
        self.case['job'] = self.put(self.ws/'job.json', job)
        project(self.case, self.out)
        new = json.loads((self.out/'job.json').read_text())
        self.assertFalse(Path(new['prepopulated_output_files'][0]['from']).is_absolute())
        validate_job(new, self.out)
        templates = self.root/'templates'
        templates.mkdir()
        (templates/'material_constructor.txt').write_text('test prompt')
        (templates/'material_package.schema.json').write_text('{}')
        prepare_material_job(new, self.out, self.root/'published', templates)
        self.assertEqual((self.root/'published/output/assets/a.txt').read_bytes(), data)

    def test_hardlink_rejected(self):
        import os
        os.link(self.candidate/'assets/a.txt', self.ws/'link.txt')
        with self.assertRaises(ValueError): project(self.case, self.out)


if __name__ == '__main__': unittest.main()
