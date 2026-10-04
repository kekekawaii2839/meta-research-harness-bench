import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from mrhbench.incremental_repair import (
    diff_outputs, prepare_incremental_review, seed_output,
)


class IncrementalRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old, self.new = self.root / "old", self.root / "new"
        self.old.mkdir()
        self.new.mkdir()

    def write(self, root, name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_seed_preserves_prepopulation_and_original_bytes(self):
        self.write(self.old, "assets/a.csv", b"x\r\n1\r\n")
        self.write(self.old, "package.json", b'{"sha256":"old-declared"}')
        self.write(self.old, "same", b"same")
        self.write(self.new, "same", b"same")
        self.write(self.new, "package.json", b'{"sha256":"prepopulated"}')
        self.write(self.new, "extra.bin", b"\x00\xff")
        self.write(self.old, "package.constructor_original.json", b"excluded")
        record = seed_output(self.old, self.new)
        self.assertEqual(record["copied"], ["assets/a.csv"])
        self.assertEqual(record["copied_bytes"], 6)
        self.assertEqual(record["conflicts"][0]["path"], "package.json")
        self.assertEqual((self.new / "package.json").read_bytes(), b'{"sha256":"prepopulated"}')
        self.assertEqual((self.old / "package.json").read_bytes(), b'{"sha256":"old-declared"}')
        self.assertFalse((self.new / "package.constructor_original.json").exists())
        self.assertEqual(record["output_inventory"]["assets/a.csv"]["sha256"],
                         hashlib.sha256(b"x\r\n1\r\n").hexdigest())

    def test_seed_new_directory(self):
        self.write(self.old, "a", b"a")
        record = seed_output(self.old, self.root / "fresh")
        self.assertEqual(record["copied"], ["a"])

    def test_reject_overlapping_trees(self):
        for target in (self.old, self.old / "nested", self.root):
            with self.subTest(target=target), self.assertRaises(ValueError):
                seed_output(self.old, target)

    def test_file_directory_conflict_fails_before_any_copy(self):
        self.write(self.old, "a", b"a")
        self.write(self.old, "z/inside", b"z")
        self.write(self.new, "z", b"blocking")
        with self.assertRaises(ValueError):
            seed_output(self.old, self.new)
        self.assertFalse((self.new / "a").exists())

    def test_directory_file_conflict(self):
        self.write(self.old, "a", b"a")
        (self.new / "a").mkdir()
        with self.assertRaises(ValueError):
            seed_output(self.old, self.new)

    def test_full_diff_all_statuses_binary_and_bytes(self):
        self.write(self.old, "same", b"same")
        self.write(self.new, "same", b"same")
        self.write(self.old, "gone", b"gone")
        self.write(self.new, "added", b"added")
        self.write(self.old, "text", b"old\r\n")
        self.write(self.new, "text", b"new\r\n")
        self.write(self.old, "bin", b"\x00\xff")
        self.write(self.new, "bin", b"\x00\xfe")
        result = diff_outputs(self.old, self.new)
        self.assertEqual(result["counts"], {"added": 1, "deleted": 1, "changed": 2, "unchanged": 1})
        entries = {e["path"]: e for e in result["entries"]}
        self.assertIn("-old\r\n+new\r\n", entries["text"]["unified_diff"])
        self.assertNotIn("unified_diff", entries["bin"])
        self.assertEqual(result["bytes"]["before_total"], 15)
        self.assertEqual(result["bytes"]["changed_or_added_after"], 12)
        self.assertFalse(result["truncated"])

    def test_no_truncation_and_missing_newline(self):
        data = b"".join(f"line{i}\n".encode() for i in range(20000))
        self.write(self.old, "large", b"old")
        self.write(self.new, "large", data + b"last")
        result = diff_outputs(self.old, self.new)["entries"][0]["unified_diff"]
        self.assertIn("+line19999\n+last\n", result)
        self.assertIn("\\ No newline at end of file", result)
        self.assertGreater(len(result), len(data))

    def test_empty_file_addition_and_deletion_recorded(self):
        self.write(self.old, "old-empty", b"")
        self.write(self.new, "new-empty", b"")
        result = diff_outputs(self.old, self.new)
        self.assertEqual(result["counts"]["added"], 1)
        self.assertEqual(result["counts"]["deleted"], 1)

    def test_review_navigation_preserves_full_inputs(self):
        self.write(self.old, "package.constructor_original.json", b"original")
        self.write(self.old, "package.json", b"old")
        self.write(self.new, "package.json", b"new")
        review = self.write(self.root, "review.json", b'{"unresolved":"method"}\r\n')
        dest = self.root / "review-inputs"
        record = prepare_incremental_review(self.old, review, self.new, dest)
        self.assertEqual((dest / "previous_review/review.json").read_bytes(), review.read_bytes())
        self.assertEqual((dest / "previous_candidate/package.constructor_original.json").read_bytes(), b"original")
        saved = json.loads((dest / "diff_navigation.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["diff"]["counts"], record["counts"])
        self.assertNotIn("diff", record)
        self.assertEqual(record["navigation_identity"]["sha256"],
                         hashlib.sha256((dest / "diff_navigation.json").read_bytes()).hexdigest())
        self.assertEqual(record["scientific_acceptance"], "not_assessed")
        self.assertIn("unresolved", record["warning"])
        self.assertIn("full review", record["warning"])
        with self.assertRaises(ValueError):
            prepare_incremental_review(self.old, review, self.new, dest)

    def test_review_rejects_nested_destination(self):
        review = self.write(self.root, "review.json", b"{}")
        for dest in (self.old / "nav", self.new / "nav"):
            with self.subTest(dest=dest), self.assertRaises(ValueError):
                prepare_incremental_review(self.old, review, self.new, dest)

    def test_missing_prior_review_requires_full_review(self):
        for index, review in enumerate((None, self.root / "missing.json")):
            record = prepare_incremental_review(self.old, review, self.new,
                                                self.root / f"nav-{index}")
            self.assertTrue(record["missing_prior_review"])
            self.assertTrue(record["full_review_required"])
            self.assertIsNone(record["previous_review"])

    def test_compact_json_changes(self):
        self.write(self.old, "p.json", json.dumps({"large": "x" * 50000, "a/b~": [1, 2], "gone": 1,
                                                 "type": {"x": 1}, "bool": True}).encode())
        self.write(self.new, "p.json", json.dumps({"large": "x" * 50000, "a/b~": [1, 3, 4], "new": None,
                                                 "type": "string", "bool": 1}).encode())
        self.write(self.old, "same.json", b'{"x":1}')
        self.write(self.new, "same.json", b'{"x":1}')
        dest = self.root / "compact"
        record = prepare_incremental_review(self.old, None, self.new, dest)
        raw = (dest / record["json_changes"]).read_bytes()
        self.assertLess(len(raw), 2500)
        changes = json.loads(raw)["changes"]
        by_pointer = {change["pointer"]: change for change in changes}
        self.assertEqual(set(by_pointer), {"/a~1b~0/1", "/a~1b~0/2", "/gone", "/new", "/type", "/bool"})
        self.assertEqual(by_pointer["/gone"]["operation"], "remove")
        self.assertEqual(by_pointer["/new"], {"path": "p.json", "pointer": "/new", "operation": "add", "after": None})
        self.assertEqual(by_pointer["/type"]["before"], {"x": 1})
        self.assertEqual(record["json_changes_identity"]["sha256"], hashlib.sha256(raw).hexdigest())

    def test_invalid_json_falls_back_to_complete_diff(self):
        self.write(self.old, "bad.json", b'{"a":1,"a":2}')
        self.write(self.new, "bad.json", b'{"a":3}')
        dest = self.root / "invalid"
        prepare_incremental_review(self.old, None, self.new, dest)
        result = json.loads((dest / "json_changes.json").read_bytes())
        self.assertEqual(result["changes"], [])
        self.assertEqual(result["fallbacks"][0]["reason"], "json_parse_failed")

    def test_one_field_change_does_not_repeat_unchanged_package(self):
        self.write(self.old, "package.json", b'{"keep":"large immutable context","field":1}')
        self.write(self.new, "package.json", b'{"keep":"large immutable context","field":2}')
        dest = self.root / "one-field"
        prepare_incremental_review(self.old, None, self.new, dest)
        result = json.loads((dest / "json_changes.json").read_bytes())
        self.assertEqual(result["changes"], [{"path": "package.json", "pointer": "/field",
                                             "operation": "replace", "before": 1, "after": 2}])

    def test_reject_hardlinks(self):
        source = self.write(self.root, "external", b"must not alias")
        os.link(source, self.old / "linked")
        with self.assertRaises(ValueError):
            seed_output(self.old, self.new)
        with self.assertRaises(ValueError):
            diff_outputs(self.old, self.new)

    def test_reject_symlinks_in_sources_outputs_and_ancestors(self):
        outside = self.root / "outside"
        outside.mkdir()
        link = self.old / "link"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Host does not permit symlinks: {exc}")
        with self.assertRaises(ValueError):
            seed_output(self.old, self.new)
        with self.assertRaises(ValueError):
            seed_output(self.new, link / "child")
        with self.assertRaises(ValueError):
            diff_outputs(self.old, self.new)


if __name__ == "__main__":
    unittest.main()
