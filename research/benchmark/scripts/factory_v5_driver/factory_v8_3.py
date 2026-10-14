"""Factory v8.3 (2026-10-12): record the first-disclosure date at fetch, so adjudication sees it.

Gap found in v6-v8.2 (zero-call review 2026-10-12): the fetch stage wrote only the arXiv version history into
papers/<pid>/sources/manifest.json; the OpenReview public date (note odate) was looked up later, in the background stage
(factory_v6.FactoryV6.background_cutoff). Adjudication runs before the background stage and reads the manifest, so for a
paper without an arXiv version it saw no date at all and deferred LIT/IDEA under policy E2 (h0vC0fm1q7, oANkBaVci5,
spDUv05cEq, kbjJ9ZOakb); early v6 background stages withdrew LIT/IDEA for "no cutoff date" (z21DkDDdgq, d1NWq4PjJW).

v8.3 changes the controller only (no prompt change; the frozen prompt snapshot is the v8.2 one):

* fetch: after the v6 fetch, the controller writes manifest["first_disclosure"] (schema first-disclosure-1):
  arxiv_v1, openreview_public (note odate via the official API), disclosure_cutoff = min of the two, public_cutoff =
  disclosure_cutoff - 14 days (v8.1 rule), basis and lookup status. The adjudication / source-audit workspaces copy the
  manifest (``{**manifest, "sources": published}``), so the adjudicator now sees a dated earliest known public version.
* single source of truth: background_cutoff() and controller_cutoff() (background stage, bg_screen, frame, build_job)
  read this record; there is no second live lookup. A manifest without the record is an error in a v8.3 root.
* carry-dated: copies the fetched sources (and optionally other paper stages that do not depend on the date, e.g.
  source_audit, area_brief) of papers from an older root into the v8.3 root and stamps the record into the COPIED manifest.
  The older root's files and states are not touched.
Credentials stay inside openreview_fetch (controller only); nothing secret is written.
"""
from pathlib import Path
import json
import shutil
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import factory_v8_2 as v82  # noqa: E402
import factory_v8_1 as v81  # noqa: E402
import factory_v8 as v8  # noqa: E402
import factory_v6  # noqa: E402
import factory_v5  # noqa: E402
from mrhbench.io import read_json, write_json, utc_now, ProtocolError  # noqa: E402
from mrhbench.factory import DONE  # noqa: E402

SCHEMA = "first-disclosure-1"
RULE = ("disclosure_cutoff = earlier of arXiv v1 (controller arXiv title search at fetch) and the OpenReview public date "
        "(note odate, official API); public_cutoff = disclosure_cutoff - %d days (user decision 2026-10-06). This is the "
        "earliest KNOWN public version for policy E2; it is not proof of earliest disclosure." % v81.PUBLIC_CUTOFF_OFFSET_DAYS)


def disclosure_record(manifest, forum_id, lookup=None):
    """Pure apart from `lookup` (default: openreview_fetch.submission_date)."""
    import openreview_fetch
    lookup = lookup or openreview_fetch.submission_date
    arxiv = ((manifest.get("arxiv") or {}).get("earliest_known_public_version") or {}).get("date")
    arxiv = str(arxiv)[:10] if arxiv else None
    try:
        orv, status = lookup(forum_id)[0], "found"
    except openreview_fetch.OpenReviewFetchError as e:  # its messages carry no secrets by construction
        orv, status = None, "failed: %s" % e
    dates = sorted(d for d in (arxiv, orv) if d)
    disclosure = dates[0] if dates else None
    if not disclosure:
        basis = "none"
    elif arxiv == orv:
        basis = "arxiv_v1 = openreview_public"
    else:
        basis = "arxiv_v1" if disclosure == arxiv else "openreview_public"
    return {"schema_version": SCHEMA, "arxiv_v1": arxiv, "openreview_public": orv, "openreview_lookup": status,
            "disclosure_cutoff": disclosure, "public_cutoff": v81.public_cutoff(disclosure) if disclosure else None,
            "public_offset_days": v81.PUBLIC_CUTOFF_OFFSET_DAYS, "basis": basis, "verified": False, "rule": RULE,
            "recorded_at": utc_now()}


def stamp_manifest(pdir, lookup=None, how="fetch"):
    path = Path(pdir) / "sources" / "manifest.json"
    m = read_json(path)
    rec = disclosure_record(m, Path(pdir).name.split("-", 1)[1], lookup)
    m["first_disclosure"] = {**rec, "recorded_by": how}
    write_json(path, m)
    return m["first_disclosure"]


class FactoryV83(v82.FactoryV82):
    def stage_fetch(self, state):
        super().stage_fetch(state)
        pdir = self.paper_dir(state["project_id"])
        if (pdir / "sources" / "manifest.json").exists():
            fd = stamp_manifest(pdir, how="fetch")
            rec = state["stages"]["fetch"]
            rec["notes"].append("first disclosure %s (basis %s; arxiv_v1 %s, openreview_public %s); public cutoff %s"
                                % (fd["disclosure_cutoff"], fd["basis"], fd["arxiv_v1"], fd["openreview_public"], fd["public_cutoff"]))
            self._save(state)

    def background_cutoff(self, pdir):
        fd = read_json(Path(pdir) / "sources" / "manifest.json").get("first_disclosure")
        if not fd or fd.get("schema_version") != SCHEMA:
            raise ProtocolError("v8.3: sources/manifest.json has no first_disclosure record (fetch in v8.3 or carry-dated)")
        return fd["disclosure_cutoff"], {"arxiv_v1": fd["arxiv_v1"], "openreview_public": fd["openreview_public"],
                                         "basis": fd["basis"], "recorded_in": "sources/manifest.json first_disclosure"}

    def controller_cutoff(self, project_id):
        cutoff, basis = super().controller_cutoff(project_id)
        recorded = read_json(self.paper_dir(project_id) / "sources" / "manifest.json")["first_disclosure"]["public_cutoff"]
        if cutoff != recorded:
            raise ProtocolError("public cutoff %s differs from the recorded %s" % (cutoff, recorded))
        return cutoff, basis


def cmd_carry_dated(root, from_root, papers, keep=("fetch",), lookup=None):
    """Carry fetched sources (plus the date-independent paper stages in `keep`) into a v8.3 root and stamp the record."""
    root, from_root = Path(root), Path(from_root)
    allowed = {"fetch": "sources", "source_audit": "source_audit", "area_brief": "area_brief"}
    if set(keep) - set(allowed) or "fetch" not in keep:
        raise ProtocolError("carry-dated keeps fetch plus optionally source_audit/area_brief, got %s" % (keep,))
    out = []
    for pid in papers:
        s, d = from_root / "papers" / pid, root / "papers" / pid
        if d.exists():
            raise ProtocolError("paper already present in the v8.3 root: " + pid)
        st = read_json(s / "state.json")
        for stage in keep:
            if (st["stages"].get(stage) or {}).get("status") != DONE:
                raise ProtocolError("%s: stage %s not done in %s" % (pid, stage, from_root))
        d.mkdir(parents=True)
        for stage in keep:
            shutil.copytree(s / allowed[stage], d / allowed[stage])
        fd = stamp_manifest(d, lookup, how="carry-dated from " + str(s))
        write_json(d / "state.json", {**st, "stages": {k: v for k, v in st["stages"].items() if k in keep}, "flags": [],
                                      "history": [], "carried_from": str(s), "carried_at": utc_now(), "carried_stages": list(keep)})
        out.append({"paper": pid, "first_disclosure": fd})
    return out


def open_factory(root, max_calls=0, native=None):
    from mrhbench import factory_sources
    from mrhbench import factory_runtime
    from mrhbench.factory import CallBudget
    root = Path(root)
    return FactoryV83(root, native_factory=native or factory_v5.native_factory(root), sources=factory_sources,
                      runtime=factory_runtime, budget=CallBudget(max_calls))


factory_v5.open_factory = open_factory
factory_v6.open_factory = open_factory
v8.open_factory = open_factory
v81.open_factory = open_factory
v82.open_factory = open_factory


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "carry-dated":
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("cmd")
        p.add_argument("--root", required=True)
        p.add_argument("--from-root", required=True)
        p.add_argument("--papers", required=True)
        p.add_argument("--keep", default="fetch")
        a = p.parse_args()
        print(json.dumps({"carried": cmd_carry_dated(a.root, a.from_root, a.papers.split(","), tuple(a.keep.split(",")))},
                         ensure_ascii=False, indent=1))
        return
    v8.main()


if __name__ == "__main__":
    main()
