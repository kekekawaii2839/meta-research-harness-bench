"""Build a self-contained local HTML review page for factory-v5 units (read-only over the factory root)."""
from pathlib import Path
import html
import json
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else r"D:/mrhbench-local-pilot/factory-v5")
LEDGER = Path(r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark\audit\development_call_ledger.json")
OUT = ROOT / "review" / "index.html"
UNIT_ORDER = ["EXP", "WRITE_EVIDENCE", "WRITE_CONTENT", "LIT", "IDEA"]
STAGES = ["construct", "review_adjudication", "repair", "repair_adjudication", "repair2", "repair2_adjudication", "runtime", "compile"]
TEXT_EXT = {".md", ".txt", ".py", ".json", ".csv", ".tex", ".yaml", ".yml"}


def rj(p):
    return json.loads(Path(p).read_text(encoding="utf8"))


def e(s):
    return html.escape(str(s))


ledger = {a["id"]: a for a in rj(LEDGER)["attempts"] if "id" in a}


def cost(ids):
    rows = [ledger[i] for i in ids if i in ledger]
    tin = tout = secs = 0
    for a in rows:
        u = a.get("usage") or {}
        tin += sum(u.get(k) or 0 for k in ("input_tokens", "cached_input_tokens", "cache_write_input_tokens"))
        tout += u.get("output_tokens") or 0
        secs += a.get("wall_seconds") or 0
    return len(rows), tin, tout, secs


def unit_calls(ustate, udir):
    ids = []
    for st in ustate["stages"].values():
        ids += st.get("calls", [])
    # include failed/set-aside attempts recorded in history
    for h in ustate.get("history", []):
        ids += h.get("calls", [])
    # also any ledger attempt whose artifact dir lies under this unit's batch dirs is not traceable here; use explicit ids
    return sorted(set(i for i in ids if isinstance(i, int)))


def findings_html(review):
    if not review:
        return "<p class=muted>no review</p>"
    out = ["<p><b>reviewer decision:</b> <span class='tag %s'>%s</span></p><ul>" % (e(review.get("decision")), e(review.get("decision")))]
    for f in review.get("findings", []):
        out.append("<li><span class='sev'>%s</span> %s<br><span class=muted>fix: %s</span></li>" % (
            e(f.get("severity")), e(f.get("observed_issue", "")), e(f.get("repair_action", ""))))
    return "".join(out) + "</ul>"


def adj_html(adj):
    if not adj:
        return ""
    s = "<p><b>adjudication:</b> <span class='tag %s'>%s</span>%s</p>" % (e(adj["action"]), e(adj["action"]),
        (" — " + e(adj["drop_reason"])) if adj.get("drop_reason") else "")
    if adj.get("repair_notes"):
        s += "<ol>" + "".join("<li>%s</li>" % e(n) for n in adj["repair_notes"]) + "</ol>"
    return s


def asset_html(root):
    parts = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        size = p.stat().st_size
        if p.suffix.lower() in TEXT_EXT and size < 200_000:
            body = p.read_text(encoding="utf8", errors="replace")
            parts.append("<details><summary><code>%s</code> <span class=muted>(%d B)</span></summary><pre>%s</pre></details>" % (e(rel), size, e(body)))
        else:
            parts.append("<div><code>%s</code> <span class=muted>(%d B, not shown)</span></div>" % (e(rel), size))
    return "".join(parts)


def unit_section(pid, unit, udir):
    st = rj(udir / "state.json")
    job = "%s__%s" % (pid, unit)
    stages = st["stages"]
    final = "done" if stages.get("compile", {}).get("status") == "completed" else next(
        (v["status"] for v in stages.values() if v["status"] not in ("completed", "skipped")), "in progress")
    n, tin, tout, secs = cost(unit_calls(st, udir))
    h = ["<section class=unit id='%s-%s'><h3>%s <span class='tag %s'>%s</span></h3>" % (e(pid), e(unit), e(unit), e(final), e(final))]
    h.append("<p class=muted>stages: %s</p>" % " · ".join("%s=%s" % (k, stages[k]["status"]) for k in STAGES if k in stages))
    h.append("<p><b>cost</b>: %d calls · input %.2fM tokens (incl. cache) · output %.1fk · model time %.1f min</p>" % (n, tin / 1e6, tout / 1e3, secs / 60))
    for batch, adjname, label in (("construct", "review_adjudication", "Round 1"), ("repair", "repair_adjudication", "Round 2 (incremental repair)"),
                                  ("repair2", "repair2_adjudication", "Round 3 (incremental repair)")):
        rv = udir / batch / job / "reviewer" / "review.json"
        ad = udir / adjname / "review_adjudication.json"
        if rv.exists() or ad.exists():
            h.append("<details %s><summary><b>%s</b></summary>%s%s</details>" % (
                "", label, findings_html(rj(rv) if rv.exists() else None), adj_html(rj(ad) if ad.exists() else None)))
    rel = udir / "release" / "identity_release_record.json"
    if rel.exists():
        rec = rj(rel)
        for r in rec["releases"]:
            troot = Path(r["release_root"])
            task = rj(troot / "task.json")
            res = task["resources"]
            h.append("<h4>Released task (what the solver sees) — <code>%s</code></h4>" % e(r["task_id"]))
            h.append("<p class=muted>identity scan: %s · container %s · budget %s · release dir <code>%s</code></p>" % (
                e(r["scan"].get("status")), e(json.dumps(res["container"])), e(json.dumps(res["execution_budget"])), e(troot)))
            h.append("<details><summary>solver prompt</summary><pre>%s</pre></details>" % e(task["prompt"]))
            h.append("<div class=assets>%s</div>" % asset_html(troot / "assets"))
        out = next((udir / b / job / "constructor" / "output" for b in ("repair2", "repair", "construct")
                    if (udir / b / job / "constructor" / "output" / "package.json").exists()), None)
        if out is not None:
            priv = [p for p in out.rglob("*") if p.is_file() and "private" in p.relative_to(out).as_posix()]
            if priv:
                h.append("<details><summary>private judge/reference materials (not shown to solver)</summary>%s</details>" % "".join(
                    "<details><summary><code>%s</code></summary><pre>%s</pre></details>" % (
                        e(p.relative_to(out).as_posix()), e(p.read_text(encoding="utf8", errors="replace")[:150_000])) for p in sorted(priv)))
    return "".join(h) + "</section>"


def main():
    papers = []
    total = [0, 0, 0, 0]
    for pdir in sorted((ROOT / "papers").iterdir()):
        if not (pdir / "units").exists():
            continue
        st = rj(pdir / "state.json")
        units = [u for u in UNIT_ORDER if (pdir / "units" / u / "state.json").exists()]
        pcalls = sorted(set(i for v in st["stages"].values() for i in v.get("calls", []) if isinstance(i, int)))
        n, tin, tout, secs = cost(pcalls)
        body = ["<h2>%s</h2><p class=title>%s</p>" % (e(pdir.name), e(st.get("title")))]
        body.append("<p><b>paper-level</b> (source audit + scope adjudication): %d calls · input %.2fM · output %.1fk · %.1f min</p>" % (n, tin / 1e6, tout / 1e3, secs / 60))
        for i, v in enumerate((n, tin, tout, secs)):
            total[i] += v
        for u in units:
            body.append(unit_section(pdir.name, u, pdir / "units" / u))
            c = cost(unit_calls(rj(pdir / "units" / u / "state.json"), pdir / "units" / u))
            for i, v in enumerate(c):
                total[i] += v
        papers.append("".join(body))
    failed = [a for a in ledger.values() if a.get("artifact_directory")
              and Path(a["artifact_directory"]).resolve().is_relative_to(ROOT.resolve())
              and a.get("status") not in ("completed", "reserved")]
    fsum = cost([a["id"] for a in failed])
    failed_html = "<p class=muted>另有失败/被限额中断的调用（已入账、未计入上面的单元成本）：%s；合计输入 %.2fM · 输出 %.1fk · %.1f 分钟</p>" % (
        ", ".join("%d(%s,%s)" % (a["id"], a.get("role"), a.get("status")) for a in sorted(failed, key=lambda a: a["id"])) or "无",
        fsum[1] / 1e6, fsum[2] / 1e3, fsum[3] / 60)
    papers.insert(0, failed_html)
    page = """<!doctype html><html lang=zh><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Factory v5 Review</title><style>
:root{--bg:#fff;--fg:#1d1d1f;--muted:#6b6b70;--card:#f5f5f7;--line:#ddd;--ok:#1a7f37;--warn:#9a6700;--bad:#cf222e}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#111;--fg:#eee;--muted:#999;--card:#1c1c1e;--line:#333}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px}
h2{border-bottom:2px solid var(--line);padding-top:24px}.title{color:var(--muted);margin-top:-8px}
.unit{background:var(--card);border-radius:10px;padding:12px 16px;margin:14px 0}.muted{color:var(--muted);font-size:13px}
pre{white-space:pre-wrap;word-break:break-word;background:var(--bg);border:1px solid var(--line);padding:10px;border-radius:6px;max-height:600px;overflow:auto;font-size:13px}
.tag{padding:1px 8px;border-radius:10px;font-size:12px;background:var(--line)}.tag.done,.tag.pass,.tag.pass_with_pending_runtime{background:var(--ok);color:#fff}
.tag.repair,.tag.revise{background:var(--warn);color:#fff}.tag.drop,.tag.reject,.tag.dropped{background:var(--bad);color:#fff}
.sev{font-weight:600;margin-right:6px}details{margin:6px 0}summary{cursor:pointer}code{font-size:13px}
</style></head><body><h1>Factory v5 小批量材料包审核</h1>
<p>运行根 <code>%s</code>。所有发布包均为私有审核暂存，语义门待人工验收，未准入solver。</p>
<p><b>合计</b>：%d 次调用 · 输入 %.1fM tokens（含缓存）· 输出 %.0fk · 模型时间 %.0f 分钟</p>%s</body></html>""" % (
        e(ROOT), total[0], total[1] / 1e6, total[2] / 1e3, total[3] / 60, "".join(papers))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf8")
    print(OUT)


if __name__ == "__main__":
    main()
