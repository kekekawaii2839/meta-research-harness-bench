"""In-process platform fixes applied until the equivalent repo change is committed (then these become no-ops).

Must be imported BEFORE any other mrhbench module so later `from ... import` bindings see the patched code.
1. materials.export_task: factory asset paths already start with "assets/"; do not add a second "assets/"
   prefix. Public assets then live at /inputs/public/<package asset path>, as task texts, the constructor
   runtime contract and the runtime smoke all assume. Legacy tasks without the prefix are unchanged.
2. container_runtime: solver containers get MRH_PUBLIC_ROOT=/inputs/public (runtime smoke already sets it).
Repo files are never modified; APPLIED records what was patched for provenance.
"""
from pathlib import Path
import sys

BENCH = Path(r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
sys.path.insert(0, str(BENCH))
if any(m.startswith("mrhbench.") for m in sys.modules):
    raise ImportError("platform_patches must be imported before any mrhbench module")

import mrhbench.materials as _materials  # noqa: E402
import mrhbench.container_runtime as _runtime  # noqa: E402

APPLIED = {}

_OLD_EXPORT = '"assets/" + asset["path"]'
_NEW_EXPORT = '(asset["path"] if asset["path"].startswith("assets/") else "assets/" + asset["path"])'
_src = Path(_materials.__file__).read_text(encoding="utf8")
if _src.count(_OLD_EXPORT) == 2:
    exec(compile(_src.replace(_OLD_EXPORT, _NEW_EXPORT), _materials.__file__, "exec"), _materials.__dict__)
    APPLIED["materials.export_task"] = "single assets/ prefix (in-process)"
elif _NEW_EXPORT in _src:
    APPLIED["materials.export_task"] = "repo already fixed"
else:
    raise ImportError("materials.export_task changed unexpectedly; review platform_patches")

_src = Path(_runtime.__file__).read_text(encoding="utf8")
_ANCHOR = "'--env','MPLBACKEND=Agg',"
if "MRH_PUBLIC_ROOT=/inputs/public'" in _src:
    APPLIED["container_runtime.MRH_PUBLIC_ROOT"] = "repo already fixed"
else:
    if "MRH_PUBLIC_ROOT=/inputs/public/assets" in _src:
        _src = _src.replace("MRH_PUBLIC_ROOT=/inputs/public/assets", "MRH_PUBLIC_ROOT=/inputs/public")
    elif _src.count(_ANCHOR) == 1:
        _src = _src.replace(_ANCHOR, _ANCHOR + "'--env','MRH_PUBLIC_ROOT=/inputs/public',")
    else:
        raise ImportError("container_runtime changed unexpectedly; review platform_patches")
    exec(compile(_src, _runtime.__file__, "exec"), _runtime.__dict__)
    APPLIED["container_runtime.MRH_PUBLIC_ROOT"] = "/inputs/public (in-process)"

# 3. container_runtime.exec: a per-call tool timeout shorter than the session deadline must end only that command,
#    not the whole container session (previously the docker-exec client was killed and the session torn down,
#    so one 60 s tool timeout ended the task). The command now runs under in-container coreutils `timeout`
#    (signals its whole process group, then SIGKILL), the host allowance gets a grace margin, and the result is
#    labelled tool_timeout. Hitting the session deadline or output overflow still ends the session as before.
_OLD_EXEC = """            allowance=min(self.remaining_seconds,timeout if timeout is not None else self.remaining_seconds)
            result=self._command(['docker','exec',*(['-i'] if _stdin is not None else []),self.cid,*argv],
                                 timeout=allowance,stdin=_stdin,kill_session_on_limit=True)"""
_NEW_EXEC = """            per_call=timeout is not None and timeout+15<self.remaining_seconds
            if per_call:
                argv=['timeout','-s','TERM','-k','5','%.3f'%timeout,*argv]
            allowance=min(self.remaining_seconds,timeout+12 if per_call else (timeout if timeout is not None else self.remaining_seconds))
            result=self._command(['docker','exec',*(['-i'] if _stdin is not None else []),self.cid,*argv],
                                 timeout=allowance,stdin=_stdin,kill_session_on_limit=True)
            if per_call and not result['timed_out'] and result['returncode'] in (124,137) and result['wall_seconds']>=timeout-0.5:
                result['timed_out']=True;result['tool_timeout']=True;result['session_kept']=True"""
_src = Path(_runtime.__file__).read_text(encoding="utf8")
if "tool_timeout" in _src:
    APPLIED["container_runtime.exec_tool_timeout"] = "repo already fixed"
elif _src.count(_OLD_EXEC) == 1:
    _src = _src.replace(_OLD_EXEC, _NEW_EXEC)
    if "MRH_PUBLIC_ROOT=/inputs/public'" not in _src:
        _src = _src.replace(_ANCHOR, _ANCHOR + "'--env','MRH_PUBLIC_ROOT=/inputs/public',") if "MRH_PUBLIC_ROOT" not in _src else _src.replace("MRH_PUBLIC_ROOT=/inputs/public/assets", "MRH_PUBLIC_ROOT=/inputs/public")
    exec(compile(_src, _runtime.__file__, "exec"), _runtime.__dict__)
    APPLIED["container_runtime.exec_tool_timeout"] = "per-call timeout ends only the command (in-process)"
else:
    raise ImportError("container_runtime.exec changed unexpectedly; review platform_patches")

# 4. executor_broker.worker_path: task texts/contracts say "write to /work/...", so executors pass absolute
#    "/work/x" paths; the broker only accepted "x" and returned an opaque invalid_request. An absolute path
#    under the tool's own root is now normalised to the relative form; everything else is checked as before.
import mrhbench.executor_broker as _broker  # noqa: E402
_orig_worker_path = _broker.worker_path
if not getattr(_orig_worker_path, "_accepts_absolute", False):
    def worker_path(value, *, root="/work"):
        if isinstance(value, str) and value.startswith(root + "/"):
            value = value[len(root) + 1:]
        return _orig_worker_path(value, root=root)
    worker_path._accepts_absolute = True
    _broker.worker_path = worker_path
    APPLIED["executor_broker.worker_path"] = "accept absolute paths under the tool root (in-process)"

# 5. io.write_json: on Windows os.replace fails with PermissionError while another process (console, second
#    pilot) has the target open for reading; call 1139's ledger.finish was lost that way. Retry for ~5 s.
import time as _time  # noqa: E402
import mrhbench.io as _io  # noqa: E402
_orig_write_json = _io.write_json
if not getattr(_orig_write_json, "_retries_replace", False):
    def write_json(path, value, *, exclusive=False):
        if exclusive:
            return _orig_write_json(path, value, exclusive=True)
        data = _io.canonical(value) + b"\n"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp-" + _io.os.urandom(8).hex())
        try:
            temp.write_bytes(data)
            for attempt in range(50):
                try:
                    _io.os.replace(temp, path)
                    break
                except PermissionError:
                    if attempt == 49:
                        raise
                    _time.sleep(0.1)
        finally:
            if temp.exists():
                temp.unlink()
    write_json._retries_replace = True
    _io.write_json = write_json
    for _name, _mod in list(sys.modules.items()):
        if _name.startswith("mrhbench.") and getattr(_mod, "write_json", None) is _orig_write_json:
            _mod.write_json = write_json
    APPLIED["io.write_json"] = "retry os.replace on PermissionError (in-process)"

# 6. container_runtime: solver containers run with --init (tini as PID 1) so processes orphaned by a per-call tool
#    timeout (patch 3) are reaped instead of lingering as zombies that count against the task's PID limit.
_orig_control = _runtime.ContainerSession._control
if getattr(_orig_control, "_adds_init", False):
    APPLIED["container_runtime.init"] = "already patched"
else:
    def _control(self, args, label, timeout=30):
        if args and args[0] == "create" and "--init" not in args:
            args = ["create", "--init", *args[1:]]
        return _orig_control(self, args, label, timeout)
    _control._adds_init = True
    _runtime.ContainerSession._control = _control
    APPLIED["container_runtime.init"] = "docker create --init (in-process)"
