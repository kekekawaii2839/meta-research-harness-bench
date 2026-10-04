"""Offline trial-driver contract tests: no native sessions or Docker."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mrhbench import factory_efficiency as f
from mrhbench.io import ProtocolError, read_json, write_json


class EfficiencyTests(unittest.TestCase):
    def test_freeze_and_transitive_membership_without_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark = root / "benchmark"
            for name in ("mrhbench/engine.py", "prompts/material_constructor.txt", "scripts/active/run_factory_efficiency.py"):
                p = benchmark / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("fixture", encoding="utf8")
            binary = root / "fake.exe"
            binary.write_bytes(b"not executable")
            roles = benchmark / "config/roles.json"
            write_json(roles, {"constructor": {"model": "claude-opus-5-5", "effort": "medium"}, "claude_binary_default": str(binary)})
            ledger = root / "ledger.json"
            write_json(ledger, {"used_attempts": 593, "attempts": [{"status": "completed"}] * 593})
            ws = root / "factory/papers/p"
            ws.mkdir(parents=True)
            source = ws / "source.txt"
            source.write_bytes(b"original")
            job = ws / "job.json"
            write_json(job, {"job_id": "j", "sources": [{"local_path": "source.txt"}]})
            prior = ws / "prior/j/constructor/output"
            prior.mkdir(parents=True)
            (prior / "package.json").write_bytes(b"{}")
            notes = ws / "notes.json"
            write_json(notes, {"repair_notes": []})
            write_json(root / "factory/factory.json", {"prompt_hashes": {"material_constructor.txt": f.file_hash(benchmark / "prompts/material_constructor.txt")}})
            case = {"case_id": "a", "workspace": str(ws), "job_path": str(job), "prior_batch": str(ws / "prior"),
                    "job_id": "j", "notes_path": str(notes), "frozen_inputs": [f.identity(source)]}
            cases = root / "cases.json"
            trial = root / "trial"
            write_json(cases, {"cases": [case, {**case, "case_id": "b"}], "experiment_root": str(trial),
                               "ledger_baseline": 593, "ledger_stop_at": 613, "pair_max_calls": 12,
                               "model": "claude-opus-5-5", "effort": "medium"})
            old_ledger = ledger.read_bytes()
            f.freeze(cases, benchmark, roles, ledger)
            f.verify_execution(trial)
            self.assertEqual(old_ledger, ledger.read_bytes())
            (prior / "new_unlisted.txt").write_bytes(b"must reject")
            with self.assertRaises(ProtocolError):
                f.verify_execution(trial)

    def test_identity_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x"
            p.write_bytes(b"a")
            row = f.identity(p)
            f.verify_files([row])
            p.write_bytes(b"b")
            with self.assertRaises(ProtocolError):
                f.verify_files([row])

    def test_order_and_audit_hash_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = {"cases": [{"case_id": "a", "order": ["old", "incremental"]},
                               {"case_id": "b", "order": ["incremental", "old"]}]}
            f.check_order(root, cases, "a", "old")
            with self.assertRaises(ProtocolError):
                f.check_order(root, cases, "a", "incremental")
            for arm in cases["cases"][0]["order"]:
                write_json(root / "arms/a" / arm / "result.json", {"status": "completed"})
            gate = {"case_id": "a", "allow_next_case": True, "reviewer": "local", "review_seconds": 23,
                    "findings": ["Read all traces; no regression observed."],
                    "result_hashes": {a: f.file_hash(root / "arms/a" / a / "result.json") for a in ("old", "incremental")}}
            write_json(root / "audits/a.json", gate)
            f.check_order(root, cases, "b", "incremental")
            write_json(root / "arms/a/old/result.json", {"status": "completed", "changed": True})
            with self.assertRaises(ProtocolError):
                f.check_order(root, cases, "b", "incremental")

    def test_findings_and_exclusions(self):
        out = {"project_id": "p", "round": 3, "action": "pass", "finding_decisions": [{"finding_index": 0}],
               "excluded_task_ids": [], "repair_notes": []}
        kw = dict(project_id="p", round_no=3, allowed=["pass", "drop", "pass_partial"],
                  review={"findings": [{}]}, package={"tasks": [{"task_id": "t"}]})
        f.validate_adjudication(out, **kw)
        for change in ({"finding_decisions": []}, {"finding_decisions": [{"finding_index": 0}, {"finding_index": 0}]},
                       {"action": "repair"}, {"action": "pass_partial", "excluded_task_ids": ["t"]}, {"project_id": "wrong"}):
            with self.assertRaises(ProtocolError):
                f.validate_adjudication({**out, **change}, **kw)

    def test_missing_usage_not_zero(self):
        row = {"id": 1, "status": "failed", "usage": None}
        result = f.cost_summary([row])
        self.assertIsNone(result["usage"]["total_input_tokens"])
        self.assertIsNone(result["model_session_seconds"])
        self.assertEqual(result["failed_calls"], 1)

    def exercise_arm(self, tmp, fail=False):
        root = Path(tmp)
        ledger = root / "ledger.json"
        write_json(ledger, {"authorized_maximum": 100, "used_attempts": 0, "attempts": []})
        job = root / "job.json"
        write_json(job, {"job_id": "j", "paper_id": "p"})
        notes = root / "notes.json"
        write_json(notes, {"repair_notes": ["Correct scope."]})
        case = {"case_id": "a", "job_path": str(job), "job_id": "j", "workspace": str(root),
                "notes_path": str(notes), "notes_key": "repair_notes", "prior_batch": str(root / "prior"), "order": ["old", "incremental"]}
        cases = {"cases": [case], "ledger_baseline": 0, "ledger_stop_at": 20, "pair_max_calls": 12}
        manifest = {"ledger_path": str(ledger), "rounds": {"a": 3}, "allowed_actions": ["pass", "drop"]}
        write_json(root / "execution/manifest.json", manifest)
        import shutil
        shutil.copytree(ROOT / "prompts", root / "execution/snapshot/prompts")

        class Runner:
            def __init__(self, ledger, arm_root):
                self.ledger, self.arm_root = ledger, arm_root
            def run(self, *, workspace, prompt, role):
                cid = self.ledger.reserve(role=role, model="test", effort="medium", request_hash="0" * 64,
                                          artifact_directory=str(self.arm_root / "native_calls" / role))
                self.ledger.finish(cid, status="completed", wall_seconds=1, usage={"input_tokens": 1, "output_tokens": 1,
                                   "cached_input_tokens": 0, "cache_write_input_tokens": 0}, metadata={})
                if role == "adjudicator":
                    write_json(workspace / "review_adjudication.json", {
                        "schema_version": "factory-review-adjudication-1", "project_id": "p", "round": 3,
                        "action": "pass", "finding_decisions": [], "repair_notes": [], "drop_reason": None, "excluded_task_ids": []})
                return {"call_id": cid, "status": "completed"}

        def batch(jobs, **kw):
            for key, role in (("constructor", "constructor"), ("reviewer", "material_reviewer")):
                kw[key].run(workspace=root, prompt="fixture", role=role)
            if fail:
                return {"jobs": [{"status": "failed_needs_attribution"}]}
            reviewer = kw["batch_root"] / "j/reviewer"
            for name, data in (("review.json", {"findings": []}), ("request.json", {}), ("structural_check.json", {}),
                               ("output/package.json", {"tasks": [{"task_id": "t"}]})):
                write_json(reviewer / name, data)
            return {"jobs": [{"status": "pass_with_pending_runtime"}]}

        with patch.object(f, "verify_execution", return_value=(manifest, cases)), patch.object(f, "run_batch", side_effect=batch):
            result = f.run_arm(root, "a", "old", runner_factory=lambda role, led, arm: Runner(led, arm))
            with self.assertRaises(ProtocolError):
                f.run_arm(root, "a", "old", runner_factory=lambda *a: self.fail("no retry"))
        return result

    def test_real_orchestration_three_fake_calls_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.exercise_arm(tmp)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["cost"]["calls"], 3)
            self.assertEqual(result["cost"]["usage"]["total_input_tokens"], 3)

    def test_failed_batch_never_calls_adjudicator(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.exercise_arm(tmp, fail=True)
            self.assertEqual(result["status"], "failed_needs_attribution")
            self.assertEqual(result["cost"]["calls"], 2)


if __name__ == "__main__":
    unittest.main()
