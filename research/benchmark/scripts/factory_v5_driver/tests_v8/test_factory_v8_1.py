"""Offline tests for factory_v8_1 (zero model calls): public cutoff offset, background screening and its use by the
paper-blind framer."""
from pathlib import Path
import json
import shutil
import sys
import unittest

DRIVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DRIVER))
import factory_v8_1 as v81  # noqa: E402
import factory_v8 as v8  # noqa: E402
import factory_v5  # noqa: E402
from tests_v8 import test_factory_v8 as T  # noqa: E402
from mrhbench.io import read_json, write_json, file_hash  # noqa: E402

DISCLOSURE = T.CUTOFF            # 2024-10-04
PUBLIC = "2024-09-20"            # minus 14 days


class Pure(unittest.TestCase):
    def test_public_cutoff(self):
        self.assertEqual(v81.public_cutoff(DISCLOSURE), PUBLIC)
        self.assertEqual(v81.public_cutoff("2024-03-01"), "2024-02-16")

    def test_background_groups(self):
        m = {"requests": [{"request_id": "bg001", "status": "found", "chosen_version": 2, "arxiv_id": "1",
                           "versions": [{"version": 1, "date": "2020-01-01"}, {"version": 2, "date": "2021-01-01"}],
                           "source_ids": ["a", "b"], "title": "t"},
                          {"request_id": "bg002", "status": "not_found", "source_ids": []}]}
        g = v81.background_groups(m)
        self.assertEqual(list(g), ["bg001"])
        self.assertEqual(g["bg001"]["version_date"], "2021-01-01")


class ScreenScript(T.Script):
    def __init__(self, keep, **kw):
        super().__init__(**kw)
        self.keep = keep


class ScreenRunner(T.FakeRunner):
    @staticmethod
    def assert_no_paper(ws):
        names = [p.name for p in (ws / "sources").rglob("*")]
        assert names and all("bg" in n for n in names), names  # background works only; the target is sources/files/paper.html

    def run(self, *, workspace, prompt, role, **kw):
        if prompt.startswith("ROLE: background screener"):
            self.script.calls.append((role, "bg_screen"))
            ws = Path(workspace)
            works = read_json(ws / "background_list.json")["works"]
            write_json(ws / "bg_screen.json", {"schema_version": "v8-bg-screen-1", "project_id": T.PID, "notes": "n",
                                               "decisions": [{"group": w["group"], "keep": w["group"] in self.script.keep,
                                                              "reason": "screened"} for w in works]})
            return {"call_id": len(self.script.calls), "status": "completed"}
        if prompt.startswith("ROLE: public-task framer"):  # the fake framer states the cutoff it was given
            old, T.CUTOFF = T.CUTOFF, read_json(Path(workspace) / "frame_request.json")["cutoff_date"]
            try:
                return super().run(workspace=workspace, prompt=prompt, role=role, **kw)
            finally:
                T.CUTOFF = old
        return super().run(workspace=workspace, prompt=prompt, role=role, **kw)


class Flow(T.Flow):
    N_BG = 7

    def make81(self, script, unit="IDEA", late=()):
        f = self.make(script, unit)  # v8 fixture (patches _review_adjudication, _batch, cutoff, candidate)
        root = self.root
        g = v81.FactoryV81(root, native_factory=lambda role: ScreenRunner(script, role), sources=None, runtime=None,
                           budget=factory_v5.CallBudget(100))
        g._factory_prompts = "factory_v4"
        # v8.1 snapshot files into the frozen snapshot + config hashes (the v8 fixture init froze a v8 snapshot)
        for name in ("bg_screen.txt", "bg_screen.schema.json"):
            shutil.copyfile(v81.V81 / name, root / "prompts_snapshot/factory_v4" / ("v8_" + name))
        cfg = read_json(root / "factory.json")
        cfg["prompt_hashes"] = g.prompt_hashes()
        write_json(root / "factory.json", cfg)
        g._candidate, g.background_cutoff, g._batch = f._candidate, f.background_cutoff, f._batch
        g._batch = self._rebind_batch(g, script)
        pdir = g.paper_dir(T.PID)
        # richer background: N_BG works with requests/versions/dates
        (pdir / "background").rename(pdir / "background_v8fixture")
        (pdir / "background/files").mkdir(parents=True)
        sources, reqs = [], []
        for i in range(self.N_BG):
            gid = "bg%03d" % i
            p = pdir / "background/files" / ("%s_paper.html" % gid)
            p.write_text("<p>background work %d</p>" % i, encoding="utf8")
            sid = gid + "_paper_html"
            sources.append({"source_id": sid, "url": "u", "version": "v1", "role": "background_paper",
                            "sha256": file_hash(p), "local_path": "background/files/%s_paper.html" % gid})
            vdate = "2024-09-25" if gid in late else "2023-0%d-01" % (1 + i % 9)
            reqs.append({"request_id": gid, "status": "found", "chosen_version": 1, "arxiv_id": "23%02d.0000%d" % (i, i),
                         "title": "Work %d" % i, "versions": [{"version": 1, "date": vdate}], "source_ids": [sid]})
        write_json(pdir / "background/manifest.json", {"sources": sources, "requests": reqs})
        return g

    def _rebind_batch(self, g, script):
        orig = T.Flow.make.__code__  # noqa: F841 (documentation: same stub as the v8 fixture, bound to g)
        pdir = g.paper_dir(T.PID)

        def fake_batch(state, batch_root, repair_from=None, repair_notes=None, job_name="job.json"):
            job = g.build_job(state)
            script.jobs.append({"batch": batch_root.name, "job": job, "notes": repair_notes})
            out = batch_root / g.job_id(state) / "constructor" / "output"
            out.mkdir(parents=True)
            for r in job.get("prepopulated_output_files", []):
                (out / r["to"]).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(pdir / r["from"], out / r["to"])
            T.write_package(out, state["unit"], g.latest_frame(state))
            return job, {"status": "pass_with_pending_runtime", "constructor": {"call_id": 101}, "reviewer": {"call_id": 102}}
        return fake_batch

    def run81(self, g, unit="IDEA"):
        p = g.state(T.PID)
        g.stage_area_brief(p)
        g.stage_bg_screen(p)
        u = g.unit_state(T.PID, unit)
        stages = tuple(s for s in v8.V8_UNIT_STAGES if s not in ("runtime", "compile"))
        g._run_stages(u, stages, stages, False)
        return g, g.unit_state(T.PID, unit)["stages"]

    def test_paper_stage_order(self):
        self.assertEqual(v81.PAPER_STAGES_V81[-3:], ("area_brief", "bg_screen", "units"))

    def test_framer_sees_only_kept_pre_cutoff_works_and_public_cutoff(self):
        s = ScreenScript(keep={"bg000", "bg001", "bg002", "bg003", "bg004", "bg005"}, verdicts=["acceptable"], adjudications=["pass"])
        g = self.make81(s, late=("bg005",))
        g, st = self.run81(g)
        self.assertEqual(st["frame"]["status"], "completed")
        req = s.frame_requests[0]
        self.assertEqual(req["cutoff_date"], PUBLIC)
        ws = g.wdir(g.unit_state(T.PID, "IDEA")) / "frame_ws"
        listed = read_json(ws / "sources_manifest.json")["sources"]
        self.assertEqual(sorted(x["source_id"] for x in listed), ["bg00%d_paper_html" % i for i in range(5)])  # bg005 late, bg006 excluded
        job = s.jobs[0]["job"]
        self.assertEqual(job["first_disclosure"]["date"], PUBLIC)
        self.assertEqual(job["first_disclosure"]["basis"]["disclosure_cutoff"], DISCLOSURE)

    def test_too_few_neutral_works_drops_frame_without_call(self):
        s = ScreenScript(keep={"bg000", "bg001"})
        g = self.make81(s)
        g, st = self.run81(g)
        self.assertEqual(st["frame"]["status"], "dropped")
        self.assertFalse(any(r == "constructor" for r, _ in s.calls))

    def test_screen_must_decide_every_work(self):
        s = ScreenScript(keep=set())
        g = self.make81(s)
        p = g.state(T.PID)
        g.stage_area_brief(p)
        orig = ScreenRunner.run

        def partial(self_, *, workspace, prompt, role, **kw):
            out = orig(self_, workspace=workspace, prompt=prompt, role=role, **kw)
            if prompt.startswith("ROLE: background screener"):
                d = read_json(Path(workspace) / "bg_screen.json")
                d["decisions"] = d["decisions"][:-1]
                write_json(Path(workspace) / "bg_screen.json", d)
            return out
        ScreenRunner.run = partial
        try:
            with self.assertRaises(Exception):
                g.stage_bg_screen(p)
        finally:
            ScreenRunner.run = orig


class FrameFactEvidence(unittest.TestCase):
    def test_self_reference_dropped_only_for_framing_scope_facts(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "output"
            out.mkdir()
            ref = {"source_id": "construction_request", "locator": "item 3", "source_sha256": "x"}
            real = {"source_id": "bg001_paper_html", "locator": "S1", "source_sha256": "y"}
            write_json(out / "package.json", {"tasks": [], "facts": [
                {"fact_id": "PF-01", "kind": "maintainer_scope", "evidence": [ref]},
                {"fact_id": "PF-02", "kind": "source_fact", "evidence": [ref, real]},
                {"fact_id": "F-9", "kind": "maintainer_scope", "evidence": [ref]},
                {"fact_id": "PF-03", "kind": "maintainer_scope", "evidence": [real, ref]}]})
            orig = v81._v8_fill
            v81._v8_fill = lambda root, *a, **k: {}
            try:
                v81.fill_sentinel_hashes(out)
            finally:
                v81._v8_fill = orig
            facts = {f["fact_id"]: f["evidence"] for f in read_json(out / "package.json")["facts"]}
            self.assertEqual(facts["PF-01"], [])
            self.assertEqual(facts["PF-02"], [real])     # source claim: self-ref dropped, declared evidence kept
            self.assertEqual(facts["F-9"], [])            # any non-source kind: self-reference removed
            self.assertEqual(facts["PF-03"], [real])
            self.assertTrue((tmp / "controller_frame_fact_evidence_normalized.json").is_file())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_undeclared_source_dropped_for_framing_facts_when_request_present(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "output"
            out.mkdir()
            write_json(tmp / "request.json", {"sources": [{"source_id": "bg001_paper_html"}]})
            frame_ref = {"source_id": "locked_frame:assets/task.md", "locator": "section 'Tools'"}
            real = {"source_id": "bg001_paper_html", "locator": "S1"}
            write_json(out / "package.json", {"tasks": [], "facts": [
                {"fact_id": "PF-01", "kind": "maintainer_scope", "evidence": [frame_ref, real]},
                {"fact_id": "PV-01", "kind": "source_fact", "evidence": [frame_ref]}]})
            orig = v81._v8_fill
            v81._v8_fill = lambda root, *a, **k: {}
            try:
                v81.fill_sentinel_hashes(out)
            finally:
                v81._v8_fill = orig
            facts = {f["fact_id"]: f["evidence"] for f in read_json(out / "package.json")["facts"]}
            self.assertEqual(facts["PF-01"], [real])
            self.assertEqual(facts["PV-01"], [frame_ref])  # a source claim with no declared evidence still faces the gate
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_source_claim_self_reference_dropped_when_declared_evidence_remains(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "output"
            out.mkdir()
            write_json(tmp / "request.json", {"sources": [{"source_id": "abs_page"}]})
            req_ref = {"source_id": "request.json", "locator": "first_disclosure"}
            real = {"source_id": "abs_page", "locator": "Submission history [v1]"}
            write_json(out / "package.json", {"tasks": [], "facts": [
                {"fact_id": "PV-D", "kind": "source_fact", "evidence": [real, req_ref]}]})
            orig = v81._v8_fill
            v81._v8_fill = lambda root, *a, **k: {}
            try:
                v81.fill_sentinel_hashes(out)
            finally:
                v81._v8_fill = orig
            self.assertEqual(read_json(out / "package.json")["facts"][0]["evidence"], [real])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()


class EvidenceRehash(unittest.TestCase):
    def test_wrong_hash_of_declared_source_is_replaced_and_recorded(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "output"
            out.mkdir()
            write_json(tmp / "request.json", {"sources": [{"source_id": "bg018_abs_page", "sha256": "a" * 64}]})
            write_json(out / "package.json", {"tasks": [], "facts": [{"fact_id": "PF-11", "kind": "source_fact", "evidence": [
                {"source_id": "bg018_abs_page", "locator": "abstract", "source_sha256": "b" * 64}]}]})
            orig = v81._v8_fill
            v81._v8_fill = lambda root, *a, **k: {}
            try:
                v81.fill_sentinel_hashes(out)
            finally:
                v81._v8_fill = orig
            ev = read_json(out / "package.json")["facts"][0]["evidence"][0]
            self.assertEqual(ev["source_sha256"], "a" * 64)
            self.assertEqual(ev["locator"], "abstract")
            rec = read_json(tmp / "controller_frame_fact_evidence_normalized.json")
            self.assertEqual(rec["rehashed"][0]["was"], "b" * 64)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
