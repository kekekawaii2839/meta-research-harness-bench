import copy
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import ProtocolError, read_json
from mrhbench.literature import LiteratureService, SharedCorpusView, original_abstract, retrieval_diagnostics


class SharedBackgroundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_json(ROOT / "materials/pilot_v2/shared_background_corpus.json")["documents"]

    def test_no_task_directed_digest(self):
        service = LiteratureService(self.rows, ROOT.parents[1], "2024-09-01", set(), shared=True)
        result = service.read("doc-2006.10726")
        self.assertEqual(result["text_kind"], "verbatim_pinned_source_abstract")
        self.assertNotIn("deterministic scalar", result["text"])
        for key in ("pdf_source_path", "index_approved", "paper_aliases", "support_pages"):
            self.assertNotIn(key, result)

    def test_exclusion_before_title_snippet_body_pdf(self):
        svc = LiteratureService(self.rows, ROOT.parents[1], "2020-01-01", set(), shared=True,
                                excluded_aliases={"1607.01719"})
        for identity in ("doc-2006.10726", "doc-1607.01719"):
            self.assertNotIn(identity, str(svc.search("adaptation", 50)))
            with self.assertRaises(ProtocolError):
                svc.read(identity)
            with self.assertRaises(ProtocolError):
                svc.read_page(identity, 1)

    def test_unknown_disclosure_and_unapproved_fail_closed(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["disclosure_status"] = "unknown"
        rows[1]["index_approved"] = False
        view = SharedCorpusView(rows, "2024-09-01", set())
        self.assertNotIn(rows[0]["document_id"], view.docs)
        self.assertNotIn(rows[1]["document_id"], view.docs)

    def test_allowed_version_and_newest_selection(self):
        rows = copy.deepcopy(self.rows[:1])
        newer = copy.deepcopy(rows[0])
        newer.update(document_id="new", published_date="2025-01-01", version="v2", version_number=2,
                     text="FUTURE_CANARY")
        rows.append(newer)
        view = SharedCorpusView(rows, "2024-09-01", set())
        self.assertEqual(len(view.docs), 1)
        self.assertNotIn("FUTURE_CANARY", str(view.search("FUTURE_CANARY")))
        view = SharedCorpusView(rows, "2026-01-01", set(), allowed_versions={rows[0]["paper_id"]: ["arxiv-v1"]})
        self.assertEqual(set(view.docs), {rows[0]["document_id"]})

    def test_private_labels_never_exposed(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["relevance"] = "CORE_CANARY"
        rows[0]["package_id"] = "PACKAGE_CANARY"
        view = SharedCorpusView(rows, "2024-09-01", set())
        text = str(view.search("adaptation", 50)) + str(view.read(rows[0]["document_id"]))
        self.assertNotIn("CANARY", text)

    def test_retrieval_stages_no_automatic_penalty(self):
        row = self.rows[0]
        result = retrieval_diagnostics(retrieved=[row["document_id"]]*2, read=[], adopted=[row["document_id"]],
             documents=self.rows, private_roles={row["paper_id"]: "confusable"})
        self.assertEqual(result["stages"]["retrieved"]["paper_count"], 1)
        self.assertEqual(result["stages"]["read"]["paper_count"], 0)
        self.assertIsNone(result["primary_score"])
        self.assertTrue(result["confusable_citation_is_not_automatic_error"])

if __name__ == "__main__":
    unittest.main()
