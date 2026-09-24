"""Real source transcription checks plus synthetic fault tests; no model scores."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import ProtocolError, read_json
from mrhbench.materials import load_task, validate_split
from mrhbench.numeric_checks import check_display_ledger
from build_material_catalog import build_catalog


class WriteMaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = read_json(ROOT / "materials/ssa_write_evidence/public/numeric_evidence.json")
        cls.ledger = [{"cell_id": r["cell_id"], "value": r["r2"]} for r in cls.source["rows"]]

    def test_source_spot_checks_and_coverage(self):
        rows = self.source["rows"]
        self.assertEqual(len(rows), 98)
        indexed = {(r["method"], r["condition"]): r["reported_decimal"] for r in rows}
        # Independently checked from fixed HTML table rows, not generated expectations.
        self.assertEqual(indexed[("Source", "Contrast")], "-3.906")
        self.assertEqual(indexed[("Source", "Mean")], "-0.678")
        self.assertEqual(indexed[("SSA (ours)", "Mean")], "0.731")
        self.assertEqual(indexed[("SSA (ours)", "Pixelate")], "0.943")
        self.assertEqual(indexed[("FR", "Pixelate")], "0.946")
        self.assertEqual(indexed[("RSD", "Mean")], "0.701")
        self.assertTrue(all(not r["replicate_values_available"] for r in rows))

    def test_matching_ledger_is_not_visual_acceptance(self):
        result = check_display_ledger(self.source, self.ledger)
        self.assertTrue(result["all_passed"])
        self.assertIn("ledger_matches_rendered_table", result["not_verified"])
        self.assertNotIn("quality", result)

    def test_negative_clipping_missing_duplicates_and_nan_fail(self):
        variants = []
        changed = copy.deepcopy(self.ledger)
        for r in changed:
            r["value"] = max(0, r["value"])
        variants.append(changed)
        variants.append(self.ledger[:-1])
        variants.append(self.ledger + [self.ledger[0]])
        changed = copy.deepcopy(self.ledger)
        changed[0]["value"] = "NaN"
        variants.append(changed)
        for variant in variants:
            self.assertFalse(check_display_ledger(self.source, variant)["all_passed"])

    def test_material_error_is_not_solver_error(self):
        changed = copy.deepcopy(self.source)
        changed["rows"][0]["r2"] = 999
        with self.assertRaises(ProtocolError):
            check_display_ledger(changed, self.ledger)

    def test_both_write_types_same_paper_and_distinct_contracts(self):
        content = load_task(ROOT / "materials/ssa_write_content/task.json")
        evidence = load_task(ROOT / "materials/ssa_write_evidence/task.json")
        self.assertEqual(content["paper_id"], evidence["paper_id"])
        validate_split([content, evidence])
        self.assertNotEqual(content["public"]["output_contract"], evidence["public"]["output_contract"])
        self.assertNotEqual(content["public"]["public_rubric"], evidence["public"]["public_rubric"])
        evidence["split"] = "test"
        with self.assertRaises(ProtocolError):
            validate_split([content, evidence])

    def test_material_catalog_counts_actual_constructed_papers(self):
        catalog = build_catalog()
        constructed = [p for p in catalog["packages"] if p["tasks"]]
        self.assertEqual(catalog["counts"]["constructed_source_paper_count"], len(constructed))
        self.assertEqual(catalog["counts"]["constructed_task_count"], sum(len(p["tasks"]) for p in catalog["packages"]))
        self.assertEqual(catalog["counts"]["formal_accepted_tasks"], 0)
        self.assertEqual(catalog["visibility"], "maintainer_only_do_not_export_to_builder_or_executor")

    def test_overlay_attributes_manifests_without_paper_id(self):
        catalog = build_catalog()
        gaussian = [p for p in catalog["packages"] if p["paper_id"] == "iclr2025-tNn6Hskmti"]
        self.assertEqual(len(gaussian), 1)
        self.assertEqual(len(gaussian[0]["raw_sources"]), 6)
        self.assertEqual(gaussian[0]["tasks"], [])

    def test_background_service_cache_not_counted_as_target_package(self):
        catalog = build_catalog()
        manifests = catalog["separate_background_manifests"]
        self.assertTrue(any("r2_v3/manifest.json" in r["path"] for r in manifests))
        self.assertTrue(all(not r["included_in_legacy_counts"] for r in manifests))
        self.assertTrue(all(len(r["sha256"]) == 64 for r in manifests))


if __name__ == "__main__":
    unittest.main()
