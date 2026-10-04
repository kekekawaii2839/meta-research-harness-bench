import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.io import ProtocolError, read_json
from mrhbench.material_quality_contract import (
    CHECKS, bound_output_schema, build_contract, coverage_schema,
    publish_contract, validate_coverage, validate_output, verify_contract,
)


class MaterialQualityContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.policy = self.root / "policy.md"
        self.policy.write_bytes(b"Full policy\r\nall rules\r\n")
        self.inventory = {"task/facts": "a" * 64, "asset/NOTICE": "b" * 64}
        self.package = "c" * 64
        self.contract = build_contract(self.policy, project_id="paper-1", round_no=2,
                                       public_inventory=self.inventory, package_sha256=self.package)
        self.base = {"type": "object", "additionalProperties": False,
                     "properties": {"project_id": {"type": "string"},
                                    "round": {"enum": [1, 2, 3]},
                                    "action": {"enum": ["pass", "pass_partial", "repair", "drop"]}},
                     "required": ["project_id", "round", "action"]}
        self.output = {"project_id": "paper-1", "round": 2, "action": "pass"}
        self.coverage = {"contract_sha256": self.contract["contract_sha256"],
                         "policy_sha256": self.contract["policy_sha256"], "checks": {}}
        for name in CHECKS:
            surfaces = list(self.inventory) if name in ("identity", "author_scale", "target_implementation") else ["task/facts"]
            self.coverage["checks"][name] = {
                "status": "clear", "scope": "entire_bound_public_inventory" if name in (
                    "identity", "author_scale", "target_implementation") else "selected_surfaces",
                "evidence": [{"surface_id": surfaces[0], "locator": "paragraph 1",
                              "observation": "Synthetic test observation, not a real audit."}],
                "rationale": "Synthetic rationale.",
            }
            if name not in ("identity", "author_scale", "target_implementation"):
                self.coverage["checks"][name]["inspected_surface_ids"] = surfaces

    def validate(self):
        return validate_output(self.output, self.base, self.contract, self.policy,
                               coverage=self.coverage, public_inventory=self.inventory,
                               package_sha256=self.package)

    def test_valid_sidecar_not_scientific_acceptance(self):
        result = self.validate()
        self.assertTrue(result["structural_contract_valid"])
        self.assertEqual(result["scientific_acceptance"], "not_established_by_this_validator")
        self.assertNotIn("quality_coverage", bound_output_schema(self.base, self.contract)["properties"])

    def test_exact_identity_not_combined_normalized_or_wrong_round(self):
        for key, value in [("project_id", "paper-1/job-1"), ("project_id", " paper-1"),
                           ("round", 1), ("round", 2.0), ("round", True)]:
            with self.subTest(key=key, value=value):
                original = self.output[key]
                self.output[key] = value
                with self.assertRaises(ProtocolError):
                    self.validate()
                self.assertEqual(self.output[key], value)
                self.output[key] = original

    def test_policy_raw_bytes_change_fails_including_newlines(self):
        self.assertEqual(self.contract["policy_sha256"], hashlib.sha256(self.policy.read_bytes()).hexdigest())
        self.policy.write_bytes(b"Full policy\nall rules\n")
        with self.assertRaises(ProtocolError):
            self.validate()

    def test_stale_inventory_package_contract_and_role_fail(self):
        for field, value in [("package_sha256", "d" * 64), ("role", "material_reviewer"),
                             ("checks", {}), ("public_inventory", {"task/facts": "d" * 64})]:
            with self.subTest(field=field):
                original = self.contract
                self.contract = {**original, field: value}
                with self.assertRaises(ProtocolError):
                    self.validate()
                self.contract = original

    def test_missing_check_or_receipt_hash_fails(self):
        for mutation in (lambda x: x["checks"].pop("identity"),
                         lambda x: x.update(contract_sha256="d" * 64),
                         lambda x: x.update(policy_sha256="d" * 64)):
            saved = copy.deepcopy(self.coverage)
            mutation(self.coverage)
            with self.assertRaises(ProtocolError):
                self.validate()
            self.coverage = saved

    def test_unknown_or_issue_never_pass_but_negative_decision_allowed(self):
        for status in ("unknown", "issue"):
            self.coverage["checks"]["identity"]["status"] = status
            for action in ("pass", "pass_partial"):
                self.output["action"] = action
                with self.assertRaises(ProtocolError):
                    self.validate()
            self.output["action"] = "drop"
            self.assertEqual(self.validate()["unresolved_checks"], ["identity"])

    def test_not_applicable_requires_reason_and_evidence(self):
        item = self.coverage["checks"]["resource"]
        item["status"] = "not_applicable"
        self.validate()
        for field, value in [("rationale", " "), ("evidence", []), ("inspected_surface_ids", [])]:
            old = item[field]
            item[field] = value
            with self.assertRaises(ProtocolError):
                self.validate()
            item[field] = old

    def test_subset_checks_allowed_but_all_surfaces_accounted(self):
        self.validate()
        for name in ("identity", "author_scale", "target_implementation"):
            self.coverage["checks"][name]["scope"] = "selected_surfaces"
            self.coverage["checks"][name]["inspected_surface_ids"] = ["task/facts"]
            with self.assertRaises(ProtocolError):
                self.validate()
            self.coverage["checks"][name]["scope"] = "entire_bound_public_inventory"
            del self.coverage["checks"][name]["inspected_surface_ids"]

    def test_compact_whole_scope_still_rejects_unknown_evidence_surface(self):
        self.coverage["checks"]["identity"]["evidence"][0]["surface_id"] = "missing"
        with self.assertRaises(ProtocolError):
            self.validate()

    def test_pending_runtime_pass_cannot_hide_unknown_semantics(self):
        self.coverage["checks"]["core_science"]["status"] = "unknown"
        with self.assertRaisesRegex(ProtocolError, "Cannot pass"):
            validate_coverage(self.coverage, self.contract, action="pass_with_pending_runtime")

    def test_reviewer_extra_action_cannot_override_decision(self):
        base = {"type": "object", "properties": {"paper_id": {"type": "string"}}}
        output = {"paper_id": "paper-1", "decision": "pass_with_pending_runtime", "action": "drop"}
        self.coverage["checks"]["identity"]["status"] = "unknown"
        with self.assertRaisesRegex(ProtocolError, "Cannot pass"):
            validate_output(output, base, self.contract, self.policy, coverage=self.coverage,
                            public_inventory=self.inventory, package_sha256=self.package,
                            identity_field="paper_id")

    def test_adjudicator_extra_decision_cannot_override_action(self):
        self.base["additionalProperties"] = True
        self.output["decision"] = "reject"
        self.coverage["checks"]["identity"]["status"] = "unknown"
        with self.assertRaisesRegex(ProtocolError, "Cannot pass"):
            self.validate()

    def test_caller_cannot_weaken_role_decision(self):
        with self.assertRaisesRegex(ProtocolError, "Caller decision differs"):
            validate_output(self.output, self.base, self.contract, self.policy,
                            coverage=self.coverage, public_inventory=self.inventory,
                            package_sha256=self.package, action="drop")

    def test_evidence_must_refer_to_inspected_known_surface(self):
        item = self.coverage["checks"]["resource"]
        item["evidence"][0]["surface_id"] = "asset/NOTICE"
        with self.assertRaisesRegex(ProtocolError, "not inspected"):
            self.validate()
        item["evidence"][0]["surface_id"] = "missing"
        with self.assertRaises(ProtocolError):
            self.validate()

    def test_reviewer_paper_id_no_round_and_no_extra_schema_fields(self):
        base = {"type": "object", "additionalProperties": False,
                "properties": {"paper_id": {"type": "string"}}, "required": ["paper_id"]}
        schema = bound_output_schema(base, self.contract, identity_field="paper_id")
        jsonschema.validate({"paper_id": "paper-1"}, schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({"paper_id": "paper-1/job"}, schema)
        self.assertEqual(set(schema["properties"]), {"paper_id"})
        self.assertEqual(base["properties"]["paper_id"], {"type": "string"})

    def test_publication_exact_bytes_and_immutable(self):
        paths = publish_contract(self.root / "release", self.contract, self.policy)
        self.assertEqual(Path(paths["policy"]).read_bytes(), self.policy.read_bytes())
        self.assertEqual(read_json(Path(paths["contract"])), self.contract)
        self.assertEqual(read_json(Path(paths["schema"])), coverage_schema(self.contract))
        with self.assertRaises(ProtocolError):
            publish_contract(self.root / "release", self.contract, self.policy)

    def test_invalid_contract_inputs_fail(self):
        defaults = dict(project_id="paper", round_no=1, public_inventory=self.inventory,
                        package_sha256=self.package)
        for field, value in [("round_no", True), ("round_no", 0), ("project_id", " "),
                             ("public_inventory", {}), ("public_inventory", {"s": "bad"}),
                             ("package_sha256", "bad"), ("role", "executor")]:
            with self.subTest(field=field):
                with self.assertRaises(ProtocolError):
                    build_contract(self.policy, **{**defaults, field: value})


if __name__ == "__main__":
    unittest.main()
