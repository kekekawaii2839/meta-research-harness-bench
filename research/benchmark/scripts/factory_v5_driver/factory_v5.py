"""Production material factory v5 (2026-09-27): factory v4 stages + the v5-validated quality bundle.

Composes existing, already-tested mrhbench modules without editing them:
  * prompts: frozen snapshot of research/benchmark/prompts with the efficiency-v3 overlays
    (policy-efficiency-3 incl. J every-run coverage; v3 review/repair/adjudicator prompts) and the
    review-adjudication schema bound to the policy's rule ids (material_policy_schema);
  * every material role (constructor / material_reviewer / adjudicator) is wrapped exactly like the
    v5 paired trial: DecisionGuidance -> QualityBound -> IdentityBound (controller-allocated opaque
    task id per unit) -> PagedNavigation; repair rounds additionally use incremental repair
    (seed prior output, diff navigation, full-policy re-review) and the optional read-batching advice;
  * compile goes through compile_identity_release (explicit budgets, final known-identity scan);
    releases stay private review staging, all semantic gates pending.
Paper-level stages (fetch/source_audit/adjudication/background/repo_files/external_data) are the
unchanged factory v4 code. No automatic retry; the first provider 429 halts the invocation.
"""
from pathlib import Path
import argparse
import json
import shutil
import sys

BENCH = Path(r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
sys.path.insert(0, str(BENCH))

from mrhbench.io import ProtocolError, read_json, write_json, file_hash  # noqa: E402
from mrhbench.factory import Factory, CallBudget, ALL_STAGES, DONE, UNIT_ORDER  # noqa: E402
from mrhbench.material_batch import MATERIAL_PROMPT_SUFFIX, run_batch  # noqa: E402
from mrhbench.material_quality_runner import QualityBoundRunner  # noqa: E402
from mrhbench.material_identity_runner import IdentityBoundRunner  # noqa: E402
from mrhbench.paged_navigation_runner import PagedNavigationRunner  # noqa: E402
from mrhbench.material_decision_guidance import DecisionGuidanceRunner  # noqa: E402
from mrhbench.evidence_read_batching import EvidenceReadBatchingRunner  # noqa: E402
from mrhbench.material_policy_schema import bind_policy_rules  # noqa: E402
from mrhbench.material_public_identity import allocate_map, _identity as identity_of  # noqa: E402
from mrhbench.material_identity_release import compile_identity_release  # noqa: E402
from mrhbench.factory_efficiency_v4 import OVERLAYS  # noqa: E402

MATERIAL_ROLES = {"constructor", "material_reviewer", "adjudicator"}
ROUND_OF_BATCH = {"construct": 1, "repair": 2, "repair2": 3}
TIMEOUTS = {"scout": 900, "source_auditor": 1800, "adjudicator": 1800, "constructor": 1800, "material_reviewer": 1800}
LEDGER = BENCH / "audit/development_call_ledger.json"
ROLES = BENCH / "config/role_transport_claude_v2.json"


def build_prompt_snapshot(dest: Path):
    """Frozen prompt tree: original prompts + v3 overlays + policy-bound adjudication schema."""
    if dest.exists():
        raise ProtocolError("Prompt snapshot exists; a factory root freezes its prompts once")
    shutil.copytree(BENCH / "prompts", dest)
    rows = []
    for target_rel, source_rel in OVERLAYS.items():
        shutil.copyfile(BENCH / "prompts" / source_rel, dest / target_rel)
        rows.append({"target": target_rel, "source": source_rel, "sha256": file_hash(dest / target_rel)})
    policy = (dest / "factory_v4/policy.md").read_bytes()
    schema, binding = bind_policy_rules(read_json(BENCH / "prompts/factory_v4/review_adjudication.schema.json"), policy)
    write_json(dest / "factory_v4/review_adjudication.schema.json", schema)
    return {"overlays": rows, "policy_schema_binding": binding}


class FactoryV5(Factory):
    def __init__(self, root, *, native_factory, **kwargs):
        self._ctx = None
        self._native = native_factory
        super().__init__(root, templates=Path(root) / "prompts_snapshot", runner_factory=self._compose, **kwargs)

    # ------------------------------------------------------------ role wrapping
    def _compose(self, role):
        inner = self._native(role)
        ctx = self._ctx
        if ctx is None or role not in MATERIAL_ROLES:
            return inner  # paper-level stages: unchanged factory v4 behaviour
        if ctx["incremental"]:
            inner = EvidenceReadBatchingRunner(inner)
        inner = DecisionGuidanceRunner(inner)
        quality = QualityBoundRunner(inner, policy_path=self.templates / "factory_v4/policy.md",
                                     project_id=ctx["project_id"], round_no=ctx["round_no"])
        return PagedNavigationRunner(IdentityBoundRunner(quality, map_identity=ctx["map"]))

    def identity_map(self, state):
        """One controller-allocated random opaque task id per construction unit (reused by every round)."""
        base = self.wdir(state) / "private_identity"
        path = base / "map.json"
        if path.exists():
            return identity_of(path)
        pid, unit = state["project_id"], state["unit"]
        write_json(base / "seed" / "package.json", {
            "paper_id": pid, "tasks": [{"task_id": "%s__%s-01" % (pid, unit), "task_type": unit}],
            "note": "Controller seed for opaque-id allocation only; not a material package."})  # map absent: seed may be rewritten
        aliases = [pid.split("-", 1)[1]] if "-" in pid else []
        if state.get("title"):
            aliases.append(state["title"])
        return allocate_map(base / "seed", path, aliases=aliases)

    def build_job(self, state):
        """A user-approved rebuild of a dropped unit carries the previous drop reason as a binding note."""
        job = super().build_job(state)
        notes = self.wdir(state) / "rebuild_notes.md" if state.get("unit") else None
        if notes is not None and notes.is_file():
            job["scope_request"] += ("\n\nREBUILD NOTE (a previous construction of this unit was dropped at review "
                                     "adjudication; avoid repeating the recorded defect):\n" + notes.read_text(encoding="utf8"))
        return job

    def _with_ctx(self, state, round_no, incremental, fn):
        self._ctx = {"project_id": state["project_id"], "round_no": round_no, "incremental": incremental,
                     "map": self.identity_map(state)}
        try:
            return fn()
        finally:
            self._ctx = None

    # ------------------------------------------------------------ batches
    def _batch(self, state, batch_root, repair_from=None, repair_notes=None, job_name="job.json"):
        if not state.get("unit"):
            raise ProtocolError("Factory v5 runs per-task construction units only")
        pdir, wdir = self.paper_dir(state["project_id"]), self.wdir(state)
        job = self.build_job(state)
        write_json(wdir / job_name, job)
        self.check_prompts()
        round_no = ROUND_OF_BATCH[batch_root.name]
        continuation = self._continuation_source(job, batch_root)
        if continuation is not None:
            from mrhbench.factory import CONTINUATION_NOTE
            from mrhbench.io import utc_now
            notes = list((repair_notes or {}).get(job["job_id"], [])) + [CONTINUATION_NOTE]
            repair_from, repair_notes = continuation, {job["job_id"]: notes}
            state.setdefault("continuations", []).append({"batch": batch_root.name, "from": continuation.name, "at": utc_now()})
            self._save(state)
        incremental = repair_from is not None
        self.budget.take(2)

        def go():
            return run_batch([job], workspace=pdir, batch_root=batch_root, templates=self.templates,
                             constructor=self.runner("constructor"), reviewer=self.runner("material_reviewer"),
                             max_workers=1, max_jobs=1, controller_hash_fill=True,
                             prompt_suffix=MATERIAL_PROMPT_SUFFIX + (self.factory_templates / "constructor_addendum.txt").read_text(encoding="utf8"),
                             repair_from=repair_from, repair_notes=repair_notes, incremental_repair=incremental)
        result = self._with_ctx(state, round_no, incremental, go)
        return job, result["jobs"][0]

    def stage_construct(self, state):
        super().stage_construct(state)
        rec = state["stages"].get("construct", {})
        msg = " ".join(rec.get("notes", []))
        # A completed construction rejected only by the deterministic known-identity scan goes to the single
        # repair round (same rule as the v2 structural-gate routing), instead of discarding the paid construction.
        # material_public_identity raises "...remains in public surface: ..." (facts/contracts/text/JSON assets) or
        # "...remains in public asset bytes: ..." (literal byte match, checked first for every asset); route both.
        if rec.get("status") == "failed_needs_attribution" and "Known private identity remains in public" in msg:
            wdir = self.wdir(state)
            note = ("The controller's deterministic identity scan rejected the previous package: " + msg +
                    ". Remove every source-identifying string (paper title, OpenReview/arXiv id, repository or method "
                    "names specific to the source paper) from all public facts, contracts, filenames and public asset "
                    "bytes, keeping the scientific content faithful. Use exactly the task ids in identity_assignment.json.")
            write_json(wdir / "review_adjudication" / "review_adjudication.json", {
                "schema_version": "factory-review-adjudication-1", "project_id": state["project_id"], "round": 1,
                "finding_decisions": [], "action": "repair", "repair_notes": [note], "drop_reason": None,
                "excluded_task_ids": [], "author": "controller_identity_scan"}, exclusive=True)
            self._record(state, "construct", DONE, rec.get("artifacts"), rec.get("calls", []),
                         rec.get("notes", []) + ["identity scan failure routed to repair (no model call)"])
            self._record(state, "review_adjudication", DONE, {"review_adjudication": "review_adjudication/review_adjudication.json"},
                         notes=["controller: identity scan failure routed to the single repair round (no model call)"])

    def _review_adjudication(self, state, stage, batch_dir, round_no):
        return self._with_ctx(state, round_no, round_no > 1,
                              lambda: super(FactoryV5, self)._review_adjudication(state, stage, batch_dir, round_no))

    def _resume_reviewer_only(self, job, batch_root):
        return None  # v5: reviewer-only resume would bypass the quality/identity wrappers; rerun the batch instead

    # ------------------------------------------------------------ compile
    def stage_compile(self, state):
        from mrhbench.factory_runtime import DEFAULT_BUDGETS
        from mrhbench.artifact_policy import make_collection_policy
        from mrhbench.material_adapter import task_container
        out = self.final_output(state)
        wdir = self.wdir(state)
        package = read_json(out / "package.json")
        request = read_json(out.parent / "request.json")
        resources = package["environment"]["resources"]
        budgets, collections = {}, {}
        for t in package["tasks"]:
            d = DEFAULT_BUDGETS[t["task_type"]]
            budgets[t["task_id"]] = {"model_calls": d["model_calls"], "tool_calls": d["tool_calls"],
                                     "wall_seconds": task_container(t, resources)["wall_seconds"]}
            collections[t["task_id"]] = make_collection_policy(max_total_bytes=d["collection"][0], max_entries=d["collection"][1])
        record = compile_identity_release(out, wdir / "release", self.identity_map(state),
                                          runtime_record=read_json(wdir / "runtime" / "runtime_record.json"),
                                          package_slug=self.package_slug(state), source_manifest=request["sources"],
                                          execution_budgets=budgets, artifact_collections=collections,
                                          per_task_resources=True)
        self._record(state, "compile", DONE, {"identity_release": "release/identity_release_record.json"},
                     notes=["%d task(s) in private review staging; semantic gates pending" % len(record["releases"])])


def native_factory(root):
    from mrhbench.claude_transport import ClaudeNativeRunner
    from mrhbench.costs import CallLedger
    roles = read_json(ROLES)
    spec = roles["constructor"]
    ledger = CallLedger(LEDGER)

    def make(role):
        return ClaudeNativeRunner(binary=Path(roles["claude_binary_default"]), model=spec["model"], reasoning_effort=spec["effort"],
                                  ledger=ledger, audit_root=Path(root).resolve() / "native_calls" / role,
                                  timeout_seconds=TIMEOUTS[role], tool_profile="material_workspace")
    return make


def open_factory(root, max_calls=0, native=None):
    from mrhbench import factory_sources
    from mrhbench import factory_runtime
    root = Path(root)
    return FactoryV5(root, native_factory=native or native_factory(root), sources=factory_sources,
                     runtime=factory_runtime, budget=CallBudget(max_calls))


def cmd_init(args):
    root, src = Path(args.root), Path(args.from_root)
    if root.exists():
        raise ProtocolError("New factory root must not exist")
    for parent in (root, *root.parents):
        if any((parent / n).exists() for n in ("AGENTS.md", "CLAUDE.md")):
            raise ProtocolError("Factory root inherits maintainer instructions")
    root.mkdir(parents=True)
    snap = build_prompt_snapshot(root / "prompts_snapshot")
    for name in ("pool", "triage"):
        shutil.copytree(src / name, root / name)
    for name in ("selection.json", "selection.md", "selection_approval.json"):
        shutil.copyfile(src / name, root / name)
    cfg = {k: v for k, v in read_json(src / "factory.json").items()
           if k not in {"created_at", "policy_sha256", "prompt_hashes", "version_note"}}
    cfg["version_note"] = ("v5 production (2026-09-27): factory v4 stages + v5-validated bundle (policy-efficiency-3 with J "
                           "coverage, quality contract, opaque identity, paged navigation, decision guidance, incremental "
                           "repair rounds, identity-bound release). Pool/triage/selection/approval copied from " + str(src))
    cfg["prompt_snapshot"] = snap
    f = open_factory(root)
    f._factory_prompts = "factory_v4"
    out = f.init({**cfg, "factory_prompts": "factory_v4"})
    for pid in args.carry_fetch or []:
        from mrhbench.factory import slug
        s_dir, d_dir = src / "papers" / slug(pid), root / "papers" / slug(pid)
        shutil.copytree(s_dir / "sources", d_dir / "sources")
        st = read_json(s_dir / "state.json")
        write_json(d_dir / "state.json", {**st, "stages": {"fetch": st["stages"]["fetch"]}, "flags": [],
                                          "carried_fetch_from": str(s_dir)})
    return {"root": str(root), "approved_papers": len(f.approved_papers()), "config_policy": out["policy_sha256"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("--root", required=True)
    i.add_argument("--from-root", required=True)
    i.add_argument("--carry-fetch", nargs="*")
    r = sub.add_parser("run")
    r.add_argument("--root", required=True)
    r.add_argument("--papers", required=True)
    r.add_argument("--stages", default=",".join(ALL_STAGES))
    r.add_argument("--units")
    r.add_argument("--max-calls", type=int, required=True)
    r.add_argument("--retry-platform", action="store_true")
    s = sub.add_parser("status")
    s.add_argument("--root", required=True)
    a = p.parse_args()
    if a.cmd == "init":
        out = cmd_init(a)
    elif a.cmd == "run":
        f = open_factory(a.root, a.max_calls)
        out = f.run_papers(a.papers.split(","), stages=tuple(a.stages.split(",")), workers=1,
                           retry_platform=a.retry_platform, units=a.units.split(",") if a.units else None)
        out = {"results": out, "calls_taken": f.budget.used, "halted": f.halted}
    else:
        out = open_factory(a.root).status()
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
