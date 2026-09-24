"""Manually reviewed CPU development execution; emphatically NOT an OS sandbox.

An external maintainer must read the exact staged source and approve its snapshot
hash before execution. The model never receives or writes the approval path.
Formal arbitrary-harness execution remains disabled until isolated infrastructure
is available. This adapter neither installs packages nor permits GPU experiments.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from .io import ProtocolError, contained, digest, file_hash, read_json, write_json
from .runtime_contracts import run_process_tree


def snapshot(root):
    return [{"path": p.relative_to(root).as_posix(), "sha256": file_hash(contained(root, p.relative_to(root).as_posix(), must_exist=True))}
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts]


class ReviewedCPURunner:
    def __init__(self, *, python: Path, audit_root: Path, input_root: Path, artifacts: Path,
                 approval_wait_seconds=600, formal=False):
        if formal:
            raise ProtocolError("Reviewed CPU development execution is not a formal isolation backend")
        if not python.is_file() or not 1 <= approval_wait_seconds <= 900:
            raise ProtocolError("Invalid CPU development configuration")
        self.python, self.audit_root = python.resolve(), audit_root.resolve()
        self.input_root, self.artifacts = input_root, artifacts
        self.approval_wait_seconds = approval_wait_seconds

    def run(self, *, script: str, arguments=None, timeout_seconds=120, deadline_monotonic=None):
        arguments = [] if arguments is None else arguments
        if not isinstance(arguments, list) or any(not isinstance(x, str) for x in arguments) or len(arguments) > 20:
            raise ProtocolError("CPU arguments must be a bounded string list")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 600:
            raise ProtocolError("CPU timeout must be 1–600 seconds")
        source = contained(self.artifacts, script, must_exist=True)
        if source.suffix != ".py" or not source.is_file():
            raise ProtocolError("CPU entrypoint must be an existing Python artifact")
        job_id = "cpu-" + uuid.uuid4().hex
        job = self.audit_root/job_id
        work = job/"work"
        work.mkdir(parents=True)
        # Staged paths, including immutable public inputs, are reviewed as one unit.
        for row in snapshot(self.artifacts):
            if row["path"].split("/")[0] == "inputs":
                raise ProtocolError("inputs is reserved for immutable released assets")
            target = contained(work, row["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(contained(self.artifacts, row["path"], must_exist=True), target)
        for row in snapshot(self.input_root):
            target = contained(work, "inputs/" + row["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(contained(self.input_root, row["path"], must_exist=True), target)
        before = snapshot(work)
        request = {"job_id": job_id, "script": script, "arguments": arguments, "timeout_seconds": timeout_seconds,
                   "snapshot": before, "snapshot_hash": digest(before), "gpu_allowed": False,
                   "review_instruction": "Read exact staged source; approve only CPU code using released inputs, with no network, subprocess, package install, hidden files or unrelated writes. This is not a security sandbox.",
                   "approval_schema": {"decision": "approve_cpu_only", "snapshot_hash": digest(before), "reviewer": "required nonempty name", "review_note": "required substantive source-review note"}}
        write_json(job/"request.json", request)
        deadline = time.monotonic() + self.approval_wait_seconds
        if deadline_monotonic is not None:
            deadline = min(deadline, deadline_monotonic)
        approval_path = job/"approval.json"
        while not approval_path.exists():
            if time.monotonic() >= deadline:
                write_json(job/"result.json", {"status": "review_not_received", "executed": False, "job_id": job_id})
                raise ProtocolError("CPU code review not received within development wait; no code executed")
            time.sleep(1)
        approval = read_json(approval_path)
        if set(approval) != {"decision", "snapshot_hash", "reviewer", "review_note"} or approval["decision"] != "approve_cpu_only" or approval["snapshot_hash"] != request["snapshot_hash"] or not all(isinstance(approval[k], str) and approval[k].strip() for k in ("reviewer", "review_note")):
            raise ProtocolError("CPU approval missing/denied or not bound to exact staged code")
        if snapshot(work) != before:
            raise ProtocolError("Staged files changed after CPU approval")
        if deadline_monotonic is not None:
            remaining = deadline_monotonic - time.monotonic()
            if remaining <= 0:
                write_json(job/"result.json", {"status": "task_deadline_exhausted", "executed": False, "job_id": job_id})
                raise ProtocolError("Task deadline exhausted during CPU review; no code executed")
            timeout_seconds = min(timeout_seconds, remaining)
        env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH"}}
        env.update(CUDA_VISIBLE_DEVICES="-1", NVIDIA_VISIBLE_DEVICES="none", HIP_VISIBLE_DEVICES="-1",
                   OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONNOUSERSITE="1", PYTHONIOENCODING="utf-8")
        command = [str(self.python), "-s", "-X", "utf8", str(contained(work, script)), *arguments]
        start, status, returncode = time.monotonic(), "completed", None
        with (job/"stdout.txt").open("wb") as out, (job/"stderr.txt").open("wb") as err:
            try:
                proc = run_process_tree(command, cwd=work, env=env, stdout=out, stderr=err, timeout=timeout_seconds,
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                returncode = proc.returncode
                if returncode: status = "failed"
            except subprocess.TimeoutExpired:
                status = "timeout"
        after = snapshot(work)
        immutable = {r["path"]: r["sha256"] for r in before if r["path"].startswith("inputs/")}
        actual = {r["path"]: r["sha256"] for r in after}
        if any(actual.get(k) != v for k,v in immutable.items()):
            status = "input_integrity_violation"
        outputs = [r for r in after if not r["path"].startswith("inputs/")]
        total = sum(contained(work, r["path"], must_exist=True).stat().st_size for r in outputs)
        if total > 200000000 or any(contained(work, r["path"], must_exist=True).stat().st_size > 20000000 for r in outputs):
            status = "output_size_violation"
        if status not in {"input_integrity_violation", "output_size_violation"}:
            for row in outputs:
                target = contained(self.artifacts, row["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(contained(work, row["path"], must_exist=True), target)
        result = {"job_id": job_id, "status": status, "exit_code": returncode, "wall_seconds": time.monotonic()-start,
                  "reviewed_snapshot_hash": request["snapshot_hash"], "artifacts": outputs, "cpu_only_reviewed": True,
                  "formal_isolation_verified": False, "gpu_execution": False, "cpu_time_seconds": None}
        for name in ("stdout", "stderr"):
            p = job/(name+".txt")
            result[name + "_sha256"] = file_hash(p)
            result[name] = p.read_text(encoding="utf-8", errors="replace") if p.stat().st_size <= 500000 else None
            result[name + "_not_returned_due_to_size"] = p.stat().st_size > 500000
        write_json(job/"result.json", result)
        # Raw diagnostic streams stay in the maintainer audit. Do not reveal the
        # host's private audit/approval directories in an ordinary Python traceback.
        public_result = dict(result)
        for name in ("stdout", "stderr"):
            value = public_result[name]
            if value is not None:
                for private in (work, job, self.audit_root, self.artifacts.resolve(), self.input_root.resolve()):
                    value = value.replace(str(private), "<task-workspace>").replace(private.as_posix(), "<task-workspace>")
                public_result[name] = value
                public_result[name + "_public_text_digest"] = digest(value)
        public_result["stream_policy"] = "Host paths redacted in returned text; *_sha256 binds original private stream bytes."
        return public_result
