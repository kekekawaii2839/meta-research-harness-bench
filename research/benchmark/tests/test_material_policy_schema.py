from copy import deepcopy
import tempfile
import unittest
from pathlib import Path
import jsonschema
from mrhbench.io import ProtocolError
from mrhbench.material_policy_schema import bind_policy_rules, publish_bound_schema, rule_ids


class PolicySchemaTests(unittest.TestCase):
    def setUp(self):
        self.policy = b"## E. Leakage\nE1. Identity.\n## H. Adjudication\nAccept evidence.\n## J. Coverage\nJ2. Whole projection.\n"
        self.schema = {"type": "object", "required": ["policy_rules"], "properties": {
            "policy_rules": {"type": "array", "minItems": 1,
                "items": {"type": "string", "pattern": "^[A-I][0-9]+$"}}}}

    def test_real_failure_class_j2_is_valid_only_in_new_schema(self):
        before = deepcopy(self.schema)
        out = {"policy_rules": ["E1", "J2"]}
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(out, self.schema)
        bound, receipt = bind_policy_rules(self.schema, self.policy)
        jsonschema.validate(out, bound)
        self.assertEqual(self.schema, before)
        self.assertFalse(receipt["historical_results_relabelled"])

    def test_undefined_rule_is_not_accepted_by_range(self):
        bound, _ = bind_policy_rules(self.schema, self.policy)
        for rule in ["J1", "J99", "E2", "Z1"]:
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate({"policy_rules": [rule]}, bound)
        jsonschema.validate({"policy_rules": ["H"]}, bound)

    def test_future_section_and_nested_schema(self):
        policy = self.policy + b"## K. Future\nK1. Rule.\n"
        nested = {"type": "array", "items": self.schema}
        bound, _ = bind_policy_rules(nested, policy)
        jsonschema.validate([{"policy_rules": ["K1"]}], bound)

    def test_missing_duplicate_or_unparented_rules_reject(self):
        for policy in [b"free text", self.policy + b"J2. Again\n", self.policy + b"K1. orphan\n"]:
            with self.assertRaises(ProtocolError): rule_ids(policy)

    def test_publication_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); p = root / "policy.md"; p.write_bytes(self.policy)
            publish_bound_schema(self.schema, p, root / "new")
            with self.assertRaises(ProtocolError): publish_bound_schema(self.schema, p, root / "new")

    def test_missing_schema_field_rejects(self):
        with self.assertRaises(ProtocolError): bind_policy_rules({"type": "object"}, self.policy)
