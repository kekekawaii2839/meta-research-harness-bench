"""Zero-call controller amendment (2026-10-01): papers blocked only because arXiv had no usable version are re-fetched
by the factory_v6 fetch, which adds the OpenReview camera-ready PDF (user decision: OpenReview first). The old fetch
record moves to state["history"]; the old sources/ directory is kept, renamed sources.blocked-arxiv-<n>."""
import sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
from mrhbench.io import read_json, write_json, utc_now
for d in sys.argv[1:]:
    d = Path(d); s = read_json(d / "state.json"); st = s["stages"].get("fetch")
    assert st and st["status"] == "blocked_source" and len(s["stages"]) == 1, d
    n = 1
    while (d / ("sources.blocked-arxiv-%d" % n)).exists():
        n += 1
    (d / "sources").rename(d / ("sources.blocked-arxiv-%d" % n))
    s.setdefault("history", []).append({"stage": "fetch", **s["stages"].pop("fetch"), "set_aside": utc_now(),
        "set_aside_reason": "arXiv-only fetch blocked; re-fetch with OpenReview camera-ready PDF (factory_v6)",
        "old_sources_dir": "sources.blocked-arxiv-%d" % n})
    write_json(d / "state.json", s); print("reset", d.name)
