"""Observed paired-trial costs; missing usage is unknown, never free.

No subscription dollar inference and no scientific quality decision. Constructor,
reviewer and adjudicator are aggregated together, including failed invocations.
"""
import json
from pathlib import Path

from .io import ProtocolError, file_hash, read_json


USAGE_KEYS = ("input_tokens", "cache_write_input_tokens", "cached_input_tokens", "output_tokens")


def trace_metrics(path):
    path = Path(path)
    if not path.is_file():
        return {"available": False}
    messages, tools, tool_messages = set(), {}, set()
    for line in path.read_text(encoding="utf8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("type") != "assistant":
            continue
        msg = event.get("message", {})
        mid = msg.get("id")
        if mid:
            messages.add(mid)
        for block in msg.get("content", []):
            if block.get("type") != "tool_use":
                continue
            tid = block.get("id")
            if not tid:
                raise ProtocolError("Tool event without identity")
            if tid in tools and tools[tid] != block:
                raise ProtocolError("Conflicting repeated tool event")
            tools[tid] = block
            if mid:
                tool_messages.add(mid)
    names = {}
    write_bytes = edit_bytes = 0
    for block in tools.values():
        name = block.get("name", "unknown")
        names[name] = names.get(name, 0) + 1
        args = block.get("input", {})
        if name == "Write" and isinstance(args.get("content"), str):
            write_bytes += len(args["content"].encode("utf8"))
        if name == "Edit" and isinstance(args.get("new_string"), str):
            edit_bytes += len(args["new_string"].encode("utf8"))
    return {"available": True, "sha256": file_hash(path),
            "assistant_messages": len(messages), "tool_bearing_messages": len(tool_messages),
            "tool_calls": len(tools), "tool_names": names,
            "write_content_utf8_bytes_requested": write_bytes,
            "edit_new_string_utf8_bytes_requested": edit_bytes,
            "note": "Requested tool payload, not successful filesystem writes or total disk growth."}


def summarize_calls(ledger_path, call_ids):
    if len(set(call_ids)) != len(call_ids):
        raise ProtocolError("Duplicate call ids would double-count cost")
    attempts = {a["id"]: a for a in read_json(ledger_path)["attempts"]}
    if not call_ids or any(i not in attempts for i in call_ids):
        raise ProtocolError("Explicit existing call ids required")
    rows = []
    for cid in call_ids:
        a = attempts[cid]
        usage = a.get("usage")
        complete = usage is not None and all(k in usage for k in USAGE_KEYS)
        rows.append({"call_id": cid, "role": a.get("role"), "status": a["status"],
                     "model": a.get("model"), "effort": a.get("reasoning_effort"),
                     "wall_seconds": a.get("wall_seconds"), "usage": usage,
                     "usage_complete": complete,
                     "trace": trace_metrics(Path(a["artifact_directory"]) / "events.jsonl")})
    usage_complete = all(r["usage_complete"] for r in rows)
    wall_complete = all(r["wall_seconds"] is not None for r in rows)
    observed = {k: sum((r["usage"] or {}).get(k, 0) for r in rows) for k in USAGE_KEYS}
    return {"calls": rows, "call_count": len(rows),
            "failure_count": sum(r["status"] not in {"completed", "reserved"} for r in rows),
            "unfinished_count": sum(r["status"] == "reserved" for r in rows),
            "usage_complete": usage_complete, "observed_usage_subtotals": observed,
            "total_input_tokens": sum(observed[k] for k in USAGE_KEYS[:3]) if usage_complete else None,
            "output_tokens": observed["output_tokens"] if usage_complete else None,
            "model_session_seconds": sum(r["wall_seconds"] for r in rows) if wall_complete else None,
            "missing_usage_is_not_zero": True, "subscription_dollar_cost": None}


def compare_pair(old, incremental):
    changes = {}
    for key in ("total_input_tokens", "output_tokens", "model_session_seconds"):
        before, after = old.get(key), incremental.get(key)
        changes[key] = {"old": before, "incremental": after,
                        "reduction_fraction": (1 - after / before)
                        if before is not None and before > 0 and after is not None else None}
    reductions = {k: v["reduction_fraction"] for k, v in changes.items()}
    known = all(v is not None for v in reductions.values())
    return {"metrics": changes, "engineering_target_met": (
        reductions["total_input_tokens"] >= 0 and reductions["output_tokens"] >= .3
        and reductions["model_session_seconds"] >= .3) if known else None,
        "scientific_quality": "requires_independent_audit",
        "comparison_validity": "requires_same_frozen_inputs_and_completed_matching_pipeline",
        "note": "A cheaper failed or incomplete arm cannot establish savings at equal quality."}
