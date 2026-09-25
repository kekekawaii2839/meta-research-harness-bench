"""Run the unified handwritten development baseline on a released stage task.

Not a formal evaluation, not a builder-generated harness, and no CPU/GPU code
execution. EXP/figure runtime acceptance must use a separately accepted adapter.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import base64
import sys
import time

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.baseline import run
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, TraceLog, canonical, digest, read_json, write_json
from mrhbench.judge_runner import evidence_record, run_judge
from mrhbench.literature import LiteratureService
from mrhbench.materials import export_task, load_task
from mrhbench.providers import CodexJSONTransport
from mrhbench.sdk import Budget, ExecutorClient, TaskTools, validate_submission
from mrhbench.cpu_runner import ReviewedCPURunner
from mrhbench.numeric_checks import check_display_ledger


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--codex-binary", type=Path, required=True)
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--model-steps", type=int, default=7)
    p.add_argument("--skip-judges", action="store_true")
    p.add_argument("--reviewed-cpu", action="store_true", help="Opt in to manual hash-bound CPU review, never formal isolation")
    p.add_argument("--resume-failed-call", type=int, help="Explicit development recovery after verified terminal transport failure; keeps previous costs and same task state")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    task = load_task(args.package/"task.json")
    if task["task_type"] not in {"LIT", "IDEA", "WRITE_CONTENT"} and not args.reviewed_cpu:
        raise ProtocolError("Current live development runner lacks EXP/WRITE_EVIDENCE execution acceptance")
    if (args.output.exists() and args.resume_failed_call is None) or not 1 <= args.model_steps <= 10:
        raise ProtocolError("Fresh output and 1–10 model steps required")
    args.output.mkdir(parents=True, exist_ok=args.resume_failed_call is not None)
    config = read_json(root/"config/development.json")
    provider = CodexJSONTransport(binary=args.codex_binary, model=config["executor"]["model"], reasoning_effort=config["executor"]["reasoning_effort"],
                                  ledger=CallLedger(root/"audit/development_call_ledger.json"), audit_root=root/"audit/model_calls")
    public = args.output/"public-input"
    if args.resume_failed_call is None:
        export_task(task, args.package, public, audience="development_executor")
    view = read_json(public/"task.json")
    trace = TraceLog(args.output/"platform.jsonl")
    corpus = task["private"].get("corpus_configuration")
    literature = None
    if corpus:
        literature = LiteratureService(read_json(root.parents[1]/corpus["corpus_manifest"])["documents"], root.parents[1],
                                       corpus["cutoff"], set(corpus["excluded_papers"]))
    history = None
    if args.resume_failed_call is not None:
        ledger = read_json(root/"audit/development_call_ledger.json")
        row = next(r for r in ledger["attempts"] if r["id"] == args.resume_failed_call)
        if row["status"] not in {"failed", "timeout"} or row["role"] != "executor" or (args.output/"submission.json").exists():
            raise ProtocolError("Resume requires a verified failed executor transport, not running/completed work")
        envelope = read_json(Path(row["artifact_directory"])/"request.json")
        prior = envelope["request"]
        events = trace.read()
        requests = [e for e in events if e["kind"] == "executor_requested"]
        if prior["task_view"] != view or requests[-1]["payload"]["request_hash"] != digest(prior) or digest(envelope) != row["request_hash"]:
            raise ProtocolError("Resume request does not match last observed task request")
        failure = read_json(args.output/"failure.json")
        remain = failure["budget"]
        if remain["model_calls"] <= 0 or remain["tool_calls"] <= 0:
            raise ProtocolError("Original task budget has no remaining attempts")
        wall = remain["wall_seconds"] - max(0,time.time()-(args.output/"failure.json").stat().st_mtime)
        budget = Budget(model_calls=remain["model_calls"], tool_calls=remain["tool_calls"], wall_seconds=wall)
        history = prior["history"]
        trace.append("explicit_transport_recovery", {"failed_call_id": row["id"], "request_hash": digest(prior), "remaining_budget": budget.remaining(), "prior_costs_retained": True})
    else:
        budget = Budget(model_calls=args.model_steps, tool_calls=50,
                        wall_seconds=view["resources"].get("development_wall_time_seconds", 2400))
    tools = TaskTools(view=view, input_root=public, output_root=args.output/"artifacts", budget=budget, trace=trace, literature=literature, resume_output=args.resume_failed_call is not None)
    if args.reviewed_cpu:
        tools.cpu_runner = ReviewedCPURunner(python=Path(sys.executable), audit_root=args.output/"cpu_jobs", input_root=public, artifacts=args.output/"artifacts")
    try:
        submission = validate_submission(run(view, ExecutorClient(provider, budget, trace), tools, budget, initial_history=history), tools)
    except Exception as exc:
        failure_path = args.output/(f"failure_after_resume_{args.resume_failed_call}.json" if args.resume_failed_call is not None else "failure.json")
        write_json(failure_path, {"status": "development_runtime_failure", "type": type(exc).__name__, "reason": str(exc), "budget": budget.remaining()})
        raise
    write_json(args.output/"submission.json", submission)
    trace.append("submission_accepted_structurally", {"submission_hash": digest(submission), "remaining_budget": budget.remaining()})
    records = [evidence_record("task", "task", canonical(view).decode()),
               evidence_record("submission", "submission", canonical(submission).decode()),
               evidence_record("platform", "platform_trace", (args.output/"platform.jsonl").read_text(encoding="utf-8"))]
    for asset in view["asset_manifest"]:
        records.append(evidence_record("input-" + asset["asset_id"], "reference", (public/asset["path"]).read_text(encoding="utf-8")))
    for asset in task["assets"]:
        if asset["visibility"] == "private":
            records.append(evidence_record("private-" + asset["asset_id"], "reference", (args.package/asset["path"]).read_text(encoding="utf-8"), visibility="private"))
    for i, artifact in enumerate(submission["artifacts"]):
        file = args.output/"artifacts"/artifact["path"]
        if file.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            records.append(evidence_record(f"artifact-{i}", "rendered_artifact", base64.b64encode(file.read_bytes()).decode(), media_type="image/png" if file.suffix.lower()==".png" else "image/jpeg"))
        elif file.suffix.lower() in {".json", ".py", ".csv", ".txt", ".md", ".svg", ".tex"}:
            records.append(evidence_record(f"artifact-{i}", "submission", "ARTIFACT PATH: " + artifact["path"] + "\n" + file.read_text(encoding="utf-8")))
    if task["task_type"] == "WRITE_EVIDENCE":
        numeric_asset = next(a for a in view["asset_manifest"] if a["asset_id"] == "numeric-evidence")
        ledgers = [a for a in submission["artifacts"] if Path(a["path"]).name == "displayed_values.json"]
        try:
            ledger = read_json(args.output/"artifacts"/ledgers[0]["path"]) if len(ledgers) == 1 else None
        except (ValueError, UnicodeError):
            ledger = None
        check = check_display_ledger(read_json(public/numeric_asset["path"]), ledger)
        write_json(args.output/"numeric_check.json", check)
        records.append(evidence_record("numeric-check", "program_check", canonical(check).decode()))
    write_json(args.output/"evidence.json", records)
    write_json(args.output/"run.json", {"task_id": task["task_id"], "task_hash": digest(task), "harness_kind": "handwritten_unified_baseline_not_builder_H0",
                                       "gpu_used": False, "formal": False, "budget": budget.remaining(), "judge_acceptance": "pending_manual_trajectory_review"})
    if not args.skip_judges:
        result = run_judge(client=provider, task_id=task["task_id"], task_type=task["task_type"], records=records, output=args.output/"score", max_steps=5, max_text_chars=400000)
        if result["status"] == "scored":
            run_judge(client=provider, task_id=task["task_id"], task_type=task["task_type"], records=records, output=args.output/"feedback", mode="feedback", dimension_scores=result["dimension_scores"], max_steps=5, max_text_chars=400000)
    print({"status": "development_only_needs_manual_review", "output": str(args.output)})
