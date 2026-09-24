from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.source_evidence_index import build_evidence_index


class SourceIndexTests(unittest.TestCase):
    def test_complete_multiline_equation_and_math_alttext(self):
        html = '''<div id="p1" class="ltx_para">Loss:
          <table id="g1" class="ltx_equationgroup"><tbody id="eq1">
          <tr><td><math alttext="D_{KL}(P||Q)"><mi>duplicate</mi></math></td></tr>
          <tr><td>+<math alttext="D_{KL}(Q||P)"><mi>duplicate</mi></math></td></tr>
          </tbody></table>End.</div>'''
        index = build_evidence_index(html, "s", "a" * 64)
        rows = {u["id"]: u for u in index["units"]}
        self.assertEqual(set(rows), {"p1", "g1"})
        self.assertIn("D_{KL}(P||Q)", rows["g1"]["text"])
        self.assertIn("D_{KL}(Q||P)", rows["g1"]["text"])
        self.assertNotIn("duplicate", rows["p1"]["text"])
        self.assertIn("eq1", rows["g1"]["child_ids"])

    def test_real_ssa_symmetric_objective_complete(self):
        from mrhbench.io import file_hash, read_json
        job = read_json(ROOT / "materials/pilot_v2/jobs/ssa.json")
        source = next(r for r in job["sources"] if r["role"] == "paper_html")
        p = ROOT.parents[1] / source["local_path"]
        result = build_evidence_index(p.read_text(encoding="utf8"), source["source_id"], file_hash(p))
        rows = {u["id"]: u for u in result["units"]}
        self.assertIn("S3.EGx4", rows)
        self.assertEqual(rows["S3.EGx4"]["text"].count("D_{\\text{KL}}"), 2)
        self.assertIn("S3.E8", rows["S3.EGx4"]["child_ids"])
        self.assertIn("S4.T4", rows)


if __name__ == "__main__":
    unittest.main()
