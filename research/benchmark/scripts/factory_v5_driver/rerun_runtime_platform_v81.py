"""Zero-call recovery for factory-v8.1 units whose runtime gate failed only because the Docker engine was not running
(2026-10-09: Docker Desktop had not restarted after a machine reboot; build.log shows the engine pipe missing).

Checks: runtime status failed_needs_attribution with notes ["image_build_failed"] AND runtime/build.log contains the
Docker connect error. The failed runtime directory is renamed runtime.failed-N, its stage record moves to the state
history, then the unchanged final constructor output is verified and compiled again with the v8.1 composition.
Usage: python rerun_runtime_platform_v81.py <root> <paper_id>:<UNIT> [...]
"""
from pathlib import Path
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import factory_v8_1  # noqa: E402
from mrhbench.io import utc_now, ProtocolError  # noqa: E402

ENGINE_DOWN = ("dockerDesktopLinuxEngine", "error during connect")


def rerun(root, target):
    pid, unit = target.split(":")
    f = factory_v8_1.open_factory(Path(root), max_calls=0)
    state = f.unit_state(pid, unit)
    rt = state["stages"].get("runtime", {})
    wdir = f.wdir(state)
    log = wdir / "runtime" / "build.log"
    if rt.get("status") != "failed_needs_attribution" or rt.get("notes") != ["image_build_failed"] or not log.is_file() \
            or not all(s in log.read_text(encoding="utf8", errors="replace") for s in ENGINE_DOWN):
        raise ProtocolError("not a Docker-engine-down runtime failure: %r" % (rt,))
    if "compile" in state["stages"]:
        raise ProtocolError("unit already has a compile stage")
    n = 1
    while (wdir / ("runtime.failed-%d" % n)).exists():
        n += 1
    (wdir / "runtime").rename(wdir / ("runtime.failed-%d" % n))
    state.setdefault("history", []).append({"stage": "runtime", **state["stages"].pop("runtime"), "set_aside": utc_now(),
                                            "moved_to": "runtime.failed-%d" % n,
                                            "reason": "platform: Docker engine was not running (no model call)"})
    state["flags"] = [x for x in state.get("flags", []) if x != "runtime_failed"]
    f.stage_runtime(state)
    out = {"target": target, "runtime": state["stages"]["runtime"]["status"]}
    if state["stages"]["runtime"]["status"] == "completed":
        f.stage_compile(state)
        out["compile"] = state["stages"]["compile"]["status"]
        out["notes"] = state["stages"]["compile"].get("notes")
    return out


if __name__ == "__main__":
    for t in sys.argv[2:]:
        print(rerun(sys.argv[1], t))
