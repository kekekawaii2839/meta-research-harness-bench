"""Material factory v8 (2026-10-06): factory v7 + separated public framing and a blind leak gate for LIT/IDEA units.

Why (factory v7 audit, 2026-10-06): 20 of 24 compiled LIT/IDEA tasks leaked the target contribution (motivating gap,
ingredient lists, novelty combination) although the v7 prompts forbade it (R4) and reviewers checked it; three IDEA
units repaired under reviewer guidance still leaked. The constructor wrote the public text after reading the paper.

v8 changes (EXP / WRITE_CONTENT / WRITE_EVIDENCE units keep the v7 flow):
  1. paper stage `area_brief` (adjudicator role, candidate title+abstract only): a neutral <=60-word problem area and
     a private list of forbidden terms (distinctive coined names/components).
  2. unit stage `frame` (constructor role): a framing session that sees ONLY the pre-cutoff background papers, the
     neutral problem area and the controller cutoff writes all solver-visible files (task.md, IDEA background report,
     deliverable schemas, optional checker) and the public facts. LIT tasks carry no required-topic list.
     Deterministic checks: forbidden terms absent, every date near "cutoff" equals the controller cutoff; one internal
     re-frame on failure, then the unit is dropped.
  3. `construct` / `repair`: the private constructor gets the frame files prepopulated and LOCKED (job note
     constructor_locked_frame.txt); after the batch the controller checks byte equality of the locked files, that no
     other public asset exists, and that the task's public facts equal the frame facts. A violation in round 1 is
     routed to repair with a controller note; in the final round it drops the unit.
  4. `probe` (material_reviewer role): a blind session sees only the public surface and predicts the contribution.
     `leak_judge` (material_reviewer role): sees the paper, the public surface and the prediction; L1-L4 verdict. The
     controller verifies every evidence quote verbatim against the public surface. Controller rule: leak/uncertain in
     round 1 -> repair with a `reframe` (framer rewrites the flagged passages from paper-free guidance); in the final
     round -> drop. The adjudicator's decision on the reviewer findings is kept and can only be made stricter.
  5. controller cutoff evidence in the job (arXiv title search status, OpenReview public date, library exclusion), and
     materialization sources (prepopulated originals copied to neutral public names) are removed from the package
     asset list after the copy (5qg6JPSgCj WRITE_EVIDENCE failed the runtime gate on them).
  6. prompts: v8 platform contract/check (exact cpu.run signature) and the v8 role prompts are frozen in the snapshot.
Usage: same CLI as factory_v6.py; `carry` copies paper-level states of chosen papers from an older root.
"""
from pathlib import Path
import json
import re
import shutil
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import factory_v7  # noqa: E402,F401  (v7 materialization wrapper + v6 rules)
import factory_v6  # noqa: E402
import factory_v5  # noqa: E402
import mrhbench.factory as _F  # noqa: E402
import mrhbench.material_batch as _mb  # noqa: E402
from mrhbench.io import read_json, write_json, file_hash, contained, utc_now, ProtocolError  # noqa: E402
from mrhbench.factory import DONE, UNIT_STAGES, TERMINAL, RETRYABLE, RATE_LIMITED, IN_PROGRESS  # noqa: E402
from mrhbench.material_public_surface import public_surface  # noqa: E402

V8 = DRIVER / "prompts_next" / "v8"
factory_v6.CONTRACT = DRIVER / "prompts_next/constructor_platform_contract_v8.txt"
factory_v6.REVIEW_CHECK = DRIVER / "prompts_next/reviewer_platform_check_v8.txt"
V8_PROMPTS = ("area_brief.txt", "area_brief.schema.json", "framer.txt", "frame.schema.json", "probe.txt",
              "probe.schema.json", "leak_judge.txt", "leak_judge.schema.json", "constructor_locked_frame.txt")
V8_UNITS = ("LIT", "IDEA")
V8_UNIT_STAGES = ("frame", "construct", "probe", "leak_judge", "review_adjudication", "reframe", "repair", "probe2",
                  "leak_judge2", "repair_adjudication", "runtime", "compile")
PAPER_STAGES_V8 = tuple(s for s in _F.PAPER_STAGES_V4 if s != "units") + ("area_brief", "units")
for _s in ("area_brief", "frame", "probe", "leak_judge", "reframe", "probe2", "leak_judge2"):
    _F.STAGE_PATHS.setdefault(_s, [_s, _s + "_ws"])
# 2026-10-10: framing sessions make a second workspace "<stage>_ws_retry" for the deterministic re-try; a platform
# retry must set it aside too (1qq1QJKM5q IDEA failed "Stage workspace must be fresh" after a 429).
for _s in ("frame", "reframe"):
    if _s + "_ws_retry" not in _F.STAGE_PATHS[_s]:
        _F.STAGE_PATHS[_s].append(_s + "_ws_retry")
DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


# ------------------------------------------------------------------ prompt snapshot
_v6_snapshot = factory_v5.build_prompt_snapshot  # factory_v6.build_prompt_snapshot (rebound by factory_v6)


def build_prompt_snapshot(dest):
    info = _v6_snapshot(dest)
    rows = []
    for name in V8_PROMPTS:
        shutil.copyfile(V8 / name, dest / "factory_v4" / ("v8_" + name))
        rows.append({"name": "factory_v4/v8_" + name, "sha256": file_hash(dest / "factory_v4" / ("v8_" + name))})
    info["factory_v8"] = {"role_prompts": rows, "constructor_platform_contract": str(factory_v6.CONTRACT),
                          "reviewer_platform_check": str(factory_v6.REVIEW_CHECK)}
    return info


factory_v5.build_prompt_snapshot = build_prompt_snapshot


# ------------------------------------------------------------------ materialization: drop copy sources from assets
_v7_fill = _mb.fill_sentinel_hashes


def fill_sentinel_hashes(output_root, *a, **k):
    """v7 materialization + hash fill, then remove the materialization SOURCES (prepopulated originals) from the
    package asset lists: the neutral-name public copies are the inputs; listing the originals made public assets
    byte-identical to private ones and put identity-bearing file names in the mount. The edited package is recorded."""
    out = _v7_fill(output_root, *a, **k)
    root = Path(output_root)
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return out
    pkg = read_json(pkg_path)
    removed = []
    for t in pkg.get("tasks", []):
        m = t.get("controller_asset_materialization") or {}
        sources = {r.get("prepopulated_path") for r in (m.get("mappings") or []) if isinstance(r, dict)}
        if not sources:
            continue
        keep = [a for a in t.get("assets", []) if a.get("path") not in sources]
        removed += [{"task_id": t.get("task_id"), "path": a["path"], "visibility": a.get("visibility")}
                    for a in t.get("assets", []) if a.get("path") in sources]
        t["assets"] = keep
    if removed:
        write_json(pkg_path, pkg)
        write_json(root.parent / "controller_materialization_sources_removed.json",
                   {"at": utc_now(), "removed_asset_entries": removed, "model_calls_made": 0,
                    "note": "factory v8: materialization sources are not package assets; files stay unlisted"})
    return out


_mb.fill_sentinel_hashes = fill_sentinel_hashes


# ------------------------------------------------------------------ deterministic checks (pure functions, tested)
def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def forbidden_hits(texts, terms):
    """Forbidden terms (case/whitespace-insensitive, word-bounded) found in any public text."""
    hits = []
    for name, text in texts.items():
        t = norm(text)
        for term in terms:
            n = norm(term)
            if n and re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", t):
                hits.append({"where": name, "term": term})
    return hits


def cutoff_mismatches(texts, cutoff):
    """The first ISO date that follows the word 'cutoff' in the same sentence (within 60 characters) must equal the
    controller cutoff. Other dates in the text (e.g. data years) are not cutoff statements."""
    bad = []
    for name, text in texts.items():
        for m in re.finditer(r"cut-?off[^.\n]{0,60}?(\d{4}-\d{2}-\d{2})", text, re.I):
            if m.group(1) != cutoff:
                bad.append({"where": name, "date": m.group(1), "context": " ".join(text[max(0, m.start() - 40):m.end() + 20].split())[:200]})
    return bad


def quote_found(quote, corpus):
    return norm(quote) in corpus


def sanitize_fixes(verdict):
    """Paper-free re-frame notes: public quotes, criterion and rewrite guidance only (paper_basis is dropped)."""
    notes = []
    for e in verdict.get("evidence", []):
        notes.append({"public_location": e["public_location"], "public_quote": e["public_quote"], "criterion": e["criterion"]})
    for f in verdict.get("public_fixes", []):
        notes.append({"public_location": f["public_location"], "rewrite_guidance": f["rewrite_guidance"]})
    return notes


def lock_violations(output_root, frame_dir, task_type):
    """Locked frame files unchanged and listed public; no other public asset; public facts == frame facts."""
    out, frame = Path(output_root), Path(frame_dir)
    fj = read_json(frame / "frame.json")
    locked = {f["path"]: file_hash(frame / f["path"]) for f in fj["files"]}
    pkg = read_json(out / "package.json")
    tasks = [t for t in pkg.get("tasks", []) if t.get("task_type") == task_type]
    v = []
    if len(tasks) != 1:
        return ["package must hold exactly one %s task (found %d)" % (task_type, len(tasks))]
    t = tasks[0]
    for path, sha in locked.items():
        p = out / path
        if not p.is_file():
            v.append("locked file missing: " + path)
        elif file_hash(p) != sha:
            v.append("locked file changed: " + path)
    public = {a["path"] for a in t.get("assets", []) if a.get("visibility") == "public"}
    for path in locked:
        if path not in public:
            v.append("locked file not listed as public asset: " + path)
    for path in sorted(public - set(locked)):
        v.append("public asset not from the frame: " + path)
    facts = {f["fact_id"]: f for f in pkg.get("facts", [])}
    want = {f["fact_id"]: f["statement"] for f in fj["public_facts"]}
    for fid in t.get("input_fact_ids", []):
        if fid not in want:
            v.append("public fact not from the frame: " + fid)
        elif facts.get(fid, {}).get("statement") != want[fid]:
            v.append("public fact statement changed: " + fid)
    for fid in want:
        if fid not in t.get("input_fact_ids", []):
            v.append("frame fact missing from input_fact_ids: " + fid)
    return v


# ------------------------------------------------------------------ factory
class FactoryV8(factory_v6.FactoryV6):
    def paper_stages(self):
        return PAPER_STAGES_V8 if self.unit_mode else super().paper_stages()

    @staticmethod
    def unit_stages(unit):
        return V8_UNIT_STAGES if unit in V8_UNITS else UNIT_STAGES

    def _call_note(self, state, stage, v8_role):
        state.setdefault("v8_roles", {})[stage] = v8_role

    # ---------------------------------------------------------- units loop (base loop with per-unit stage lists)
    def stage_units(self, state, stages, retry_platform):
        summary, rate_limited, finished = {}, False, True
        units = self.units(state["project_id"])
        for unit in units:
            if getattr(self, "_unit_filter", None) is not None and unit not in self._unit_filter:
                finished = False
                continue
            if self.halted:
                rate_limited = True
                break
            ustate = self.unit_state(state["project_id"], unit)
            order = self.unit_stages(unit)
            self._run_stages(ustate, order, tuple(stages) + tuple(s for s in order if s not in UNIT_STAGES and
                                                                     set(stages) & set(UNIT_STAGES)), retry_platform)
            statuses = {k: v["status"] for k, v in ustate["stages"].items()}
            summary[unit] = statuses
            if set(statuses.values()) & RETRYABLE:
                rate_limited = True
                break
            if not (set(statuses.values()) & TERMINAL) and not set(order) <= set(statuses):
                finished = False
        if rate_limited:
            status = RATE_LIMITED
        elif not finished or len(summary) < len(units):
            status = IN_PROGRESS
        elif any(s.get("compile") == DONE for s in summary.values()):
            status = DONE
        elif all(set(s.values()) & TERMINAL <= {"dropped"} for s in summary.values()):
            status = "dropped"
        else:
            status = "failed_needs_attribution"
        self._record(state, "units", status, {u: "units/%s/state.json" % u for u in summary},
                     notes=["%s: %s" % (u, ",".join("%s=%s" % kv for kv in s.items())) for u, s in summary.items()])

    # ---------------------------------------------------------- paper stage: area brief
    def stage_area_brief(self, state):
        pdir = self.paper_dir(state["project_id"])
        if not set(V8_UNITS) & set(self.units(state["project_id"])):
            self._record(state, "area_brief", "skipped", notes=["no LIT/IDEA unit"])
            return
        ws = pdir / "area_brief_ws"
        if ws.exists():
            raise ProtocolError("Stage workspace must be fresh")
        ws.mkdir(parents=True)
        write_json(ws / "candidate.json", {k: v for k, v in self._candidate(state["project_id"]).items()
                                           if k in ("project_id", "title", "abstract")})
        self.publish_common(ws, ["v8_area_brief.schema.json"])
        (ws / "v8_area_brief.schema.json").rename(ws / "area_brief.schema.json")
        out, call = self.agent_stage(ws, prompt_name="v8_area_brief.txt", role="adjudicator", output_name="area_brief.json",
                                     schema_name="v8_area_brief.schema.json", inputs=("candidate.json", "area_brief.schema.json"))
        if out["project_id"] != state["project_id"]:
            raise ProtocolError("Area brief names the wrong paper")
        # the brief must not contain its own forbidden terms
        hits = forbidden_hits({"problem_area": out["problem_area"]}, [t["term"] for t in out["forbidden_terms"]])
        if hits:
            raise ProtocolError("Area brief contains its own forbidden terms: %s" % hits)
        (pdir / "area_brief").mkdir(exist_ok=True)
        shutil.copyfile(ws / "area_brief.json", pdir / "area_brief" / "area_brief.json")
        self._call_note(state, "area_brief", "v8 area brief (ledger role adjudicator)")
        self._record(state, "area_brief", DONE, {"area_brief": "area_brief/area_brief.json"}, [call["call_id"]],
                     ["%d forbidden terms" % len(out["forbidden_terms"])])

    # ---------------------------------------------------------- informational quote length (controller fix 2026-10-06)
    QUOTE_FIELDS = {("steering_passages", "quote"), ("evidence", "public_quote")}

    @classmethod
    def relaxed_schema(cls, schema):
        """Copy of a frozen v8 schema whose informational quote fields have no maxLength. A 305-character steering
        quote (n8h1z588eu LIT probe2) failed a whole unit; quotes are verified against the public text separately."""
        import copy
        sch = copy.deepcopy(schema)
        for arr, field in cls.QUOTE_FIELDS:
            node = sch.get("properties", {}).get(arr, {}).get("items", {}).get("properties", {}).get(field)
            if node is not None:
                node.pop("maxLength", None)
        return sch

    def agent_stage(self, workspace, *, prompt_name, role, output_name, schema_name, inputs):
        if not schema_name.startswith("v8_"):
            return super().agent_stage(workspace, prompt_name=prompt_name, role=role, output_name=output_name,
                                       schema_name=schema_name, inputs=inputs)
        import jsonschema
        from mrhbench.material_batch import _check_inputs, _input_snapshot
        self.check_prompts()
        self.budget.take()
        snapshot = _input_snapshot(workspace, inputs)
        prompt = (self.factory_templates / prompt_name).read_text(encoding="utf8")
        call = self.runner(role).run(workspace=workspace, prompt=prompt, role=role)
        _check_inputs(workspace, inputs, snapshot, role)
        return self._validate_v8_output(workspace, output_name, schema_name, call)

    def _validate_v8_output(self, workspace, output_name, schema_name, call):
        import jsonschema
        out_path = Path(workspace) / output_name
        if not out_path.is_file():
            raise ProtocolError("stage wrote no " + output_name)
        output = read_json(out_path)
        frozen = read_json(self.factory_templates / schema_name)
        warnings = []
        try:
            jsonschema.validate(output, frozen)
        except jsonschema.ValidationError:
            jsonschema.validate(output, self.relaxed_schema(frozen))  # anything beyond quote length still fails
            warnings.append("over-length informational quote accepted (frozen schema maxLength relaxed by controller)")
            write_json(Path(workspace) / "controller_validation_warning.json", {"at": utc_now(), "warnings": warnings})
        return output, {"call_id": call.get("call_id"), "status": call.get("status"), "audit_directory": call.get("audit_directory"),
                        "output_sha256": file_hash(out_path), "warnings": warnings}

    def area_brief(self, project_id):
        return read_json(self.paper_dir(project_id) / "area_brief" / "area_brief.json")

    def controller_cutoff(self, project_id):
        cache = self.__dict__.setdefault("_cutoff_cache", {})
        if project_id not in cache:  # one OpenReview date lookup per paper and process
            cache[project_id] = self.background_cutoff(self.paper_dir(project_id))
        cutoff, basis = cache[project_id]
        if not cutoff:
            raise ProtocolError("No controller cutoff for a LIT/IDEA unit")
        return cutoff, basis

    # ---------------------------------------------------------- unit stage: frame / reframe
    def _frame_texts(self, frame_out):
        fj = read_json(frame_out / "frame.json")
        texts = {"frame.json:research_question": fj["research_question"]}
        texts.update({"frame.json:fact:" + f["fact_id"]: f["statement"] for f in fj["public_facts"]})
        for f in fj["files"]:
            p = frame_out / f["path"]
            if not p.is_file():
                raise ProtocolError("frame lists a missing file: " + f["path"])
            texts[f["path"]] = p.read_text(encoding="utf8", errors="replace")
        listed = {f["path"] for f in fj["files"]}
        extra = [p.relative_to(frame_out).as_posix() for p in (frame_out / "assets").rglob("*") if p.is_file()]
        if set(extra) - listed:
            raise ProtocolError("frame wrote unlisted files: %s" % sorted(set(extra) - listed))
        if any("/private" in x or x.startswith("assets/private") for x in listed):
            raise ProtocolError("frame files must all be public")
        return fj, texts

    def frame_background_sources(self, project_id):
        """Background source rows the framing session may read (v8: all fetched background sources)."""
        return read_json(self.paper_dir(project_id) / "background" / "manifest.json")["sources"]

    def _frame_workspace(self, state, ws, previous=None, notes=None):
        pid = state["project_id"]
        pdir = self.paper_dir(pid)
        if ws.exists():
            raise ProtocolError("Stage workspace must be fresh: " + str(ws))
        ws.mkdir(parents=True)
        bg = self.frame_background_sources(pid)
        listed = []
        from mrhbench.source_evidence_index import build_evidence_index  # same index the constructor gets
        (ws / "sources").mkdir()
        for i, s in enumerate(bg):
            src = contained(pdir, s["local_path"], must_exist=True)
            if file_hash(src) != s["sha256"]:
                raise ProtocolError("Background source changed: " + s["source_id"])
            rel = "sources/%03d-%s" % (i, src.name)
            shutil.copyfile(src, ws / rel)
            listed.append({"source_id": s["source_id"], "title": s.get("title"), "version": s.get("version"), "path": rel})
            if src.suffix.lower() in (".html", ".htm"):
                write_json(ws / "source_navigation" / ("%03d.json" % i),
                           build_evidence_index((ws / rel).read_text(encoding="utf8", errors="replace"), s["source_id"], s["sha256"]))
        write_json(ws / "sources_manifest.json", {"sources": listed})
        cutoff, _ = self.controller_cutoff(pid)
        req = {"unit": state["unit"], "problem_area": self.area_brief(pid)["problem_area"], "cutoff_date": cutoff,
               "platform": factory_v6.CONTRACT.read_text(encoding="utf8").split("Consistency rules")[0],
               "deliverable_conventions": "Solver deliverables are files the solver writes under /work; give each JSON "
                                          "deliverable a JSON Schema asset and name the same files and fields in task.md."}
        if previous is not None:
            shutil.copytree(previous / "assets", ws / "previous_frame" / "assets")
            shutil.copyfile(previous / "frame.json", ws / "previous_frame" / "frame.json")
            req["reframe_notes"] = notes
        write_json(ws / "frame_request.json", req)
        self.publish_common(ws, ["v8_frame.schema.json"])
        (ws / "v8_frame.schema.json").rename(ws / "frame.schema.json")
        return cutoff

    def _run_framer(self, state, stage, previous=None, notes=None):
        """One framing session (+ one internal deterministic re-try); returns (status, calls, notes)."""
        wdir = self.wdir(state)
        terms = [t["term"] for t in self.area_brief(state["project_id"])["forbidden_terms"]]
        calls, msgs = [], []
        attempt_notes, attempt_prev = notes, previous
        for attempt in (1, 2):
            ws = wdir / (stage + "_ws" + ("" if attempt == 1 else "_retry"))
            cutoff = self._frame_workspace(state, ws, attempt_prev, attempt_notes)
            inputs = ("sources", "source_navigation", "sources_manifest.json", "frame_request.json", "frame.schema.json") + \
                     (("previous_frame",) if attempt_prev is not None else ())
            out, call = self.agent_stage(ws, prompt_name="v8_framer.txt", role="constructor", output_name="frame_output/frame.json",
                                         schema_name="v8_frame.schema.json", inputs=tuple(i for i in inputs if (ws / i).exists()))
            calls.append(call["call_id"])
            if out["unit"] != state["unit"]:
                raise ProtocolError("frame unit mismatch")
            fj, texts = self._frame_texts(ws / "frame_output")
            problems = ([{"cutoff_field": fj["cutoff_date"]}] if fj["cutoff_date"] != cutoff else []) + \
                       cutoff_mismatches(texts, cutoff) + forbidden_hits(texts, terms)
            if not problems:
                target = wdir / stage
                shutil.copytree(ws / "frame_output", target)
                return DONE, calls, msgs + ["frame ok (attempt %d)" % attempt]
            msgs.append("attempt %d deterministic problems: %s" % (attempt, json.dumps(problems, ensure_ascii=False)[:600]))
            attempt_prev = ws / "frame_output"
            attempt_notes = (notes or []) + [{"controller_check": "Fix these deterministic problems; a forbidden term must "
                                              "not appear in any form; every cutoff mention must be " + cutoff,
                                              "problems": [{k: v for k, v in p.items() if k != "term"} | ({"term": p["term"]} if "term" in p else {})
                                                           for p in problems]}]
        return "dropped", calls, msgs + ["frame failed deterministic checks twice"]

    def stage_frame(self, state):
        status, calls, notes = self._run_framer(state, "frame")
        self._call_note(state, "frame", "v8 framer (ledger role constructor)")
        self._record(state, "frame", status, {"frame": "frame/frame.json"} if status == DONE else {}, calls, notes)

    def latest_frame(self, state):
        return self.wdir(state) / ("reframe" if state["stages"].get("reframe", {}).get("status") == DONE else "frame")

    def stage_reframe(self, state):
        verdict = self._verdict(state, "leak_judge")
        if not self._leaky(verdict):
            self._record(state, "reframe", "skipped", notes=["leak gate round 1: acceptable"])
            return
        if self._final_drop(state, "review_adjudication"):
            self._record(state, "reframe", "skipped", notes=["adjudicator dropped the unit"])
            return
        status, calls, notes = self._run_framer(state, "reframe", previous=self.wdir(state) / "frame",
                                                notes=sanitize_fixes(verdict))
        self._call_note(state, "reframe", "v8 re-framer (ledger role constructor)")
        self._record(state, "reframe", status, {"frame": "reframe/frame.json"} if status == DONE else {}, calls, notes)

    # ---------------------------------------------------------- job: locked frame + cutoff evidence
    def build_job(self, state):
        job = super().build_job(state)
        pid = state["project_id"]
        if state.get("unit") not in V8_UNITS:
            return job
        cutoff, basis = self.controller_cutoff(pid)
        manifest = read_json(self.paper_dir(pid) / "sources" / "manifest.json")
        arx = manifest.get("arxiv") or {}
        job["first_disclosure"] = {
            "date": cutoff, "verified": False, "basis": basis,
            "evidence": {"arxiv_title_search_at_fetch": arx.get("status"),
                         "openreview_public_date": basis.get("openreview_public"),
                         "library_exclusion": "the literature service excludes the target by its arXiv id (when known) and "
                                              "its OpenReview id/project aliases; the library holds only background works "
                                              "requested for benchmark papers"},
            "reason": "controller cutoff = earlier of arXiv v1 and OpenReview public date; binding for this task"}
        frame = self.latest_frame(state)
        if not (frame / "frame.json").is_file():
            return job
        fj = read_json(frame / "frame.json")
        rel = frame.relative_to(self.paper_dir(pid)).as_posix()
        job.setdefault("prepopulated_output_files", [])
        job["prepopulated_output_files"] = [r for r in job["prepopulated_output_files"]
                                            if r["to"] not in {f["path"] for f in fj["files"]}] + [
            {"from": rel + "/" + f["path"], "to": f["path"], "sha256": file_hash(frame / f["path"]),
             "provenance": {"url": "controller:v8-frame", "version": rel}} for f in fj["files"]]
        tmpl = (self.factory_templates / "v8_constructor_locked_frame.txt").read_text(encoding="utf8")
        job["scope_request"] += "\n\n" + tmpl.format(
            locked_files="\n".join("- %s (%s)" % (f["path"], f["role"]) for f in fj["files"]),
            public_facts="\n".join("- %s [%s]: %s" % (f["fact_id"], f["kind"], f["statement"]) for f in fj["public_facts"]),
            cutoff_date=cutoff)
        return job

    # ---------------------------------------------------------- construct / repair with lock check
    def _batch_output(self, state, batch):
        return self.wdir(state) / batch / self.job_id(state) / "constructor" / "output"

    def stage_construct(self, state):
        super().stage_construct(state)
        if state.get("unit") not in V8_UNITS:
            return
        rec = state["stages"].get("construct", {})
        if rec.get("status") != DONE:
            return
        if "review_adjudication" in state["stages"]:  # routed to repair by a deterministic gate: nothing to probe
            for s in ("probe", "leak_judge"):
                self._record(state, s, "skipped", notes=["construct routed to repair by a deterministic gate"])
            return
        v = lock_violations(self._batch_output(state, "construct"), self.wdir(state) / "frame", state["unit"])
        if v:
            wdir = self.wdir(state)
            write_json(wdir / "review_adjudication" / "review_adjudication.json", {
                "schema_version": "factory-review-adjudication-1", "project_id": state["project_id"], "round": 1,
                "finding_decisions": [], "action": "repair", "repair_notes": [
                    "The controller's locked-frame check rejected the package: " + "; ".join(v) + ". Restore the locked "
                    "files byte-for-byte, list them as public assets, add no other public asset, and use exactly the "
                    "framing facts as the task's public facts."],
                "drop_reason": None, "excluded_task_ids": [], "author": "controller_locked_frame_check"}, exclusive=True)
            self._record(state, "construct", DONE, rec.get("artifacts"), rec.get("calls", []),
                         rec.get("notes", []) + ["locked-frame check failed, routed to repair (no model call): " + "; ".join(v)[:400]])
            for s in ("probe", "leak_judge"):
                self._record(state, s, "skipped", notes=["construct routed to repair by locked-frame check"])
            self._record(state, "review_adjudication", DONE, {"review_adjudication": "review_adjudication/review_adjudication.json"},
                         notes=["controller: locked-frame check failure routed to the single repair round (no model call)"])

    # ---------------------------------------------------------- probe / leak judge
    def _public_pack(self, state, batch, ws):
        out = self._batch_output(state, batch)
        surf = public_surface(out)
        (ws / "public").mkdir(parents=True)
        pkg = read_json(out / "package.json")
        for t in pkg["tasks"]:
            for a in t["assets"]:
                if a.get("visibility") == "public":
                    target = contained(ws / "public", a["path"])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(contained(out, a["path"], must_exist=True), target)
        values = {k: v["value"] for k, v in surf["records"].items() if not k.endswith(":resource_overrides")
                  and not k.startswith("environment:")}
        write_json(ws / "public_surface.json", {"records": values,
                                                "note": "solver-visible structured fields of the task (v8 probe input)"})
        corpus = norm(" ".join([json.dumps(values, ensure_ascii=False)] +
                               [p.read_text(encoding="utf8", errors="replace") for p in (ws / "public").rglob("*") if p.is_file()]
                               + [json.dumps(values)]))
        return corpus

    def _probe(self, state, stage, batch):
        ws = self.wdir(state) / (stage + "_ws")
        if ws.exists():
            raise ProtocolError("Stage workspace must be fresh")
        ws.mkdir(parents=True)
        self._public_pack(state, batch, ws)
        self.publish_common(ws, ["v8_probe.schema.json"])
        (ws / "v8_probe.schema.json").rename(ws / "probe.schema.json")
        out, call = self.agent_stage(ws, prompt_name="v8_probe.txt", role="material_reviewer", output_name="prediction.json",
                                     schema_name="v8_probe.schema.json", inputs=("public", "public_surface.json", "probe.schema.json"))
        (self.wdir(state) / stage).mkdir(exist_ok=True)
        shutil.copyfile(ws / "prediction.json", self.wdir(state) / stage / "prediction.json")
        self._call_note(state, stage, "v8 blind probe (ledger role material_reviewer)")
        self._record(state, stage, DONE, {"prediction": stage + "/prediction.json"}, [call["call_id"]],
                     ["specificity " + out["specificity"] + ("; recognised paper" if out["recognised_paper"] else "")])

    def _judge(self, state, stage, batch, probe_stage):
        wdir = self.wdir(state)
        ws = wdir / (stage + "_ws")
        self._source_workspace(state, ws)  # target paper sources + navigation + candidate.json (fresh dir)
        corpus = self._public_pack(state, batch, ws)
        shutil.copyfile(wdir / probe_stage / "prediction.json", ws / "prediction.json")
        shutil.copyfile(self.paper_dir(state["project_id"]) / "area_brief" / "area_brief.json", ws / "area_brief.json")
        self.publish_common(ws, ["v8_leak_judge.schema.json"])
        (ws / "v8_leak_judge.schema.json").rename(ws / "leak_judge.schema.json")
        out, call = self.agent_stage(ws, prompt_name="v8_leak_judge.txt", role="material_reviewer", output_name="leak_verdict.json",
                                     schema_name="v8_leak_judge.schema.json",
                                     inputs=tuple(i for i in ("sources", "source_navigation", "source_manifest.json", "candidate.json",
                                                              "public", "public_surface.json", "prediction.json", "area_brief.json",
                                                              "leak_judge.schema.json") if (ws / i).exists()))
        if out["project_id"] != state["project_id"]:
            raise ProtocolError("Leak verdict names the wrong paper")
        unverified = [e["public_quote"] for e in out["evidence"] if not quote_found(e["public_quote"], corpus)]
        if out["verdict"] in ("leak", "uncertain") and len(unverified) == len(out["evidence"]):
            raise ProtocolError("Leak verdict without any verifiable public quote")
        (wdir / stage).mkdir(exist_ok=True)
        shutil.copyfile(ws / "leak_verdict.json", wdir / stage / "leak_verdict.json")
        write_json(wdir / stage / "controller_quote_check.json", {"unverified_quotes": unverified, "checked_at": utc_now()})
        self._call_note(state, stage, "v8 leak judge (ledger role material_reviewer)")
        self._record(state, stage, DONE, {"leak_verdict": stage + "/leak_verdict.json"}, [call["call_id"]],
                     ["verdict %s %s; prediction match %s%s" % (out["verdict"], ",".join(out["criteria_hit"]), out["prediction_match"],
                                                                "; %d unverified quote(s)" % len(unverified) if unverified else "")])

    def stage_probe(self, state):
        self._probe(state, "probe", "construct")

    def stage_leak_judge(self, state):
        self._judge(state, "leak_judge", "construct", "probe")

    def stage_probe2(self, state):
        if state["stages"].get("repair", {}).get("status") != DONE:
            self._record(state, "probe2", "skipped", notes=["no repair round"])
            return
        self._probe(state, "probe2", "repair")

    def stage_leak_judge2(self, state):
        if state["stages"].get("probe2", {}).get("status") != DONE:
            self._record(state, "leak_judge2", "skipped", notes=["no repair round"])
            return
        self._judge(state, "leak_judge2", "repair", "probe2")

    def _verdict(self, state, stage):
        p = self.wdir(state) / stage / "leak_verdict.json"
        return read_json(p) if p.is_file() else None

    @staticmethod
    def _leaky(verdict):
        return bool(verdict) and verdict["verdict"] in ("leak", "uncertain")

    def _final_drop(self, state, adj_stage):
        p = self.wdir(state) / adj_stage / "review_adjudication.json"
        return p.is_file() and read_json(p)["action"] == "drop"

    # ---------------------------------------------------------- adjudication with the leak rule
    def _review_adjudication(self, state, stage, batch_dir, round_no):
        out = super()._review_adjudication(state, stage, batch_dir, round_no)
        if state.get("unit") not in V8_UNITS:
            return out
        verdict = self._verdict(state, "leak_judge" if round_no == 1 else "leak_judge2")
        if self._leaky(verdict) and out["action"] != "drop":
            wdir = self.wdir(state)
            final = round_no > 1
            override = {"at": utc_now(), "adjudicator_action": out["action"], "controller_action": "drop" if final else "repair",
                        "rule": "factory v8 leak gate: leak/uncertain verdict -> repair with re-frame (round 1) or drop (final round)",
                        "leak_verdict": "%s/leak_verdict.json" % ("leak_judge" if round_no == 1 else "leak_judge2")}
            write_json(wdir / stage / "controller_leak_override.json", override, exclusive=True)
            rec = state["stages"][stage]
            self._record(state, stage, "dropped" if final else DONE, rec.get("artifacts"), rec.get("calls", []),
                         rec.get("notes", []) + ["controller leak gate: adjudicator %s -> %s" % (out["action"], override["controller_action"])])
        return out

    def _needs_repair(self, state, adjudication_stage="review_adjudication"):
        if super()._needs_repair(state, adjudication_stage):
            return True
        return state.get("unit") in V8_UNITS and (self.wdir(state) / adjudication_stage / "controller_leak_override.json").is_file() \
            and read_json(self.wdir(state) / adjudication_stage / "controller_leak_override.json")["controller_action"] == "repair"

    def _repair(self, state, stage, source_batch, adjudication_stage, job_name):
        if state.get("unit") not in V8_UNITS:
            return super()._repair(state, stage, source_batch, adjudication_stage, job_name)
        wdir = self.wdir(state)
        notes = list(read_json(wdir / adjudication_stage / "review_adjudication.json").get("repair_notes") or [])
        if state["stages"].get("reframe", {}).get("status") == DONE:
            notes.append("The public frame was rewritten by the framing session after the independent leak gate; the new "
                         "locked files are prepopulated in output/ and replace the old ones. Keep them byte-for-byte and "
                         "update the task's public facts to the new framing facts.")
        if not notes:
            notes = ["Controller: no reviewer repair notes; re-check the package against the locked frame."]
        job, row = self._batch(state, wdir / stage, repair_from=wdir / source_batch,
                               repair_notes={self.job_id(state): notes}, job_name=job_name)
        calls = [(row.get(k) or {}).get("call_id") for k in ("constructor", "reviewer")]
        self._record(state, stage, self._batch_status(row), {"receipt": "%s/%s/receipt.json" % (stage, job["job_id"]),
                     "review": "%s/%s/reviewer/review.json" % (stage, job["job_id"])}, calls, ["reviewer decision " + row["status"]])

    def stage_repair(self, state):
        if state.get("unit") in V8_UNITS and state["stages"].get("reframe", {}).get("status") == "dropped":
            self._record(state, "repair", "dropped", notes=["re-frame failed deterministic checks twice"])
            return
        super().stage_repair(state)

    def stage_repair_adjudication(self, state):
        if state.get("unit") in V8_UNITS and state["stages"].get("repair", {}).get("status") == DONE:
            v = lock_violations(self._batch_output(state, "repair"), self.latest_frame(state), state["unit"])
            if v:
                self._record(state, "repair_adjudication", "dropped",
                             notes=["controller locked-frame check failed in the final round (no model call): " + "; ".join(v)[:600]])
                return
        super().stage_repair_adjudication(state)


def open_factory(root, max_calls=0, native=None):
    from mrhbench import factory_sources
    from mrhbench import factory_runtime
    from mrhbench.factory import CallBudget
    root = Path(root)
    return FactoryV8(root, native_factory=native or factory_v5.native_factory(root), sources=factory_sources,
                     runtime=factory_runtime, budget=CallBudget(max_calls))


factory_v5.open_factory = open_factory
factory_v6.open_factory = open_factory

PAPER_CARRY = ("sources", "source_audit", "adjudication", "background", "repo_files", "external_data", "data_conversion")
PAPER_CARRY_FILES = ("background_decision.json",)
CARRY_STAGES = ("fetch", "source_audit", "adjudication", "background", "repo_files", "external_data")


def cmd_carry(root, from_root, papers):
    """Copy paper-level material (fetched sources, audits, adjudication, background) of finished papers from an older
    root, so v8 re-runs only the new paper stage (area brief) and the selected units. Unit directories are not copied."""
    root, from_root = Path(root), Path(from_root)
    out = []
    for pid in papers:
        s, d = from_root / "papers" / pid, root / "papers" / pid
        if d.exists():
            raise ProtocolError("paper already present in the v8 root: " + pid)
        d.mkdir(parents=True)
        for name in PAPER_CARRY:
            if (s / name).exists():
                shutil.copytree(s / name, d / name)
        for name in PAPER_CARRY_FILES:
            shutil.copyfile(s / name, d / name)
        st = read_json(s / "state.json")
        write_json(d / "state.json", {**st, "stages": {k: v for k, v in st["stages"].items() if k in CARRY_STAGES},
                                      "flags": st.get("flags", []), "carried_from": str(s), "carried_at": utc_now()})
        out.append(pid)
    return out


def cmd_accept_stage(root, pid, unit, stage):
    """Zero-call recovery: a probe/probe2 stage whose model call completed but was rejected only by the frozen schema's
    informational quote length is re-validated with the controller rule (FactoryV8._validate_v8_output) and recorded
    from the SAME call's output. The failed stage record moves to the state history."""
    if stage not in ("probe", "probe2"):
        raise ProtocolError("accept-stage handles probe stages only")
    f = open_factory(root)
    state = f.unit_state(pid, unit)
    rec = state["stages"].get(stage, {})
    if rec.get("status") != "failed_needs_attribution" or "maxLength" not in " ".join(rec.get("notes", [])):
        raise ProtocolError("stage is not a quote-length schema failure: %r" % rec.get("notes"))
    ws = f.wdir(state) / (stage + "_ws")
    ledger = read_json(factory_v5.LEDGER)
    key = str(ws.resolve()).replace("\\", "/").lower()
    calls = [a for a in ledger["attempts"] if a.get("artifact_directory") and (Path(a["artifact_directory"]) / "request.json").is_file()
             and key in (Path(a["artifact_directory"]) / "request.json").read_text(encoding="utf8", errors="replace").replace("\\\\", "/").replace("\\", "/").lower()]
    if len(calls) != 1 or calls[0]["status"] != "completed":
        raise ProtocolError("expected exactly one completed call for %s, found %s" % (ws, [(c["id"], c["status"]) for c in calls]))
    out, call = f._validate_v8_output(ws, "prediction.json", "v8_probe.schema.json", {"call_id": calls[0]["id"], "status": "completed",
                                                                                      "audit_directory": calls[0]["artifact_directory"]})
    state.setdefault("history", []).append({"stage": stage, **state["stages"].pop(stage), "set_aside": utc_now(),
                                            "reason": "re-validated under controller quote-length rule (no new call)"})
    (f.wdir(state) / stage).mkdir(exist_ok=True)
    shutil.copyfile(ws / "prediction.json", f.wdir(state) / stage / "prediction.json")
    f._record(state, stage, DONE, {"prediction": stage + "/prediction.json"}, [call["call_id"]],
              ["specificity " + out["specificity"] + ("; recognised paper" if out["recognised_paper"] else ""),
               "accepted from the completed call %s after controller quote-length relaxation (no new call)" % call["call_id"]])
    return {"stage": stage, "call_id": call["call_id"], "warnings": call["warnings"]}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "accept-stage":
        _, _, root, pid, unit, stage = sys.argv
        print(json.dumps(cmd_accept_stage(root, pid, unit, stage), indent=1))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "carry":
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("cmd")
        p.add_argument("--root", required=True)
        p.add_argument("--from-root", required=True)
        p.add_argument("--papers", required=True)
        a = p.parse_args()
        print(json.dumps({"carried": cmd_carry(a.root, a.from_root, a.papers.split(","))}, indent=1))
        return
    factory_v6.main()


if __name__ == "__main__":
    main()
