"""Run a frozen harness in a fresh CPU container through a bounded model broker."""
from __future__ import annotations

import json
import hashlib
import sys
import time
from pathlib import Path

from .container_runtime import ContainerSession
from .executor_broker import ExecutorBroker
from .io import ProtocolError, TraceLog, canonical, file_hash, read_json, write_json, parse_json, contained
from .sdk import Budget, validate_submission
from .artifact_policy import collection_policy


def _record_incomplete_execution(output, broker, exc):
    """Record absence of collection, never infer absence of solver artifacts.

    This is best-effort host bookkeeping after failure, not a deadline extension
    or a container checkpoint. Bookkeeping failure must not hide the primary error.
    """
    errors = []
    checkpoint = None
    try:
        checkpoint = broker.budget.checkpoint()
    except Exception as problem:
        errors.append({"operation": "budget_checkpoint", "type": type(problem).__name__, "message": str(problem)})
    preserved = []
    try:
        candidates = [output / "platform.jsonl", output / "invocation.json"]
        candidates += list((output / "broker").glob("rpc-*.json"))
        candidates += list((output / "broker").glob("image-*"))
        candidates += list((output / "container" / "executed-entrypoints").glob("*.py"))
        for path in sorted(set(candidates)):
            if path.is_file():
                preserved.append({"path": path.relative_to(output).as_posix(),
                                  "bytes": path.stat().st_size, "sha256": file_hash(path)})
    except Exception as problem:
        errors.append({"operation": "preserved_receipt_inventory", "type": type(problem).__name__, "message": str(problem)})
    record = {"type": type(exc).__name__, "message": str(exc), "budget": checkpoint,
              "attribution": "pending_evidence_review_not_automatic_agent_zero",
              "quality_score": None, "automatic_zero": False,
              "artifact_status": "unknown_uncollected_or_incomplete",
              "artifact_completeness_verified": False,
              "missing_capture_proves_no_solver_output": False,
              "timeout_policy": "Hard deadline terminates task container. Writable tmpfs not already captured may be lost; no periodic artifact backup is promised.",
              "preserved_controller_evidence": preserved,
              "preservation_scope": "Only already captured host receipts, model responses in RPCs, executed entrypoint snapshots and image bytes. Not complete solver filesystem/history; no container read attempted after failure.",
              "prior_collection_inventory_present": (output / "artifact_inventory.json").is_file(),
              "recording_errors": errors}
    try:
        write_json(output / "failure.json", record)
    except Exception as problem:
        if hasattr(exc, "add_note"):
            exc.add_note("Failure audit could not be written: %s: %s" % (type(problem).__name__, problem))


def run_container_harness(*, harness, public_root, image_id, provider, output,
                          literature=None, max_artifact_bytes, max_artifact_files):
    """Development invocation. No private package paths or provider enter worker.

    Resource settings come only from the released task. Model broker has its own
    immutable budget and exact executor role. This does not accept formal gates.
    """
    harness, public_root, output = Path(harness), Path(public_root), Path(output)
    if output.exists():
        raise ProtocolError("Fresh execution output required")
    task_bytes = (public_root / "task.json").read_bytes()
    view = parse_json(task_bytes.decode('utf-8-sig'))
    resources = view["resources"]["container"]
    budget = view["resources"]["execution_budget"]
    collection = collection_policy(view['resources'])
    if (type(max_artifact_bytes) is not int or type(max_artifact_files) is not int or
        max_artifact_bytes != collection['max_total_bytes'] or max_artifact_files != collection['max_entries']):
        raise ProtocolError('Controller collection limits differ from published task contract')
    if view['resources'].get('image_id') != image_id:
        raise ProtocolError('Runner image does not match explicitly published image ID')
    if budget["wall_seconds"] != resources["wall_seconds"]:
        raise ProtocolError("Published task deadlines differ")
    if not 0 < max_artifact_bytes <= resources["disk_mb"]*1024*1024:
        raise ProtocolError("Artifact collection cap exceeds task disk")
    files = {"harness.py": harness, "worker.py": Path(__file__).resolve().parents[1]/"runtime/container_worker.py",
             "public/task.json": public_root/"task.json"}
    for asset in view["asset_manifest"]:
        p = contained(public_root, asset["path"], must_exist=True)
        if file_hash(p) != asset["sha256"]:
            raise ProtocolError("Public asset release changed or escaped")
        files["public/" + asset["path"]] = p
    output.mkdir(parents=True)
    trace = TraceLog(output / "platform.jsonl")
    budget_counter = Budget.from_task(view)
    expected_hashes = {name: file_hash(path) for name,path in files.items()}
    expected_hashes["public/task.json"] = hashlib.sha256(task_bytes).hexdigest()
    for asset in view["asset_manifest"]:
        expected_hashes["public/"+asset["path"]] = asset["sha256"]
    session = ContainerSession(image_id=image_id, resources=resources, input_files=files, input_hashes=expected_hashes,
                               audit_dir=output/"container", deadline_monotonic=budget_counter.deadline)
    broker = ExecutorBroker(view=view, session=session, provider=provider, trace=trace, audit_root=output/"broker", literature=literature, budget=budget_counter)
    write_json(output/"invocation.json", {"harness_sha256": expected_hashes['harness.py'], "task_sha256": expected_hashes['public/task.json'],
               "image_id": image_id, "resources": resources, "artifact_collection": collection,
               "formal": False, "credentials_in_worker": False})
    try:
        session.start()
        session.write("/work/.broker/initialized", b"controller-ready")
        handle = session.start_process(["python", "-I", "/inputs/worker.py"])
        while broker.budget.remaining()["wall_seconds"] > 0:
            names = {r["name"] for r in session.list("/work/.broker")}
            seq = broker.next_sequence
            request_name = f"request-{seq}.json"
            if request_name in names:
                request = parse_json(session.read("/work/.broker/"+request_name, max_bytes=2_000_000).decode('utf8'))
                response = broker.dispatch(request)
                temporary = f"/work/.broker/response-{seq}.tmp"
                final = f"/work/.broker/response-{seq}.json"
                session.write(temporary, canonical(response))
                result = session.exec(["python", "-I", "-S", "-c", "import os,sys;os.replace(sys.argv[1],sys.argv[2])", temporary, final])
                if result["returncode"]:
                    raise ProtocolError("Broker response publication failed")
                continue
            if "worker_failure.json" in names:
                failure = json.loads(session.read("/work/.broker/worker_failure.json", max_bytes=100000))
                write_json(output/"worker_failure.json", failure)
                raise ProtocolError("Harness reported failure (untrusted report; inspect platform evidence)")
            if "submission.json" in names:
                submission = validate_submission(parse_json(session.read("/work/.broker/submission.json", max_bytes=2_000_000).decode('utf8')), broker)
                write_json(output/"submission.json", submission)
                artifacts = session.artifacts(output/"artifacts", max_bytes=max_artifact_bytes, max_files=max_artifact_files, exclude_internal=True)
                for row in submission["artifacts"]:
                    captured = output/"artifacts"/row["path"]
                    if not captured.is_file() or file_hash(captured) != row["sha256"]:
                        raise ProtocolError("Artifact changed between submission and collection")
                write_json(output/"artifact_inventory.json", artifacts)
                if broker.budget.remaining()["wall_seconds"] <= 0:
                    raise ProtocolError("Task deadline exhausted during collection; no completed claim")
                write_json(output/"run.json", {"status": "completed_structural_development_check", "formal": False,
                           "task_elapsed_seconds": time.time()-broker.budget.started_at,
                           "budget": broker.budget.checkpoint(), "worker_status_trusted": False,
                           "scientific_acceptance": "requires_independent_judge_and_trajectory_review"})
                return submission
            time.sleep(.2)
        raise ProtocolError("Task wall deadline exhausted")
    except Exception as exc:
        try:
            _record_incomplete_execution(output, broker, exc)
        except Exception as recording_error:
            if hasattr(exc, "add_note"):
                exc.add_note("Failure recording failed: %s: %s" % (type(recording_error).__name__, recording_error))
        raise
    finally:
        primary = sys.exc_info()[1]
        try:
            session.close()
        except Exception as cleanup_error:
            if primary is None:
                raise
            # A cleanup error remains visible without replacing the task failure.
            try:
                write_json(output / "cleanup_failure.json", {
                    "type": type(cleanup_error).__name__, "message": str(cleanup_error),
                    "cleanup_verified": False, "primary_failure_preserved": True})
            except Exception:
                pass
            if hasattr(primary, "add_note"):
                primary.add_note("Container cleanup failed: %s: %s" % (type(cleanup_error).__name__, cleanup_error))
