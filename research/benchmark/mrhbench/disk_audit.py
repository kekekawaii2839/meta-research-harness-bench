"""Read-only local pilot storage measurements; unavailable is never zero.

File lengths are logical bytes, not allocated clusters or Docker layer usage.
Docker output is retained verbatim because image sizes share layers and cannot
be summed as physical disk consumption. No cleanup or daemon changes occur.
"""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path
from .io import utc_now


def file_storage(path: Path):
    """Allocated file bytes where the filesystem API exposes them (not VHD capacity)."""
    path = Path(path)
    stat = path.stat()
    allocated, error = None, None
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            fn = kernel.GetCompressedFileSizeW
            fn.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
            fn.restype = wintypes.DWORD
            high = wintypes.DWORD()
            ctypes.set_last_error(0)
            low = fn(str(path.absolute()), ctypes.byref(high))
            if low == 0xffffffff and ctypes.get_last_error():
                raise ctypes.WinError(ctypes.get_last_error())
            allocated = (high.value << 32) | low
        elif hasattr(stat, "st_blocks"):
            allocated = stat.st_blocks * 512
    except OSError as exc:
        error = str(exc)
    return {"path": str(path.absolute()), "logical_bytes": stat.st_size,
            "allocated_file_bytes": allocated, "allocated_query_error": error,
            "not_exclusive_physical_ownership": True}


def tree_usage(root: Path):
    root = Path(root)
    result = {"path": str(root.absolute()), "status": "available", "files": 0,
              "logical_bytes": 0, "skipped_links": 0, "errors": []}
    if not root.exists():
        return dict(result, status="not_present", logical_bytes=None)
    if root.is_symlink():
        return dict(result, status="link_not_followed", logical_bytes=None)
    def error(exc):
        result["errors"].append(str(exc))
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=error):
        for name in list(dirs):
            p = Path(directory) / name
            if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
                dirs.remove(name)
                result["skipped_links"] += 1
        for name in files:
            p = Path(directory) / name
            try:
                if p.is_symlink():
                    result["skipped_links"] += 1
                    continue
                result["logical_bytes"] += p.stat().st_size
                result["files"] += 1
            except OSError as exc:
                error(exc)
    if result["errors"]:
        result["status"] = "partial"
    return result


def command_record(args, timeout=25):
    try:
        p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return {"status": "available" if p.returncode == 0 else "unavailable",
                "command": args, "returncode": p.returncode,
                "stdout": p.stdout, "stderr": p.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "command": args, "error": str(exc)}


def snapshot(workspace: Path, *, phase: str, drives=(), docker_binary=None, extra_trees=()):
    workspace = workspace.resolve()
    result = {"schema_version": "0.1", "captured_at": utc_now(), "phase": phase,
              "workspace": str(workspace), "scope": "local_small_batch_development",
              "measurements_are_not_atomic": True, "directories": {}, "drives": {},
              "notes": ["Directory logical bytes include separate copies and may share physical blocks.",
                        "Workspace total includes the listed subdirectories: do not add them.",
                        "Docker layers can be shared: do not sum nominal image sizes.",
                        "Drive deltas include unrelated host activity, not causal package cost.",
                        "VHDX file logical length is not necessarily allocated host disk bytes."]}
    paths = {"workspace_total": workspace, "raw_sources": workspace / "research/source_cache",
             "materials": workspace / "research/benchmark/materials",
             "audit_and_traces": workspace / "research/benchmark/audit",
             "runtime": workspace / "research/benchmark/runtime"}
    result["directories"] = {name: tree_usage(path) for name, path in paths.items()}
    for path in extra_trees:
        p = Path(path).absolute()
        result["directories"]["external:" + str(p)] = tree_usage(p)
        if p.is_dir():
            for child in sorted(p.iterdir()):
                if child.is_dir() and not child.is_symlink():
                    result["directories"]["external_child:" + str(child)] = tree_usage(child)
    if extra_trees:
        result["notes"].append("External child directories are subsets of external roots; do not add twice.")
    for drive in drives or [workspace.anchor]:
        try:
            u = shutil.disk_usage(drive)
            result["drives"][str(drive)] = dict(status="available", total=u.total, used=u.used, free=u.free)
        except OSError as exc:
            result["drives"][str(drive)] = dict(status="unavailable", error=str(exc))
    docker = docker_binary or shutil.which("docker")
    if not docker:
        result["docker"] = {"status": "unavailable", "reason": "cli_not_found", "usage_bytes": None}
    else:
        server = command_record([str(docker), "version", "--format", "{{json .Server}}"])
        result["docker"] = {"status": server["status"], "server": server, "usage_bytes": None}
        if server["status"] == "available":
            result["docker"]["system_df_verbose"] = command_record([str(docker), "system", "df", "-v"])
            result["docker"]["system_df_json"] = command_record([str(docker), "system", "df", "--format", "{{json .}}"])
            result["docker"]["daemon_info"] = command_record([str(docker), "info", "--format", "{{json .}}"])
    return result


def comparison(before, after):
    """Observed deltas only; caller labels package/build interval explicitly."""
    rows = {}
    for key, a in after["directories"].items():
        b = before["directories"].get(key, {})
        valid = a.get("status") == b.get("status") == "available"
        rows[key] = {"logical_bytes_delta": a["logical_bytes"]-b["logical_bytes"] if valid else None,
                     "complete_pair": valid}
    return {"before_phase": before["phase"], "after_phase": after["phase"], "directories": rows,
            "docker_physical_delta_bytes": None,
            "warning": "Observed interval growth, not attribution. Docker shared-layer/backing-store costs require separate inspection."}
