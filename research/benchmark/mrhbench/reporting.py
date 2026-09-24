"""Observed development costs joined by recorded call IDs, never invented prices."""
from pathlib import Path

from .io import ProtocolError, digest, file_hash, read_json


def summarize_calls(ledger: dict, ids: list[int] | None = None):
    all_rows = {r["id"]: r for r in ledger["attempts"]}
    selected = sorted(all_rows) if ids is None else sorted(set(ids))
    if any(isinstance(i, bool) or i not in all_rows for i in selected):
        raise ProtocolError("Cost report references an unobserved call")
    roles = {}
    for id in selected:
        item = all_rows[id]
        role = item.get("role", "legacy_probe")
        row = roles.setdefault(role, {"call_ids": [], "statuses": {}, "observed_tokens": {}, "calls_missing_usage": [],
                                      "sum_observed_call_wall_seconds": 0.0, "calls_missing_wall_seconds": []})
        row["call_ids"].append(id)
        status = item["status"]
        row["statuses"][status] = row["statuses"].get(status, 0) + 1
        if item.get("usage") is None:
            row["calls_missing_usage"].append(id)
        else:
            for key, value in item["usage"].items():
                row["observed_tokens"][key] = row["observed_tokens"].get(key, 0) + value
        if item.get("wall_seconds") is None:
            row["calls_missing_wall_seconds"].append(id)
        else:
            row["sum_observed_call_wall_seconds"] += item["wall_seconds"]
    return {"call_ids": selected, "runs_including_failures": len(selected), "roles": roles,
            "call_records_digest": digest([all_rows[i] for i in selected]), "dollar_cost": None,
            "cost_basis": "subscription_no_observed_per_call_price", "missing_is_not_zero": True,
            "wall_time_note": "Sum of call durations is not elapsed run latency when calls overlap.",
            "token_note": "Cached-input and reasoning-token fields are subsets as defined by provider, not extra tokens to add again."}


def run_cost_report(run_root: Path, ledger: dict):
    ids, sources = set(), []
    for path in sorted(run_root.rglob("*.jsonl")):
        if path.name not in {"trace.jsonl", "platform.jsonl"}:
            continue
        from .io import parse_json
        for line in path.read_text(encoding="utf-8").splitlines():
            event = parse_json(line)
            payload = event.get("payload", {})
            if event.get("kind") in {"executor_completed", "judge_model_response"}:
                ids.add(payload["call_id"])
        sources.append({"path": path.relative_to(run_root).as_posix(), "sha256": file_hash(path)})
    old_solver = run_root/"solver_run.json"
    if old_solver.is_file():
        ids.add(read_json(old_solver)["call_id"])
        sources.append({"path": "solver_run.json", "sha256": file_hash(old_solver)})
    # A failed transport can stop before the controller receives a call ID.
    # Such calls remain in the global ledger; this report does not infer an
    # association from timestamps or silently attribute them to a run.
    cpu = []
    for p in sorted((run_root/"cpu_jobs").glob("*/result.json")):
        value = read_json(p)
        cpu.append({"job_id": value["job_id"], "status": value["status"], "wall_seconds": value.get("wall_seconds"),
                    "result_sha256": file_hash(p), "gpu_execution": value.get("gpu_execution", False)})
    return {"model": summarize_calls(ledger, list(ids)), "trace_sources": sources, "cpu_jobs": cpu,
            "limitations": ["Includes every recorded rejudge/feedback under this run directory; not a single frozen evaluation cost.",
                            "Transport failures without controller call IDs may be absent here; global ledger remains authoritative and counts all attempts.",
                            "Shared parent submissions in controlled mutations must not be counted as newly generated solver runs."]}
