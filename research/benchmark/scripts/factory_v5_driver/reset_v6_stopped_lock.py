"""Zero-call controller amendment (2026-10-01): a construct whose batch lock was left by the maintainer's between-call stop
of run 006 (constructor call completed, reviewer not started) moves to history; workspace renamed <name>.stopped-<n>."""
import sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
from mrhbench.io import read_json, write_json, utc_now
d, call = Path(sys.argv[1]), int(sys.argv[2])
s = read_json(d / "state.json"); st = s["stages"]["construct"]
assert st["status"] == "failed_needs_attribution" and "owns this run" in st["notes"][0] and not st["calls"]
moved = []
for p in ("construct", "job.json"):
    n = 1
    while (d / (p + ".stopped-%d" % n)).exists():
        n += 1
    (d / p).rename(d / (p + ".stopped-%d" % n)); moved.append(p + ".stopped-%d" % n)
s.setdefault("history", []).append({"stage": "construct", **s["stages"].pop("construct"), "set_aside": utc_now(), "moved": moved,
    "set_aside_reason": "batch lock left by maintainer stop of run 006 between calls; constructor call %d completed, reviewer not started; output kept, not reused" % call})
write_json(d / "state.json", s); print("reset", moved)
