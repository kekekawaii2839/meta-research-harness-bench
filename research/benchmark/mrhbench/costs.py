"""Controller-owned call authorization and observed cost ledger.

The explicit ledger DEVELOPMENT authorization is distinct from the research protocol's
round-limited, cost-recorded outer evolution. No invented subscription dollar price.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

from .io import ProtocolError, numeric, read_json, utc_now, write_json


class CallLedger:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def _locked(self):
        lock = self.path.with_suffix(self.path.suffix + ".lock")
        # Waiting for a short transaction lock retries bookkeeping, never models.
        deadline = time.monotonic() + 30
        while True:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError as exc:
                if time.monotonic() >= deadline:
                    raise ProtocolError("Call ledger busy: do not delete a lock or retry a model call blindly") from exc
                time.sleep(.05)
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            yield
        finally:
            lock.unlink()

    def _read(self):
        state = read_json(self.path)
        attempts = state["attempts"]
        if state["used_attempts"] != len(attempts) or [a["id"] for a in attempts] != list(range(1, len(attempts)+1)):
            raise ProtocolError("Call ledger inconsistent")
        return state

    def reserve(self, *, role: str, model: str, effort: str, request_hash: str, artifact_directory: str) -> int:
        if role not in {"probe", "builder", "executor", "judge", "feedback", "constructor", "material_reviewer"}:
            raise ProtocolError("Unknown model-call role")
        with self._locked():
            state = self._read()
            if state["used_attempts"] >= state["authorized_maximum"]:
                raise ProtocolError("Authorized development runs exhausted")
            id = state["used_attempts"] + 1
            state["attempts"].append({"id": id, "status": "reserved", "role": role, "model": model,
                                      "reasoning_effort": effort, "request_hash": request_hash,
                                      "artifact_directory": artifact_directory, "reserved_at": utc_now()})
            state["used_attempts"] = id
            write_json(self.path, state)
            return id

    def finish(self, id: int, *, status: str, wall_seconds: float, usage: dict | None, metadata: dict):
        if status not in {"completed", "failed", "timeout", "rejected_native_tool_activity"}:
            raise ProtocolError("Unknown final call status")
        numeric(wall_seconds, "wall time")
        if usage is not None:
            for key, value in usage.items():
                numeric(value, key)
                if not float(value).is_integer():
                    raise ProtocolError("Token usage must be integral")
        with self._locked():
            state = self._read()
            if not 1 <= id <= len(state["attempts"]) or state["attempts"][id-1]["status"] != "reserved":
                raise ProtocolError("Call missing/already finalized; do not overwrite uncertain or completed attempts")
            state["attempts"][id-1].update(status=status, finished_at=utc_now(), wall_seconds=wall_seconds,
                                          usage=usage, dollar_cost=None, cost_basis="subscription_price_not_metered_per_call",
                                          metadata=metadata)
            write_json(self.path, state)

    def summary(self):
        state = self._read()
        roles = {}
        for a in state["attempts"]:
            role = a.get("role", "legacy_probe")
            row = roles.setdefault(role, {"runs": 0, "wall_seconds_observed": 0, "usage_observed": {}, "runs_without_usage": 0})
            row["runs"] += 1
            row["wall_seconds_observed"] += a.get("wall_seconds", 0)
            if a.get("usage") is None:
                row["runs_without_usage"] += 1
            else:
                for k, v in a["usage"].items():
                    row["usage_observed"][k] = row["usage_observed"].get(k, 0) + v
        return {"authorized_maximum": state["authorized_maximum"], "used_runs_including_failures": state["used_attempts"],
                "roles": roles, "dollar_cost": None, "missing_usage_is_not_zero": True}
