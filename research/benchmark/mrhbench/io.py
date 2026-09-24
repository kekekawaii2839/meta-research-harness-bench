"""Strict JSON, stable hashes, safe asset paths, and append-only evidence records."""
from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


class ProtocolError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    return parse_json(path.read_text(encoding="utf-8-sig"))


def parse_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ProtocolError(f"Nonfinite JSON: {x}")))


def write_json(path: Path, value: Any, *, exclusive: bool = False) -> None:
    # Canonical serialization fails before a partial file is created.
    data = canonical(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("xb") as f:
            f.write(data)
    else:
        temp = path.with_name(path.name + ".tmp-" + os.urandom(8).hex())
        try:
            temp.write_bytes(data)
            os.replace(temp, path)
        finally:
            if temp.exists():
                temp.unlink()


def relative_path(name: str) -> PurePosixPath:
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\x00" in name:
        raise ProtocolError("Asset path must be a nonempty POSIX relative path without ADS/drives")
    p = PurePosixPath(name)
    parts = name.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
    if p.is_absolute() or any(x in ("", ".", "..") or x.endswith((".", " "))
                              or x.split(".")[0].upper() in reserved for x in parts):
        raise ProtocolError(f"Unsafe asset path: {name}")
    return p


def contained(root: Path, name: str, *, must_exist: bool = False) -> Path:
    p = relative_path(name)
    root = root.resolve(strict=True)
    candidate = root.joinpath(*p.parts)
    # Do not publish links/reparse points, even if their current target is inside root.
    current = root
    for part in p.parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ProtocolError("Linked assets are not publishable")
    resolved = candidate.resolve(strict=must_exist)
    if not resolved.is_relative_to(root):
        raise ProtocolError("Asset escapes its release root")
    return resolved


def numeric(value: Any, label: str, minimum: float = 0, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ProtocolError(f"{label} must be a finite number")
    if value < minimum or (maximum is not None and value > maximum):
        raise ProtocolError(f"{label} outside allowed range")
    return float(value)


class TraceLog:
    """Platform-written hash chain. Not a signature or an OS isolation boundary.

    Keep this file outside the writable solver environment. Solver-provided logs must
    be recorded as untrusted artifacts, not imported as platform events.
    """
    def __init__(self, path: Path):
        self.path = path

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        events = [json.loads(line, object_pairs_hook=_pairs) for line in self.path.read_text(encoding="utf-8").splitlines()]
        previous = None
        for i, event in enumerate(events):
            body = {k: v for k, v in event.items() if k != "hash"}
            if event.get("sequence") != i or event.get("previous_hash") != previous or event.get("hash") != digest(body):
                raise ProtocolError("Trace integrity failure")
            previous = event["hash"]
        return events

    def append(self, kind: str, payload: dict) -> dict:
        # A single platform controller owns each trace; concurrent writers need a broker.
        existing = self.read()
        body = {"sequence": len(existing), "previous_hash": existing[-1]["hash"] if existing else None,
                "time_utc": utc_now(), "kind": kind, "payload": payload}
        event = {**body, "hash": digest(body)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as f:
            f.write(canonical(event) + b"\n")
        return event


class BudgetExhausted(ProtocolError):
    """The task's own model/tool/wall budget is exhausted or cancelled (public category budget_exhausted)."""


class ProviderRefusal(ProtocolError):
    """The executor model provider refused the request (public category provider_refusal)."""
