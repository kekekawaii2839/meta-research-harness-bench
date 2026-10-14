"""Offline tests for factory_v8 (zero model calls, no network): deterministic checks and the LIT/IDEA unit flow with a
fake native runner and a stubbed construction batch."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

DRIVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DRIVER))
import factory_v8 as v8  # noqa: E402
import factory_v5  # noqa: E402
from mrhbench.io import read_json, write_json, file_hash  # noqa: E402

PID = "iclr2025-TESTpaper1"
CUTOFF = "2024-10-04"


# ------------------------------------------------------------------ pure functions
class PureChecks(unittest.TestCase):
    def test_forbidden_hits_word_bounded_case_insensitive(self):
        texts = {"a": "We study Score  Matching for densities", "b": "scorematching is not a hit"}
        hits = v8.forbidden_hits(texts, ["score matching", "flow"])
        self.assertEqual(hits, [{"where": "a", "term": "score matching"}])

    def test_cutoff_mismatch(self):
        ok = {"t": "Knowledge cutoff: 2024-10-04. Data from 2019-01-01 is fine. Works before the cutoff (2024-10-04) only."}
        self.assertEqual(v8.cutoff_mismatches(ok, CUTOFF), [])
        bad = {"t": "The knowledge cut-off date is 2024-10-10."}
        self.assertEqual(v8.cutoff_mismatches(bad, CUTOFF)[0]["date"], "2024-10-10")

    def test_sanitize_drops_paper_basis(self):
        verdict = {"evidence": [{"public_quote": "q", "public_location": "assets/task.md", "criterion": "L2",
                                 "paper_basis": "SECRET method X"}],
                   "public_fixes": [{"public_location": "assets/task.md", "rewrite_guidance": "broaden"}]}
        notes = v8.sanitize_fixes(verdict)
        self.assertNotIn("SECRET", json.dumps(notes))
        self.assertEqual(len(notes), 2)

    def test_quote_found_whitespace_insensitive(self):
        self.assertTrue(v8.quote_found("open  problem\nin", v8.norm("an open problem in the area")))
        self.assertFalse(v8.quote_found("closed problem", v8.norm("an open problem")))


# ------------------------------------------------------------------ fixtures
def write_frame(dirpath, unit, text_extra=""):
    (dirpath / "assets").mkdir(parents=True, exist_ok=True)
    (dirpath / "assets" / "task.md").write_text("Task: survey the area. Knowledge cutoff: %s.%s" % (CUTOFF, text_extra), encoding="utf8")
    files = [{"path": "assets/task.md", "role": "task_statement"}]
    if unit == "IDEA":
        (dirpath / "assets" / "background_report.md").write_text("Approach A [bg0]. Approach B [bg1].", encoding="utf8")
        files.append({"path": "assets/background_report.md", "role": "background_report"})
    write_json(dirpath / "frame.json", {"schema_version": "v8-frame-1", "unit": unit, "cutoff_date": CUTOFF,
                                        "research_question": "What approaches exist and what remains open?",
                                        "files": files, "deliverables": [{"path": "review.md", "format": "markdown"}],
                                        "public_facts": [{"fact_id": "PF-01", "statement": "Knowledge cutoff " + CUTOFF, "kind": "maintainer_scope"},
                                                         {"fact_id": "PF-02", "statement": "Deliverable review.md", "kind": "maintainer_scope"}]})


def write_package(out, unit, frame_dir, *, tamper=False, extra_public=False, change_fact=False):
    fj = read_json(frame_dir / "frame.json")
    assets = []
    for f in fj["files"]:
        if not (out / f["path"]).is_file():
            (out / f["path"]).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(frame_dir / f["path"], out / f["path"])
        if tamper and f["path"] == "assets/task.md":
            (out / f["path"]).write_text("changed by constructor", encoding="utf8")
        assets.append({"path": f["path"], "visibility": "public", "sha256": file_hash(out / f["path"])})
    (out / "assets/private").mkdir(parents=True, exist_ok=True)
    (out / "assets/private/rubric.md").write_text("private rubric", encoding="utf8")
    assets.append({"path": "assets/private/rubric.md", "visibility": "private", "sha256": file_hash(out / "assets/private/rubric.md")})
    if extra_public:
        (out / "assets/hint.md").write_text("extra", encoding="utf8")
        assets.append({"path": "assets/hint.md", "visibility": "public", "sha256": file_hash(out / "assets/hint.md")})
    facts = [{"fact_id": f["fact_id"], "statement": f["statement"] + (" CHANGED" if change_fact else ""), "kind": f["kind"],
              "allowed_stages": [unit], "evidence": [], "discloses_target_contribution": False} for f in fj["public_facts"]]
    write_json(out / "package.json", {"schema_version": "material-package-1", "status": "candidate", "paper_id": PID,
                                      "facts": facts, "environment": {"resources": {"cpus": 1}},
                                      "tasks": [{"task_id": "task-x", "task_type": unit, "assets": assets,
                                                 "input_contract": {"files": [{"path": a["path"]} for a in assets if a["visibility"] == "public"]},
                                                 "output_contract": {"description": "write review.md"},
                                                 "input_fact_ids": [f["fact_id"] for f in fj["public_facts"]]}]})


class LockChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        write_frame(self.tmp / "frame", "IDEA")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_package_passes(self):
        write_package(self.tmp / "out", "IDEA", self.tmp / "frame")
        self.assertEqual(v8.lock_violations(self.tmp / "out", self.tmp / "frame", "IDEA"), [])

    def test_tamper_extra_public_and_fact_change_detected(self):
        write_package(self.tmp / "out", "IDEA", self.tmp / "frame", tamper=True, extra_public=True, change_fact=True)
        v = " | ".join(v8.lock_violations(self.tmp / "out", self.tmp / "frame", "IDEA"))
        self.assertIn("locked file changed: assets/task.md", v)
        self.assertIn("public asset not from the frame: assets/hint.md", v)
        self.assertIn("public fact statement changed: PF-01", v)


class MaterializationSourceRemoval(unittest.TestCase):
    def test_sources_unlisted_after_fill(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "output"
            out.mkdir()
            write_json(out / "package.json", {"tasks": [{"task_id": "t", "assets": [
                {"path": "assets/repo_data/Orig_NAME.npy", "visibility": "private"},
                {"path": "assets/data/neutral.npy", "visibility": "public"}],
                "controller_asset_materialization": {"mappings": [{"prepopulated_path": "assets/repo_data/Orig_NAME.npy",
                                                                    "public_path": "assets/data/neutral.npy"}]}}]})
            orig = v8._v7_fill
            v8._v7_fill = lambda root, *a, **k: {"filled": 0}
            try:
                v8.fill_sentinel_hashes(out)
            finally:
                v8._v7_fill = orig
            paths = [a["path"] for a in read_json(out / "package.json")["tasks"][0]["assets"]]
            self.assertEqual(paths, ["assets/data/neutral.npy"])
            self.assertTrue((tmp / "controller_materialization_sources_removed.json").is_file())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ flow
class FakeRunner:
    def __init__(self, script, role):
        self.script, self.role = script, role

    def run(self, *, workspace, prompt, role, **kw):
        s = self.script
        s.calls.append((role, prompt.splitlines()[0]))
        ws = Path(workspace)
        if prompt.startswith("ROLE: problem-area brief"):
            write_json(ws / "area_brief.json", {"schema_version": "v8-area-brief-1", "project_id": PID,
                                                "problem_area": "Learning densities in high dimensions where normalisation is hard",
                                                "forbidden_terms": [{"term": "secretnet", "why": "coined"},
                                                                    {"term": "zeta trick", "why": "component"},
                                                                    {"term": "omega loss", "why": "component"}], "notes": "neutral"})
        elif prompt.startswith("ROLE: public-task framer"):
            req = read_json(ws / "frame_request.json")
            s.frame_requests.append(req)
            self.assert_no_paper(ws)
            extra = " Use the zeta trick." if s.frame_forbidden > 0 else ""
            s.frame_forbidden -= 1
            write_frame(ws / "frame_output", req["unit"], extra + (" v2" if "reframe_notes" in req else ""))
        elif prompt.startswith("ROLE: blind probe"):
            s.probe_inputs.append(sorted(p.relative_to(ws).as_posix() for p in ws.rglob("*") if p.is_file()))
            write_json(ws / "prediction.json", {"schema_version": "v8-probe-1", "task_type": "IDEA",
                                                "predicted_contribution": "Some generic idea about densities.",
                                                "key_ingredients": ["a"], "predicted_findings": "none inferable",
                                                "steering_passages": [], "specificity": "generic", "recognised_paper": False})
        elif prompt.startswith("ROLE: independent leak judge"):
            verdict = s.verdicts.pop(0)
            quote = "survey the area" if s.verifiable else "text that is not in the task"
            write_json(ws / "leak_verdict.json", {"schema_version": "v8-leak-verdict-1", "project_id": PID, "verdict": verdict,
                                                  "criteria_hit": ["L2"] if verdict != "acceptable" else [],
                                                  "prediction_match": "partial", "target_contribution_summary": "x",
                                                  "evidence": [{"public_quote": quote, "public_location": "assets/task.md",
                                                                "criterion": "L2", "paper_basis": "PAPER-ONLY-DETAIL"}]
                                                  if verdict != "acceptable" else [],
                                                  "public_fixes": [{"public_location": "assets/task.md", "rewrite_guidance": "broaden"}]
                                                  if verdict != "acceptable" else [], "reason": "r"})
        return {"call_id": len(s.calls), "status": "completed"}

    @staticmethod
    def assert_no_paper(ws):
        names = [p.name for p in (ws / "sources").rglob("*")]
        assert all(n.startswith(("000-", "001-")) for n in names), names
        assert not any("paper" in n for n in names), names


class Script:
    def __init__(self, verdicts=("acceptable",), adjudications=("pass",), frame_forbidden=0, verifiable=True,
                 tamper_construct=False):
        self.calls, self.frame_requests, self.probe_inputs = [], [], []
        self.verdicts, self.adjudications = list(verdicts), list(adjudications)
        self.frame_forbidden, self.verifiable, self.tamper_construct = frame_forbidden, verifiable, tamper_construct
        self.jobs = []


class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "factory-v8"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, script, unit="IDEA"):
        root = self.root
        root.mkdir(parents=True)
        v8.build_prompt_snapshot(root / "prompts_snapshot")
        f = v8.FactoryV8(root, native_factory=lambda role: FakeRunner(script, role), sources=None, runtime=None,
                         budget=factory_v5.CallBudget(100))
        f._factory_prompts = "factory_v4"
        f.init({"factory_prompts": "factory_v4", "unit_split": True, "conference_end": "2025-04-28"})
        (root / "pool").mkdir()
        (root / "pool" / "candidates.jsonl").write_text(json.dumps({"project_id": PID, "title": "Secretnet: a title"}) + chr(10), encoding="utf8")
        pdir = f.paper_dir(PID)
        (pdir / "sources/files").mkdir(parents=True)
        (pdir / "sources/files/paper.html").write_text("<p>target paper text</p>", encoding="utf8")
        write_json(pdir / "sources/manifest.json", {"arxiv": {"status": "arxiv_not_found"}, "sources": [
            {"source_id": "paper_html", "url": "u", "version": "v", "role": "paper_html",
             "sha256": file_hash(pdir / "sources/files/paper.html"), "local_path": "sources/files/paper.html"}]})
        (pdir / "background/files").mkdir(parents=True)
        bg = []
        for i in range(2):
            p = pdir / "background/files" / ("bg%d.html" % i)
            p.write_text("<p>background %d</p>" % i, encoding="utf8")
            bg.append({"source_id": "bg%d" % i, "title": "B%d" % i, "version": "v1", "role": "background_paper",
                       "sha256": file_hash(p), "local_path": "background/files/bg%d.html" % i, "url": "u"})
        write_json(pdir / "background/manifest.json", {"sources": bg})
        write_json(pdir / "background_decision.json", {"requested_task_types": [unit]})
        write_json(pdir / "adjudication/adjudication.json", {
            "requested_task_types": [unit], "scope_request": "Build the unit.", "task_scopes": {unit: "scope"},
            "ambiguity_decisions": [], "withheld_from_solver": ["target method"], "rights_review": "internal",
            "environment_candidate": {"cpus": 1, "memory_mb": 1024, "disk_mb": 512, "pids_limit": 64, "wall_seconds": 600,
                                      "gpu": False, "network": "none", "scientific_rationale": "text task"}})
        f._candidate = lambda pid: {"project_id": PID, "title": "Secretnet: a title", "abstract": "We propose secretnet."}
        f.background_cutoff = lambda pdir: (CUTOFF, {"arxiv_v1": None, "openreview_public": CUTOFF})

        def fake_batch(state, batch_root, repair_from=None, repair_notes=None, job_name="job.json"):
            job = f.build_job(state)
            script.jobs.append({"batch": batch_root.name, "job": job, "notes": repair_notes})
            out = batch_root / f.job_id(state) / "constructor" / "output"
            out.mkdir(parents=True)
            for r in job.get("prepopulated_output_files", []):
                (out / r["to"]).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(pdir / r["from"], out / r["to"])
            write_package(out, state["unit"], f.latest_frame(state), tamper=script.tamper_construct and batch_root.name == "construct")
            return job, {"status": "pass_with_pending_runtime", "constructor": {"call_id": 101}, "reviewer": {"call_id": 102}}
        f._batch = fake_batch

        def fake_adj(this, state, stage, batch_dir, round_no):
            action = script.adjudications.pop(0)
            write_json(this.wdir(state) / stage / "review_adjudication.json",
                       {"project_id": PID, "round": round_no, "action": action, "repair_notes": ["fix x"] if action == "repair" else [],
                        "drop_reason": "d" if action == "drop" else None, "finding_decisions": [], "excluded_task_ids": []})
            this._record(state, stage, "dropped" if action == "drop" else v8.DONE, {}, [201], ["action " + action])
            return read_json(this.wdir(state) / stage / "review_adjudication.json")
        self._orig_adj = factory_v5.FactoryV5._review_adjudication
        factory_v5.FactoryV5._review_adjudication = fake_adj
        self.addCleanup(lambda: setattr(factory_v5.FactoryV5, "_review_adjudication", self._orig_adj))
        pstate = f.state(PID)
        pstate["stages"] = {k: {"status": "completed"} for k in ("fetch", "source_audit", "adjudication", "background")}
        f._save(pstate)
        return f

    def run_unit(self, f, unit="IDEA"):
        pstate = f.state(PID)
        f.stage_area_brief(pstate)
        u = f.unit_state(PID, unit)
        stages = tuple(s for s in v8.V8_UNIT_STAGES if s not in ("runtime", "compile"))
        f._run_stages(u, stages, stages, False)
        return f.unit_state(PID, unit)["stages"]

    def test_acceptable_path_no_repair(self):
        s = Script(verdicts=["acceptable"], adjudications=["pass"])
        f = self.make(s)
        st = self.run_unit(f)
        self.assertEqual({k: v["status"] for k, v in st.items()}, {
            "frame": "completed", "construct": "completed", "probe": "completed", "leak_judge": "completed",
            "review_adjudication": "completed", "reframe": "skipped", "repair": "skipped", "probe2": "skipped",
            "leak_judge2": "skipped", "repair_adjudication": "skipped"})
        # framer saw no paper, problem area from the brief, controller cutoff; job prepopulates locked frame
        self.assertEqual(s.frame_requests[0]["cutoff_date"], CUTOFF)
        self.assertIn("normalisation", s.frame_requests[0]["problem_area"])
        job = s.jobs[0]["job"]
        self.assertEqual({r["to"] for r in job["prepopulated_output_files"]}, {"assets/task.md", "assets/background_report.md"})
        self.assertIn("LOCKED PUBLIC FRAME", job["scope_request"])
        self.assertEqual(job["first_disclosure"]["date"], CUTOFF)
        # probe saw only the public surface (no private rubric, no paper)
        files = s.probe_inputs[0]
        self.assertTrue(all(not x.startswith("public/assets/private") for x in files), files)
        self.assertFalse(any("paper" in x or "rubric" in x for x in files), files)

    def test_leak_round1_reframes_and_repairs_with_paper_free_notes(self):
        s = Script(verdicts=["leak", "acceptable"], adjudications=["pass", "pass"])
        f = self.make(s)
        st = self.run_unit(f)
        self.assertEqual(st["reframe"]["status"], "completed")
        self.assertEqual(st["repair"]["status"], "completed")
        self.assertEqual(st["leak_judge2"]["status"], "completed")
        self.assertEqual(st["repair_adjudication"]["status"], "completed")
        reframe_req = s.frame_requests[-1]
        self.assertIn("reframe_notes", reframe_req)
        self.assertNotIn("PAPER-ONLY-DETAIL", json.dumps(reframe_req))
        repair_job = [j for j in s.jobs if j["batch"] == "repair"][0]
        self.assertTrue(all(r["from"].startswith("units/IDEA/reframe/") for r in repair_job["job"]["prepopulated_output_files"]))
        self.assertTrue((f.wdir(f.unit_state(PID, "IDEA")) / "review_adjudication/controller_leak_override.json").is_file())

    def test_leak_in_final_round_drops(self):
        s = Script(verdicts=["leak", "leak"], adjudications=["pass", "pass"])
        f = self.make(s)
        st = self.run_unit(f)
        self.assertEqual(st["repair_adjudication"]["status"], "dropped")

    def test_uncertain_counts_as_leak(self):
        s = Script(verdicts=["uncertain", "acceptable"], adjudications=["pass", "pass"])
        f = self.make(s)
        st = self.run_unit(f)
        self.assertEqual(st["reframe"]["status"], "completed")

    def test_lock_violation_routes_to_repair_without_probe(self):
        s = Script(verdicts=["acceptable"], adjudications=["pass"], tamper_construct=True)
        f = self.make(s)
        st = self.run_unit(f)
        self.assertEqual(st["probe"]["status"], "skipped")
        self.assertEqual(st["repair"]["status"], "completed")
        self.assertEqual(st["repair_adjudication"]["status"], "completed")

    def test_forbidden_term_twice_drops_frame(self):
        s = Script(frame_forbidden=2)
        f = self.make(s)
        st = self.run_unit(f)
        self.assertEqual(st["frame"]["status"], "dropped")
        self.assertEqual(sum(1 for r, _ in s.calls if r == "constructor"), 2)

    def test_forbidden_term_once_retries_then_passes(self):
        s = Script(frame_forbidden=1, verdicts=["acceptable"], adjudications=["pass"])
        f = self.make(s)
        st = self.run_unit(f)
        self.assertEqual(st["frame"]["status"], "completed")
        self.assertIn("controller_check", json.dumps(s.frame_requests[1].get("reframe_notes")))

    def test_unverifiable_leak_quote_fails_with_attribution(self):
        s = Script(verdicts=["leak"], verifiable=False)
        f = self.make(s)
        st = self.run_unit(f)
        self.assertEqual(st["leak_judge"]["status"], "failed_needs_attribution")

    def test_lit_unit_uses_v8_flow_and_exp_keeps_base_flow(self):
        self.assertEqual(v8.FactoryV8.unit_stages("LIT"), v8.V8_UNIT_STAGES)
        self.assertEqual(v8.FactoryV8.unit_stages("EXP"), v8.UNIT_STAGES)


class RelaxedQuoteSchema(unittest.TestCase):
    def test_only_quote_length_is_relaxed(self):
        import jsonschema
        sch = read_json(v8.V8 / "probe.schema.json")
        rel = v8.FactoryV8.relaxed_schema(sch)
        out = {"schema_version": "v8-probe-1", "task_type": "LIT", "predicted_contribution": "x" * 30, "key_ingredients": ["a"],
               "predicted_findings": "n", "steering_passages": [{"quote": "q" * 305, "location": "assets/task.md"}],
               "specificity": "generic", "recognised_paper": False}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(out, sch)
        jsonschema.validate(out, rel)
        out["specificity"] = "very"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(out, rel)
        self.assertIn("maxLength", sch["properties"]["steering_passages"]["items"]["properties"]["quote"])
        jrel = v8.FactoryV8.relaxed_schema(read_json(v8.V8 / "leak_judge.schema.json"))
        self.assertNotIn("maxLength", jrel["properties"]["evidence"]["items"]["properties"]["public_quote"])


if __name__ == "__main__":
    unittest.main()
