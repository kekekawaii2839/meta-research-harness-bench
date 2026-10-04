"""Zero-call controller amendment (2026-10-01).
1. Orphan workspaces left by the maintainer's stop of run 005 (between model calls) are renamed <name>.stopped-<n> and
   logged in state history; the stage re-runs (the stopped constructor output, call 1615, is kept on disk, not reused).
2. Papers whose full text is the OpenReview PDF get the controller pypdf text extraction as a derived source
   (role paper_text_derived), because the Claude CLI Read tool refused those unencrypted PDFs as password-protected.
3. Stages that already ran on such a paper without readable full text (source_audit / adjudication) move to history."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import openreview_fetch
sys.path.insert(0, r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
from mrhbench.io import read_json, write_json, utc_now, file_hash
P = Path(r"D:/mrhbench-local-pilot/factory-v6/papers")

def aside(path):
    n = 1
    while path.with_name(path.name + ".stopped-%d" % n).exists():
        n += 1
    path.rename(path.with_name(path.name + ".stopped-%d" % n)); return path.name + ".stopped-%d" % n

u = P / "iclr2025-1vrpdV9U3i/units/WRITE_CONTENT"; s = read_json(u / "state.json")
assert "construct" not in s["stages"]
moved = [aside(u / "construct"), aside(u / "job.json")]
s.setdefault("history", []).append({"stage": "construct", "status": "stopped_by_maintainer", "set_aside": utc_now(), "moved": moved,
    "set_aside_reason": "maintainer stopped run 005 between model calls to switch to parallel workers; constructor call 1615 had completed, reviewer not started"})
write_json(u / "state.json", s); print("orphan set aside", moved)

for pid in ("iclr2025-l11DZY5Nxu", "iclr2025-z21DkDDdgq", "iclr2025-h0vC0fm1q7", "iclr2025-d1NWq4PjJW"):
    d = P / pid; m = read_json(d / "sources/manifest.json")
    if any(r["source_id"] == "openreview_paper_text" for r in m["sources"]):
        continue
    pdf = d / "sources/files/openreview_paper.pdf"
    assert file_hash(pdf) == m["openreview"]["sha256"]
    t = d / "sources/files/openreview_paper.txt"; t.write_bytes(openreview_fetch.pdf_text(pdf))
    m["sources"].append({"source_id": "openreview_paper_text", "url": m["openreview"]["url"],
        "version": "controller pypdf text extraction of openreview_paper_pdf sha256 " + m["openreview"]["sha256"],
        "sha256": file_hash(t), "bytes": t.stat().st_size, "role": "paper_text_derived",
        "local_path": t.relative_to(d.resolve()).as_posix()})
    write_json(d / "sources/manifest.json", m)
    s = read_json(d / "state.json")
    for stage in ("adjudication", "source_audit"):
        st = s["stages"].get(stage)
        if st and st["status"] in ("completed", "dropped", "failed_needs_attribution", "platform_rate_limited"):
            ws = d / stage; moved = aside(ws) if ws.exists() else None
            s.setdefault("history", []).append({"stage": stage, **s["stages"].pop(stage), "set_aside": utc_now(), "moved": moved,
                "set_aside_reason": "ran without readable paper full text (CLI Read refused the OpenReview PDF); re-run with controller text extraction"})
    write_json(d / "state.json", s)
    print(pid, "text", t.stat().st_size, "stages now", list(s["stages"]))
