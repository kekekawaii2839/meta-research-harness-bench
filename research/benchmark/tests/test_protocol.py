"""Synthetic software tests only; these are not scientific benchmark results."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.io import ProtocolError, TraceLog, contained, digest, file_hash, read_json, write_json
from mrhbench.scoring import DIMENSIONS, aggregate, validate_grade, version_summary
from mrhbench.materials import TASK_GATES, FrozenCorpus, check_task, export_task, validate_split
from mrhbench.evolution import EvolutionRun


def tasks(split="search", paper="paper_a"):
    return [{"task_id": split + "_" + k, "task_type": k, "paper_id": paper, "split": split} for k in DIMENSIONS]


def results(manifest, value=3):
    return [{**t, "status": "scored", "dimension_scores": {k: value for k in DIMENSIONS[t["task_type"]]}} for t in manifest]


class IOTests(unittest.TestCase):
    def test_json_duplicate_nonfinite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "input.json"
            for value in ('{"a":1,"a":2}', '{"a":NaN}'):
                p.write_text(value)
                with self.assertRaises(ProtocolError):
                    read_json(p)

    def test_paths_reject_escape_ads_and_reserved(self):
        with tempfile.TemporaryDirectory() as d:
            for value in ("../x", "/x", "C:/x", "x:stream", "x\\y", "x//y", "./x", "nul.txt", "x. "):
                with self.subTest(value=value), self.assertRaises(ProtocolError):
                    contained(Path(d), value)

    def test_trace_mutation_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "trace.jsonl"
            log = TraceLog(p)
            log.append("tool_started", {"tool": "read"})
            log.append("tool_finished", {"exit_code": 0})
            self.assertEqual(len(log.read()), 2)
            p.write_text(p.read_text().replace('"exit_code":0', '"exit_code":1'))
            with self.assertRaises(ProtocolError):
                log.read()


class ScoringTests(unittest.TestCase):
    def test_all_modules_and_cost_not_in_score(self):
        ts = tasks()
        rs = results(ts)
        for r in rs:
            r["cost"] = {"usd": 100000}
        self.assertEqual(aggregate(ts, rs)["total_quality"], 3)

    def test_exp_resource_cannot_compensate(self):
        r = results(tasks())[2]
        self.assertEqual(r["task_type"], "EXP")
        r["dimension_scores"] = dict.fromkeys(DIMENSIONS["EXP"], 0)
        r["dimension_scores"]["resource_reasonableness"] = 4
        self.assertEqual(validate_grade("EXP", r), 0)

    def test_many_slices_do_not_overweight_paper(self):
        ts = [{"task_id": "a" + str(i), "paper_id": "a", "task_type": "EXP", "split": "search"} for i in range(10)]
        ts += [{"task_id": "b", "paper_id": "b", "task_type": "EXP", "split": "search"}]
        rs = results(ts[:10], 4) + results(ts[10:], 0)
        summary = aggregate(ts, rs, require_all_modules=False)
        self.assertEqual(summary["module_scores"]["EXP"], 2)
        self.assertIsNone(summary["total_quality"])

    def test_write_types_do_not_add_module_weight(self):
        ts = tasks()
        rs = results(ts, 0)
        for r in rs:
            if r["task_type"].startswith("WRITE_"):
                r["dimension_scores"] = dict.fromkeys(DIMENSIONS[r["task_type"]], 4)
        self.assertEqual(aggregate(ts, rs)["total_quality"], 1)

    def test_missing_task_duplicate_and_wrong_identity(self):
        ts, rs = tasks(), results(tasks())
        for bad in (rs[:-1], rs + [rs[0]], [{**rs[0], "paper_id": "other"}] + rs[1:]):
            with self.assertRaises(ProtocolError):
                aggregate(ts, bad)

    def test_infra_failure_not_silently_dropped(self):
        ts, rs = tasks(), results(tasks())
        rs[0]["status"] = "infrastructure_failed"
        with self.assertRaises(ProtocolError):
            aggregate(ts, rs)

    def test_scored_model_failure_stays_in_denominator(self):
        ts, rs = tasks(), results(tasks(), 4)
        rs[0].update(status="model_failed", dimension_scores=dict.fromkeys(DIMENSIONS["LIT"], 0))
        self.assertEqual(aggregate(ts, rs)["total_quality"], 3)

    def test_invalid_grade_and_dimension_set(self):
        r = results(tasks())[0]
        for value in (True, -1, 5, float("nan"), 2.5):
            bad = copy.deepcopy(r)
            bad["dimension_scores"]["factual_citation_accuracy"] = value
            with self.assertRaises(ProtocolError):
                validate_grade("LIT", bad)
        with self.assertRaises(ProtocolError):
            validate_grade("IDEA", r)

    def test_oracle_tie_earliest_and_builder_autonomy(self):
        cps = [{"version_id": "H0", "round": 0, "test_total_quality": 2},
               {"version_id": "H1", "round": 1, "test_total_quality": 4},
               {"version_id": "H2", "round": 2, "test_total_quality": 4}]
        out = version_summary(cps, "H0")
        self.assertEqual(out["builder_selected"]["version_id"], "H0")
        self.assertEqual(out["test_best"]["version_id"], "H1")


class MaterialTests(unittest.TestCase):
    def fixture(self, root):
        (root / "input.txt").write_text("Public task input", encoding="utf-8")
        (root / "gold.txt").write_text("PRIVATE_CANARY_DO_NOT_EXPORT", encoding="utf-8")
        t = {"schema_version": "0.1", "task_id": "opaque001", "paper_id": "private_paper",
             "task_type": "IDEA", "split": "development", "private": {"answer": "PRIVATE_CANARY_DO_NOT_EXPORT"},
             "gates": {k: {"status": "pending", "evidence": "Synthetic test, not real acceptance"} for k in TASK_GATES},
             "assets": [{"asset_id": name, "path": name + ".txt", "visibility": visibility,
                         "sha256": file_hash(root / (name + ".txt"))} for name, visibility in (("input", "public"), ("gold", "private"))]}
        t["public"] = {"task_id": t["task_id"], "task_type": "IDEA", "prompt": "Propose an idea.", "inputs": ["input"],
                       "output_contract": {}, "resources": {}, "tools": [], "public_rubric": []}
        return t

    def test_export_only_whitelisted_public_assets(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            t = self.fixture(root)
            out = root / "release"
            info = export_task(t, root, out, audience="development_executor")
            self.assertEqual(info["private_assets_exported"], 0)
            all_text = "\n".join(p.read_text() for p in out.rglob("*") if p.is_file())
            self.assertNotIn("PRIVATE_CANARY", all_text)
            self.assertNotIn("private_paper", all_text)
            with self.assertRaises(ProtocolError):
                export_task(t, root, out, audience="development_executor")

    def test_changed_asset_blocks_export(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            t = self.fixture(root)
            (root / "input.txt").write_text("tampered")
            with self.assertRaises(ProtocolError):
                check_task(t, root)

    def test_formal_pending_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            t = self.fixture(root)
            t["split"] = "search"
            with self.assertRaises(ProtocolError):
                check_task(t, root, formal=True)

    def test_hidden_export_to_search_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            t = self.fixture(root)
            t["split"] = "test"
            with self.assertRaises(ProtocolError):
                export_task(t, root, root / "out", audience="search_executor")

    def test_split_same_paper_versions_together(self):
        with self.assertRaises(ProtocolError):
            validate_split(tasks("search", "same") + tasks("test", "same"))
        validate_split(tasks("search", "a") + tasks("test", "b"))

    def test_historical_search_and_read_share_filter(self):
        docs = [{"document_id": name, "paper_id": paper, "version": "v1", "source_url": "https://example.invalid/" + name,
                 "published_evidence": "Synthetic fixture", "published_date": date, "title": "Adaptation", "text": "adaptation evidence"}
                for name, paper, date in (("old", "a", "2020-01-01"), ("future", "b", "2025-01-01"), ("target", "c", "2020-01-01"))]
        corpus = FrozenCorpus(docs, "2024-01-01", {"c"})
        self.assertEqual([x["document_id"] for x in corpus.search("adaptation")], ["old"])
        for name in ("future", "target"):
            with self.assertRaises(ProtocolError):
                corpus.read(name)


class EvolutionTests(unittest.TestCase):
    def feedback(self, tasks):
        return [{"task_id": t["task_id"], "task_type": t["task_type"], "mode": "feedback",
                 "feedback": {"issues": [], "limitations": ["Synthetic protocol fixture, not real judge feedback"]},
                 "public_evidence_inventory_hash": "synthetic-public-hash"} for t in tasks]
    def setup_run(self, root):
        harness = root / "harness"
        harness.mkdir()
        (harness / "agent.py").write_text("# Synthetic test fixture, not an actual research agent\n")
        ts = tasks("search", "a") + tasks("test", "b")
        return EvolutionRun.create(root / "control", ts, 1), harness, ts

    def test_full_cycle_and_no_hidden_feedback(self):
        with tempfile.TemporaryDirectory() as d:
            run, harness, ts = self.setup_run(Path(d))
            self.assertEqual(run.builder_view()["search_tasks"], [])
            self.assertEqual(run.submit(harness), "H0")
            run.record_evaluation("H0", "search", results(ts[:5], 2))
            with self.assertRaises(ProtocolError):
                run.submit(harness)
            with self.assertRaises(ProtocolError):
                run.publish_search_feedback("H0", results(ts[:5], 2))
            run.publish_search_feedback("H0", self.feedback(ts[:5]))
            self.assertEqual(run.submit(harness, note="No-change submission is allowed"), "H1")
            run.record_evaluation("H1", "search", results(ts[:5], 3))
            run.publish_search_feedback("H1", self.feedback(ts[:5]))
            run.select("H0", "Prefer the simpler starting version")
            before = run.builder_view()
            self.assertNotIn("paper_scores", json.dumps(before))
            run.record_evaluation("H0", "test", results(ts[5:], 2))
            run.record_evaluation("H1", "test", results(ts[5:], 4))
            self.assertEqual(before, run.builder_view())
            self.assertEqual(run.summary()["test_best"]["version_id"], "H1")
            self.assertEqual(run.summary()["builder_selected"]["version_id"], "H0")

    def test_round_skipping_repeated_evaluation_and_early_test_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            run, harness, ts = self.setup_run(Path(d))
            run.submit(harness)
            with self.assertRaises(ProtocolError):
                run.submit(harness)
            with self.assertRaises(ProtocolError):
                run.record_evaluation("H0", "test", results(ts[5:]))
            run.record_evaluation("H0", "search", results(ts[:5]))
            with self.assertRaises(ProtocolError):
                run.record_evaluation("H0", "search", results(ts[:5]))

    def test_frozen_code_mutation_detected(self):
        with tempfile.TemporaryDirectory() as d:
            run, harness, ts = self.setup_run(Path(d))
            run.submit(harness)
            (run.root / "snapshots/H0/agent.py").write_text("changed")
            with self.assertRaises(ProtocolError):
                run.record_evaluation("H0", "search", results(ts[:5]))

    def test_formal_runner_not_falsely_accepted(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ProtocolError):
            EvolutionRun.create(Path(d) / "formal", tasks("search", "a") + tasks("test", "b"), 1, development=False)


if __name__ == "__main__":
    unittest.main()
