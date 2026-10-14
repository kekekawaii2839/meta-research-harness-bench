"""Output checks on synthetic good/bad submissions against the real GETS public assets (no model calls)."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from output_checks import run_checks  # noqa: E402

UNITS = Path(r"D:/mrhbench-local-pilot/factory-v5/papers/iclr2025-qgsXsqahMq/units")


def public_root(unit):
    return next((UNITS / unit / "release/review_releases").iterdir()) / "assets"


def spec(unit):
    # rerun (container re-execution) is exercised on real pilot output, not on synthetic files
    return [c for c in json.loads((UNITS / unit / "checks.json").read_text(encoding="utf8"))["checks"] if c["type"] != "rerun"]


def put(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if isinstance(text, str) else json.dumps(text), encoding="utf8")


class OutputChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_write_evidence(self):
        pub = public_root("WRITE_EVIDENCE")
        good = self.tmp / "good"
        for f in ("make_figure.py", "caption.md", "interpretation.md"):
            put(good, "submission/" + f, "ECE (x10^-2) as reported, mean ± std over 10 runs.")
        put(good, "submission/figure.png", "png")
        manifest = {"artifact_files": ["figure.png"], "source_csv": "assets/data/ece_main_table.csv",
                    "plotted_values": [{"row_id": "R007", "field": "ece_mean", "value_shown": "2.50", "element": "x"}],
                    "derived_values": [], "omitted_rows": []}
        put(good, "submission/manifest.json", manifest)
        r = run_checks(spec("WRITE_EVIDENCE"), good, pub)
        self.assertEqual(r["hard_failed"], [], r)
        self.assertEqual(r["flags_raised"], [], r)
        bad = self.tmp / "bad"
        shutil.copytree(good, bad)
        (bad / "submission/figure.png").unlink()
        manifest["plotted_values"] += [{"row_id": "R999", "field": "ece_mean", "value_shown": "1", "element": "x"},
                                       {"row_id": "R001", "field": "ece_mean", "value_shown": "9.99", "element": "x"}]
        put(bad, "submission/manifest.json", manifest)
        put(bad, "submission/caption.md", "GETS is significantly better (p-value < 0.05).")
        r = run_checks(spec("WRITE_EVIDENCE"), bad, pub)
        self.assertEqual(set(r["hard_failed"]), {"we-files", "we-manifest-rows-exist"}, r)
        self.assertTrue({"we-manifest-values-match", "we-no-fabricated-inference", "we-identity-caption"} <= set(r["flags_raised"]), r)

    def test_write_content(self):
        pub = public_root("WRITE_CONTENT")
        body = ("word " * 1200 + "\n$$\\mathrm{Softmax}(\\mathrm{TopK}(Q,k))$$ Softplus noise $\\mathcal{N}(0,1)$, "
                "$\\tilde D^{-1/2}\\tilde A\\tilde D^{-1/2}$, M=7, k=2, a 16-dimensional embedding, B=10 bins, ECE.")
        good = self.tmp / "good"
        put(good, "output/method_section.md", body)
        put(good, "output/fact_trace.json", {"sections": [{"heading": "a", "fact_ids": ["F01", "F11"]}],
                                             "implementation_derived_marked": ["F11", "F17"], "notation": {}})
        r = run_checks(spec("WRITE_CONTENT"), good, pub)
        self.assertEqual((r["hard_failed"], r["flags_raised"]), ([], []), r)
        bad = self.tmp / "bad"
        put(bad, "output/method_section.md", "word " * 300 + " a GETS-like method got 28.60% with learning rate 0.01")
        put(bad, "output/fact_trace.json", {"sections": [{"heading": "a", "fact_ids": ["F99"]}],
                                            "implementation_derived_marked": ["F11"], "notation": {}})
        r = run_checks(spec("WRITE_CONTENT"), bad, pub)
        self.assertEqual(set(r["hard_failed"]), {"wc-required-content", "wc-trace-ids", "wc-impl-derived-marked"}, r)
        self.assertEqual(set(r["flags_raised"]), {"wc-length", "wc-out-of-scope-numbers", "wc-identity"}, r)

    def test_ordinary_word_gets_not_flagged(self):
        pub = public_root("WRITE_CONTENT")
        d = self.tmp / "g"
        put(d, "output/method_section.md", "The gate gets two experts.")
        put(d, "output/fact_trace.json", {})
        r = run_checks(spec("WRITE_CONTENT"), d, pub)
        self.assertNotIn("wc-identity", r["flags_raised"])

    def test_idea_and_lit(self):
        pub = public_root("IDEA")
        d = self.tmp / "idea"
        put(d, "output/proposal.json", {"background_grounding": [{"ref_id": "R03", "use": "x"}, {"ref_id": "R77", "use": "y"}]})
        r = run_checks(spec("IDEA"), d, pub)
        self.assertEqual(set(r["hard_failed"]), {"idea-schema", "idea-ref-ids"}, r)
        r = run_checks(spec("LIT"), self.tmp / "empty", public_root("LIT"))
        self.assertIn("lit-files", r["hard_failed"])


if __name__ == "__main__":
    unittest.main()
