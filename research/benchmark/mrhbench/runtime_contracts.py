"""Controller runtime primitives. These do not establish filesystem isolation."""
from __future__ import annotations
import os
import signal
import subprocess
from .io import ProtocolError


class _WindowsJob:
    """Kill-on-close Job Object; assign while child is suspended to avoid races."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        class Basic(ctypes.Structure):
            _fields_ = [("process_time",ctypes.c_int64),("job_time",ctypes.c_int64),("flags",wintypes.DWORD),
                ("min_ws",ctypes.c_size_t),("max_ws",ctypes.c_size_t),("active",wintypes.DWORD),
                ("affinity",ctypes.c_size_t),("priority",wintypes.DWORD),("scheduling",wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name,ctypes.c_uint64) for name in ("read_ops","write_ops","other_ops","read_bytes","write_bytes","other_bytes")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic",Basic),("io",IO),("process_memory",ctypes.c_size_t),("job_memory",ctypes.c_size_t),
                        ("peak_process",ctypes.c_size_t),("peak_job",ctypes.c_size_t)]
        self.ctypes=ctypes
        self.kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR]; self.kernel.CreateJobObjectW.restype=wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]; self.kernel.SetInformationJobObject.restype=wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]; self.kernel.AssignProcessToJobObject.restype=wintypes.BOOL
        self.kernel.CloseHandle.argtypes=[wintypes.HANDLE]; self.kernel.CloseHandle.restype=wintypes.BOOL
        self.handle=self.kernel.CreateJobObjectW(None,None)
        if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
        info=Extended(); info.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            error=ctypes.get_last_error(); self.close(); raise ctypes.WinError(error)

    def attach_and_resume(self,proc):
        if not self.kernel.AssignProcessToJobObject(self.handle,int(proc._handle)):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        ntdll=self.ctypes.WinDLL("ntdll")
        ntdll.NtResumeProcess.argtypes=[self.ctypes.c_void_p]; ntdll.NtResumeProcess.restype=self.ctypes.c_long
        status=ntdll.NtResumeProcess(int(proc._handle))
        if status != 0: raise OSError("Could not resume job-bound process",status)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle); self.handle=None


def run_process_tree(args, *, timeout, **kwargs):
    """Like subprocess.run, but timeout terminates descendants before returning.

    Windows uses kill-on-close Job Objects; POSIX uses a new session.
    This controls time, not permissions or scientific correctness.
    """
    if timeout <= 0:
        raise ProtocolError("Process deadline exhausted before spawn")
    data = kwargs.pop("input", None)
    if kwargs.pop("capture_output", False):
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if data is not None:
        kwargs["stdin"] = subprocess.PIPE
    job = None
    if os.name == "nt":
        job = _WindowsJob()
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW | 0x00000004  # CREATE_SUSPENDED
    else:
        kwargs["start_new_session"] = True
    try:
        with subprocess.Popen(args, **kwargs) as proc:
            try:
                if job: job.attach_and_resume(proc)
            except Exception:
                proc.kill(); proc.communicate(timeout=30); raise
            try:
                out, err = proc.communicate(data, timeout=timeout)
            except subprocess.TimeoutExpired:
                if job: job.close()
                else: os.killpg(proc.pid, signal.SIGKILL)
                out, err = proc.communicate(timeout=30)
                raise subprocess.TimeoutExpired(args, timeout, output=out, stderr=err)
            return subprocess.CompletedProcess(args, proc.returncode, out, err)
    finally:
        if job: job.close()


def failure_record(*, category, phase, reason, evidence, recoverable=False):
    """Explicit typed attribution: no text-guessing or automatic zero scores."""
    if category not in {"material", "platform", "judge", "agent", "unresolved"}:
        raise ProtocolError("Unknown failure category")
    if not phase or not reason or not evidence:
        raise ProtocolError("Failure attribution requires phase/reason/evidence")
    return {"category": category, "phase": phase, "reason": reason, "evidence": evidence,
            "recoverable": bool(recoverable), "quality_score": None,
            "include_in_failure_accounting": True, "automatic_zero": False}


def capability_preflight(required, probes):
    """Run actual caller-provided capability checks; declarations aren't proof.

    Probes must return {passed: bool, evidence: nonempty JSON object}. A visual
    probe must include actual model observation evidence, not just image paths.
    """
    results = {}
    for name in required:
        if name not in probes:
            results[name] = {"passed": False, "reason": "probe_unavailable"}
            continue
        try:
            row = probes[name]()
            valid = isinstance(row, dict) and row.get("passed") is True and bool(row.get("evidence"))
            results[name] = {**row, "passed": valid} if isinstance(row, dict) else {"passed": False, "reason": "invalid_probe_result"}
        except Exception as exc:
            results[name] = {"passed": False, "error_type": type(exc).__name__, "reason": str(exc)}
    return {"ready": all(v["passed"] for v in results.values()), "capabilities": results,
            "formal_isolation_verified": False}
