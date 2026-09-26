"""Material factory orchestration with synthetic runners, sources and runtime (no model calls, no network)."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.factory import CallBudget, Factory, TASK_TYPES  # noqa: E402
from mrhbench.io import ProtocolError, file_hash, read_json, write_json  # noqa: E402

RESOURCES = dict(cpus=1, memory_mb=256, disk_mb=128, pids_limit=32, wall_seconds=60)
TOPICS = ["Theory", "Optimization", "Deep Learning"]


class FakeRunner:
    def __init__(self, script, role):
        self.script, self.role = script, role

    def run(self, *, workspace, prompt, role, **kwargs):
        assert role == self.role and prompt.strip()
        self.script.calls.append(role)
        getattr(self.script, role)(Path(workspace))
        return {"call_id": len(self.script.calls), "status": "completed", "audit_directory": None}


class Script:
    """Deterministic stand-ins for each model role; scenario flags steer behaviour."""

    def __init__(self, **flags):
        self.calls, self.flags = [], flags

    def scout(self, ws):
        papers = []
        for i, card in enumerate(sorted((ws / "papers").glob("*.json"))):
            pid = read_json(card)["project_id"]
            mod = lambda p: {"plausible": p, "reason": "fixture"}
            papers.append({"project_id": pid, "modules": {"LIT": mod(i % 2 == 0), "IDEA": mod(False),
                           "EXP": {"plausible": True, "reason": "fixture", "cpu_branch": "synthetic"},
                           "WRITE_CONTENT": mod(i % 3 == 0), "WRITE_EVIDENCE": mod(False)},
                           "cpu_feasibility": "high", "research_type": "method", "rights_flags": [],
                           "priority": 3 if pid.endswith("0") else 2, "notes": ""})
        write_json(ws / "triage.json", {"schema_version": "factory-triage-1", "papers": papers})

    def source_auditor(self, ws):
        pid = read_json(ws / "candidate.json")["project_id"]
        loc = [{"source_id": "paper_html", "locator": "Eq. 1"}]
        module = {"feasible": "yes", "scope_proposal": "fixture", "reason": "fixture", "locations": loc}
        if self.flags.get("auditor_tampers"):
            (ws / "sources" / "paper.html").write_text("tampered", encoding="utf8")
        write_json(ws / "source_audit.json", {
            "schema_version": "factory-source-audit-1", "project_id": pid, "research_type": "method",
            "methods": [{"method_id": "M1", "name": "m", "definition": "d", "fixed_conditions": [], "locations": loc}],
            "ambiguities": [{"ambiguity_id": "A1", "kind": "paper_internal", "description": "two normalisations",
                             "locations": loc, "candidate_resolutions": [{"resolution_id": "R1", "description": "use Eq. 5",
                             "basis": "text", "faithfulness_risk": "low"}], "recommended_resolution_id": "R1",
                             "affects": ["EXP"], "blocking": False}],
            "modules": {t: module for t in TASK_TYPES}, "cpu_branches": [], "excluded_gpu_claims": [], "results_for_write": [],
            "background_candidates": [], "first_disclosure": {"earliest_known_version_date": "2024-10-01", "evidence": "abs", "verified": False},
            "rights": {"paper_license": "CC BY 4.0", "code_license": "MIT", "notes": ""}, "unverified": []})

    def adjudicator(self, ws):
        if (ws / "adjudication.schema.json").exists():
            pid = read_json(ws / "candidate.json")["project_id"]
            decisions = [] if self.flags.get("skip_ambiguity") else [{
                "ambiguity_id": "A1", "decision": "adopt_resolution", "resolution_id": "R1", "statement": "Use Eq. 5.",
                "rationale": "Supported by the text.", "policy_rules": ["B2"], "locations": [{"source_id": "paper_html", "locator": "Eq. 5"}]}]
            write_json(ws / "adjudication.json", {
                "schema_version": "factory-adjudication-1", "project_id": pid, "decision": "construct", "drop_reason": None,
                "ambiguity_decisions": decisions, "requested_task_types": ["EXP"],
                "unrequested_reasons": {t: "fixture" for t in TASK_TYPES if t != "EXP"}, "scope_request": "Build one EXP task.",
                "environment_candidate": {"docker_base": "python:3.12-slim", "dependencies": ["numpy==2.3.3"], "gpu": False,
                                          "network": "none", "scientific_rationale": "small", **RESOURCES},
                "background_requests": [], "rights_review": "MIT code", "withheld_from_solver": ["author code"],
                "checked_against_sources": ["Eq. 5"],
                **({"repo_file_requests": [{"path": "data/x.bin", "why": "dataset"}]}
                   if "repo_file_requests" in (ws / "adjudication.schema.json").read_text(encoding="utf8") else {})})
            return
        rnd = read_json(ws / "round.json")["round"]
        pid = read_json(ws / "request.json")["paper_id"]
        action = self.flags.get("round%d" % rnd, "pass")
        findings = read_json(ws / "review.json").get("findings", [])
        extra = {}
        if "excluded_task_ids" in (ws / "review_adjudication.schema.json").read_text(encoding="utf8"):
            extra["excluded_task_ids"] = self.flags.get("exclude", []) if action == "pass_partial" else []
        write_json(ws / "review_adjudication.json", {**extra,
            "schema_version": "factory-review-adjudication-1", "project_id": pid, "round": rnd,
            "finding_decisions": [{"finding_index": i, "decision": "accept", "severity": "major", "rationale": "real",
                                   "policy_rules": ["C1"], "repair_note": "fix it"} for i in range(len(findings))],
            "action": action, "repair_notes": ["Restate H3 relative to label variance."] if action == "repair" else [],
            "drop_reason": "unfixable" if action == "drop" else None})

    def constructor(self, ws):
        request = read_json(ws / "request.json")
        self.seen_prepopulated = [(p["path"], (ws / "output" / p["path"]).read_bytes()) for p in request.get("prepopulated_output_files", [])]
        bad = self.flags.pop("bad_coverage_once", False)
        n_tasks = 2 if self.flags.get("two_tasks") else 1
        out = ws / "output"
        (out / "environment/image").mkdir(parents=True)
        (out / "environment/image/Dockerfile").write_text("FROM python:3.12-slim\n")
        (out / "environment/smoke.py").write_text("assert True\n")
        write_json(out / "package.json", dict(
            schema_version="material-package-1", status="candidate", paper_id=request["paper_id"],
            facts=[dict(fact_id="f", kind="maintainer_scope", statement="Fixture", allowed_stages=["EXP"])],
            coverage=[dict(task_type=t, status="candidate" if t == "EXP" else "deferred", reason="Fixture") for t in TASK_TYPES][: 4 if bad else 5],
            tasks=[dict(task_id="t" if i == 0 else "t%d" % (i + 1), paper_id=request["paper_id"], split="development", task_type="EXP",
                        input_fact_ids=["f"], input_contract={"description": "Fixture"}, output_contract={"description": "Fixture"},
                        verification_plan={"pending": True}) for i in range(n_tasks)],
            environment=dict(gpu=False, network="none", runtime_verified=False, dependencies=[], scientific_rationale="Fixture",
                             resources=RESOURCES, dockerfile="environment/image/Dockerfile", smoke_test="environment/smoke.py")))

    def material_reviewer(self, ws):
        if self.flags.pop("reviewer_rate_limit_once", False):
            from mrhbench.io import ProviderRateLimit
            raise ProviderRateLimit("Provider rate/session limit (HTTP 429)")
        pid = read_json(ws / "request.json")["paper_id"]
        write_json(ws / "review.json", {"schema_version": "material-review-1", "paper_id": pid, "decision": "revise",
                                        "findings": [{"severity": "major", "issue": "H3 trivially true"}]})


class FakeSources:
    def fetch_paper_sources(self, candidate, pdir, *, conference_end):
        files = pdir / "sources" / "files"
        files.mkdir(parents=True)
        (files / "paper.html").write_text("<html><body><p>Eq. 1 x = y</p></body></html>", encoding="utf8")
        manifest = {"schema_version": "factory-sources-1", "project_id": candidate["project_id"],
                    "arxiv": {"status": "fetched", "earliest_known_public_version": {"version": "v1", "date": "2024-10-01"}},
                    "repo": {"status": "fetched", "url": "https://github.com/o/r", "commit": "a" * 40},
                    "sources": [{"source_id": "paper_html", "url": "https://arxiv.org/html/0000.0000v1", "version": "arXiv:0000.0000v1",
                                 "sha256": file_hash(files / "paper.html"), "bytes": 10, "role": "paper_html",
                                 "local_path": "sources/files/paper.html"}]}
        write_json(pdir / "sources" / "manifest.json", manifest)
        return manifest


    def fetch_repo_files(self, repo_url, commit, reqs, dest, *, base_dir):
        (dest / "files" / "data").mkdir(parents=True)
        (dest / "files" / "data" / "x.bin").write_bytes(b"\x00\x01data")
        m = {"schema_version": "factory-repo-files-1", "repo": repo_url, "commit": commit, "total_bytes": 6,
             "requests": [{"path": "data/x.bin", "status": "fetched", "sha256": file_hash(dest / "files" / "data" / "x.bin"),
                           "bytes": 6, "source_id": "repofile_001"}],
             "sources": [{"source_id": "repofile_001", "url": repo_url + "/blob/x", "version": "git:" + commit,
                          "sha256": file_hash(dest / "files" / "data" / "x.bin"), "role": "repo_data_file",
                          "local_path": "repo_files/files/data/x.bin"}]}
        write_json(dest / "manifest.json", m)
        return m


class FakeRuntime:
    def verify_runtime(self, out, package, dest, *, package_slug):
        record = {"status": "passed", "reasons": []}
        write_json(dest / "runtime_record.json", record)
        return record

    def compile_tasks(self, out, package, record, dest, *, package_slug):
        dest.mkdir(parents=True)
        return [{"task_id": t["task_id"]} for t in package["tasks"]]

    def build_dossier(self, pdir):
        path = pdir / "dossier" / "dossier.json"
        write_json(path, read_json(pdir / "state.json"))
        return path

    def select_for_final_review(self, dossiers, *, seed, first_n, sample_rate):
        return [{"project_id": d["project_id"], "reason": "first_n"} for d in dossiers[:first_n]]


def pilot(state, pdir, budget):
    return {"calls": [], "flags": [], "tasks": []}


class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.templates = base / "prompts"
        shutil.copytree(ROOT / "prompts", self.templates)
        self.root = base / "factory"
        rows = []
        for i in range(6):
            pid = "iclr2025-p%d" % i
            readme = self.root / "pool" / "readmes" / (pid + ".md")
            readme.parent.mkdir(parents=True, exist_ok=True)
            readme.write_text("# repo %d" % i, encoding="utf8")
            rows.append({"project_id": pid, "title": "Paper %d" % i, "abstract": "abstract %d" % i, "topic": "t",
                         "topic_group": TOPICS[i % 3], "decision": "Accept", "repo": {"owner": "o", "name": "r%d" % i, "url": "u"},
                         "readme": {"status": "found", "path": "readmes/%s.md" % pid, "sha256": file_hash(readme)},
                         "license_file": None})
        (self.root / "pool" / "candidates.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf8")

    def tearDown(self):
        self.tmp.cleanup()

    def factory(self, script, budget=100):
        return Factory(self.root, templates=self.templates, runner_factory=lambda role: FakeRunner(script, role),
                       sources=FakeSources(), runtime=FakeRuntime(), budget=CallBudget(budget), pilot=pilot)

    def prepared(self, script, budget=100, v2=False):
        f = self.factory(script, budget)
        extra = {"factory_prompts": "factory_v2", "structural_gate_to_repair": True} if v2 else {}
        f.init({"triage_pool_size": 6, "triage_batch_size": 3, "fulltext_papers": 3, **extra})
        f.run_triage()
        f.select()
        return f

    def test_triage_selection_is_deterministic_and_gated_by_approval(self):
        script = Script()
        f = self.prepared(script)
        self.assertEqual(script.calls, ["scout", "scout"])
        selection = read_json(self.root / "selection.json")
        self.assertEqual(len(selection["papers"]), 3)
        self.assertEqual(len({r["topic_group"] for r in selection["papers"]}), 3)
        self.assertTrue((self.root / "selection.md").exists())
        with self.assertRaisesRegex(ProtocolError, "not approved"):
            f.run_papers([selection["papers"][0]["project_id"]])
        f.approve_selection("user")
        with self.assertRaisesRegex(ProtocolError, "outside the approved"):
            f.run_papers(["iclr2025-unknown"])
        # Same inputs, fresh root: identical selection.
        other = Path(self.tmp.name) / "factory2"
        shutil.copytree(self.root / "pool", other / "pool")
        g = Factory(other, templates=self.templates, runner_factory=lambda role: FakeRunner(Script(), role), budget=CallBudget(10))
        g.init({"triage_pool_size": 6, "triage_batch_size": 3, "fulltext_papers": 3})
        g.run_triage()
        self.assertEqual([r["project_id"] for r in g.select()["papers"]], [r["project_id"] for r in selection["papers"]])

    def test_full_paper_pipeline_with_one_repair_round(self):
        script = Script(round1="repair", round2="pass")
        f = self.prepared(script)
        f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        result = f.run_papers([pid])[0]
        self.assertEqual(result["stages"]["dossier"], "completed")
        self.assertEqual(result["stages"]["repair"], "completed")
        self.assertEqual(script.calls[2:], ["source_auditor", "adjudicator", "constructor", "material_reviewer", "adjudicator",
                                            "constructor", "material_reviewer", "adjudicator"])
        pdir = f.paper_dir(pid)
        job = read_json(pdir / "job.json")
        self.assertIn("[A1] adopt_resolution: Use Eq. 5.", job["scope_request"])
        self.assertIn("Withhold from solver inputs: author code", job["scope_request"])
        self.assertTrue(f.final_output(f.state(pid)).as_posix().endswith("repair/%s/constructor/output" % pid))
        notes = read_json(pdir / "repair" / pid / "constructor" / "repair_request.json")["maintainer_adjudicated_notes"]
        self.assertEqual(notes, ["Restate H3 relative to label variance."])
        self.assertEqual(f.review_queue(), [{"project_id": pid, "reason": "first_n"}])

    def test_pass_skips_repair(self):
        script = Script(round1="pass")
        f = self.prepared(script)
        f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        stages = f.run_papers([pid])[0]["stages"]
        self.assertEqual((stages["repair"], stages["repair_adjudication"], stages["dossier"]), ("skipped", "skipped", "completed"))

    def test_second_round_cannot_repair_again(self):
        f = self.prepared(Script(round1="repair", round2="repair"))
        f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        stages = f.run_papers([pid])[0]["stages"]
        self.assertEqual(stages["repair_adjudication"], "failed_needs_attribution")
        self.assertNotIn("runtime", stages)

    def test_drop_is_terminal(self):
        f = self.prepared(Script(round1="drop"))
        f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        stages = f.run_papers([pid])[0]["stages"]
        self.assertEqual(stages["review_adjudication"], "dropped")
        self.assertNotIn("repair", stages)

    def test_undecided_ambiguity_and_tampering_fail_with_attribution(self):
        for flags, stage in (({"skip_ambiguity": True}, "adjudication"), ({"auditor_tampers": True}, "source_audit")):
            with self.subTest(flags=flags):
                shutil.rmtree(self.root / "papers", ignore_errors=True)
                for name in ("factory.json", "selection.json", "selection_approval.json", "selection.md"):
                    (self.root / name).unlink(missing_ok=True)
                shutil.rmtree(self.root / "triage", ignore_errors=True)
                f = self.prepared(Script(**flags))
                f.approve_selection("user")
                pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
                stages = f.run_papers([pid])[0]["stages"]
                self.assertEqual(stages[stage], "failed_needs_attribution")
                self.assertEqual(list(stages)[-1], stage)

    def test_rate_limited_reviewer_resumes_without_reconstructing(self):
        script = Script(round1="pass", reviewer_rate_limit_once=True)
        f = self.prepared(script)
        f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        stages = f.run_papers([pid])[0]["stages"]
        self.assertEqual(stages["construct"], "platform_rate_limited")
        self.assertNotIn("review_adjudication", stages)
        before = script.calls.count("constructor")
        f.halted = None  # limit has reset
        stages = f.run_papers([pid], retry_platform=True)[0]["stages"]
        self.assertEqual(stages["construct"], "completed")
        self.assertEqual(stages["dossier"], "completed")
        self.assertEqual(script.calls.count("constructor"), before)  # constructor not re-run
        receipt = read_json(f.paper_dir(pid) / "construct" / pid / "receipt.json")
        self.assertTrue(receipt["constructor_reused"])
        self.assertTrue((f.paper_dir(pid) / "construct.failed-1").is_dir())

    def test_v2_pass_partial_excludes_tasks_at_compile(self):
        f = self.prepared(Script(round1="pass_partial", exclude=["t2"], two_tasks=True), v2=True)
        f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        stages = f.run_papers([pid])[0]["stages"]
        self.assertEqual((stages["review_adjudication"], stages["repair"], stages["dossier"]), ("completed", "skipped", "completed"))
        self.assertEqual([t["task_id"] for t in read_json(f.paper_dir(pid) / "compiled" / "compiled_tasks.json")], ["t"])
        self.assertIn("excluded by adjudication: t2", f.state(pid)["stages"]["compile"]["notes"])

    def test_v2_pass_partial_cannot_exclude_everything(self):
        f = self.prepared(Script(round1="pass_partial", exclude=["t"]), v2=True)
        f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        self.assertEqual(f.run_papers([pid])[0]["stages"]["review_adjudication"], "failed_needs_attribution")

    def test_v2_structural_gate_failure_routes_to_repair(self):
        script = Script(bad_coverage_once=True, round2="pass")
        f = self.prepared(script, v2=True)
        f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        stages = f.run_papers([pid])[0]["stages"]
        self.assertEqual((stages["construct"], stages["review_adjudication"], stages["repair"], stages["dossier"]),
                         ("completed", "completed", "completed", "completed"))
        adj = read_json(f.paper_dir(pid) / "review_adjudication" / "review_adjudication.json")
        self.assertEqual((adj["author"], adj["action"]), ("controller_structural_gate", "repair"))
        self.assertIn("coverage matrix", adj["repair_notes"][0])
        # first material_reviewer never ran (gate failed before review); adjudicator ran only for round 2
        self.assertEqual(script.calls.count("adjudicator"), 2)

    def test_v1_structural_gate_failure_stays_terminal(self):
        f = self.prepared(Script(bad_coverage_once=True))
        f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        self.assertEqual(f.run_papers([pid])[0]["stages"]["construct"], "failed_needs_attribution")

    def test_v3_repo_files_prepopulate_constructor_output(self):
        script = Script(round1="pass")
        f = self.factory(script)
        f.init({"triage_pool_size": 6, "triage_batch_size": 3, "fulltext_papers": 3, "factory_prompts": "factory_v3",
                "structural_gate_to_repair": True})
        f.run_triage(); f.select(); f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        stages = f.run_papers([pid])[0]["stages"]
        self.assertEqual((stages["repo_files"], stages["dossier"]), ("completed", "completed"))
        self.assertEqual(script.seen_prepopulated, [("assets/repo_data/data/x.bin", b"\x00\x01data")])
        self.assertIn("data/x.bin: fetched", read_json(f.paper_dir(pid) / "job.json")["scope_request"])

    def test_v2_has_no_repo_file_stage_effect(self):
        f = self.prepared(Script(round1="pass"), v2=True)
        f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        stages = f.run_papers([pid])[0]["stages"]
        self.assertEqual(stages["repo_files"], "skipped")
        self.assertNotIn("prepopulated_output_files", read_json(f.paper_dir(pid) / "job.json"))

    def test_call_budget_and_prompt_freeze(self):
        f = self.prepared(Script(), budget=3)  # two scout calls used
        f.approve_selection("user")
        pid = read_json(self.root / "selection.json")["papers"][0]["project_id"]
        stages = f.run_papers([pid])[0]["stages"]
        self.assertEqual(stages["source_audit"], "completed")
        self.assertEqual(stages["adjudication"], "failed_needs_attribution")
        self.assertIn("budget", f.state(pid)["stages"]["adjudication"]["notes"][0])
        (self.templates / "factory" / "policy.md").write_text("changed", encoding="utf8")
        with self.assertRaisesRegex(ProtocolError, "changed since factory init"):
            f.check_prompts()


if __name__ == "__main__":
    unittest.main()
