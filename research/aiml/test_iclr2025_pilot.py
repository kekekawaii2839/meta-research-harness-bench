"""Offline integrity checks for the pilot collector; not scientific validation."""
import json
import hashlib
import unittest
from collect_iclr2025_pilot import CACHE, OUT, ROOT, normalize, repository_links, sample


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((CACHE / 'iclr-2025-orals-posters.json').read_bytes())
        cls.rows, cls.excluded = normalize(cls.data)

    def test_count_accounting(self):
        self.assertEqual(len(self.data['results']), len(self.rows) + sum(self.excluded.values()))

    def test_unique_forums_and_positive_submission_ids(self):
        self.assertEqual(len(self.rows), len({r['forum_id'] for r in self.rows}))
        self.assertTrue(all(r['conference_submission_number'] > 0 for r in self.rows))
        self.assertTrue(all(not r['forum_id'].startswith('2025-Oral--') for r in self.rows))

    def test_deterministic_sample(self):
        first, second = sample(self.rows), sample(list(reversed(self.rows)))
        self.assertEqual([r['project_id'] for r in first], [r['project_id'] for r in second])
        self.assertEqual(len(first), 30)
        self.assertEqual(len({r['project_id'] for r in first}), 30)

    def test_coverage_and_no_score_imputation(self):
        chosen = sample(self.rows)
        groups = {r['topic_group'] for r in self.rows if r['repository_candidates']}
        self.assertEqual(groups, {r['topic_group'] for r in chosen})
        self.assertTrue(all(r['review_score'] is None for r in chosen))
        self.assertTrue(all(r['split'] == 'design_pilot_unassigned' for r in chosen))

    def test_repository_url_deduplication(self):
        event = {'url': 'https://github.com/Example/Project.git',
                 'abstract': 'Code: https://github.com/example/project. https://github.com/topics/ml'}
        links = repository_links(event)
        self.assertEqual(len(links), 1)
        self.assertEqual(set(links[0]['evidence_fields']), {'url', 'abstract'})

    def test_saved_sample_matches_selection(self):
        saved = json.loads((OUT / 'pilot30.json').read_bytes())
        self.assertEqual([r['project_id'] for r in sample(self.rows)], [r['project_id'] for r in saved])
        self.assertTrue(all(not r['runtime_verified'] for r in saved))

    def test_retained_source_hashes(self):
        manifest = json.loads((OUT / 'download_manifest.json').read_bytes())
        self.assertEqual(len(manifest), 59)
        for asset in manifest:
            path = (ROOT / asset['local_path']).resolve()
            self.assertIn(CACHE.resolve(), path.parents)
            self.assertEqual(path.stat().st_size, asset['bytes'])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), asset['sha256'])

    def test_repository_provenance_sidecars(self):
        sidecars = list((CACHE / 'repos').rglob('*.provenance.json'))
        self.assertTrue(sidecars)
        for sidecar in sidecars:
            metadata = json.loads(sidecar.read_bytes())
            path = sidecar.with_name(sidecar.name.removesuffix('.provenance.json'))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), metadata['sha256'])
            self.assertTrue(metadata['url'].startswith('https://'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
