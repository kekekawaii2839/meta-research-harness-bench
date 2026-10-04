import tempfile
import unittest
from pathlib import Path

from mrhbench.evidence_read_batching import (
    EVIDENCE_READ_BATCHING_GUIDANCE, EvidenceReadBatchingRunner,
)


class FakeNative:
    def __init__(self, error=None):
        self.calls = []
        self.error = error
        self.response = {"decision": "revise", "core_issue": "retained"}

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        Path(kwargs["workspace"], "review.json").write_bytes(b'{"decision":"revise"}\r\n')
        return self.response


class EvidenceReadBatchingTests(unittest.TestCase):
    def test_both_tail_roles_keep_full_prompt_kwargs_and_response_identity(self):
        for role in ("material_reviewer", "adjudicator"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as td:
                original = "FULL ORIGINAL POLICY\r\noriginal review / private refs\n"
                fake = FakeNative()
                schema = {"type": "object"}
                result = EvidenceReadBatchingRunner(fake).run(
                    workspace=td, prompt=original, role=role, schema=schema, timeout_seconds=30)
                self.assertIs(result, fake.response)
                self.assertEqual(len(fake.calls), 1)
                self.assertEqual(fake.calls[0]["prompt"], original + "\n" + EVIDENCE_READ_BATCHING_GUIDANCE)
                self.assertIs(fake.calls[0]["schema"], schema)
                self.assertEqual(fake.calls[0]["timeout_seconds"], 30)
                self.assertEqual(fake.calls[0]["workspace"], td)
                self.assertEqual(fake.calls[0]["role"], role)
                self.assertEqual(Path(td, "review.json").read_bytes(), b'{"decision":"revise"}\r\n')
                self.assertEqual([p.name for p in Path(td).iterdir()], ["review.json"])

    def test_constructor_and_unrelated_roles_are_unchanged(self):
        for role in ("constructor", "other"):
            with tempfile.TemporaryDirectory() as td:
                fake = FakeNative()
                EvidenceReadBatchingRunner(fake).run(workspace=td, prompt="original", role=role)
                self.assertEqual(fake.calls[0]["prompt"], "original")
                self.assertEqual(len(fake.calls), 1)

    def test_native_error_is_not_retried_or_normalized(self):
        error = RuntimeError("429: stop")
        fake = FakeNative(error)
        with self.assertRaises(RuntimeError) as caught:
            EvidenceReadBatchingRunner(fake).run(workspace="unused", prompt="p", role="adjudicator")
        self.assertIs(caught.exception, error)
        self.assertEqual(len(fake.calls), 1)

    def test_guidance_preserves_required_evidence_and_fallback(self):
        for phrase in ("Sequential reads remain correct", "complete candidate package",
                       "private scientific", "actual public asset bytes", "necessary original sources",
                       "original review", "full current policy", "every missing part",
                       "All original instructions", "Do not batch writes"):
            self.assertIn(phrase, EVIDENCE_READ_BATCHING_GUIDANCE)


if __name__ == "__main__":
    unittest.main()
