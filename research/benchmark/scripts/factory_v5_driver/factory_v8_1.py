"""Material factory v8.1 (2026-10-06): factory v8 + background screening + public cutoff 14 days before disclosure.

Why (v8 pilot, 2026-10-06): both IDEA leaks caught by the v8 leak gate had the same root cause - the background set was
chosen by an adjudicator who had read the target paper and contained side-field papers that supply the target method's
ingredients (score matching for a Fokker-Planck solver; active-learning loss prediction / adversarial task generators
for an amortized sampler). The paper-blind framer summarised them faithfully. An auditor also noted that a public cutoff
equal to the target's arXiv v1 date is a recognition cue.

v8.1 changes (user decisions 2026-10-06):
  1. paper stage `bg_screen` after `area_brief` (adjudicator role): sees the neutral area brief, the private forbidden
     terms and the background abstracts (not the target paper); keeps the routine literature of the problem area and
     excludes side-field works whose relevance is supplying a forbidden term. The framing session reads only kept works.
  2. public cutoff = controller disclosure cutoff (earlier of arXiv v1 and OpenReview public date) minus 14 days. Every
     public statement, the frame check and the job use it; the true disclosure date stays in the private job record.
     Background works whose version date is not strictly before the public cutoff are not given to the framer.
  3. LIT units: compile writes lit_corpus_configuration.json with the same public cutoff (current shared library;
     the frozen library version is set at search-set freeze, T17).
  If fewer than min_background_found works remain for the framer, the unit's frame stage is dropped (no model call).
EXP/WRITE units and every other v8 rule are unchanged.
"""
from pathlib import Path
from datetime import date, timedelta
import json
import shutil
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import factory_v8 as v8  # noqa: E402
import factory_v6  # noqa: E402
import factory_v5  # noqa: E402
import mrhbench.factory as _F  # noqa: E402
from mrhbench.io import read_json, write_json, file_hash, utc_now, ProtocolError  # noqa: E402
from mrhbench.factory import DONE  # noqa: E402

V81 = DRIVER / "prompts_next" / "v8_1"
PUBLIC_CUTOFF_OFFSET_DAYS = 14
LIBRARY_ROOT = Path(r"D:/mrhbench-local-pilot/shared-library-v5")
PAPER_STAGES_V81 = tuple(s for s in v8.PAPER_STAGES_V8 if s != "units") + ("bg_screen", "units")
_F.STAGE_PATHS.setdefault("bg_screen", ["bg_screen", "bg_screen_ws"])

_v8_snapshot = factory_v5.build_prompt_snapshot


def build_prompt_snapshot(dest):
    info = _v8_snapshot(dest)
    rows = []
    for name in ("bg_screen.txt", "bg_screen.schema.json"):
        shutil.copyfile(V81 / name, dest / "factory_v4" / ("v8_" + name))
        rows.append({"name": "factory_v4/v8_" + name, "sha256": file_hash(dest / "factory_v4" / ("v8_" + name))})
    info["factory_v8_1"] = {"role_prompts": rows, "public_cutoff_offset_days": PUBLIC_CUTOFF_OFFSET_DAYS}
    return info


factory_v5.build_prompt_snapshot = build_prompt_snapshot


# ------------------------------------------------------------------ frame facts: drop self-referential evidence
import re as _re  # noqa: E402
import mrhbench.material_batch as _mb  # noqa: E402

FRAME_FACT = _re.compile(r"^PF-[0-9]{2}$")
NEEDS_SOURCE = {"source_fact", "source_result"}  # material_pipeline.validate_package: kinds that require evidence
SELF_REFS = {"construction_request", "request.json", "request", "scope_request", "frame", "frame.json"}
_v8_fill = _mb.fill_sentinel_hashes


def fill_sentinel_hashes(output_root, *a, **k):
    """v8 fill (materialization + hash fill + materialization-source removal), then drop evidence refs of
    maintainer_scope framing facts (PF-NN) that point at the construction request itself (2026-10-09: three v8.1
    units failed the structural gate with "Unknown source or empty locator" because the constructor cited
    source_id "construction_request"; maintainer_scope facts need no source evidence). Recorded per fact."""
    out = _v8_fill(output_root, *a, **k)
    root = Path(output_root)
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return out
    pkg = read_json(pkg_path)
    # 2026-10-10: BdmVgLMvaf LIT cited "locked_frame:assets/task.md"; any id that is not a declared source of this
    # construction request is likewise a self-reference for these framing facts.
    declared, declared_sha = None, {}
    req = root.parent / "request.json"
    if req.is_file():
        declared_sha = {s.get("source_id"): s.get("sha256") for s in read_json(req).get("sources", []) if isinstance(s, dict)}
        declared = set(declared_sha)

    def self_ref(e):
        sid = str(e.get("source_id", ""))
        return sid.lower() in SELF_REFS or (declared is not None and sid not in declared)

    # 2026-10-10 (IXyfbaGlps LIT): the same self-reference appears on facts with other ids and on kind "unknown".
    # The structural gate requires original evidence only for source_fact/source_result, so self-references are
    # removed from every other fact kind; on source claims only when declared evidence remains (they still face the gate).
    removed = []
    for f in pkg.get("facts", []):
        keep = [e for e in f.get("evidence", []) if not self_ref(e)]
        # source claims keep the gate's requirement: self-references are removed only when declared evidence remains
        # (2026-10-11, cyPMEXdqQ2 IDEA PV-DISCLOSURE-DATE: abs_page + request.json)
        if f.get("kind") not in NEEDS_SOURCE or keep:
            if len(keep) != len(f.get("evidence", [])):
                removed.append({"fact_id": f["fact_id"], "dropped": [e for e in f["evidence"] if e not in keep]})
                f["evidence"] = keep
    # 2026-10-11 (pdF86dyoS6 IDEA repair): a constructor transcribed a wrong source_sha256 for a declared source
    # (gate: "Evidence source hash differs from original"). Hashes are controller bookkeeping (CONTROLLER_FILL): for a
    # declared source id the controller writes the request's hash; source id and locator are untouched. Recorded.
    rehashed = []
    for f in pkg.get("facts", []):
        for e in f.get("evidence", []):
            want = declared_sha.get(e.get("source_id"))
            if want and e.get("source_sha256") and e["source_sha256"] != want:
                rehashed.append({"fact_id": f["fact_id"], "source_id": e["source_id"], "was": e["source_sha256"], "now": want})
                e["source_sha256"] = want
    if removed or rehashed:
        write_json(pkg_path, pkg)
        write_json(root.parent / "controller_frame_fact_evidence_normalized.json",
                   {"at": utc_now(), "removed": removed, "rehashed": rehashed, "model_calls_made": 0,
                    "note": "factory v8.1: maintainer_scope framing facts need no source evidence; self-references to the "
                            "construction request were removed before the structural gate"})
    return out


_mb.fill_sentinel_hashes = fill_sentinel_hashes


def public_cutoff(disclosure_cutoff, offset_days=PUBLIC_CUTOFF_OFFSET_DAYS):
    return (date.fromisoformat(disclosure_cutoff[:10]) - timedelta(days=offset_days)).isoformat()


def background_groups(manifest):
    """group id (bgNNN) -> {title, arxiv_id, version, version_date, source_ids} from a background manifest."""
    groups = {}
    for r in manifest.get("requests", []):
        if r.get("status") != "found" or not r.get("source_ids"):
            continue
        vdate = next((v["date"] for v in r.get("versions", []) if v.get("version") == r.get("chosen_version")), None)
        groups[r["request_id"]] = {"title": r.get("title"), "arxiv_id": r.get("arxiv_id"), "version": r.get("chosen_version"),
                                   "version_date": vdate, "source_ids": list(r["source_ids"])}
    return groups


class FactoryV81(v8.FactoryV8):
    def paper_stages(self):
        return PAPER_STAGES_V81 if self.unit_mode else super().paper_stages()

    # ---------------------------------------------------------- cutoffs
    def controller_cutoff(self, project_id):
        """PUBLIC cutoff (disclosure - 14 days); basis records the disclosure date and the offset."""
        cache = self.__dict__.setdefault("_cutoff_cache", {})
        if project_id not in cache:
            disclosure, basis = self.background_cutoff(self.paper_dir(project_id))
            if not disclosure:
                raise ProtocolError("No controller cutoff for a LIT/IDEA unit")
            cache[project_id] = (public_cutoff(disclosure), {**basis, "disclosure_cutoff": disclosure,
                                                             "public_offset_days": PUBLIC_CUTOFF_OFFSET_DAYS})
        return cache[project_id]

    def build_job(self, state):
        job = super().build_job(state)
        if state.get("unit") in v8.V8_UNITS:
            fd = job["first_disclosure"]
            fd["reason"] = ("binding PUBLIC knowledge cutoff = controller disclosure cutoff (earlier of arXiv v1 and OpenReview "
                            "public date, %s) minus %d days (user decision 2026-10-06); state only this date publicly"
                            % (fd["basis"].get("disclosure_cutoff"), PUBLIC_CUTOFF_OFFSET_DAYS))
        return job

    # ---------------------------------------------------------- paper stage: background screen
    def stage_bg_screen(self, state):
        pid = state["project_id"]
        pdir = self.paper_dir(pid)
        if not set(v8.V8_UNITS) & set(self.units(pid)):
            self._record(state, "bg_screen", "skipped", notes=["no LIT/IDEA unit"])
            return
        manifest = read_json(pdir / "background" / "manifest.json")
        groups = background_groups(manifest)
        ws = pdir / "bg_screen_ws"
        if ws.exists():
            raise ProtocolError("Stage workspace must be fresh")
        (ws / "background").mkdir(parents=True)
        by_sid = {s["source_id"]: s for s in manifest["sources"]}
        for gid, g in groups.items():
            for sid in g["source_ids"]:
                row = by_sid[sid]
                src = pdir / row["local_path"]
                if file_hash(src) != row["sha256"]:
                    raise ProtocolError("Background source changed: " + sid)
                shutil.copyfile(src, ws / "background" / src.name)
        write_json(ws / "background_list.json", {"works": [{"group": gid, **{k: g[k] for k in ("title", "arxiv_id", "version", "version_date")},
                                                            "files": [Path(by_sid[s]["local_path"]).name for s in g["source_ids"]]}
                                                           for gid, g in sorted(groups.items())]})
        shutil.copyfile(pdir / "area_brief" / "area_brief.json", ws / "area_brief.json")
        self.publish_common(ws, ["v8_bg_screen.schema.json"])
        (ws / "v8_bg_screen.schema.json").rename(ws / "bg_screen.schema.json")
        out, call = self.agent_stage(ws, prompt_name="v8_bg_screen.txt", role="adjudicator", output_name="bg_screen.json",
                                     schema_name="v8_bg_screen.schema.json",
                                     inputs=("background", "background_list.json", "area_brief.json", "bg_screen.schema.json"))
        if out["project_id"] != pid:
            raise ProtocolError("Background screen names the wrong paper")
        decided = [d["group"] for d in out["decisions"]]
        if sorted(decided) != sorted(groups) or len(set(decided)) != len(decided):
            raise ProtocolError("Background screen must decide every background work exactly once")
        (pdir / "bg_screen").mkdir(exist_ok=True)
        shutil.copyfile(ws / "bg_screen.json", pdir / "bg_screen" / "bg_screen.json")
        kept = sum(1 for d in out["decisions"] if d["keep"])
        self._call_note(state, "bg_screen", "v8.1 background screen (ledger role adjudicator)")
        self._record(state, "bg_screen", DONE, {"bg_screen": "bg_screen/bg_screen.json"}, [call["call_id"]],
                     ["kept %d of %d background works" % (kept, len(groups))])

    def frame_background_sources(self, project_id):
        pdir = self.paper_dir(project_id)
        manifest = read_json(pdir / "background" / "manifest.json")
        groups = background_groups(manifest)
        keep = {d["group"] for d in read_json(pdir / "bg_screen" / "bg_screen.json")["decisions"] if d["keep"]}
        cutoff, _ = self.controller_cutoff(project_id)
        allowed = set()
        for gid, g in groups.items():
            if gid in keep and g["version_date"] and g["version_date"] < cutoff:
                allowed |= set(g["source_ids"])
        return [s for s in manifest["sources"] if s["source_id"] in allowed]

    def framer_background_works(self, project_id):
        sids = {s["source_id"] for s in self.frame_background_sources(project_id)}
        return [gid for gid, g in background_groups(read_json(self.paper_dir(project_id) / "background" / "manifest.json")).items()
                if set(g["source_ids"]) & sids]

    def stage_frame(self, state):
        works = self.framer_background_works(state["project_id"])
        need = self.config()["min_background_found"]
        if len(works) < need:
            self._record(state, "frame", "dropped", notes=["controller rule: %d neutral pre-cutoff background works after "
                                                           "screening, fewer than %d (no model call)" % (len(works), need)])
            return
        super().stage_frame(state)

    # ---------------------------------------------------------- LIT library configuration at the public cutoff
    def stage_compile(self, state):
        super().stage_compile(state)
        if state.get("unit") != "LIT" or state["stages"].get("compile", {}).get("status") != DONE:
            return
        pid = state["project_id"]
        cutoff, basis = self.controller_cutoff(pid)
        arx = (read_json(self.paper_dir(pid) / "sources" / "manifest.json").get("arxiv") or {}).get("id")
        forum = pid.split("-", 1)[1]
        write_json(self.wdir(state) / "lit_corpus_configuration.json", {
            "schema_version": "lit-corpus-configuration-4", "library_root": str(LIBRARY_ROOT),
            "corpus_sha256": file_hash(LIBRARY_ROOT / "corpus.json"), "cutoff": cutoff, "cutoff_basis": basis,
            "cutoff_semantics": "version_date strictly before cutoff (public cutoff = disclosure - %d days)" % PUBLIC_CUTOFF_OFFSET_DAYS,
            "excluded_papers": ["background-arxiv-" + arx] if arx else [],
            "excluded_aliases": [a for a in (arx, pid, forum) if a],
            "library_version_note": "development library; replaced by the frozen search-set library at T17"})


def open_factory(root, max_calls=0, native=None):
    from mrhbench import factory_sources
    from mrhbench import factory_runtime
    from mrhbench.factory import CallBudget
    root = Path(root)
    return FactoryV81(root, native_factory=native or factory_v5.native_factory(root), sources=factory_sources,
                      runtime=factory_runtime, budget=CallBudget(max_calls))


factory_v5.open_factory = open_factory
factory_v6.open_factory = open_factory
v8.open_factory = open_factory


DEFERRED = DRIVER / "v8_1_deferred_papers.json"  # 2026-10-11: papers moved to factory v8.2 (user approved v8.2)


def main():
    if DEFERRED.is_file() and "--papers" in sys.argv:
        deferred = set(read_json(DEFERRED)["papers"])
        papers = sys.argv[sys.argv.index("--papers") + 1].split(",")
        if set(papers) & deferred:
            print(json.dumps({"skipped_deferred_to_v8_2": sorted(set(papers) & deferred), "calls_taken": 0, "halted": None}))
            return
    v8.main()


if __name__ == "__main__":
    main()
