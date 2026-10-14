"""Checks the real shared-library-v4 against the GETS LIT task (zero model calls)."""
from datetime import date
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import factory_library as fl  # noqa: E402
from mrhbench.io import ProtocolError  # noqa: E402
from mrhbench.literature_judge_evidence import build_literature_judge_evidence  # noqa: E402

LIB = Path(r"D:/mrhbench-local-pilot/shared-library-v4")
LIT = Path(r"D:/mrhbench-local-pilot/factory-v5/papers/iclr2025-qgsXsqahMq/units/LIT")
CUTOFF = "2024-10-12"


def manifest():
    out = next(LIT.glob("repair/*/constructor/output"))
    return json.loads((out / "assets/lit_private/library_manifest.json").read_text(encoding="utf8"))


class SharedLibraryV4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = fl.SharedLibraryService(LIB, CUTOFF, ["background-arxiv-2410.09570"],
                                          excluded_aliases=["2410.09570", "iclr2025-qgsXsqahMq", "qgsXsqahMq"])
        cls.corpus = json.loads((LIB / "corpus.json").read_text(encoding="utf8"))

    def test_required_items_visible(self):
        visible = {(d["paper_id"].replace("background-arxiv-", ""), d["version"]) for d in self.svc.corpus.docs.values()}
        ids = {d["paper_id"].replace("background-arxiv-", "") for d in self.svc.corpus.docs.values()}
        missing, version_diff = [], []
        for it in manifest()["items"]:
            arx, ver = it["arxiv"].rsplit("v", 1)
            if arx not in ids:
                missing.append(it["title"])
            elif (arx, "arxiv-v" + ver) not in visible:
                version_diff.append((it["title"], ver))
        print("\nrequired", len(manifest()["items"]), "missing", missing, "version differs", version_diff)
        self.assertEqual(missing, [])

    def test_cutoff_strict_and_target_excluded(self):
        for d in self.svc.corpus.docs.values():
            self.assertLess(date.fromisoformat(d["version_date"]), date.fromisoformat(CUTOFF), d["document_id"])
            self.assertNotEqual(d["paper_id"], "background-arxiv-2410.09570")
        later = [d for d in self.corpus["documents"] if date.fromisoformat(d["version_date"]) >= date.fromisoformat(CUTOFF)]
        print("\ncorpus docs at/after cutoff (must be hidden):", len(later), "visible:", len(self.svc.corpus.docs))
        for d in later:
            with self.assertRaises(ProtocolError):
                self.svc.read(d["document_id"])

    def test_one_version_per_paper(self):
        papers = [d["paper_id"] for d in self.svc.corpus.docs.values()]
        self.assertEqual(len(papers), len(set(papers)))

    def test_search_and_html_pages(self):
        hits = self.svc.search("temperature scaling graph neural network calibration", 10)
        print("\nsearch top:", [h["title"][:60] for h in hits[:5]])
        self.assertTrue(hits)
        doc = next(k for k, v in self.svc.records.items() if v.get("fulltext_kind") == "arxiv_html" and k in self.svc.corpus.docs)
        p1 = self.svc.read_page(doc, 1)
        self.assertGreater(p1["page_count"], 1)
        self.assertLessEqual(len(p1["text"]), fl.PAGE_CHARS)
        joined = "\n".join(self.svc.read_page(doc, n)["text"] for n in range(1, p1["page_count"] + 1))
        self.assertEqual(joined, fl.html_text((LIB / self.svc.records[doc]["html_source_path"]).read_text(encoding="utf8")))
        with self.assertRaises(ProtocolError):
            self.svc.read_page(doc, p1["page_count"] + 1)

    def test_existing_judge_evidence_builder_accepts_service(self):
        recs = build_literature_judge_evidence(self.svc, allow_incomplete=True)
        print("\njudge evidence records:", len(recs))
        self.assertGreater(len(recs), 1)


if __name__ == "__main__":
    unittest.main()
