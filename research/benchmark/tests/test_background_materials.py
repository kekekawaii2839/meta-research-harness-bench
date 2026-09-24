"""Historical interface and real package visibility tests, not judge calibration."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import ProtocolError, read_json
from mrhbench.materials import FrozenCorpus, export_task, load_task, validate_split
from mrhbench.literature import LiteratureService


class BackgroundMaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = read_json(ROOT / "materials/background_corpus.json")["documents"]

    def test_cutoff_and_exclusion_before_search_read(self):
        corpus = FrozenCorpus(self.docs, "2020-01-01", {"background-arxiv-1607.01719"})
        self.assertNotIn("doc-2006.10726", corpus.docs)
        self.assertNotIn("doc-1607.01719", corpus.docs)
        self.assertTrue(all(x["document_id"] not in {"doc-2006.10726", "doc-1607.01719"} for x in corpus.search("adaptation", 50)))
        with self.assertRaises(ProtocolError):
            corpus.read("doc-2006.10726")

    def test_private_metadata_and_mutable_input_not_exposed(self):
        rows = copy.deepcopy(self.docs)
        rows[0]["private_judge_note"] = "PRIVATE_NOTE_CANARY"
        corpus = FrozenCorpus(rows, "2024-09-01", set())
        rows[0]["text"] = "MODIFIED_AFTER_INIT"
        result = corpus.read(rows[0]["document_id"])
        self.assertNotIn("private_judge_note", result)
        self.assertNotIn("pdf_source_path", result)
        self.assertNotEqual(result["text"], "MODIFIED_AFTER_INIT")

    def test_pdf_read_cannot_bypass_filter_even_without_pdf_dependency(self):
        service = LiteratureService(self.docs, ROOT.parents[1], "2014-01-01", set())
        with self.assertRaisesRegex(ProtocolError, "not available"):
            service.read_page("doc-2006.10726", 3)

    def test_idea_no_source_target_method_and_complete_source_group(self):
        paths = sorted((ROOT/"materials").glob("*/task.json"))
        tasks = [load_task(p) for p in paths]
        validate_split(tasks)
        self.assertEqual({t["task_type"] for t in tasks}, {"LIT", "IDEA", "EXP", "WRITE_CONTENT", "WRITE_EVIDENCE"})
        idea = load_task(ROOT/"materials/ssa_idea/task.json")
        # A mechanical canary check is not semantic leakage acceptance.
        text = (ROOT/"materials/ssa_idea/public/background_report.json").read_text()
        for forbidden in ("2410.03263", "Significant-subspace Alignment", "0.731", "alpha_d"):
            self.assertNotIn(forbidden, text)
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)/"task"
            export_task(idea, ROOT/"materials/ssa_idea", destination, audience="development_executor")
            release = (destination/"task.json").read_text()
            self.assertNotIn("excluded_papers", release)
            self.assertFalse(any("private" in p.parts for p in destination.rglob("*")))

    def test_v1_names_preserved_not_replaced_by_later_titles(self):
        titles = {d["document_id"]: d["title"] for d in self.docs}
        self.assertEqual(titles["doc-1909.13231"], "Test-Time Training for Out-of-Distribution Generalization")
        self.assertEqual(titles["doc-2006.10726"], "Fully Test-time Adaptation by Entropy Minimization")

    def test_lit_judge_not_idea_and_write_method_is_complete(self):
        lit = read_json(ROOT/"materials/ssa_lit/private/evaluation.json")
        idea = read_json(ROOT/"materials/ssa_idea/private/evaluation.json")
        self.assertFalse(any(c.startswith("Hypotheses should") for c in lit["checks"]))
        self.assertTrue(any(c.startswith("Hypotheses should") for c in idea["checks"]))
        for folder in ("ssa_write_content", "ssa_write_evidence"):
            facts = read_json(ROOT/"materials"/folder/"public/research_facts.json")
            updates = next(f for f in facts["method_facts"] if f["id"] == "M5")
            self.assertIn("only", updates["fact"])
            self.assertIn("normalization affine", updates["fact"])


if __name__ == "__main__":
    unittest.main()
