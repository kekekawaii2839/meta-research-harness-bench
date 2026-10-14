"""Offline smoke for factory_v5.py: zero real model calls, fake native roles, fake docker runner.

Drives one WRITE_CONTENT construction unit of a synthetic paper through
construct -> review_adjudication(repair) -> repair (incremental) -> repair_adjudication(pass)
-> repair2/repair2_adjudication (skipped) -> runtime (real verify_runtime, fake docker) -> compile
(real compile_identity_release). The real ledger is never touched; the real ClaudeNativeRunner never runs.
"""
from argparse import Namespace
from pathlib import Path
import json
import shutil
import sys
import unittest
import uuid

HERE = Path(__file__).resolve().parent
DRIVER = HERE.parent
BENCH = Path(r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
for p in (str(DRIVER), str(BENCH), str(BENCH / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import factory_v5 as fv5  # noqa: E402
from mrhbench.io import read_json, write_json, file_hash, digest  # noqa: E402
from mrhbench.factory import DEFAULT_CONFIG, TASK_TYPES  # noqa: E402
from mrhbench import factory_runtime as fr  # noqa: E402
from mrhbench.material_decision_guidance import DECISION_GUIDANCE  # noqa: E402
from mrhbench.evidence_read_batching import EVIDENCE_READ_BATCHING_GUIDANCE  # noqa: E402
from test_factory_runtime import FakeDocker  # noqa: E402

PID = "iclr2025-Synth9QpX1"
TITLE = "Synthetic Gradient Averaging Study"
RESOURCES = dict(cpus=1, memory_mb=512, disk_mb=128, pids_limit=32, wall_seconds=600)
STAGES = ("construct", "review_adjudication", "repair", "repair_adjudication", "repair2", "repair2_adjudication",
          "runtime", "compile", "units", "background", "repo_files", "external_data")
PRIVATE_TEXT = "Private reference answer: the averaged estimator keeps variance below the single-gradient baseline."


class FakeRuntime:
    """Real factory_runtime.verify_runtime with an in-process fake docker runner (no image is built)."""

    def __init__(self):
        self.docker = FakeDocker()

    def verify_runtime(self, out, package, dest, *, package_slug):
        return fr.verify_runtime(out, package, dest, package_slug=package_slug, docker=self.docker)

    def __getattr__(self, name):
        return getattr(fr, name)


class Recorder:
    def __init__(self, test):
        self.test, self.calls, self.flags = test, [], set()
        # Which (role, round) should carry the read-batching advice: incremental rounds only by default.
        self.expect_batching = lambda role, rnd: rnd > 1
        self.actions = {1: "repair", 2: "pass", 3: "pass"}


def fake_native_factory(rec):
    """role -> runner; writes valid role outputs, asserts every v5 wrapper published its inputs."""
    test = rec.test

    class Native:
        def __init__(self, role):
            self.role = role

        def run(self, *, workspace, prompt, role, **kwargs):
            ws = Path(workspace)
            test.assertEqual(role, self.role)
            test.assertFalse(kwargs, "unexpected kwargs to native runner: %r" % kwargs)
            rec.calls.append({"role": role, "workspace": str(ws)})
            # Wrapper publication checks (all material roles run inside the unit context).
            test.assertTrue((ws / "paged_source_navigation/catalog.json").is_file(), ws)
            test.assertTrue((ws / "identity_assignment.json").is_file(), ws)
            test.assertEqual(DECISION_GUIDANCE in prompt, role != "constructor")
            assignment = read_json(ws / "identity_assignment.json")["tasks"]
            if role == "constructor":
                self.constructor(ws, assignment)
            else:
                contract = read_json(ws / "quality_contract.json")
                rnd = contract["round"]
                test.assertEqual(EVIDENCE_READ_BATCHING_GUIDANCE in prompt, rec.expect_batching(role, rnd), (role, rnd))
                self.coverage(ws, contract, issue=(rnd == 1))
                if role == "material_reviewer":
                    self.reviewer(ws, rnd)
                else:
                    self.adjudicator(ws, rnd)
            return {"call_id": "fake-%d" % len(rec.calls), "status": "completed", "audit_directory": None}

        # ------------------------------------------------------------ roles
        def constructor(self, ws, assignment):
            request = read_json(ws / "request.json")
            ttype = request["requested_task_types"][0]
            test.assertEqual(request["requested_task_types"], [ttype])
            test.assertTrue((ws / "quality_policy.md").is_file())
            out = ws / "output"
            if "truncate_once" in rec.flags:
                rec.flags.discard("truncate_once")
                from mrhbench.io import ProviderRateLimit
                out.mkdir(exist_ok=True)
                (out / "partial_notes.md").write_text("half-written brief", encoding="utf8")
                raise ProviderRateLimit("Provider rate/session limit (HTTP 429)")
            repair = (ws / "previous_candidate" / "package.json").is_file()
            if repair:
                # Incremental repair: controller seeded output/ with the previous candidate bytes.
                test.assertTrue((out / "package.json").is_file(), "incremental seed missing")
                (out / "assets/brief.md").write_text(
                    "Write a concise method paragraph describing how two normalised gradients are averaged, "
                    "and state the assumption on step size explicitly.\n", encoding="utf8")
                package = read_json(out / "package.json")
                package["facts"][0]["statement"] = "The estimator averages two normalised gradients."
                for a in package["tasks"][0]["assets"]:
                    a["sha256"] = "CONTROLLER_FILL"
                package["tasks"][0]["input_contract"]["files"][0]["sha256"] = "CONTROLLER_FILL"
                write_json(out / "package.json", package)
                return
            paper = next(s for s in request["sources"] if s["role"] == "paper_html")
            (out / "environment/image").mkdir(parents=True, exist_ok=True)
            (out / "environment/image/Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf8")
            (out / "environment/smoke.py").write_text("print('ok')\n", encoding="utf8")
            (out / "assets").mkdir(exist_ok=True)
            (out / "private").mkdir(exist_ok=True)
            brief = "Write a concise method paragraph for the averaged estimator.\n"
            if "leak_asset_once" in rec.flags:
                rec.flags.discard("leak_asset_once")
                brief = "Write the method paragraph of " + TITLE + ".\n"
            (out / "assets/brief.md").write_text(brief, encoding="utf8")
            (out / "private/reference.md").write_text(PRIVATE_TEXT + "\n", encoding="utf8")
            tid = assignment[0]["task_id"]
            public = {"path": "assets/brief.md", "sha256": "CONTROLLER_FILL", "visibility": "public"}
            write_json(out / "package.json", {
                "schema_version": "material-package-1", "status": "candidate", "paper_id": request["paper_id"],
                "facts": [
                    {"fact_id": "F1", "kind": "source_fact", "statement": "The estimator averages two normalised gradients.",
                     "allowed_stages": [ttype], "discloses_target_contribution": False,
                     "evidence": [{"source_id": paper["source_id"], "source_sha256": paper["sha256"], "locator": "Sec 2"}]},
                    {"fact_id": "F2", "kind": "source_result", "statement": PRIVATE_TEXT, "allowed_stages": [],
                     "discloses_target_contribution": True,
                     "evidence": [{"source_id": paper["source_id"], "source_sha256": paper["sha256"], "locator": "Table 1"}]}],
                "coverage": [{"task_type": t, "status": "candidate" if t == ttype else "deferred",
                              "reason": "synthetic fixture"} for t in TASK_TYPES],
                "tasks": [{"task_id": tid, "task_type": ttype, "paper_id": request["paper_id"],
                           "split": "development", "input_fact_ids": ["F1"], "private_fact_ids": ["F2"],
                           "private_source_ids": [paper["source_id"]],
                           "assets": [dict(public), {"path": "private/reference.md", "sha256": "CONTROLLER_FILL",
                                                     "visibility": "private"}],
                           "input_contract": {"description": "Brief and fact card", "files": [dict(public)]},
                           "output_contract": {"description": "One method paragraph with source mapping"},
                           "verification_plan": {"pending": True}}],
                "environment": {"gpu": False, "network": "none", "runtime_verified": False, "dependencies": [],
                                "scientific_rationale": "Text-only writing task", "resources": dict(RESOURCES),
                                "dockerfile": "environment/image/Dockerfile", "smoke_test": "environment/smoke.py"}})

        def coverage(self, ws, contract, issue):
            ids = sorted(contract["public_inventory"])
            checks = {}
            for key in contract["checks"]:
                whole = key in ("identity", "author_scale", "target_implementation")
                checks[key] = {"status": "issue" if (issue and key == "core_science") else "clear",
                               "rationale": "Synthetic only",
                               "evidence": [{"surface_id": ids[0], "locator": "fixture", "observation": "Synthetic"}],
                               **({"scope": "entire_bound_public_inventory"} if whole else
                                  {"scope": "selected_surfaces", "inspected_surface_ids": ids})}
            write_json(ws / "quality_coverage.json", {"contract_sha256": contract["contract_sha256"],
                                                      "policy_sha256": contract["policy_sha256"], "checks": checks})

        def reviewer(self, ws, rnd):
            pid = read_json(ws / "request.json")["paper_id"]
            if rnd == 1:
                review = {"decision": "revise", "findings": [{"severity": "major", "issue": "Brief omits step-size assumption"}]}
            else:
                test.assertTrue((ws / "repair_context").is_dir(), "incremental review context missing")
                review = {"decision": "pass_with_pending_runtime", "findings": []}
            write_json(ws / "review.json", {"schema_version": "material-review-1", "paper_id": pid, **review})

        def adjudicator(self, ws, rnd):
            pid = read_json(ws / "request.json")["paper_id"]
            allowed = read_json(ws / "round.json")["allowed_actions"]
            schema = read_json(ws / "review_adjudication.schema.json")
            rule = schema["properties"]["finding_decisions"]["items"]["properties"]["policy_rules"]["items"]["enum"][0]
            findings = read_json(ws / "review.json").get("findings", [])
            action = rec.actions[rnd]
            test.assertIn(action, allowed)
            write_json(ws / "review_adjudication.json", {
                "schema_version": "factory-review-adjudication-1", "project_id": pid, "round": rnd,
                "finding_decisions": [{"finding_index": i, "decision": "accept", "severity": "major",
                                       "rationale": "Real omission", "policy_rules": [rule],
                                       "repair_note": "State the step-size assumption"} for i in range(len(findings))],
                "action": action, "repair_notes": ["State the step-size assumption in the brief."] if action == "repair" else [],
                "drop_reason": None, "excluded_task_ids": []})

    return lambda role: Native(role)


def forbidden_native(root):
    def make(role):
        raise AssertionError("real native runner factory must not be used in the smoke")
    return make


class FactoryV5Smoke(unittest.TestCase):
    def setUp(self):
        base = HERE / "tmp"
        base.mkdir(exist_ok=True)
        self.tmp = base / uuid.uuid4().hex[:10]
        self.tmp.mkdir()

    def tearDown(self):
        # A real paid run may be updating the shared ledger concurrently; only assert this smoke never wrote to it.
        text = fv5.LEDGER.read_text(encoding="utf8")
        for needle in (str(self.tmp), self.tmp.as_posix(), str(self.tmp).replace("\\", "\\\\")):
            self.assertNotIn(needle, text, "smoke leaked into the real ledger")

    def source_root(self):
        src = self.tmp / "src"
        (src / "pool").mkdir(parents=True)
        (src / "triage").mkdir()
        (src / "triage" / "README.txt").write_text("synthetic", encoding="utf8")
        row = {"project_id": PID, "title": TITLE, "abstract": "Synthetic abstract.", "topic": "Optimization",
               "topic_group": "Optimization", "repo": "https://github.com/o/r"}
        (src / "pool" / "candidates.jsonl").write_text(json.dumps(row) + "\n", encoding="utf8")
        write_json(src / "selection.json", {"schema_version": "factory-selection-1", "papers": [
            {"rank": 1, "project_id": PID, "title": TITLE}]})
        (src / "selection.md").write_text("# selection\n", encoding="utf8")
        write_json(src / "selection_approval.json", {"schema_version": "factory-selection-approval-1",
                                                     "selection_sha256": file_hash(src / "selection.json"),
                                                     "approved_by": "synthetic", "approved_at": "2026-09-27T00:00:00Z"})
        write_json(src / "factory.json", {**DEFAULT_CONFIG, "created_at": "x", "policy_sha256": "x", "prompt_hashes": {},
                                          "version_note": "src", "factory_prompts": "factory_v4", "unit_split": True,
                                          "per_task_resources": True, "structural_gate_to_repair": True,
                                          "continue_truncated": True, "exp_second_repair": True})
        pdir = src / "papers" / PID
        files = pdir / "sources" / "files"
        (files / "code").mkdir(parents=True)
        (files / "paper.html").write_text("<html><body><h2>2 Method</h2><p>We average two normalised gradients."
                                          "</p><p>Table 1 reports variance.</p></body></html>", encoding="utf8")
        (files / "code" / "m.py").write_text("def avg(a, b):\n    return (a + b) / 2\n", encoding="utf8")
        manifest = {"schema_version": "factory-sources-1", "project_id": PID,
                    "arxiv": {"status": "fetched", "earliest_known_public_version": {"version": "v1", "date": "2024-10-01"}},
                    "repo": {"status": "fetched", "url": "https://github.com/o/r", "commit": "a" * 40},
                    "sources": [
                        {"source_id": "paper_html", "url": "https://arxiv.org/html/0000.0000v1", "version": "arXiv:0000.0000v1",
                         "sha256": file_hash(files / "paper.html"), "role": "paper_html", "local_path": "sources/files/paper.html"},
                        {"source_id": "code_0001", "url": "https://github.com/o/r/blob/m.py", "version": "git:" + "a" * 40,
                         "sha256": file_hash(files / "code" / "m.py"), "role": "code_file", "local_path": "sources/files/code/m.py"}]}
        write_json(pdir / "sources" / "manifest.json", manifest)
        write_json(pdir / "state.json", {"schema_version": "factory-paper-state-1", "project_id": PID, "title": TITLE,
                                         "stages": {"fetch": {"status": "completed", "artifacts": {}, "calls": [],
                                                              "finished_at": "x", "notes": []}}, "flags": []})
        return src

    def init_root(self, unit="WRITE_CONTENT"):
        src = self.source_root()
        root = self.tmp / "v5root"
        original = fv5.native_factory
        fv5.native_factory = forbidden_native
        try:
            out = fv5.cmd_init(Namespace(root=str(root), from_root=str(src), carry_fetch=[PID]))
        finally:
            fv5.native_factory = original
        self.assertEqual(out["approved_papers"], 1)
        # Synthetic paper-level model outputs (source_audit/adjudication would be paid model stages).
        pdir = root / "papers" / PID
        write_json(pdir / "source_audit" / "source_audit.json", {"project_id": PID, "ambiguities": []})
        write_json(pdir / "adjudication" / "adjudication.json", {
            "schema_version": "factory-adjudication-1", "project_id": PID, "decision": "construct", "drop_reason": None,
            "ambiguity_decisions": [{"ambiguity_id": "A1", "decision": "adopt_resolution", "statement": "Use Eq. 5."}],
            "requested_task_types": [unit],
            "unrequested_reasons": {t: "fixture" for t in TASK_TYPES if t != unit},
            "scope_request": "Build one %s task." % unit, "task_scopes": {unit: "One synthetic task."},
            "environment_candidate": {"docker_base": "python:3.12-slim", "dependencies": [], "gpu": False, "network": "none",
                                      "scientific_rationale": "text only", **RESOURCES},
            "background_requests": [], "rights_review": "MIT code", "withheld_from_solver": ["author code"],
            "repo_file_requests": [], "external_data_requests": []})
        state = read_json(pdir / "state.json")
        for stage in ("source_audit", "adjudication"):
            state["stages"][stage] = {"status": "completed", "artifacts": {}, "calls": [], "finished_at": "x", "notes": []}
        write_json(pdir / "state.json", state)
        return root

    def test_write_content_unit_full_chain(self):
        root = self.init_root()
        rec = Recorder(self)
        f = fv5.open_factory(root, max_calls=10, native=fake_native_factory(rec))
        f.runtime = FakeRuntime()
        result = f.run_papers([PID], stages=STAGES, units=["WRITE_CONTENT"])
        unit = read_json(root / "papers" / PID / "units" / "WRITE_CONTENT" / "state.json")
        statuses = {k: v["status"] for k, v in unit["stages"].items()}
        msg = json.dumps({"result": result, "unit": unit["stages"]}, indent=1)
        self.assertEqual(statuses, {"construct": "completed", "review_adjudication": "completed", "repair": "completed",
                                    "repair_adjudication": "completed", "repair2": "skipped",
                                    "repair2_adjudication": "skipped", "runtime": "completed", "compile": "completed"}, msg)
        roles = [c["role"] for c in rec.calls]
        self.assertEqual(roles, ["constructor", "material_reviewer", "adjudicator"] * 2)
        self.assertEqual(f.budget.used, 6)
        wdir = root / "papers" / PID / "units" / "WRITE_CONTENT"
        # Incremental repair round actually used.
        receipt = read_json(wdir / "repair" / (PID + "__WRITE_CONTENT") / "receipt.json")
        self.assertTrue(receipt["incremental_repair"])
        self.assertIn("incremental_seed", receipt)
        self.assertFalse(read_json(wdir / "construct" / (PID + "__WRITE_CONTENT") / "receipt.json")["incremental_repair"])
        # Opaque id stable across rounds, compiled release carries only the opaque id.
        mapping = read_json(wdir / "private_identity" / "map.json")
        opaque = list(mapping["task_ids"].values())[0]
        pkg = read_json(f.final_output(unit) / "package.json")
        self.assertEqual(pkg["tasks"][0]["task_id"], opaque)
        record = read_json(wdir / "release" / "identity_release_record.json")
        self.assertEqual([r["task_id"] for r in record["releases"]], [opaque])
        self.assertEqual(record["releases"][0]["scan"]["status"], "no_known_identity_match")
        released = (wdir / "release" / "review_releases" / opaque / "task.json").read_text(encoding="utf8")
        for needle in (PID, "Synth9QpX1", TITLE, PRIVATE_TEXT):
            self.assertNotIn(needle, released)
        # Every material role workspace got the wrapper receipts.
        for rel in ("construct/%s__WRITE_CONTENT/constructor" % PID, "construct/%s__WRITE_CONTENT/reviewer" % PID,
                    "review_adjudication", "repair/%s__WRITE_CONTENT/constructor" % PID,
                    "repair/%s__WRITE_CONTENT/reviewer" % PID, "repair_adjudication"):
            self.assertTrue((wdir / rel / "identity_controller_validation.json").is_file(), rel)
            self.assertTrue((wdir / rel / "paged_navigation_receipt.json").is_file(), rel)
        for rel in ("construct/%s__WRITE_CONTENT/reviewer" % PID, "review_adjudication",
                    "repair/%s__WRITE_CONTENT/reviewer" % PID, "repair_adjudication"):
            self.assertTrue((wdir / rel / "quality_controller_validation.json").is_file(), rel)
        # Runtime record is the real verify_runtime output bound to the final package.
        rt = read_json(wdir / "runtime" / "runtime_record.json")
        self.assertEqual(rt["package_json_sha256"], file_hash(f.final_output(unit) / "package.json"))
        self.assertEqual(rt["status"], "passed")
        # No docker image build via real CLI: every docker call went through the fake.
        self.assertTrue(any(c[1] == "build" for c in f.runtime.docker.calls))

    def test_identity_scan_failure_routes_to_repair(self):
        """Construction leaking the paper title into a public fact is routed to repair without a model adjudication."""
        root = self.init_root()
        rec = Recorder(self)
        base = fake_native_factory(rec)

        def leaky(role):
            inner = base(role)
            orig = inner.constructor

            def constructor(ws, assignment):
                orig(ws, assignment)
                if not (ws / "previous_candidate").is_dir():
                    p = read_json(ws / "output/package.json")
                    p["facts"][0]["statement"] = "From " + TITLE + ": the estimator averages two gradients."
                    write_json(ws / "output/package.json", p)
            inner.constructor = constructor
            return inner
        f = fv5.open_factory(root, max_calls=10, native=leaky)
        f.runtime = FakeRuntime()
        f.run_papers([PID], stages=STAGES, units=["WRITE_CONTENT"])
        unit = read_json(root / "papers" / PID / "units" / "WRITE_CONTENT" / "state.json")
        statuses = {k: v["status"] for k, v in unit["stages"].items()}
        self.assertEqual(statuses.get("construct"), "completed", json.dumps(unit["stages"], indent=1))
        self.assertEqual(read_json(root / "papers" / PID / "units/WRITE_CONTENT/review_adjudication/review_adjudication.json")["author"],
                         "controller_identity_scan")
        self.assertEqual(statuses.get("compile"), "completed", json.dumps(unit["stages"], indent=1))
        # construct constructor, (reviewer refused before call), repair ctor+reviewer, repair adjudicator
        self.assertEqual([c["role"] for c in rec.calls], ["constructor", "constructor", "material_reviewer", "adjudicator"])

    def test_identity_leak_in_public_asset_bytes_routes_to_repair(self):
        """Title leaked into a public text asset (not a fact) must also route to the single repair round."""
        root = self.init_root()
        rec = Recorder(self)
        rec.flags.add("leak_asset_once")
        f = fv5.open_factory(root, max_calls=10, native=fake_native_factory(rec))
        f.runtime = FakeRuntime()
        f.run_papers([PID], stages=STAGES, units=["WRITE_CONTENT"])
        unit = read_json(root / "papers" / PID / "units" / "WRITE_CONTENT" / "state.json")
        statuses = {k: v["status"] for k, v in unit["stages"].items()}
        self.assertEqual(statuses.get("construct"), "completed", json.dumps(unit["stages"], indent=1))
        self.assertEqual(statuses.get("compile"), "completed", json.dumps(unit["stages"], indent=1))

    def test_truncated_constructor_continues_after_explicit_retry(self):
        """429 mid-construction halts; an explicit --retry-platform continues from the partial output."""
        root = self.init_root()
        rec = Recorder(self)
        rec.flags.add("truncate_once")
        f = fv5.open_factory(root, max_calls=10, native=fake_native_factory(rec))
        f.runtime = FakeRuntime()
        f.run_papers([PID], stages=STAGES, units=["WRITE_CONTENT"])
        unit = read_json(root / "papers" / PID / "units" / "WRITE_CONTENT" / "state.json")
        self.assertEqual(unit["stages"]["construct"]["status"], "platform_rate_limited")
        self.assertTrue(f.halted)
        self.assertEqual([c["role"] for c in rec.calls], ["constructor"])
        # The continuation seeds the partial output (incremental) -> round-1 reviewer gets batching advice.
        rec.expect_batching = lambda role, rnd: rnd > 1 or (role == "material_reviewer" and rnd == 1)
        f2 = fv5.open_factory(root, max_calls=10, native=fake_native_factory(rec))
        f2.runtime = FakeRuntime()
        f2.run_papers([PID], stages=STAGES, units=["WRITE_CONTENT"], retry_platform=True)
        unit = read_json(root / "papers" / PID / "units" / "WRITE_CONTENT" / "state.json")
        statuses = {k: v["status"] for k, v in unit["stages"].items()}
        self.assertEqual(statuses.get("compile"), "completed", json.dumps(unit["stages"], indent=1))
        self.assertEqual(len(unit.get("continuations", [])), 1)
        wdir = root / "papers" / PID / "units" / "WRITE_CONTENT"
        self.assertTrue((wdir / "construct.failed-1").is_dir())
        mapping = read_json(wdir / "private_identity" / "map.json")
        self.assertEqual(read_json(f2.final_output(unit) / "package.json")["tasks"][0]["task_id"],
                         list(mapping["task_ids"].values())[0])

    def test_exp_unit_two_incremental_repairs(self):
        """EXP (exp_second_repair): round1 repair -> round2 repair -> round3 pass, both repairs incremental."""
        root = self.init_root("EXP")
        rec = Recorder(self)
        rec.actions = {1: "repair", 2: "repair", 3: "pass"}
        f = fv5.open_factory(root, max_calls=12, native=fake_native_factory(rec))
        f.runtime = FakeRuntime()
        f.run_papers([PID], stages=STAGES, units=["EXP"])
        wdir = root / "papers" / PID / "units" / "EXP"
        unit = read_json(wdir / "state.json")
        statuses = {k: v["status"] for k, v in unit["stages"].items()}
        self.assertEqual(set(statuses.values()), {"completed"}, json.dumps(unit["stages"], indent=1))
        self.assertEqual([c["role"] for c in rec.calls], ["constructor", "material_reviewer", "adjudicator"] * 3)
        self.assertTrue(read_json(wdir / "repair2" / (PID + "__EXP") / "receipt.json")["incremental_repair"])
        self.assertEqual(read_json(wdir / "repair2_adjudication" / "round.json")["allowed_actions"], ["pass", "pass_partial", "drop"])
        self.assertEqual(f.final_output(unit), wdir / "repair2" / (PID + "__EXP") / "constructor" / "output")


if __name__ == "__main__":
    unittest.main(verbosity=2)
