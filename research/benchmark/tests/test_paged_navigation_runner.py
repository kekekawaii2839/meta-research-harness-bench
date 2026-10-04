import tempfile
import unittest
from pathlib import Path

from mrhbench.io import write_json, read_json, file_hash, ProtocolError
from mrhbench.paged_navigation_runner import PagedNavigationRunner


class Fake:
    calls = 0
    mutate = False

    def run(self, *, workspace, prompt, role, **kwargs):
        self.calls += 1
        self.catalog = read_json(workspace/'paged_source_navigation/catalog.json')
        assert 'NOT scientific approval' in prompt
        if self.mutate:
            (workspace/'paged_source_navigation/catalog.json').write_text('{}')
        return {'unchanged_contract': 42}


class PagedRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ws = Path(self.temp.name)
        (self.ws/'sources').mkdir()
        (self.ws/'sources/paper.html').write_text('<p>source</p>')
        sha = file_hash(self.ws/'sources/paper.html')
        write_json(self.ws/'request.json', {'sources': [{'source_id': 'paper',
            'path': 'sources/paper.html', 'sha256': sha}]})
        self.nav = {'schema_version': 'source-navigation-1', 'source_id': 'paper',
                    'source_sha256': sha, 'units': [{'id': 'p1', 'text': 'abc'}]}
        write_json(self.ws/'source_navigation/000.json', self.nav)
        self.fake = Fake()

    def run_role(self, role='constructor'):
        return PagedNavigationRunner(self.fake).run(workspace=self.ws, prompt='full policy', role=role)

    def test_success_no_response_or_original_rewrite(self):
        before = (self.ws/'source_navigation/000.json').read_bytes()
        self.assertEqual(self.run_role(), {'unchanged_contract': 42})
        self.assertEqual(self.fake.calls, 1)
        self.assertEqual(before, (self.ws/'source_navigation/000.json').read_bytes())
        self.assertEqual(self.fake.catalog['sources'][0]['status'], 'paged_losslessly')
        receipt = read_json(self.ws/'paged_navigation_receipt.json')
        self.assertFalse(receipt['model_read_verified'])
        self.assertTrue(receipt['unchanged_after_role'])

    def test_known_size_fallback_keeps_original(self):
        self.nav['units'][0]['text'] = 'large' * 10000
        write_json(self.ws/'source_navigation/000.json', self.nav)
        self.run_role('material_reviewer')
        self.assertEqual(self.fake.catalog['sources'][0]['status'], 'use_original_size_fallback')
        self.assertFalse((self.ws/'paged_source_navigation/source-0000').exists())
        self.assertEqual(read_json(self.ws/'source_navigation/000.json'), self.nav)

    def test_source_mutation_no_call(self):
        (self.ws/'sources/paper.html').write_text('changed')
        with self.assertRaises(ProtocolError):
            self.run_role()
        self.assertEqual(self.fake.calls, 0)

    def test_role_tamper_detected(self):
        self.fake.mutate = True
        with self.assertRaises(ProtocolError):
            self.run_role('adjudicator')
        self.assertFalse((self.ws/'paged_navigation_receipt.json').exists())

    def test_existing_publication_no_retry(self):
        self.run_role()
        with self.assertRaises(ProtocolError):
            self.run_role()
        self.assertEqual(self.fake.calls, 1)


if __name__ == '__main__':
    unittest.main()
