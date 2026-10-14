"""Re-run only the runtime gate + compile of one factory-v7 unit after a controller rule change (0 model calls).

Used 2026-10-06 after the user extended leak rule A to public checker scripts: the unit's earlier runtime failure
(string_leak_hits only) is kept - its runtime/ directory is renamed runtime.failed-N and its stage record moves to the
state history - and the unchanged final constructor output is verified and compiled again with the v7 composition.
Usage: python rerun_runtime_v7.py <paper_id>:<UNIT>
"""
from pathlib import Path
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import factory_v7  # noqa: E402,F401  (v7 prompts/materialization + v6 rules incl. leak rule A)
import factory_v6  # noqa: E402
from mrhbench.io import utc_now, ProtocolError  # noqa: E402

ROOT = Path(r"D:/mrhbench-local-pilot/factory-v7")


def main(target):
    pid, unit = target.split(":")
    f = factory_v6.open_factory(ROOT, max_calls=0)
    state = f.unit_state(pid, unit)
    rt = state["stages"].get("runtime", {})
    if rt.get("status") != "failed_needs_attribution" or rt.get("notes") != ["string_leak_hits"]:
        raise ProtocolError("only a runtime failure caused solely by string_leak_hits is re-run: %r" % (rt,))
    if "compile" in state["stages"]:
        raise ProtocolError("unit already has a compile stage")
    wdir = f.wdir(state)
    n = 1
    while (wdir / ("runtime.failed-%d" % n)).exists():
        n += 1
    (wdir / "runtime").rename(wdir / ("runtime.failed-%d" % n))
    state.setdefault("history", []).append({"stage": "runtime", **state["stages"].pop("runtime"), "set_aside": utc_now(),
                                            "moved_to": "runtime.failed-%d" % n,
                                            "reason": "leak rule A extended to public checker scripts (user 2026-10-06)"})
    state["flags"] = [x for x in state.get("flags", []) if x != "runtime_failed"]
    f.stage_runtime(state)
    print("runtime:", state["stages"]["runtime"]["status"], state["stages"]["runtime"].get("notes"))
    if state["stages"]["runtime"]["status"] == "completed":
        f.stage_compile(state)
        print("compile:", state["stages"]["compile"]["status"], state["stages"]["compile"].get("notes"))


if __name__ == "__main__":
    main(sys.argv[1])
