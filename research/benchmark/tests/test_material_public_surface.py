import json
import tempfile
import unittest
from pathlib import Path
from mrhbench.io import ProtocolError, file_hash
from mrhbench.material_public_surface import public_surface


class PublicSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "task.md").write_text("Neutral task", encoding="utf-8")
        self.pkg = {"facts": [{"fact_id": "F", "kind": "source_fact",
                    "statement": "Given scientific condition", "allowed_stages": ["EXP"],
                    "evidence": [{"locator": "PRIVATE source identity"}]}],
            "environment": {"resources": {"cpus": 2}}, "tasks": [{
                "task_id": "T", "task_type": "EXP", "input_fact_ids": ["F"],
                "input_contract": {"files": [{"path": "task.md"}]},
                "output_contract": {"required": "solution/neutral.py"},
                "verification_plan": {"private": "gold answer"},
                "assets": [{"path": "task.md", "visibility": "public",
                            "sha256": file_hash(self.root / "task.md")}]}]}

    def run_inventory(self):
        (self.root / "package.json").write_text(json.dumps(self.pkg), encoding="utf-8")
        return public_surface(self.root)

    def test_all_scientific_public_fields_not_private_locator(self):
        out = self.run_inventory()
        text = json.dumps(out["records"])
        self.assertIn("Given scientific condition", text)
        self.assertIn("solution/neutral.py", text)
        self.assertNotIn("PRIVATE", text)
        self.assertNotIn("gold answer", text)
        self.assertFalse(out["scientific_acceptance"])

    def test_unchanged_fact_or_output_name_changes_inventory(self):
        before = self.run_inventory()["inventory"]
        self.pkg["facts"][0]["statement"] = "Author used 2400 fits"
        self.pkg["tasks"][0]["output_contract"]["required"] = "source_method.py"
        after = self.run_inventory()["inventory"]
        self.assertNotEqual(before["task:T:fact:F"], after["task:T:fact:F"])
        self.assertNotEqual(before["task:T:output_contract"], after["task:T:output_contract"])

    def test_bad_asset_hash_rejected(self):
        (self.root / "task.md").write_text("changed", encoding="utf-8")
        with self.assertRaises(ProtocolError): self.run_inventory()

    def test_private_asset_in_input_rejected(self):
        self.pkg["tasks"][0]["assets"][0]["visibility"] = "private"
        with self.assertRaises(ProtocolError): self.run_inventory()

    def test_stage_ineligible_fact_rejected(self):
        self.pkg["facts"][0]["allowed_stages"] = []
        with self.assertRaises(ProtocolError): self.run_inventory()

    def test_binary_is_in_inventory(self):
        p = self.root / "task.md"
        p.write_bytes(b"\xff\x00\x01")
        self.pkg["tasks"][0]["assets"][0]["sha256"] = file_hash(p)
        out = self.run_inventory()
        self.assertEqual(out["records"]["task:T:asset:task.md"]["value"]["bytes"], 3)
