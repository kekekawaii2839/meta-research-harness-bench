import tempfile
import unittest
from pathlib import Path

from mrhbench.io import ProtocolError, write_json, file_hash, read_json
from mrhbench.paged_source_navigation import publish_pages, verify_pages


class PagedNavigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'paper.html'
        self.source.write_text('<p>科研 β</p>', encoding='utf8')
        self.nav = self.root / 'nav.json'
        self.dest = self.root / 'pages'
        write_json(self.nav, {'schema_version': 'source-navigation-1',
            'source_sha256': file_hash(self.source), 'source_id': 'paper',
            'derived_not_independent_evidence': True,
            'units': [{'id': str(i), 'text': ('科研 β — "x"\n' * 60)} for i in range(12)]})

    def test_exact_order_unicode_and_bounded_pages(self):
        old = self.nav.read_bytes(), self.source.read_bytes()
        manifest = publish_pages(self.nav, self.source, self.dest, max_page_bytes=8000)
        result = verify_pages(self.dest, self.nav, self.source)
        self.assertEqual(result['units'], 12)
        self.assertGreater(result['pages'], 1)
        self.assertFalse(result['model_read_verified'])
        self.assertTrue(all(p.stat().st_size <= 8000 for p in self.dest.iterdir()))
        self.assertEqual(old, (self.nav.read_bytes(), self.source.read_bytes()))
        self.assertTrue(manifest['metadata']['derived_not_independent_evidence'])
        with self.assertRaises(ProtocolError):
            publish_pages(self.nav, self.source, self.dest)

    def test_oversized_unit_no_partial_output(self):
        nav = read_json(self.nav)
        nav['units'][0]['text'] = 'x' * 20000
        write_json(self.nav, nav)
        with self.assertRaisesRegex(ProtocolError, 'Indivisible'):
            publish_pages(self.nav, self.source, self.dest)
        self.assertFalse(self.dest.exists())

    def test_source_mismatch_before_write(self):
        self.source.write_text('changed', encoding='utf8')
        with self.assertRaises(ProtocolError):
            publish_pages(self.nav, self.source, self.dest)
        self.assertFalse(self.dest.exists())

    def test_page_tamper_or_extra_file(self):
        publish_pages(self.nav, self.source, self.dest)
        p = self.dest / 'page-0000.json'
        raw = p.read_bytes()
        p.write_bytes(raw + b' ')
        with self.assertRaises(ProtocolError):
            verify_pages(self.dest, self.nav, self.source)
        p.write_bytes(raw)
        (self.dest / 'extra').write_text('x')
        with self.assertRaises(ProtocolError):
            verify_pages(self.dest, self.nav, self.source)

    def test_empty_and_invalid_bounds(self):
        nav = read_json(self.nav)
        nav['units'] = []
        write_json(self.nav, nav)
        for bound in (True, 1, 16001):
            with self.assertRaises(ProtocolError):
                publish_pages(self.nav, self.source, self.dest, max_page_bytes=bound)
        publish_pages(self.nav, self.source, self.dest)
        self.assertEqual(verify_pages(self.dest, self.nav, self.source)['units'], 0)


if __name__ == '__main__':
    unittest.main()
