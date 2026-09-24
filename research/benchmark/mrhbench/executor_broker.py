"""Controller-owned executor RPC. Research Python stays in the task container.

This is a development adapter, not a declaration of formal isolation acceptance.
No caller-supplied role, model, host path, provider configuration or deadline is
accepted. The container may make arbitrary requests; it cannot reset this budget.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath

from .io import ProtocolError, canonical, digest, write_json
from .sdk import Budget, ExecutorClient
from .container_runtime import ArtifactHashError


def worker_path(value, *, root="/work"):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ProtocolError("Invalid worker-relative path")
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in {".", ".."} for x in value.split("/")):
        raise ProtocolError("Worker path must be normalized and relative")
    if any(not x or ":" in x for x in value.split("/")) or value.startswith(".broker/"):
        raise ProtocolError("Reserved or ambiguous worker path")
    return root + "/" + value


PUBLIC_ERROR_MESSAGES = {
    "budget_exhausted": "budget_exhausted: this task's model/tool/wall budget is exhausted or the task was cancelled; check budget.remaining().",
    "provider_refusal": "provider_refusal: the executor model provider declined this request. This one call was counted; other calls may still be available.",
    "provider_error": "provider_error: the model call did not return a valid response (timeout, malformed or schema-invalid output). The call was counted.",
    "invalid_request": "invalid_request: the request, arguments or capability were not accepted by the broker.",
    "tool_error": "tool_error: the tool call failed; check its arguments and capabilities.",
}


def public_error_category(exc, operation):
    from .io import BudgetExhausted, ProviderRefusal
    if isinstance(exc, BudgetExhausted):
        return "budget_exhausted"
    if isinstance(exc, ProviderRefusal):
        return "provider_refusal"
    if operation == "complete":
        # Broker-side argument checks raise before the provider; provider failures after.
        return "provider_error" if getattr(exc, "provider_side", False) else "invalid_request"
    if operation == "tool":
        return "tool_error"
    return "invalid_request"


class ExecutorBroker:
    def __init__(self, *, view, session, provider, trace, audit_root, literature=None, budget=None):
        self.view = copy.deepcopy(view)
        self.budget = budget if budget is not None else Budget.from_task(view)
        published = view["resources"]["execution_budget"]
        if self.budget.limits != {"model": published["model_calls"], "tool": published["tool_calls"]} or self.budget.wall_limit != published["wall_seconds"]:
            raise ProtocolError("Controller budget conflicts with published limits")
        resources = view["resources"]["container"]
        if resources["wall_seconds"] != self.budget.wall_limit:
            raise ProtocolError("Container and model/tool wall deadlines disagree")
        if getattr(session, "resources", None) != resources:
            raise ProtocolError("Session does not use the published package resources")
        self.session, self.trace, self.literature = session, trace, literature
        self.audit_root = Path(audit_root)
        self.audit_root.mkdir(parents=True, exist_ok=False)
        self.images = {}
        self.client = ExecutorClient(provider, self.budget, trace, self.images)
        self.assets = {a["asset_id"]: a for a in view["asset_manifest"]}
        self.next_sequence = 1

    def dispatch(self, envelope):
        if len(canonical(envelope)) > 2_000_000:
            raise ProtocolError("RPC envelope exceeds limit")
        if not isinstance(envelope, dict) or set(envelope) != {"sequence", "operation", "arguments"}:
            raise ProtocolError("Invalid RPC envelope")
        seq = envelope["sequence"]
        if type(seq) is not int or seq != self.next_sequence:
            raise ProtocolError("Replayed or out-of-order RPC")
        self.next_sequence += 1
        args = envelope["arguments"]
        if not isinstance(args, dict):
            raise ProtocolError("RPC arguments must be an object")
        self.trace.append("broker_request", {"sequence": seq, "operation": envelope["operation"], "request_hash": digest(envelope)})
        try:
            op = envelope["operation"]
            if op == "remaining" and not args:
                value = self.budget.remaining()
            elif op == "complete":
                if not {"request", "output_schema"} <= set(args) or not set(args) <= {"request", "output_schema", "image_ids"} or \
                        not isinstance(args["request"], dict) or not isinstance(args["output_schema"], dict):
                    raise ProtocolError("Model request, schema or role override invalid")
                value = self.client.complete(**args)
            elif op == "tool" and set(args) == {"name", "arguments"}:
                self.budget.consume("tool")
                value = self.tool(args["name"], args["arguments"])
            else:
                raise ProtocolError("Unknown broker operation")
            result = {"sequence": seq, "ok": True, "value": value}
            if len(canonical(result)) > 512*1024:
                write_json(self.audit_root/f"rpc-{seq:05d}-oversize-result.json", result, exclusive=True)
                result = {"sequence": seq, "ok": False, "error": "ResponseCapacityExceeded",
                          "message": "Result exceeds 512 KiB RPC limit; full result retained in platform audit. Reduce stdout; save data as artifacts and read bounded portions. No successful data delivery claimed."}
        except Exception as exc:
            # Host exceptions may contain private paths or provider internals, so only a
            # typed public category and a fixed message cross the boundary (interface v4).
            category = public_error_category(exc, envelope.get("operation"))
            self.trace.append("broker_failure", {"sequence": seq, "error_type": type(exc).__name__, "reason": str(exc), "category": category})
            result = {"sequence": seq, "ok": False, "error": type(exc).__name__, "category": category, "message": PUBLIC_ERROR_MESSAGES[category]}
        write_json(self.audit_root / f"rpc-{seq:05d}.json", {"request": envelope, "response": result}, exclusive=True)
        return result

    def tool(self, name, args):
        if not isinstance(args, dict):
            raise ProtocolError("Tool arguments must be an object")
        caps = self.view["tools"]
        if name == "asset.read" and set(args) == {"asset_id"}:
            row = self.assets.get(args["asset_id"])
            if row is None:
                raise ProtocolError("Unknown released asset")
            data = self.session.read(worker_path(row["path"], root="/inputs/public"), max_bytes=500000)
            if hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ProtocolError("Released asset changed")
            return {"asset_id": row["asset_id"], "sha256": row["sha256"], "text": data.decode("utf8")}
        if name in {"artifact.write_text", "artifact.read_text", "artifact.view_image"}:
            cap = "artifact_image_view" if name.endswith("view_image") else "artifact_read_write"
            expected = {"path", "text"} if name.endswith("write_text") else {"path"}
            if cap not in caps or set(args) != expected:
                raise ProtocolError("Artifact capability or fields invalid")
            path = worker_path(args["path"])
            if name.endswith("write_text"):
                if not isinstance(args["text"], str) or len(args["text"].encode("utf8")) > 500000:
                    raise ProtocolError("Invalid text artifact")
                data = args["text"].encode("utf8")
                self.session.write(path, data)
            else:
                data = self.session.read(path, max_bytes=20*1024*1024 if cap == "artifact_image_view" else 500000)
            sha = hashlib.sha256(data).hexdigest()
            result = {"path": args["path"], "sha256": sha}
            if cap == "artifact_image_view":
                suffix = ".png" if data.startswith(b"\x89PNG\r\n\x1a\n") else ".jpg" if data.startswith(b"\xff\xd8\xff") else None
                if suffix is None:
                    raise ProtocolError("Unsupported image bytes")
                key = "image-" + sha
                target = self.audit_root / (key + suffix)
                if not target.exists():
                    target.write_bytes(data)
                self.images[key] = {"path": str(target), "sha256": sha}
                result.update(image_id=key, delivery="Use model_client.complete(image_ids=[image_id]) to inspect actual pixels.")
            elif name.endswith("read_text"):
                result["text"] = data.decode("utf8")
            return result
        if name == "cpu.run":
            if "cpu_python_execution" not in caps or "script" not in args or not set(args) <= {"script", "arguments", "timeout_seconds"}:
                raise ProtocolError("CPU capability/arguments invalid")
            script = worker_path(args["script"])
            argv = args.get("arguments", [])
            if not script.endswith(".py") or not isinstance(argv, list) or any(not isinstance(x, str) or "\x00" in x for x in argv):
                raise ProtocolError("CPU script/arguments invalid")
            remain = self.budget.remaining()["wall_seconds"]
            timeout = args.get("timeout_seconds", remain)
            if isinstance(timeout, bool) or not isinstance(timeout, (int,float)) or not math.isfinite(timeout) or timeout <= 0:
                raise ProtocolError("Invalid CPU timeout")
            return self.session.exec_python_snapshot(script, argv, timeout=min(timeout, remain))
        if name in {"literature.search", "literature.read", "literature.read_page"}:
            if name not in caps or self.literature is None:
                raise ProtocolError("Literature capability not granted")
            return getattr(self.literature, name.split(".")[1])(**args)
        raise ProtocolError("Unreleased tool or invalid arguments")

    def verify_artifacts(self, artifacts):
        if not isinstance(artifacts, list):
            raise ProtocolError("Invalid artifacts list")
        seen = set(); total = 0
        # Hash verification is not a content-read operation. Its cumulative byte
        # bound derives from published package disk, not the image reader cap.
        allowance = self.session.resources['disk_mb']*1024*1024
        resources = getattr(self,'view',{}).get('resources',{})
        if 'artifact_collection' in resources:
            from .artifact_policy import collection_policy
            policy = collection_policy(resources)
            allowance = min(allowance,policy['max_total_bytes'])
            # Directory entries/non-declared files are counted by collection,
            # so this is only an early necessary condition, not full admission.
            if len(artifacts)>policy['max_entries']:
                raise ArtifactHashError('declared_entry_limit_exceeded')
        receipts = []
        for row in artifacts:
            if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
                raise ProtocolError("Artifact fields invalid")
            path = worker_path(row["path"])
            if path.casefold() in seen:
                raise ProtocolError("Duplicate artifact")
            seen.add(path.casefold())
            if not isinstance(row['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',row['sha256']):
                raise ArtifactHashError('invalid_declared_sha256')
            receipt = self.session.hash_file(path, max_bytes=allowance-total)
            total += receipt['bytes']
            if receipt['sha256'] != row['sha256']:
                raise ArtifactHashError('hash_mismatch')
            receipts.append(receipt)
        return {'total_bytes':total,'limit_bytes':allowance,'files':receipts,
                'scope':'stream_hash_verification_not_artifact_collection_acceptance'}
