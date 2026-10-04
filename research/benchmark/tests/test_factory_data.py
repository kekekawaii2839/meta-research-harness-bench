"""Conversion publication and orchestration regression tests; no Docker/model calls."""
import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.factory_data import apply_conversions, check_plan, convert_plan
from mrhbench.factory import Factory
from mrhbench.io import ProtocolError, file_hash, read_json, write_json


class FactoryDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.paper = Path(self.tmp.name)
        (self.paper / 'evidence.json').write_text('{}')
        self.plan = {'schema_version': 'factory-data-conversion-plan-1',
            'evidence': [{'path': 'evidence.json', 'sha256': file_hash(self.paper / 'evidence.json')}],
            'conversions': []}
        self.pre = []
        for name in ('forces', 'kinematics'):
            src = self.paper / ('repo_files/' + name + '.pt')
            src.parent.mkdir(exist_ok=True)
            src.write_bytes(name.encode())
            row = {'source': src.relative_to(self.paper).as_posix(), 'source_sha256': file_hash(src),
                   'replace_path': 'assets/repo_data/' + name + '.pt', 'name': name}
            self.plan['conversions'].append(row)
            self.pre.append({'from': row['source'], 'to': row['replace_path'], 'sha256': row['source_sha256']})
        self.plan_path = self.paper / 'plan.json'
        write_json(self.plan_path, self.plan)
        self.commands = []
        self.fail_on = None

    def fake_docker(self, cmd, *, timeout):
        self.commands.append((cmd, timeout))
        if cmd[1] == 'rm':
            return {'returncode': 0, 'stdout': '', 'stderr': ''}
        mount = next(x for x in cmd if x.startswith('type=bind,src=') and x.endswith(',dst=/output'))
        item = Path(mount[len('type=bind,src='):-len(',dst=/output')])
        if item.name == self.fail_on:
            return {'returncode': 1, 'stdout': '', 'stderr': 'synthetic failure'}
        (item / 'data.npz').write_bytes(b'FAKE-NPZ-' + item.name.encode())
        row = next(r for r in self.plan['conversions'] if r['name'] == item.name)
        write_json(item / 'manifest.json', {'source': {'sha256': row['source_sha256']},
            'output': {'sha256': file_hash(item / 'data.npz')}, 'container_type': 'list',
            'arrays': [{'npz_key': 'arr_000000', 'source_locator': 0, 'shape': [3, 4], 'numpy_dtype': '<f8'}]})
        return {'returncode': 0, 'stdout': '', 'stderr': ''}

    def publish(self, **kwargs):
        return convert_plan(self.paper, self.plan_path, self.paper / 'data_conversion',
                            image_id='sha256:' + 'a' * 64, docker=kwargs.get('docker', self.fake_docker))

    def test_without_conversion_preserves_prepopulation_identity(self):
        rows, note = apply_conversions(self.paper, self.pre)
        self.assertIs(rows, self.pre)
        self.assertEqual(note, '')

    def test_complete_publication_replaces_pt_with_npz_and_metadata(self):
        self.publish()
        rows, note = apply_conversions(self.paper, self.pre)
        self.assertEqual(len(rows), 4)
        self.assertEqual({r['to'] for r in rows}, {
            'assets/converted_data/' + n + suffix for n in ('forces', 'kinematics')
            for suffix in ('.npz', '.metadata.json')})
        self.assertFalse(any(r['from'].endswith('.pt') for r in rows))
        self.assertIn('allow_pickle=False', note)
        for n in ('forces', 'kinematics'):
            meta = read_json(self.paper / 'data_conversion' / n / 'array_metadata.json')
            self.assertNotIn('source', meta)
            self.assertNotIn('evidence', meta)

    def test_container_bounds_and_cleanup(self):
        self.publish()
        self.assertEqual([c[0][1] for c in self.commands], ['run', 'rm', 'run', 'rm'])
        cmd, timeout = self.commands[0]
        self.assertEqual(timeout, 120)
        for flag, value in (('--network', 'none'), ('--user', '10001:10001'),
                            ('--memory', '1g'), ('--pids-limit', '64'), ('--cap-drop', 'ALL')):
            self.assertEqual(cmd[cmd.index(flag) + 1], value)
        self.assertIn('--read-only', cmd)
        self.assertNotIn('--privileged', cmd)

    def test_source_evidence_output_metadata_receipt_and_plan_changes_rejected(self):
        self.publish()
        for rel in ('repo_files/forces.pt', 'evidence.json', 'plan.json',
                    'data_conversion/forces/data.npz', 'data_conversion/forces/array_metadata.json',
                    'data_conversion/forces/manifest.json'):
            p = self.paper / rel
            original = p.read_bytes()
            p.write_bytes(original + b' ')
            with self.subTest(path=rel), self.assertRaises(ProtocolError):
                apply_conversions(self.paper, self.pre)
            p.write_bytes(original)

    def test_failed_second_conversion_does_not_publish(self):
        self.fail_on = 'kinematics'
        with self.assertRaises(ProtocolError): self.publish()
        self.assertTrue((self.paper / 'data_conversion/forces/data.npz').exists())
        self.assertFalse((self.paper / 'data_conversion/publication.json').exists())
        self.assertEqual(self.commands[-1][0][1], 'rm')
        with self.assertRaises(FileNotFoundError): apply_conversions(self.paper, self.pre)

    def test_existing_output_refused(self):
        self.publish()
        with self.assertRaises(FileExistsError): self.publish()

    def test_mismatched_job_source_hash_and_partial_job_rejected(self):
        self.publish()
        for key, value in (('from', 'wrong.pt'), ('sha256', '0' * 64)):
            rows = copy.deepcopy(self.pre)
            rows[0][key] = value
            with self.assertRaises(ProtocolError): apply_conversions(self.paper, rows)
        with self.assertRaises(ProtocolError): apply_conversions(self.paper, self.pre[:1])

    def test_unknown_and_duplicate_plan_rejected(self):
        for mutation in ('schema', 'name', 'target'):
            plan = copy.deepcopy(self.plan)
            if mutation == 'schema': plan['schema_version'] = 'unknown'
            elif mutation == 'name': plan['conversions'][1]['name'] = plan['conversions'][0]['name']
            else: plan['conversions'][1]['replace_path'] = plan['conversions'][0]['replace_path']
            with self.assertRaises(ProtocolError): check_plan(self.paper, plan)

    def test_plan_paths_and_names_cannot_escape(self):
        for field in ('source', 'replace_path', 'name'):
            for unsafe in ('../escape', '/absolute', 'C:/drive', 'a/../b', 'a\\b'):
                plan = copy.deepcopy(self.plan)
                plan['conversions'][0][field] = unsafe
                with self.subTest(field=field, path=unsafe), self.assertRaises(ProtocolError):
                    check_plan(self.paper, plan)

    def test_duplicate_or_missing_publication_entries_rejected(self):
        self.publish()
        path = self.paper / 'data_conversion/publication.json'
        original = read_json(path)
        for entries in (original['entries'][:1], original['entries'] + original['entries'][:1]):
            write_json(path, {**original, 'entries': entries})
            with self.assertRaises(ProtocolError): apply_conversions(self.paper, self.pre)

    def test_publication_output_escape_rejected(self):
        self.publish()
        path = self.paper / 'data_conversion/publication.json'
        pub = read_json(path)
        pub['entries'][0]['output'] = '../outside'
        write_json(path, pub)
        with self.assertRaises(ProtocolError): apply_conversions(self.paper, self.pre)

    def test_factory_build_job_integrates_conversion(self):
        self.publish()
        write_json(self.paper / 'adjudication/adjudication.json', {
            'ambiguity_decisions': [], 'scope_request': 'test scope', 'task_scopes': {'EXP': 'experiment'},
            'withheld_from_solver': [], 'environment_candidate': {}, 'rights_review': {}})
        sources = [{'source_id': n, 'url': 'https://example.test/' + n, 'version': 'fixed',
                    'sha256': r['sha256'], 'role': 'repository_file', 'local_path': r['from']}
                   for n, r in zip(('forces', 'kinematics'), self.pre)]
        write_json(self.paper / 'sources/manifest.json', {'sources': []})
        write_json(self.paper / 'repo_files/manifest.json', {'commit': 'a' * 40, 'sources': sources,
            'requests': [{'path': n + '.pt', 'status': 'fetched', 'source_id': n, 'sha256': r['sha256']}
                         for n, r in zip(('forces', 'kinematics'), self.pre)]})
        obj = SimpleNamespace(paper_dir=lambda pid: self.paper, job_id=lambda state: 'test__EXP')
        job = Factory.build_job(obj, {'project_id': 'test', 'unit': 'EXP'})
        self.assertEqual(len(job['prepopulated_output_files']), 4)
        self.assertFalse(any(r['from'].endswith('.pt') for r in job['prepopulated_output_files']))
        self.assertIn('Trusted controller representation conversion', job['scope_request'])

    def test_duplicate_prepopulation_and_converted_target_collision_rejected(self):
        self.publish()
        for rows in (self.pre + self.pre[:1], self.pre + [{
                'from': 'other.npz', 'to': 'assets/converted_data/forces.npz', 'sha256': '0' * 64}]):
            with self.assertRaises(ProtocolError): apply_conversions(self.paper, rows)

    def test_renamed_source_cannot_bypass_configured_conversion(self):
        self.publish()
        rows = [{**r, 'to': 'assets/renamed/' + str(i) + '.pt'} for i, r in enumerate(self.pre)]
        with self.assertRaises(ProtocolError): apply_conversions(self.paper, rows)

    def test_plan_change_during_conversion_prevents_publication(self):
        def docker(cmd, *, timeout):
            result = self.fake_docker(cmd, timeout=timeout)
            if cmd[1] == 'run':
                altered = {**self.plan, 'changed_during_execution': True}
                write_json(self.plan_path, altered)
            return result
        with self.assertRaises(ProtocolError): self.publish(docker=docker)
        self.assertFalse((self.paper / 'data_conversion/publication.json').exists())


if __name__ == '__main__':
    unittest.main()
