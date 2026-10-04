"""Zero-call audit: background works whose chosen arXiv version is dated on/after the corrected cutoff
(earlier of arXiv v1 and OpenReview public date)."""
import json, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import openreview_fetch
out = []
for root in ("factory-v5", "factory-v6"):
    for pdir in sorted(glob.glob(r"D:/mrhbench-local-pilot/%s/papers/*" % root)):
        bm = os.path.join(pdir, "background", "manifest.json")
        sm = os.path.join(pdir, "sources", "manifest.json")
        if not (os.path.exists(bm) and os.path.exists(sm)):
            continue
        pid = os.path.basename(pdir)
        b = json.load(open(bm, encoding="utf8"))
        used = sorted({r.get("cutoff_date") for r in b.get("requests", b.get("results", [])) if isinstance(r, dict) and r.get("cutoff_date")})
        orv = openreview_fetch.submission_date(pid.split("-", 1)[1])[0]
        arx = ((json.load(open(sm, encoding="utf8")).get("arxiv") or {}).get("earliest_known_public_version") or {}).get("date")
        cut = min(d[:10] for d in (orv, arx) if d)
        late = []
        for r in b.get("requests", []):
            v = r.get("chosen_version")
            vd = next((x["date"] for x in r.get("versions", []) if x["version"] == v), None)
            if vd and vd >= cut:
                earlier = [x for x in r.get("versions", []) if x["date"] < cut]
                late.append({"arxiv": r.get("arxiv_id"), "chosen": "v%s %s" % (v, vd), "pre_cutoff_version_exists": bool(earlier)})
        units = sorted(u for u in ("LIT", "IDEA") if os.path.exists(os.path.join(pdir, "units", u, "state.json")) and
                       json.load(open(os.path.join(pdir, "units", u, "state.json"), encoding="utf8"))["stages"].get("compile", {}).get("status") == "completed")
        out.append({"root": root, "paper": pid, "cutoff_used": used, "corrected_cutoff": cut, "arxiv_v1": arx, "openreview_public": orv,
                    "late_background": late, "compiled_LIT_IDEA": units})
json.dump(out, open(r"D:/mrhbench-local-pilot/background_cutoff_audit_20261002.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
for r in out:
    print(r["root"], r["paper"], "used", r["cutoff_used"], "-> corrected", r["corrected_cutoff"], "| late:", len(r["late_background"]),
          [x["arxiv"] + " " + x["chosen"] + (" (pre-cutoff exists)" if x["pre_cutoff_version_exists"] else " (no pre-cutoff)") for x in r["late_background"]], "| compiled", r["compiled_LIT_IDEA"])
