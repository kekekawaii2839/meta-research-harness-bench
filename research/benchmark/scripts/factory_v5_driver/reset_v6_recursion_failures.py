"""Zero-call controller amendment (2026-10-01): set aside review_adjudication stages that failed with the factory_v6
driver's own RecursionError (driver bug, no model call made), so the corrected driver re-runs them. The failed stage
record is kept in state["history"] with the reason; construct outputs/receipts are untouched."""
import json, sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
from mrhbench.io import read_json, write_json, utc_now
for f in sys.argv[1:]:
    p = Path(f); s = read_json(p)
    st = s["stages"].get("review_adjudication")
    assert st and st["status"] == "failed_needs_attribution" and not st["calls"] and "RecursionError" in st["notes"][0], f
    s.setdefault("history", []).append({"stage": "review_adjudication", **s["stages"].pop("review_adjudication"),
        "set_aside": utc_now(), "set_aside_reason": "factory_v6 driver bug (super(FactoryV5) recursion after rebinding the class name); zero model calls; fixed in factory_v6.open_factory"})
    write_json(p, s); print("reset", p)
