"""Prospective controller tests; never launches a model or fetches sources."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import shutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench import efficiency_prospective as p
from mrhbench.io import ProtocolError, read_json, write_json
import test_factory as fixtures


class ProspectiveTests(unittest.TestCase):
    def test_identity_prompt_does_not_normalize_invalid_review_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seen = []
            class Invalid:
                def run(self, *, workspace, prompt, role):
                    seen.append(prompt)
                    write_json(workspace / "review_adjudication.json", {
                        "schema_version": "factory-review-adjudication-1", "project_id": "p/p__EXP", "round": 2,
                        "action": "pass", "finding_decisions": [], "repair_notes": [], "drop_reason": None, "excluded_task_ids": []})
                    return {"call_id": 1, "status": "completed"}
            factory = p.ProspectiveFactory(root, templates=ROOT / "prompts", runner_factory=lambda role: Invalid(), budget=p.CallBudget(1))
            factory.init({"factory_prompts": "factory_v4", "unit_split": True})
            state = {"project_id": "p", "unit": "EXP", "stages": {}, "flags": []}
            reviewer = factory.wdir(state) / "construct/p__EXP/reviewer"
            for name, value in (("request.json", {"paper_id": "p", "job_id": "p__EXP"}),
                                ("review.json", {"findings": []}), ("structural_check.json", {}),
                                ("output/package.json", {"tasks": [{"task_id": "t"}]})):
                write_json(reviewer / name, value)
            with self.assertRaisesRegex(ProtocolError, "identity/round/action"):
                factory._review_adjudication(state, "repair_adjudication", "construct", 2)
            self.assertIn('exactly equal "p", taken from request.json paper_id', seen[0])
            self.assertIn("Do not concatenate job_id", seen[0])
            self.assertEqual(read_json(factory.wdir(state) / "repair_adjudication/review_adjudication.json")["project_id"], "p/p__EXP")
            source_ws = root / "source_identity"
            write_json(source_ws / "candidate.json", {"project_id": "p"})
            factory.runner("adjudicator").run(workspace=source_ws, prompt="source", role="adjudicator")
            self.assertIn('exactly equal "p", taken from candidate.json project_id', seen[-1])

    def test_known_identity_diagnostic_is_narrow_and_preserves_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arm = root / "arms/c/incremental"
            ws = arm / "adjudicator"
            job = root / "job.json"
            write_json(job, {"paper_id": "p", "job_id": "j"})
            case = {"case_id": "c", "job_path": str(job)}
            ledger_path = root / "ledger.json"
            attempts = [{"id": i + 1, "role": role, "status": "completed", "metadata": {},
                         "artifact_directory": str(arm / "native_calls" / role)}
                        for i, role in enumerate(("constructor", "material_reviewer", "adjudicator"))]
            write_json(ledger_path, {"attempts": attempts})
            write_json(root / "execution/manifest.json", {"ledger_path": str(ledger_path), "rounds": {"c": 2},
                                                          "allowed_actions": ["pass", "pass_partial", "drop"]})
            schema = root / "execution/snapshot/prompts/factory_v4/review_adjudication.schema.json"
            schema.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / "prompts/factory_v4/review_adjudication.schema.json", schema)
            result = {"status": "failed_needs_attribution", "error": {"type": "ProtocolError", "message": "Adjudication identity/round/action invalid"},
                      "ledger_attempts": attempts}
            write_json(arm / "result.json", result)
            out = {"schema_version": "factory-review-adjudication-1", "project_id": "p/j", "round": 2, "action": "pass",
                   "finding_decisions": [], "repair_notes": [], "drop_reason": None, "excluded_task_ids": []}
            for name, value in (("request.json", {"paper_id": "p", "job_id": "j"}), ("review_adjudication.json", out),
                                ("review.json", {"findings": []}), ("output/package.json", {"tasks": [{"task_id": "t"}]})):
                write_json(ws / name, value)
            original_result = (arm / "result.json").read_bytes()
            self.assertEqual(len(p.known_identity_failure(root, case, "incremental", result)), 4)
            self.assertEqual(original_result, (arm / "result.json").read_bytes())
            self.assertEqual(read_json(ws / "review_adjudication.json")["project_id"], "p/j")
            for bad in ({**out, "project_id": "wrong"}, {**out, "round": 3}, {**out, "excluded_task_ids": ["t"]}):
                write_json(ws / "review_adjudication.json", bad)
                with self.assertRaises(ProtocolError):
                    p.known_identity_failure(root, case, "incremental", result)
            write_json(ws / "review_adjudication.json", out)
            for status in ("reserved", "failed", "timeout"):
                changed = [dict(a) for a in attempts]
                changed[-1]["status"] = status
                write_json(ledger_path, {"attempts": changed})
                with self.assertRaises(ProtocolError):
                    p.known_identity_failure(root, case, "incremental", {**result, "ledger_attempts": changed})

    def test_source_unit_lifecycle_repair_eight_fake_sessions(self):
        """Real Factory stages, schema gates, publication, incremental repair, costs."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper_id = "iclr2025-qgsXsqahMq"
            prospective = root / "prospective"
            factory_root = prospective / "factory"
            templates = root / "execution/snapshot/prompts"
            shutil.copytree(ROOT / "prompts", templates)
            ledger_path = root / "ledger.json"
            write_json(ledger_path, {"used_attempts": 605, "authorized_maximum": 1668,
                                    "attempts": [{"id": i, "status": "completed"} for i in range(1, 606)]})
            script = fixtures.Script(types=["WRITE_EVIDENCE", "EXP"], round1="repair", round2="pass")
            observed_ledgers = []

            def runner_factory(role, ledger, out):
                observed_ledgers.append(ledger)
                class Runner:
                    def run(self, *, workspace, prompt, role):
                        cid = ledger.reserve(role=role, model="claude-opus-5-5", effort="medium",
                                             request_hash="0" * 64, artifact_directory=str(out / "native_calls" / str(len(script.calls))))
                        try:
                            fixtures.FakeRunner(script, role).run(workspace=workspace, prompt=prompt, role=role)
                        except Exception:
                            ledger.finish(cid, status="failed", wall_seconds=1, usage=None, metadata={})
                            raise
                        ledger.finish(cid, status="completed", wall_seconds=1,
                                      usage={"input_tokens": 2, "cached_input_tokens": 3, "cache_write_input_tokens": 4, "output_tokens": 5}, metadata={})
                        return {"call_id": cid, "status": "completed"}
                return Runner()

            class Runtime(fixtures.FakeRuntime):
                verified = []
                compiled = []
                def verify_runtime(self, out, package, dest, **kw):
                    self.verified.append(out)
                    return super().verify_runtime(out, package, dest, **kw)
                def compile_tasks(self, out, package, record, dest, **kw):
                    self.compiled.append(out)
                    return super().compile_tasks(out, package, record, dest, **kw)
            runtime = Runtime()
            sources = fixtures.FakeSourcesV4()
            factory = p.ProspectiveFactory(factory_root, templates=templates, runner_factory=lambda role: None)
            factory.init({"factory_prompts": "factory_v4", "unit_split": True, "exp_second_repair": False,
                          "continue_truncated": False, "structural_gate_to_repair": False})
            candidate = {"project_id": paper_id, "title": "fixture"}
            (factory_root / "pool").mkdir()
            (factory_root / "pool/candidates.jsonl").write_text(__import__("json").dumps(candidate) + "\n", encoding="utf8")
            paper = factory.paper_dir(paper_id)
            sources.fetch_paper_sources(candidate, paper, conference_end="2025-04-30")
            state = factory.state(paper_id)
            factory._record(state, "fetch", "completed")
            base = {"ledger_path": str(ledger_path)}
            cases = {"model": "claude-opus-5-5", "effort": "medium"}
            manifest = {"paper": paper_id}
            with patch.object(p, "verify_prospective", return_value=(base, cases, manifest)):
                source = p.run_phase(root, "source", runner_factory=runner_factory, sources=sources, runtime=runtime)
                self.assertEqual(source["status"], "completed", source)
                self.assertEqual(source["costs"]["call_count"], 2)
                unit = p.run_phase(root, "unit", runner_factory=runner_factory, sources=sources, runtime=runtime)
                self.assertEqual(unit["status"], "completed", unit)
                self.assertEqual(unit["costs"]["call_count"], 6)
                with self.assertRaises(FileExistsError):
                    p.run_phase(root, "source", runner_factory=runner_factory, sources=sources, runtime=runtime)
            self.assertEqual(unit["selected_unit"], "EXP")
            self.assertEqual(set(unit["unit_state"]["stages"]), {"construct", "review_adjudication", "repair", "repair_adjudication", "runtime", "compile"})
            self.assertEqual(script.calls, ["source_auditor", "adjudicator", "constructor", "material_reviewer", "adjudicator", "constructor", "material_reviewer", "adjudicator"])
            self.assertFalse((paper / "units/WRITE_EVIDENCE").exists())
            self.assertTrue((paper / "units/EXP/repair" / (paper_id + "__EXP") / "reviewer/repair_context/json_changes.json").is_file())
            self.assertTrue(all("repair" in path.parts and "repair2" not in path.parts for path in runtime.verified + runtime.compiled))
            self.assertEqual(len(runtime.verified), 1)
            self.assertEqual(len(runtime.compiled), 1)
            self.assertEqual(read_json(ledger_path)["used_attempts"], 613)
            with self.assertRaises(ProtocolError):
                observed_ledgers[-1].reserve(role="constructor", model="claude-opus-5-5", effort="medium",
                                             request_hash="0" * 64, artifact_directory=str(prospective / "native_calls/ninth"))

    def test_fixed_selection_no_unadjudicated_fallback(self):
        self.assertEqual(p.choose_unit({"requested_task_types": ["LIT", "EXP", "WRITE_CONTENT"]},
                                       {"requested_task_types": ["WRITE_CONTENT", "EXP"]}), "EXP")
        self.assertIsNone(p.choose_unit({"requested_task_types": ["LIT"]}, {"requested_task_types": []}))
        with self.assertRaises(ProtocolError):
            p.choose_unit({"requested_task_types": ["LIT"]}, {"requested_task_types": ["EXP"]})

    def gates(self, root):
        cases = {"cases": [{"case_id": c, "order": ["old", "incremental"]} for c in ("a", "b")]}
        for case in cases["cases"]:
            hashes = {}
            for arm in case["order"]:
                path = root / "arms" / case["case_id"] / arm / "result.json"
                write_json(path, {"status": "completed"})
                hashes[arm] = p.file_hash(path)
            write_json(root / "audits" / (case["case_id"] + ".json"), {
                "case_id": case["case_id"], "result_hashes": hashes, "allow_prospective": True,
                "reviewer": "offline fixture", "review_seconds": 20, "findings": ["Fixture only."]})
        return cases

    def test_both_gates_explicit_and_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = self.gates(root)
            self.assertEqual(len(p.check_gates(root, cases)), 2)
            gate = root / "audits/b.json"
            obj = read_json(gate)
            obj.pop("allow_prospective")
            write_json(gate, obj)
            with self.assertRaises(ProtocolError):
                p.check_gates(root, cases)

    def test_freeze_copies_only_sources_and_selected_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = self.gates(root)
            paper_id = "iclr2025-qgsXsqahMq"
            origin = root / "old/papers" / paper_id
            write_json(origin / "sources/manifest.json", {"sources": []})
            write_json(origin / "source_audit/forbidden.json", {"old": True})
            write_json(root / "old/factory.json", {"factory_prompts": "factory_v4", "unit_split": True})
            (root / "old/pool").mkdir()
            (root / "old/pool/candidates.jsonl").write_text('{"project_id":"' + paper_id + '","title":"fixture"}\n', encoding="utf8")
            cases["prospective"] = {"paper": paper_id, "max_calls": 8, "source_dir": str(origin),
                                    "source_manifest_sha256": p.file_hash(origin / "sources/manifest.json")}
            ledger = root / "ledger.json"
            write_json(ledger, {"used_attempts": 593, "authorized_maximum": 1668,
                               "attempts": [{"id": i, "status": "completed"} for i in range(1, 594)]})
            write_json(root / "execution/manifest.json", {"fixture": True})
            base = {"ledger_path": str(ledger), "benchmark": str(ROOT)}
            old = ledger.read_bytes()
            with patch.object(p, "verify_execution", return_value=(base, cases)):
                manifest = p.freeze_prospective(root)
                p.verify_prospective(root)
                self.assertFalse((root / "prospective/factory/papers" / paper_id / "source_audit").exists())
                self.assertEqual(old, ledger.read_bytes())
                self.assertFalse(read_json(root / "prospective/factory/factory.json")["exp_second_repair"])
                (origin / "sources/new.txt").write_bytes(b"unexpected")
                with self.assertRaises(ProtocolError):
                    p.verify_prospective(root)
            self.assertEqual(manifest["maximum_calls"], 8)

    def test_only_one_repair_and_no_second_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            factory = p.ProspectiveFactory(Path(tmp), templates=ROOT / "prompts", runner_factory=lambda role: None)
            self.assertEqual(factory.max_repair_rounds({"unit": "EXP"}), 1)
            with self.assertRaises(ProtocolError):
                factory._batch({}, Path(tmp))

    def test_pilot_phase_rejected_before_loading_or_calls(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(p, "verify_prospective", side_effect=AssertionError("must not load")):
            with self.assertRaises(ProtocolError):
                p.run_phase(Path(tmp), "pilot")


if __name__ == "__main__":
    unittest.main()
