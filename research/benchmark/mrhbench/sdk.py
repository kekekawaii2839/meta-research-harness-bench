"""Versioned DEVELOPMENT harness ABI. Capability checks are not an OS sandbox.

Controller clients never expose private scoring data. Formal execution of arbitrary
harness Python still requires an accepted process/network isolation adapter.
"""
from __future__ import annotations

import copy
import math
import time
from pathlib import Path

from .io import ProtocolError, contained, digest, file_hash, write_json, BudgetExhausted

INTERFACE_VERSION = "mrhb-dev-0.1"


class Budget:
    def __init__(self, *, model_calls: int, tool_calls: int, wall_seconds: float):
        if any(isinstance(x, bool) or not isinstance(x, int) or x < 1 for x in (model_calls, tool_calls)):
            raise ProtocolError("Positive model/tool call limits required")
        if isinstance(wall_seconds, bool) or not isinstance(wall_seconds, (int, float)) or not math.isfinite(wall_seconds) or wall_seconds <= 0:
            raise ProtocolError("Invalid wall-time limit")
        self.limits = {"model": model_calls, "tool": tool_calls}
        self.used = {"model": 0, "tool": 0}
        self.deadline = time.monotonic() + wall_seconds
        self.wall_limit = wall_seconds
        self.started_at = time.time()
        self.expires_at = self.started_at + wall_seconds
        self.cancelled = False

    @classmethod
    def from_task(cls, view, *, overrides=None):
        """One exact published budget. Never invent runtime-only default caps."""
        config = view.get("resources", {}).get("execution_budget")
        if not isinstance(config, dict) or set(config) != {"model_calls", "tool_calls", "wall_seconds"}:
            raise ProtocolError("Task must publish a complete execution_budget")
        if overrides is not None and overrides != config:
            raise ProtocolError("Runtime budget conflicts with published task budget")
        return cls(**config)

    def checkpoint(self):
        return {"limits": dict(self.limits), "used": dict(self.used), "wall_limit": self.wall_limit,
                "started_at": self.started_at, "expires_at": self.expires_at, "cancelled": self.cancelled}

    @classmethod
    def restore(cls, state):
        """Downtime counts. Restoring cannot grant new calls or extend deadline."""
        if set(state) != {"limits", "used", "wall_limit", "started_at", "expires_at", "cancelled"}:
            raise ProtocolError("Invalid budget checkpoint")
        obj = cls(model_calls=state["limits"]["model"], tool_calls=state["limits"]["tool"], wall_seconds=state["wall_limit"])
        if set(state["used"]) != {"model", "tool"} or any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= obj.limits[k] for k,v in state["used"].items()):
            raise ProtocolError("Invalid used-resource counters")
        if abs(state["expires_at"] - state["started_at"] - state["wall_limit"]) > .001:
            raise ProtocolError("Budget checkpoint deadline inconsistent")
        obj.used = dict(state["used"])
        obj.started_at, obj.expires_at, obj.cancelled = state["started_at"], state["expires_at"], state["cancelled"]
        obj.deadline = time.monotonic() + max(0, obj.expires_at - time.time())
        return obj

    def remaining(self):
        return {**{k + "_calls": self.limits[k] - self.used[k] for k in self.limits},
                "wall_seconds": max(0, self.deadline - time.monotonic()), "cancelled": self.cancelled}

    def consume(self, kind):
        if kind not in self.limits or self.cancelled or time.monotonic() >= self.deadline or self.used[kind] >= self.limits[kind]:
            if kind not in self.limits:
                raise ProtocolError("Unknown budget resource")
            raise BudgetExhausted("Task budget exhausted/cancelled")
        self.used[kind] += 1  # Failed attempts count, too.


class ExecutorClient:
    """Bound role: harness cannot select a provider role, model, or audit path."""
    def __init__(self, provider, budget, trace, image_registry=None):
        self._provider, self._budget, self._trace = provider, budget, trace
        self._image_registry = image_registry if image_registry is not None else {}

    def complete(self, request: dict, *, output_schema: dict, image_ids=None):
        images = []
        for key in image_ids or []:
            if key not in self._image_registry:
                raise ProtocolError("Image was not released by artifact.view_image")
            row = self._image_registry[key]
            p = Path(row["path"])
            if file_hash(p) != row["sha256"]:
                raise ProtocolError("Released image changed before model invocation")
            images.append(p)
        self._budget.consume("model")
        self._trace.append("executor_requested", {"request_hash": digest(request), "schema_hash": digest(output_schema)})
        try:
            result = self._provider.complete(request, output_schema=output_schema, role="executor", images=images,
                                             timeout_seconds=self._budget.remaining()["wall_seconds"], deadline_monotonic=self._budget.deadline)
        except Exception as exc:
            self._trace.append("executor_failed", {"type": type(exc).__name__})
            exc.provider_side = True  # counted provider attempt, distinct from broker prechecks
            raise
        self._trace.append("executor_completed", {"call_id": result["call_id"], "response_hash": digest(result["response"]), "usage": result["usage"]})
        return {key: copy.deepcopy(result[key]) for key in ("response", "call_id", "usage")}


class TaskTools:
    def __init__(self, *, view, input_root: Path, output_root: Path, budget, trace, literature=None, cpu_runner=None, resume_output=False, image_registry=None):
        self.view = copy.deepcopy(view)
        self.input_root, self.output_root = input_root, output_root
        self.budget, self.trace, self.literature = budget, trace, literature
        self.cpu_runner = cpu_runner
        self.image_registry = image_registry if image_registry is not None else {}
        if output_root.exists() and not resume_output:
            raise ProtocolError("Fresh per-task output root required")
        if resume_output and not output_root.is_dir():
            raise ProtocolError("Resume requires the same existing task output directory")
        output_root.mkdir(parents=True, exist_ok=resume_output)
        self.assets = {a["asset_id"]: a for a in view["asset_manifest"]}
        self.written = {}

    def call(self, name: str, arguments: dict):
        self.budget.consume("tool")
        self.trace.append("tool_requested", {"name": name, "arguments": copy.deepcopy(arguments)})
        try:
            result = self._call(name, arguments)
        except Exception as exc:
            self.trace.append("tool_failed", {"name": name, "type": type(exc).__name__, "reason": str(exc)})
            raise
        self.trace.append("tool_completed", {"name": name, "result": copy.deepcopy(result), "result_hash": digest(result)})
        return result

    def _call(self, name, arguments):
        if not isinstance(arguments, dict):
            raise ProtocolError("Tool arguments must be an object")
        if name == "asset.read":
            if set(arguments) != {"asset_id"} or arguments["asset_id"] not in self.assets:
                raise ProtocolError("Unknown public asset")
            asset = self.assets[arguments["asset_id"]]
            p = contained(self.input_root, asset["path"], must_exist=True)
            if file_hash(p) != asset["sha256"] or p.stat().st_size > 500000:
                raise ProtocolError("Asset changed or exceeds explicit development read size")
            return {"asset_id": asset["asset_id"], "sha256": asset["sha256"], "text": p.read_text(encoding="utf-8")}
        if name == "artifact.view_image":
            if "artifact_image_view" not in self.view["tools"] or set(arguments) != {"path"}:
                raise ProtocolError("Image capability not granted or invalid arguments")
            p = contained(self.output_root, arguments["path"], must_exist=True)
            if p.suffix.lower() not in {".png", ".jpg", ".jpeg"} or p.stat().st_size > 20*1024*1024:
                raise ProtocolError("Invalid image artifact")
            header = p.read_bytes()[:8]
            if not (header.startswith(b"\x89PNG\r\n\x1a\n") or header.startswith(b"\xff\xd8\xff")):
                raise ProtocolError("Image signature does not match supported pixel format")
            sha = file_hash(p); key = "image-" + sha
            self.image_registry[key] = {"path": str(p.resolve()), "sha256": sha}
            return {"image_id": key, "path": arguments["path"], "sha256": sha,
                    "delivery": "Pass this image_id to model_client.complete(image_ids=[...]); path text alone is not visual inspection."}
        if name in {"artifact.write_text", "artifact.read_text"}:
            if "artifact_read_write" not in self.view["tools"]:
                raise ProtocolError("Artifact capability not granted")
            expected = {"path", "text"} if name.endswith("write_text") else {"path"}
            if set(arguments) != expected:
                raise ProtocolError("Invalid artifact arguments")
            p = contained(self.output_root, arguments["path"])
            if name.endswith("write_text"):
                value = arguments["text"]
                if not isinstance(value, str) or len(value.encode("utf-8")) > 500000:
                    raise ProtocolError("Text artifact size/type invalid")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(value, encoding="utf-8")
                self.written[arguments["path"]] = file_hash(p)
                return {"path": arguments["path"], "sha256": file_hash(p)}
            if not p.is_file() or p.stat().st_size > 500000:
                raise ProtocolError("Artifact missing or too large")
            return {"path": arguments["path"], "sha256": file_hash(p), "text": p.read_text(encoding="utf-8")}
        if name in {"literature.search", "literature.read", "literature.read_page"}:
            if name not in self.view["tools"] or self.literature is None:
                raise ProtocolError("Literature capability not granted")
            return getattr(self.literature, name.split(".")[1])(**arguments)
        if name == "cpu.run":
            if "cpu_python_execution" not in self.view["tools"] or self.cpu_runner is None:
                raise ProtocolError("CPU development runner not supplied")
            if not {"script"}.issubset(arguments) or not set(arguments).issubset({"script", "arguments", "timeout_seconds"}):
                raise ProtocolError("CPU tool arguments cannot override controller deadline")
            return self.cpu_runner.run(**arguments, deadline_monotonic=self.budget.deadline)
        # Deliberately no arbitrary local execution until an appropriate CPU
        # runner has been accepted. A GPU prohibition must not be just a prompt.
        raise ProtocolError("Capability unavailable in this development adapter: " + str(name))

    def verify_artifacts(self, artifacts):
        if not isinstance(artifacts, list) or any(not isinstance(a, dict) or set(a) != {"path", "sha256"} for a in artifacts):
            raise ProtocolError("Artifacts require relative path and actual sha256")
        seen = set()
        for a in artifacts:
            p = contained(self.output_root, a["path"], must_exist=True)
            if a["path"].casefold() in seen or not p.is_file() or file_hash(p) != a["sha256"]:
                raise ProtocolError("Duplicate, missing or mutated submission artifact")
            seen.add(a["path"].casefold())


def validate_submission(value, tools):
    if not isinstance(value, dict) or set(value) != {"status", "content", "artifacts", "omissions"}:
        raise ProtocolError("Submission requires status/content/artifacts/omissions")
    if value["status"] not in {"completed", "partial", "failed"} or not isinstance(value["content"], dict):
        raise ProtocolError("Invalid submission status/content")
    if not isinstance(value["omissions"], list) or any(not isinstance(x, str) for x in value["omissions"]):
        raise ProtocolError("Omissions must be text list")
    tools.verify_artifacts(value["artifacts"])
    return copy.deepcopy(value)
