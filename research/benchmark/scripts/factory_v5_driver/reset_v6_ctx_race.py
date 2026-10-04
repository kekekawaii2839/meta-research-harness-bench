"""Zero-call controller amendment (2026-10-01): stages that failed before any model call because of the factory_v6
--workers race on the shared v5 role context (self._ctx; fixed with thread-local storage) move to history; their
workspaces are renamed <name>.ctxrace-<n>. Only stages whose recorded calls are empty and whose error matches the
race signatures are touched."""
import sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
from mrhbench.io import read_json, write_json, utc_now
from mrhbench.factory import STAGE_PATHS
SIGS = ("FileNotFoundError: [Errno 2] No such file or directory", "ProtocolError: Identity assignment and request belong to different private paper")
for arg in sys.argv[1:]:
    d, stage = arg.rsplit(":", 1); d = Path(d)
    s = read_json(d / "state.json"); st = s["stages"][stage]
    assert st["status"] == "failed_needs_attribution" and not st["calls"] and st["notes"][0].startswith(SIGS), (arg, st)
    moved = []
    for p in STAGE_PATHS[stage]:
        if (d / p).exists():
            n = 1
            while (d / (p + ".ctxrace-%d" % n)).exists():
                n += 1
            (d / p).rename(d / (p + ".ctxrace-%d" % n)); moved.append(p + ".ctxrace-%d" % n)
    s.setdefault("history", []).append({"stage": stage, **s["stages"].pop(stage), "set_aside": utc_now(), "moved": moved,
        "set_aside_reason": "factory_v6 --workers race on shared role context (zero model calls); fixed with thread-local context"})
    write_json(d / "state.json", s); print("reset", d.name, stage, moved)
