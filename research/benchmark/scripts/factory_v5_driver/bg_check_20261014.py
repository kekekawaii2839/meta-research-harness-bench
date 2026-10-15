"""Zero-call background availability check (2026-10-14, user "可以"): for the Posters that lost LIT/IDEA to the
pre-v8.3 missing-cutoff bug and whose original adjudication already listed background_requests, fetch those
backgrounds with the factory's own fetch_background under the v8.3/v8.4 cutoff rule (OpenReview public date minus 14
days, versions strictly before). Network only, no model calls; writes D:/mrhbench-local-pilot/bg-check-20261014/<pid>/.
Factory roots are not touched."""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark")
from mrhbench import factory_sources  # noqa: E402

OUT = Path(r"D:/mrhbench-local-pilot/bg-check-20261014")
PAPERS = {"iclr2025-z21DkDDdgq": r"D:/mrhbench-local-pilot/factory-v6/papers/iclr2025-z21DkDDdgq",
          "iclr2025-d1NWq4PjJW": r"D:/mrhbench-local-pilot/factory-v6/papers/iclr2025-d1NWq4PjJW"}
CUTOFF = "2024-09-20"  # public cutoff: OpenReview public date 2024-10-04 (no arXiv version) minus 14 days
MIN = 5

OUT.mkdir(exist_ok=True)
summary = {}
for pid, pdir in PAPERS.items():
    adj = json.loads((Path(pdir) / "adjudication" / "adjudication.json").read_text(encoding="utf8"))
    reqs = [{"request_id": "bg%03d" % i, "title": r["title"], "arxiv_id": r["arxiv_id"], "cutoff_date": CUTOFF}
            for i, r in enumerate(adj["background_requests"])]
    base = OUT / pid
    base.mkdir(exist_ok=True)
    m = factory_sources.fetch_background(reqs, base / "background", base_dir=base)
    st = {}
    for r in m["requests"]:
        st[r["status"]] = st.get(r["status"], 0) + 1
    found = sum(1 for s in m["sources"] if s["role"] == "background_paper")
    summary[pid] = {"requested": len(reqs), "status_counts": st, "background_papers_fetched": found,
                    "meets_min_before_bg_screen": found >= MIN,
                    "rows": [{"id": r["request_id"], "status": r["status"], "arxiv": r["arxiv_id"],
                              "version": r["chosen_version"], "title": r["title"][:90]} for r in m["requests"]]}
    print(pid, len(reqs), st, "fetched", found, flush=True)
(OUT / "summary.json").write_text(json.dumps({"cutoff": CUTOFF, "min_background_found": MIN, "papers": summary},
                                             ensure_ascii=False, indent=1), encoding="utf8", newline="")
