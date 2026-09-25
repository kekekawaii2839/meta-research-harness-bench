"""CLI for the standard material factory (AGENTS §0.2.16). See mrhbench/factory.py for the stages.

Model commands (triage, run) require an explicit --max-calls cap on top of the shared ledger's
global authorization. The factory root must live outside any tree holding AGENTS.md/CLAUDE.md,
e.g. D:/mrhbench-local-pilot/factory-v1. Typical order:

  init -> pool -> triage -> select -> (user reads selection.md) approve-selection --by <user>
  -> run --stages fetch,source_audit,... -> status / review-queue
"""
import argparse
import json
from pathlib import Path

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench import factory_sources
from mrhbench.claude_transport import ClaudeNativeRunner
from mrhbench.costs import CallLedger
from mrhbench.factory import PAPER_STAGES, CallBudget, Factory
from mrhbench.io import ProtocolError, file_hash, read_json

ROOT = Path(__file__).resolve().parents[2]
TIMEOUTS = {"scout": 900, "source_auditor": 1800, "adjudicator": 1800, "constructor": 1800, "material_reviewer": 1800}


def make_pilot(harness: Path, harness_sha256: str, roles_path: Path):
    """P11: each compiled task runs once with the frozen H0, the configured executor and the judge. No retries."""
    from mrhbench.stage_controller import run_stage
    if file_hash(harness) != harness_sha256:
        raise ProtocolError("Frozen H0 hash mismatch")
    roles = read_json(roles_path)

    def pilot(state, paper_dir, budget):
        rows, calls, flags = [], [], []
        for task_dir in sorted(p.parent for p in (paper_dir / "compiled").glob("*/task.json")):
            task = read_json(task_dir / "task.json")
            budget.take(task["public"]["resources"]["execution_budget"]["model_calls"] + 1)
            out = paper_dir / "pilot" / task_dir.name
            try:
                r = run_stage(task_dir, harness, out, Path(roles["claude_binary_default"]), roles=roles)
                judge = out / "judge_run_result.json"
                j = read_json(judge) if judge.is_file() else {}
                row = {"task_id": task.get("task_id"), "status": r["submission_status"], "judge_status": j.get("status"),
                       "quality_score": j.get("quality"), "dimension_scores": j.get("dimension_scores"), "run_dir": str(out)}
                if r["submission_status"] != "completed":
                    flags.append("pilot_submission_%s:%s" % (r["submission_status"], task_dir.name))
                if j.get("quality") is None:
                    flags.append("pilot_no_judge_score:" + task_dir.name)
                elif j["quality"] < 1.0:
                    flags.append("pilot_low_quality:" + task_dir.name)
            except Exception as exc:
                row = {"task_id": task.get("task_id"), "status": "stage_failed", "error": "%s: %s" % (type(exc).__name__, str(exc)[:500])}
                flags.append("pilot_stage_failed:" + task_dir.name)
            rows.append(row)
        return {"schema_version": "factory-pilot-1", "harness": str(harness), "harness_sha256": harness_sha256,
                "roles_sha256": file_hash(roles_path), "results": rows, "flags": flags, "calls": calls, "retry": False,
                "note": "One development run per task; ledger call ids live in each run's broker/judge records."}
    return pilot


def build(args, max_calls=0):
    roles = read_json(args.roles)
    spec = roles["constructor"]
    ledger = CallLedger(ROOT / "audit/development_call_ledger.json")

    def runner(role):
        return ClaudeNativeRunner(binary=Path(roles["claude_binary_default"]), model=spec["model"], reasoning_effort=spec["effort"],
                                  ledger=ledger, audit_root=args.root.resolve() / "native_calls" / role,
                                  timeout_seconds=TIMEOUTS[role], tool_profile="material_workspace")
    try:
        from mrhbench import factory_runtime as runtime
    except ImportError:
        runtime = None
    pilot = None
    if getattr(args, "harness", None):
        pilot = make_pilot(args.harness, args.harness_sha256, args.roles)
    return Factory(args.root, templates=ROOT / "prompts", runner_factory=runner, sources=factory_sources, runtime=runtime,
                   budget=CallBudget(max_calls), pilot=pilot)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--roles", type=Path, default=ROOT / "config/role_transport_claude_v2.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").add_argument("--config", type=Path, help="JSON overrides of DEFAULT_CONFIG")
    sub.add_parser("pool").add_argument("--no-readmes", action="store_true")
    t = sub.add_parser("triage")
    t.add_argument("--max-calls", type=int, required=True)
    t.add_argument("--workers", type=int, default=2)
    t.add_argument("--retry-platform", action="store_true", help="Re-run batches that hit a provider rate limit (failed attempt kept)")
    sub.add_parser("select")
    sub.add_parser("approve-selection").add_argument("--by", required=True, help="Name of the person who read selection.md")
    r = sub.add_parser("run")
    r.add_argument("--max-calls", type=int, required=True)
    r.add_argument("--papers", default="all", help="'all' or comma-separated project ids from the approved selection")
    r.add_argument("--stages", default=",".join(PAPER_STAGES))
    r.add_argument("--workers", type=int, default=2)
    r.add_argument("--harness", type=Path, help="Frozen H0 harness.py for the pilot stage")
    r.add_argument("--harness-sha256")
    r.add_argument("--retry-platform", action="store_true", help="Re-run stages that hit a provider rate limit (failed attempt kept)")
    sub.add_parser("status")
    sub.add_parser("review-queue")
    a = p.parse_args()
    if a.cmd in ("triage", "run") and not 1 <= a.workers <= 4:
        raise ProtocolError("Between 1 and 4 workers")
    f = build(a, getattr(a, "max_calls", 0))
    if a.cmd == "init":
        out = f.init(read_json(a.config) if a.config else None)
    elif a.cmd == "pool":
        out = factory_sources.build_pool(ROOT.parent / "aiml/iclr2025_pilot/candidate_index.jsonl",
                                         ROOT.parent / "source_cache/iclr2025_pilot/iclr-2025-orals-posters.json",
                                         a.root / "pool", fetch_readmes=not a.no_readmes)
    elif a.cmd == "triage":
        out = f.run_triage(workers=a.workers, retry_platform=a.retry_platform)
    elif a.cmd == "select":
        out = f.select()
        out = {k: out[k] for k in ("triaged", "eligible", "quotas_target", "quotas_reached")} | {"selected": len(out["papers"]),
               "read": str(a.root / "selection.md")}
    elif a.cmd == "approve-selection":
        out = f.approve_selection(a.by)
    elif a.cmd == "run":
        papers = f.approved_papers() if a.papers == "all" else a.papers.split(",")
        stages = tuple(s for s in a.stages.split(",") if s)
        if set(stages) - set(PAPER_STAGES):
            raise ProtocolError("Unknown stage")
        out = f.run_papers(papers, stages=stages, workers=a.workers, retry_platform=a.retry_platform)
    elif a.cmd == "status":
        out = f.status()
    else:
        out = f.review_queue()
    print(json.dumps(out, ensure_ascii=False, indent=1)[:20000])


if __name__ == "__main__":
    main()
