"""One genuine solver + independent judge + public-only feedback development case.

Only the whitelisted WRITE task reaches the fresh solver context. This hand-written
minimal baseline is NOT builder-generated H0 and is NOT a formal benchmark run.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from mrhbench.costs import CallLedger
from mrhbench.io import canonical, digest, read_json, write_json
from mrhbench.judge_runner import evidence_record, run_judge
from mrhbench.materials import export_task, load_task
from mrhbench.providers import CodexJSONTransport


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.output.exists():
        raise ValueError("Use a new run directory; never rerun uncertain active work blindly")
    args.output.mkdir(parents=True)
    config = read_json(root/"config/development.json")
    client = CodexJSONTransport(binary=args.codex_binary, model=config["executor"]["model"], reasoning_effort=config["executor"]["reasoning_effort"],
                              ledger=CallLedger(root/"audit/development_call_ledger.json"), audit_root=root/"audit/model_calls")
    package = root/"materials/ssa_write_content"
    task = load_task(package/"task.json")
    export = args.output/"solver-input"
    export_task(task, package, export, audience="development_executor")
    view = read_json(export/"task.json")
    assets = {a["asset_id"]: read_json(export/a["path"]) for a in view["asset_manifest"]}
    request = {"role": "research_executor", "task_view": view, "input_assets": assets,
               "instruction": "Complete this WRITE_CONTENT task using only the supplied inputs. No tool calls, file reads or internet needed. Return passage and claim-to-source map in the requested JSON."}
    schema = {"type": "object", "additionalProperties": False, "properties": {"research_passage": {"type": "string"},
              "claim_source_map": {"type": "array", "items": {"type": "object", "additionalProperties": False,
              "properties": {"claim": {"type": "string"}, "source_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["claim", "source_ids"]}}}, "required": ["research_passage", "claim_source_map"]}
    reply = client.complete(request, output_schema=schema, role="executor")
    write_json(args.output/"submission.json", reply["response"])
    write_json(args.output/"solver_run.json", {**reply, "request_hash": digest(request), "task_manifest_hash": digest(task),
               "harness_kind": "hand_written_minimal_development_baseline_not_builder_H0", "gpu_used": False})
    records = [evidence_record("task", "task", canonical(view).decode()),
               evidence_record("input-facts", "reference", canonical(assets).decode()),
               evidence_record("submission", "submission", canonical(reply["response"]).decode()),
               evidence_record("platform", "platform_trace", canonical({"event": "model_generated_submission", "call_id": reply["call_id"], "usage": reply["usage"], "request_hash": digest(request), "no_research_experiment_claimed": True}).decode()),
               evidence_record("private-evaluation", "reference", canonical(read_json(package/"private/evaluation.json")).decode(), visibility="private")]
    scored = run_judge(client=client, task_id=task["task_id"], task_type=task["task_type"], records=records, output=args.output/"score", max_steps=5)
    if scored["status"] == "scored":
        run_judge(client=client, task_id=task["task_id"], task_type=task["task_type"], records=records,
                  output=args.output/"feedback", mode="feedback", dimension_scores=scored["dimension_scores"], max_steps=5)
    print({"status": "development_run_finished_needs_direct_trajectory_review", "output": str(args.output), "model": config["executor"]["model"]})
