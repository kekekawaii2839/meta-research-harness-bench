"""Actual development judge loop with read-only evidence and separate feedback.

The model requests evidence; this controller alone grants read receipts and invokes
validators. No submitted code or native model tool is executed by a judge.
"""
from __future__ import annotations

import base64
from pathlib import Path

from .io import ProtocolError, TraceLog, digest, parse_json, write_json
from .judging import EvidenceSession, feedback_request, scoring_request, validate_feedback, validate_judgment

ACTION_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "kind": {"type": "string", "enum": ["read_evidence", "final"]},
    "payload_json": {"type": "string"}}, "required": ["kind", "payload_json"]}


def evidence_record(id: str, origin: str, content: str, *, visibility="public", media_type="text/plain"):
    return {"evidence_id": id, "origin": origin, "visibility": visibility, "media_type": media_type,
            "content": content, "sha256": digest(content)}


def run_judge(*, client, task_id: str, task_type: str, records: list[dict], output: Path, mode="score", dimension_scores=None, max_steps=8, max_text_chars=120000):
    if mode not in {"score", "feedback"} or not 1 <= max_steps <= 20:
        raise ProtocolError("Invalid judge development mode/step bound")
    if output.exists():
        raise ProtocolError("Each judge run requires a new private output directory")
    output.mkdir(parents=True)
    session = EvidenceSession(records, public_only=mode == "feedback", max_text_chars=max_text_chars)
    # Feedback archive itself contains only allowed records, never the discarded private context.
    write_json(output/"evidence.json", list(session.records.values()))
    initial = scoring_request(task_id, task_type, session) if mode == "score" else feedback_request(task_id, task_type, session, dimension_scores)
    initial["response_protocol"] = {
        "read_evidence": 'payload_json encodes {"reads":[{"evidence_id":"id","start_line":1,"end_line":20}]} with 1–10 reads. Each text read must span 1–400 actual lines; inspect long records in pages. Omit line fields for an image.',
        "final": "payload_json encodes the exact complete judgment/feedback object required by the system rules.",
        "maximum_model_steps": max_steps, "warning": "These are external harness actions, not native Codex tools. Read actual evidence before grades. A whole text record may be one long JSON line; line counts are given in inventory.",
        "maximum_evidence_text_chars": max_text_chars,
    }
    trace = TraceLog(output/"trace.jsonl")
    trace.append("judge_started", {"task_id": task_id, "task_type": task_type, "mode": mode, "request_hash": digest(initial), "evidence_inventory_hash": session.inventory_hash})
    history, images, pending_images = [], [], []
    try:
        for step in range(max_steps):
            request = {**initial, "history": history, "remaining_model_steps_including_this": max_steps-step,
                       "remaining_evidence_text_chars": session.max_text_chars - session.text_chars,
                       "allowed_citation_receipts": [{"receipt_id": key, "evidence_id": value["evidence_id"]}
                                                     for key, value in session.receipts.items()]}
            write_json(output/f"request-{step}.json", request)
            reply = client.complete(request, output_schema=ACTION_SCHEMA, role="judge" if mode == "score" else "feedback", images=images)
            for receipt in pending_images:
                session.record_image_delivery(receipt, transport_event_id=f"model-call-{reply['call_id']}")
            pending_images = []
            action = reply["response"]
            trace.append("judge_model_response", {"step": step, "call_id": reply["call_id"], "audit_directory": reply["audit_directory"], "action": action})
            if not isinstance(action, dict) or set(action) != {"kind", "payload_json"}:
                raise ProtocolError("Invalid judge action envelope")
            body = parse_json(action["payload_json"])
            history.append({"model_action": action})
            if action["kind"] == "final":
                result = validate_judgment(task_type, body, session) if mode == "score" else validate_feedback(body, session)
                result.update(task_id=task_id, task_type=task_type, mode=mode, model_steps=step+1,
                              acceptance_status="awaiting_manual_trajectory_review", formal_scientific_score=False)
                write_json(output/"result.json", result)
                write_json(output/"retrieval_events.json", session.events)
                trace.append("judge_finished", {"result_hash": digest(result), "model_steps": step+1})
                return result
            if action["kind"] != "read_evidence" or not isinstance(body, dict) or set(body) != {"reads"} or not isinstance(body["reads"], list) or not 1 <= len(body["reads"]) <= 10:
                raise ProtocolError("Invalid evidence-read request")
            results = []
            for read in body["reads"]:
                if not isinstance(read, dict) or not {"evidence_id"}.issubset(read) or not set(read).issubset({"evidence_id", "start_line", "end_line"}):
                    raise ProtocolError("Unknown evidence tool parameters")
                observed = session.read(**read)
                if observed["media_type"].startswith("image/"):
                    suffix = ".png" if observed["media_type"] == "image/png" else ".jpg"
                    path = output/(observed["receipt_id"] + suffix)
                    path.write_bytes(base64.b64decode(observed["content"]))
                    images.append(path)
                    pending_images.append(observed["receipt_id"])
                    observed = {k:v for k,v in observed.items() if k != "content"}
                    observed["image_attachment_index"] = len(images)-1
                results.append(observed)
                trace.append("evidence_read", {k:v for k,v in observed.items() if k != "content"})
            history.append({"tool_results": results})
        raise ProtocolError("Judge reached explicit development model-step limit without accepted result")
    except Exception as exc:
        write_json(output/"retrieval_events.json", session.events)
        trace.append("judge_failed", {"error_type": type(exc).__name__, "reason": str(exc)})
        write_json(output/"failure.json", {"status": "judge_failure", "error_type": type(exc).__name__, "reason": str(exc), "scientific_quality": None})
        raise
