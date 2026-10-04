"""Material factory v6 (2026-10-01): factory v5 + platform contract + frozen executor budgets + platform lint.

Differences from factory v5 (everything else is the unchanged v5 composition):
  1. prompts: the frozen snapshot appends prompts_next/constructor_platform_contract_v6.txt to the constructor
     addendum and prompts_next/reviewer_platform_check_v6.txt to material_reviewer.txt (used by the construct
     round and, followed by review.txt, by incremental repair rounds). Cause: factory v4/v5 never told
     constructors the platform's real tools, so LIT tasks invented library interfaces and one task ran a checker from the read-only public root (P11 review
     2026-09-30). The repo prompts are not modified; the snapshot is frozen at init as before.
  2. compile: the in-process platform fixes used for release-v5 (single assets/ prefix, /work-relative tool
     paths, controller note 1, LIT tool note without an example anchor, LIT tool grant) are applied, and
     executor model-call budgets come from executor_budget_freeze_v1.json (measured once, frozen) instead of
     the factory defaults. Tool calls, wall time and collection limits are unchanged.
  4. admissibility_v6: a tool call the CLI itself refused as unavailable ("No such tool available") is a warning,
     not a rejection of the whole session (user decision 2026-10-01); all other out-of-profile activity still rejects.
  3. after compile, task_platform_lint runs on every compiled task; findings are recorded in
     <unit>/platform_lint.json and as a state note (review flags for maintenance repair, not rejections).
Usage: same CLI as factory_v5.py (init / run / status).
"""
from pathlib import Path
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import platform_patches  # noqa: E402,F401  (must precede every mrhbench import)
import recompile_v5_platform_notes  # noqa: E402,F401  (applies the release-v5 note/tool-grant fixes in-process)
import factory_v5  # noqa: E402
import admissibility_v6  # noqa: E402,F401  (CLI-refused unavailable tool -> warning, user decision 2026-10-01)
import leak_rule_v6  # noqa: E402,F401  (plan/rubric restating a public requirement -> review flag, user decision 2026-10-02)
from mrhbench.io import read_json, write_json, file_hash  # noqa: E402
from mrhbench.factory import DONE  # noqa: E402
import task_platform_lint  # noqa: E402

# v6.1 (2026-10-01): exact granted tool names incl. artifact_image_view. The v6 texts omitted image view from the
# reviewer check, so reviewers flagged WRITE_EVIDENCE "image view" as an ungranted tool. The factory-v6 root keeps
# its frozen v6 snapshot; new roots initialised from here get v6.1.
CONTRACT = DRIVER / "prompts_next/constructor_platform_contract_v6_1.txt"
REVIEW_CHECK = DRIVER / "prompts_next/reviewer_platform_check_v6_1.txt"
BUDGET_FREEZE = DRIVER / "executor_budget_freeze_v1.json"
REVIEWER_PROMPTS = ("material_reviewer.txt",)  # repair-round reviewers get material_reviewer.txt + review.txt
_v5_snapshot = factory_v5.build_prompt_snapshot


def _append(path, extra):
    path.write_bytes(path.read_bytes().rstrip(b"\r\n") + b"\n\n" + extra.read_bytes())


def build_prompt_snapshot(dest):
    info = _v5_snapshot(dest)
    _append(dest / "factory_v4/constructor_addendum.txt", CONTRACT)
    for rel in REVIEWER_PROMPTS:
        _append(dest / rel, REVIEW_CHECK)
    info["factory_v6"] = {
        "constructor_platform_contract": {"source": str(CONTRACT), "sha256": file_hash(CONTRACT)},
        "reviewer_platform_check": {"source": str(REVIEW_CHECK), "sha256": file_hash(REVIEW_CHECK), "appended_to": list(REVIEWER_PROMPTS)},
        "snapshot_sha256": {rel: file_hash(dest / rel) for rel in ("factory_v4/constructor_addendum.txt", *REVIEWER_PROMPTS)},
        "executor_budget_freeze": {"source": str(BUDGET_FREEZE), "sha256": file_hash(BUDGET_FREEZE)}}
    return info


factory_v5.build_prompt_snapshot = build_prompt_snapshot


METADATA_CITATIONS = {"source_manifest.json", "candidate.json", "source_audit.json"}  # controller-published paper metadata of the stage workspace


import threading as _threading


class FactoryV6(factory_v5.FactoryV5):
    # v5 keeps the per-stage role context (paper id, round, identity map) in self._ctx. With --workers > 1 the paper
    # threads overwrote each other's context, so a call could be wrapped for another paper (seen 2026-10-01: three
    # adjudications failed, one identity guard fired). Thread-local storage gives each paper thread its own context.
    @property
    def _ctx(self):
        tl = self.__dict__.setdefault("_ctx_tl", _threading.local())
        return getattr(tl, "value", None)

    @_ctx.setter
    def _ctx(self, value):
        self.__dict__.setdefault("_ctx_tl", _threading.local()).value = value

    def background_cutoff(self, pdir):
        """Earliest known public disclosure: the earlier of arXiv v1 and the OpenReview public date (note odate).
        Fix 2026-10-02: v5/v6 used arXiv v1 only; for papers whose arXiv v1 came after the conference this let
        background versions that post-date the OpenReview submission through (Root Cause IDEA, 2406.05014v2)."""
        import openreview_fetch
        m = read_json(pdir / "sources" / "manifest.json")
        arxiv = ((m.get("arxiv") or {}).get("earliest_known_public_version") or {}).get("date")
        orv = None
        if True:  # every factory paper is an OpenReview forum id; absent public date -> arXiv only
            try:
                orv = openreview_fetch.submission_date(Path(pdir).name.split("-", 1)[1])[0]
            except openreview_fetch.OpenReviewFetchError:
                orv = None
        dates = [d[:10] for d in (arxiv, orv) if d]
        return (min(dates) if dates else None), {"arxiv_v1": arxiv[:10] if arxiv else None, "openreview_public": orv}

    def stage_background(self, state):
        """v4 background stage with the corrected cutoff (see background_cutoff)."""
        pdir = self.paper_dir(state["project_id"])
        adj = read_json(pdir / "adjudication" / "adjudication.json")
        requested = list(adj["requested_task_types"])
        notes, artifacts = [], {}
        if {"LIT", "IDEA"} & set(requested):
            cutoff, basis = self.background_cutoff(pdir)
            if not cutoff or not adj["background_requests"]:
                found = 0
                notes.append("no cutoff date or no background requests")
            else:
                reqs = [{"request_id": "bg%03d" % i, "title": r["title"], "arxiv_id": r["arxiv_id"], "cutoff_date": cutoff}
                        for i, r in enumerate(adj["background_requests"])]
                manifest = self.sources.fetch_background(reqs, pdir / "background", base_dir=pdir)
                found = sum(1 for s in manifest["sources"] if s["role"] == "background_paper")
                artifacts["background_manifest"] = "background/manifest.json"
                notes.append("%d of %d background works fetched before %s (cutoff basis %s)" % (found, len(reqs), cutoff, basis))
            if found < self.config()["min_background_found"]:
                requested = [t for t in requested if t not in ("LIT", "IDEA")]
                notes.append("controller rule: LIT/IDEA withdrawn, fewer than %d background works" % self.config()["min_background_found"])
                state["flags"].append("lit_idea_withdrawn_insufficient_background")
        write_json(pdir / "background_decision.json", {"requested_task_types": requested})
        artifacts["decision"] = "background_decision.json"
        self._record(state, "background", DONE if requested else "dropped", artifacts, notes=notes)

    @staticmethod
    def _check_ids(out, project_id, manifest):
        """v5 check, plus (user decision 2026-10-01, option A) a citation may name a controller-published paper metadata
        file of the workspace (source_manifest.json: version dates; candidate.json: OpenReview abstract; source_audit.json);
        every other unknown source_id still fails."""
        def strip(node):
            if isinstance(node, dict):
                if node.get("source_id") in METADATA_CITATIONS and "locator" in node:
                    return None
                return {k: strip(v) for k, v in node.items()}
            if isinstance(node, list):
                return [x for x in (strip(v) for v in node) if x is not None]
            return node
        return factory_v5.FactoryV5._check_ids(strip(out), project_id, manifest)

    def stage_fetch(self, state):
        """v5 fetch (arXiv version history + HTML/PDF, repo at the conference-end commit) plus the OpenReview
        camera-ready PDF through the official API (user decision 2026-09-25: OpenReview first; arXiv as backup and
        version/earliest-disclosure evidence). A paper with no usable arXiv version proceeds on the OpenReview PDF."""
        from mrhbench.factory import ARXIV_FINAL, FETCH_FAILED
        from mrhbench.factory_sources import contained
        import openreview_fetch
        pid = state["project_id"]
        pdir = self.paper_dir(pid)
        manifest = self.sources.fetch_paper_sources(self._candidate(pid), pdir, conference_end=self.config()["conference_end"])
        forum = pid.split("-", 1)[1]
        target = contained(pdir / "sources" / "files", "openreview_paper.pdf")
        try:
            rec = openreview_fetch.fetch_pdf(forum, target)
            manifest["sources"].append({"source_id": "openreview_paper_pdf", "url": rec["url"], "version": "openreview camera-ready (as served %s)" % rec["fetched_at"],
                                        "sha256": file_hash(target), "bytes": rec["bytes"], "role": "paper_pdf",
                                        "local_path": target.relative_to(pdir.resolve()).as_posix()})
            text_path = contained(pdir / "sources" / "files", "openreview_paper.txt")
            text_path.write_bytes(openreview_fetch.pdf_text(target))
            manifest["sources"].append({"source_id": "openreview_paper_text", "url": rec["url"],
                                        "version": "controller pypdf text extraction of openreview_paper_pdf sha256 " + rec["sha256"],
                                        "sha256": file_hash(text_path), "bytes": text_path.stat().st_size, "role": "paper_text_derived",
                                        "local_path": text_path.relative_to(pdir.resolve()).as_posix()})
            manifest["openreview"] = {**rec, "status": "fetched",
                                      "note": "OpenReview serves the current camera-ready; revisions after the conference are possible and not detected here"}
        except openreview_fetch.OpenReviewFetchError as e:
            manifest["openreview"] = {"status": "failed", "forum_id": forum, "detail": str(e)}
        write_json(pdir / "sources" / "manifest.json", manifest)
        roles = {s["role"] for s in manifest["sources"]}
        arxiv_status = manifest["arxiv"]["status"]
        status = DONE if roles & {"paper_html", "paper_pdf"} else ("blocked_source" if arxiv_status in ARXIV_FINAL else FETCH_FAILED)
        notes = ["openreview %s; arxiv %s" % (manifest["openreview"]["status"], arxiv_status)]
        if status != DONE:
            notes.append("no paper full text fetched")
        self._record(state, "fetch", status, {"source_manifest": "sources/manifest.json"}, notes=notes)

    def stage_compile(self, state):
        from mrhbench.factory_runtime import DEFAULT_BUDGETS
        from mrhbench.artifact_policy import make_collection_policy
        from mrhbench.material_adapter import task_container
        frozen = read_json(BUDGET_FREEZE)["frozen_model_calls"]
        out, wdir = self.final_output(state), self.wdir(state)
        package, request = read_json(out / "package.json"), read_json(out.parent / "request.json")
        resources = package["environment"]["resources"]
        budgets, collections = {}, {}
        for t in package["tasks"]:
            d = DEFAULT_BUDGETS[t["task_type"]]
            budgets[t["task_id"]] = {"model_calls": frozen[t["task_type"]], "tool_calls": d["tool_calls"],
                                     "wall_seconds": task_container(t, resources)["wall_seconds"]}
            collections[t["task_id"]] = make_collection_policy(max_total_bytes=d["collection"][0], max_entries=d["collection"][1])
        record = factory_v5.compile_identity_release(out, wdir / "release", self.identity_map(state),
                                                     runtime_record=read_json(wdir / "runtime" / "runtime_record.json"),
                                                     package_slug=self.package_slug(state), source_manifest=request["sources"],
                                                     execution_budgets=budgets, artifact_collections=collections,
                                                     per_task_resources=True)
        lint = [task_platform_lint.lint(p.parent) for p in sorted((wdir / "release/compiled").glob("task-*/task.json"))]
        n = sum(len(r["findings"]) for r in lint)
        write_json(wdir / "platform_lint.json", {"lint_sha256": file_hash(Path(task_platform_lint.__file__)),
                                                 "budget_freeze_sha256": file_hash(BUDGET_FREEZE), "tasks": lint})
        notes = ["%d task(s) in private review staging; semantic gates pending" % len(record["releases"]),
                 "platform lint: %d finding(s)%s" % (n, " -> maintenance repair queue" if n else "")]
        self._record(state, "compile", DONE, {"identity_release": "release/identity_release_record.json",
                                              "platform_lint": "platform_lint.json"}, notes=notes)


def open_factory(root, max_calls=0, native=None):
    """factory_v5.open_factory with FactoryV6. factory_v5.FactoryV5 itself must stay bound to the v5 class:
    its methods call super(FactoryV5, self), which recursed forever when the name was rebound to the
    subclass (bug in this driver's first version, 2026-10-01; 3 review adjudications failed before any call)."""
    from mrhbench import factory_sources
    from mrhbench import factory_runtime
    from mrhbench.factory import CallBudget
    root = Path(root)
    return FactoryV6(root, native_factory=native or factory_v5.native_factory(root), sources=factory_sources,
                     runtime=factory_runtime, budget=CallBudget(max_calls))


factory_v5.open_factory = open_factory  # main()/cmd_init look the name up at call time

def main():
    """factory_v5 CLI plus `run --workers N` (papers advance in parallel threads; default 1 as before)."""
    import argparse
    import json as _json
    if len(sys.argv) > 1 and sys.argv[1] == "run" and "--workers" in sys.argv:
        p = argparse.ArgumentParser()
        p.add_argument("cmd")
        p.add_argument("--root", required=True)
        p.add_argument("--papers", required=True)
        p.add_argument("--stages", default=",".join(factory_v5.ALL_STAGES))
        p.add_argument("--units")
        p.add_argument("--max-calls", type=int, required=True)
        p.add_argument("--retry-platform", action="store_true")
        p.add_argument("--workers", type=int, required=True)
        a = p.parse_args()
        f = open_factory(a.root, a.max_calls)
        out = f.run_papers(a.papers.split(","), stages=tuple(a.stages.split(",")), workers=a.workers,
                           retry_platform=a.retry_platform, units=a.units.split(",") if a.units else None)
        print(_json.dumps({"results": out, "calls_taken": f.budget.used, "halted": f.halted, "workers": a.workers},
                          ensure_ascii=False, indent=1))
    else:
        factory_v5.main()


if __name__ == "__main__":
    main()
