"""Factory v8.2 (user decision 2026-10-11: "做8.2"): route frame-targeting review findings to the paper-blind re-framer.

Gap found in v8.1 (iclr2025-1qq1QJKM5q IDEA, dropped): the independent reviewer's accepted round-1 findings on the LOCKED
public files (background quotes, checker bugs) could never be fixed: the repair constructor may not edit locked files and
the re-frame ran only after a leak verdict, with leak fixes only. v8.2 adds one controller rule, no prompt change:

* After round-1 adjudication action "repair" (or the controller leak override), every accepted reviewer finding whose
  locator / issue / repair text names a locked frame file (or a frame fact id PF-NN) is a frame finding.
* A frame finding is ROUTED to the re-framer as {public_location, rewrite_guidance} only when its guidance (the
  adjudicator's repair_note, else the reviewer's repair_action) and locator contain no target-paper source id
  (paper_html, abs_page, paper_pdf, ...; background ids bgNNN_* are fine), no reference to the construction scope request,
  and no area-brief forbidden term. The reviewer's observed_issue (which may quote the paper) is never passed.
* Anything else is BLOCKED (kept in the repair notes for the constructor, with the reason): paper-specific coverage demands
  conflict with the v8 principle that LIT/IDEA public files are written without the paper.
* The re-frame then runs when the leak verdict is leak/uncertain (leak fixes + routed findings, as before) OR when routed
  findings exist (routed findings only). Probe2 + leak judge 2 still gate the result. If a review-only re-frame fails its
  deterministic checks twice, the old frame stays (no drop); a leak-triggered re-frame keeps the v8 rule.
Each decision is written to <unit>/reframe_review_routing.json.
"""
from pathlib import Path
import glob
import re
import shutil
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import factory_v8_1 as v81  # noqa: E402
import factory_v8 as v8  # noqa: E402
import factory_v6  # noqa: E402
import factory_v5  # noqa: E402
from mrhbench.io import read_json, write_json, utc_now  # noqa: E402
from mrhbench.factory import DONE  # noqa: E402

TARGET_SOURCE = re.compile(r"(?<![A-Za-z0-9_])(?:paper_html|paper_pdf|paper_text|paper_tex|abs_page|paper_abs)(?![A-Za-z0-9])"
                           r"|scope_request|request\.json|source paper|target paper|the paper's", re.I)
FRAME_FACT_ID = re.compile(r"\bPF-[0-9]{2}\b")


def _text(*parts):
    return " ".join(str(p) for p in parts if p)


def classify_frame_findings(review, adjudication, frame_json, forbidden_terms):
    """Return (routed, blocked, constructor_only) lists of dicts. Pure function (tested offline)."""
    files = [f["path"] for f in frame_json.get("files", [])]
    names = {p: Path(p).name for p in files}
    decisions = adjudication.get("finding_decisions") or []
    accepted = {d["finding_index"]: d for d in decisions if d.get("decision") == "accept" and d.get("finding_index") is not None}
    if not decisions:
        accepted = {i: {} for i in range(len(review.get("findings", [])))}
    terms = [t.lower() for t in forbidden_terms if t]
    routed, blocked, ctor = [], [], []
    for i, f in enumerate(review.get("findings", [])):
        if i not in accepted:
            continue
        where = _text(f.get("locator"), f.get("observed_issue"), f.get("repair_action"), f.get("fact_id"), f.get("asset_path"))
        hit = sorted({p for p in files if p in where or names[p] in where})
        if not hit and FRAME_FACT_ID.search(_text(f.get("fact_id"), f.get("locator"))):
            hit = ["frame public facts"]
        if not hit:
            ctor.append({"finding_index": i, "id": f.get("id")})
            continue
        guidance = (accepted[i].get("repair_note") or f.get("repair_action") or "").strip()
        reason = None
        if not guidance:
            reason = "no repair guidance"
        elif TARGET_SOURCE.search(_text(guidance, f.get("locator"))):
            reason = "guidance or locator cites the target paper or the construction scope request"
        else:
            low = guidance.lower()
            bad = [t for t in terms if t in low]
            if bad:
                reason = "guidance contains area-brief forbidden term(s): " + ", ".join(bad)
        row = {"finding_index": i, "id": f.get("id"), "public_location": hit}
        if reason:
            blocked.append({**row, "reason": reason})
        else:
            routed.append({**row, "rewrite_guidance": guidance})
    return routed, blocked, ctor


class FactoryV82(v81.FactoryV81):
    def _frame_routing(self, state):
        wdir = self.wdir(state)
        p = wdir / "reframe_review_routing.json"
        if p.is_file():
            return read_json(p)
        adj_path = wdir / "review_adjudication" / "review_adjudication.json"
        rv = glob.glob(str(wdir / "construct" / "*" / "reviewer" / "review.json"))
        frame = wdir / "frame" / "frame.json"
        if not adj_path.is_file() or not rv or not frame.is_file():
            rec = {"routed": [], "blocked": [], "constructor_only": [], "note": "no round-1 review to route"}
        else:
            adj = read_json(adj_path)
            if adj.get("action") == "drop":
                rec = {"routed": [], "blocked": [], "constructor_only": [], "note": "round-1 action drop"}
            else:
                terms = [t["term"] for t in self.area_brief(state["project_id"])["forbidden_terms"]]
                r, b, c = classify_frame_findings(read_json(Path(rv[0])), adj, read_json(frame), terms)
                rec = {"routed": r, "blocked": b, "constructor_only": c}
        rec.update({"at": utc_now(), "rule": "factory v8.2 frame-finding routing", "model_calls_made": 0})
        write_json(p, rec)
        return rec

    # 2026-10-11 (iclr2025-cyPMEXdqQ2 IDEA, dropped): when the structural/lock gate routed construct to repair, v8 skipped the
    # round-1 probe + leak judge, so a frame leak was first seen in the final round (drop, no re-frame). The public surface
    # is the locked frame, which the gate failure does not change: probe and judge it anyway when the package can be packed.
    GATE_SKIP_NOTE = ["construct routed to repair by a deterministic gate"]

    def stage_construct(self, state):
        super().stage_construct(state)
        if state.get("unit") not in v8.V8_UNITS:
            return
        st = state["stages"]
        if st.get("probe", {}).get("notes") == self.GATE_SKIP_NOTE and (self._batch_output(state, "construct") / "package.json").is_file():
            for s in ("probe", "leak_judge"):
                state.setdefault("history", []).append({"stage": s, **st.pop(s), "set_aside": utc_now(),
                                                        "reason": "v8.2: round-1 leak gate also runs after a deterministic gate routing"})
            self._save(state)

    def stage_probe(self, state):
        if state.get("unit") in v8.V8_UNITS and (self.wdir(state) / "review_adjudication" / "review_adjudication.json").is_file() \
                and "review_adjudication" in state["stages"]:
            import tempfile
            tmp = Path(tempfile.mkdtemp(prefix="v82-pack-"))
            try:  # dry pack only (no model call): a gate-failed package that cannot be packed keeps the v8 behaviour
                self._public_pack(state, "construct", tmp / "ws")
                packed, err = True, None
            except Exception as e:  # noqa: BLE001
                packed, err = False, "%s: %s" % (type(e).__name__, str(e)[:200])
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            if not packed:
                self._record(state, "probe", "skipped", notes=self.GATE_SKIP_NOTE + ["v8.2 dry pack failed: " + err])
                self._record(state, "leak_judge", "skipped", notes=self.GATE_SKIP_NOTE)
                return
        return super().stage_probe(state)

    def stage_reframe(self, state):
        if state.get("unit") not in v8.V8_UNITS:
            return super().stage_reframe(state)
        verdict = self._verdict(state, "leak_judge")
        leaky = self._leaky(verdict)
        if self._final_drop(state, "review_adjudication"):
            self._record(state, "reframe", "skipped", notes=["adjudicator dropped the unit"])
            return
        routing = self._frame_routing(state) if self._needs_repair(state) else {"routed": [], "blocked": []}
        routed = [{"public_location": r["public_location"], "rewrite_guidance": r["rewrite_guidance"],
                   "origin": "independent material review, round 1 (controller-filtered, paper-free)"} for r in routing["routed"]]
        if not leaky and not routed:
            self._record(state, "reframe", "skipped", notes=["leak gate round 1: acceptable; no routable frame findings (%d blocked)"
                                                              % len(routing.get("blocked", []))])
            return
        notes_in = (v8.sanitize_fixes(verdict) if leaky else []) + routed
        status, calls, notes = self._run_framer(state, "reframe", previous=self.wdir(state) / "frame", notes=notes_in)
        self._call_note(state, "reframe", "v8 re-framer (ledger role constructor)")
        trigger = "leak verdict + %d routed review finding(s)" % len(routed) if leaky else "%d routed review finding(s)" % len(routed)
        if status != DONE and not leaky:
            self._record(state, "reframe", "skipped", {}, calls,
                         notes + ["v8.2 review-only re-frame failed its deterministic checks; the round-1 frame stays locked"])
            return
        self._record(state, "reframe", status, {"frame": "reframe/frame.json"} if status == DONE else {}, calls,
                     notes + ["v8.2 trigger: " + trigger])

    def _repair(self, state, stage, source_batch, adjudication_stage, job_name):
        if state.get("unit") in v8.V8_UNITS and stage == "repair":
            routing = self._frame_routing(state)
            if routing.get("blocked"):
                p = self.wdir(state) / adjudication_stage / "review_adjudication.json"
                adj = read_json(p)
                extra = ("Controller (factory v8.2): review finding(s) %s target the locked public frame but were NOT sent to "
                         "the paper-blind framer because their repair text relies on the target paper or the construction "
                         "scope request. LIT/IDEA public files are written without the paper by design, so paper-specific "
                         "coverage of the locked files is not a repair requirement; do not attempt to edit locked files."
                         % ", ".join(str(b.get("id") or b["finding_index"]) for b in routing["blocked"]))
                if extra not in (adj.get("repair_notes") or []):
                    self._v82_extra_note = extra
        return super()._repair(state, stage, source_batch, adjudication_stage, job_name)

    def _batch(self, state, batch_root, repair_from=None, repair_notes=None, job_name="job.json"):
        extra = getattr(self, "_v82_extra_note", None)
        if extra and repair_notes:
            repair_notes = {k: list(v) + [extra] for k, v in repair_notes.items()}
            self._v82_extra_note = None
        return super()._batch(state, batch_root, repair_from=repair_from, repair_notes=repair_notes, job_name=job_name)


def open_factory(root, max_calls=0, native=None):
    from mrhbench import factory_sources
    from mrhbench import factory_runtime
    from mrhbench.factory import CallBudget
    root = Path(root)
    return FactoryV82(root, native_factory=native or factory_v5.native_factory(root), sources=factory_sources,
                      runtime=factory_runtime, budget=CallBudget(max_calls))


factory_v5.open_factory = open_factory
factory_v6.open_factory = open_factory
v8.open_factory = open_factory
v81.open_factory = open_factory


def main():
    v8.main()


if __name__ == "__main__":
    main()
