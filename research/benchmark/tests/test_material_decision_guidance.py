import unittest

from mrhbench.io import ProtocolError
from mrhbench.material_decision_guidance import DecisionGuidanceRunner, DECISION_GUIDANCE


class Fake:
    def __init__(self, error=None):
        self.calls = []
        self.result = {"decision": "pass_with_pending_runtime", "unresolved": True}
        self.error = error

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


class DecisionGuidanceTests(unittest.TestCase):
    def test_both_review_roles_receive_same_semantics_without_output_rewrite(self):
        for role in ("material_reviewer", "adjudicator"):
            f = Fake()
            result = DecisionGuidanceRunner(f).run(workspace="unused", prompt="FULL POLICY",
                                                  role=role, output_schema={"x": 1})
            self.assertIs(result, f.result)  # Even invalid output goes to the real quality gate.
            self.assertTrue(f.calls[0]["prompt"].startswith("FULL POLICY"))
            self.assertIn(DECISION_GUIDANCE, f.calls[0]["prompt"])
            self.assertEqual(f.calls[0]["output_schema"], {"x": 1})
            self.assertEqual(len(f.calls), 1)

    def test_constructor_unchanged(self):
        f = Fake()
        DecisionGuidanceRunner(f).run(workspace="unused", prompt="original", role="constructor")
        self.assertEqual(f.calls[0]["prompt"], "original")

    def test_no_retry_or_error_masking(self):
        e = ProtocolError("Cannot pass unresolved full-package checks: core_science")
        f = Fake(e)
        with self.assertRaises(ProtocolError) as caught:
            DecisionGuidanceRunner(f).run(workspace="unused", prompt="policy", role="adjudicator")
        self.assertIs(caught.exception, e)
        self.assertEqual(len(f.calls), 1)

    def test_unsupported_role_rejected_without_call(self):
        f = Fake()
        with self.assertRaises(ProtocolError):
            DecisionGuidanceRunner(f).run(workspace="unused", prompt="policy", role="executor")
        self.assertFalse(f.calls)
