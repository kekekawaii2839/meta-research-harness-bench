"""Factory v8.4 (user decision 2026-10-12: "O1 O2都做了吧"): IDEA leak rule aligned with the protocol + round-1 gate fix.

Why (zero-call analysis D:/mrhbench-local-pilot/idea-leak-analysis-20261012/analysis.json): of 15 v8 IDEA units 8 were
dropped. The persistent leaks (IXyf, Xo0Q, cyPM, pdF8) were papers whose contribution is the direct predecessor's own
stated limitation / future work: an accurate background report states it, and L1 forbade that for IDEA although AGENTS
section 3.2 defines the IDEA input as a report with "limitations and candidate gaps". Re-framers deleted the flagged
sentences (0 of the round-1 quotes survived) and in pdF8 the deletion made the report misstate its sources, which the
adjudicator then dropped. Two units (QMtr, cyPM) never got a round-1 verdict and the re-frame treated the missing
verdict as acceptable.

v8.4 = v8.3 (first-disclosure record) plus:

O2 (prompt change, prompts_next/v8_4; only leak_judge.txt and framer.txt differ from prompts_next/v8):
* leak judge, IDEA only: a limitation / condition / open question / future-work item that a cited pre-cutoff background
  source states about its own work, reported accurately and attributed, is not L1/L2 on its own; it counts only when
  the public text goes beyond the source (singles it out as THE gap, pairs it with a remedy, assembles a recipe, or
  states a framer-authored gap). L3/L4 unchanged. prediction_match is judged on the solution (method / mechanism /
  analysis design); identifying the gap or the predecessor alone is at most "partial".
* framer, IDEA background report: accuracy first - report sources' own limitations attributed; never drop a true
  condition to look less steering; in a re-frame, keep such statements and remove the editorial emphasis instead.
O1 (controller only):
* round-1 probe + leak judge always run. When construct was routed to repair by a deterministic gate (structural or
  locked-frame check), the probe sees the LOCKED FRAME (frame/assets + frame public facts), which is the public surface
  the repair must keep byte-for-byte; the v8.2 "dry pack failed -> skip" path and the v8 locked-frame skip path are gone.
* stage_reframe refuses a missing round-1 verdict for a LIT/IDEA unit (ProtocolError, failed_needs_attribution) instead
  of recording "leak gate round 1: acceptable".
Zero-call maintenance commands (no model call, the older roots are never modified):
* carry-paper: copy a paper's paper-level stages (all but units/, optionally one unit with --with-unit) from an older
  root, stamp the v8.3 first-disclosure record into the COPY, and refuse when its public cutoff differs from the cutoff
  the existing frames used.
* rejudge-final (1 model call per unit: the v8.4 leak judge on the carried unit's final repair package and its existing
  probe2 prediction): set the v8.2 leak_judge2 aside, judge again, and re-apply the controller leak gate to the
  EXISTING repair adjudication (no new adjudicator call). Only an adjudicator "pass" with a non-leaky new verdict is
  restored to completed; runtime/compile then run with the normal `run` command.
"""
from pathlib import Path
import json
import shutil
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import factory_v8_3 as v83  # noqa: E402
import factory_v8_2 as v82  # noqa: E402
import factory_v8_1 as v81  # noqa: E402
import factory_v8 as v8  # noqa: E402
import factory_v6  # noqa: E402
import factory_v5  # noqa: E402
from mrhbench.io import read_json, write_json, utc_now, ProtocolError  # noqa: E402
from mrhbench.factory import DONE  # noqa: E402

V84 = DRIVER / "prompts_next" / "v8_4"
_prev_snapshot = factory_v5.build_prompt_snapshot  # the v8.1 chain (v6 -> v8 -> v8.1 bg_screen)


def build_prompt_snapshot(dest):
    """The v8.1 snapshot chain with the v8_4 role prompts (module global swapped only for this call: no import side effect)."""
    old, v8.V8 = v8.V8, V84
    try:
        info = _prev_snapshot(dest)
    finally:
        v8.V8 = old
    info["factory_v8"]["role_prompt_dir"] = str(V84)
    return info


factory_v5.build_prompt_snapshot = build_prompt_snapshot
FRAME_PACK_NOTE = "v8.4: round-1 probe on the locked frame (construct routed to repair by a deterministic gate)"


def frame_surface(frame_dir, ws):
    """Write the locked frame as the probe/judge public surface: frame/assets -> ws/public/<path>, frame facts as records.
    Returns the normalised corpus used by the controller's verbatim quote check."""
    frame_dir, ws = Path(frame_dir), Path(ws)
    frame = read_json(frame_dir / "frame.json")
    (ws / "public").mkdir(parents=True)
    texts = []
    for f in frame["files"]:
        src = v8.contained(frame_dir, f["path"], must_exist=True)
        dst = v8.contained(ws / "public", f["path"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        texts.append(dst.read_text(encoding="utf8", errors="replace"))
    values = {"frame:fact:" + p["fact_id"]: p for p in frame.get("public_facts", [])}
    values["frame:research_question"] = frame.get("research_question")
    write_json(ws / "public_surface.json", {"records": values, "note": "solver-visible structured fields of the task "
                                            "(v8.4: taken from the locked frame because construct was routed to repair)"})
    return v8.norm(" ".join([json.dumps(values, ensure_ascii=False)] + texts + [json.dumps(values)]))


class FactoryV84(v83.FactoryV83):
    # ------------------------------------------------------------------ O1: round-1 gate always runs
    def _gate_routed(self, state):
        return "review_adjudication" in state["stages"]

    def stage_construct(self, state):
        super().stage_construct(state)
        if state.get("unit") not in v8.V8_UNITS:
            return
        st = state["stages"]
        for s in ("probe", "leak_judge"):
            if st.get(s, {}).get("status") == "skipped":
                state.setdefault("history", []).append({"stage": s, **st.pop(s), "set_aside": utc_now(),
                                                        "reason": "v8.4: the round-1 leak gate always runs"})
        self._save(state)

    def _public_pack(self, state, batch, ws):
        if batch == "construct" and state.get("unit") in v8.V8_UNITS and self._gate_routed(state):
            corpus = frame_surface(self.wdir(state) / "frame", ws)
            write_json(Path(ws) / "controller_frame_pack.json", {"at": utc_now(), "note": FRAME_PACK_NOTE})
            return corpus
        return super()._public_pack(state, batch, ws)

    def stage_probe(self, state):
        if state.get("unit") in v8.V8_UNITS:
            self._probe(state, "probe", "construct")  # bypass the v8.2 dry-pack skip
            if self._gate_routed(state):
                rec = state["stages"]["probe"]
                rec["notes"] = rec.get("notes", []) + [FRAME_PACK_NOTE]
                self._save(state)
            return
        return super().stage_probe(state)

    def stage_reframe(self, state):
        if state.get("unit") in v8.V8_UNITS and not self._final_drop(state, "review_adjudication") \
                and self._verdict(state, "leak_judge") is None:
            raise ProtocolError("v8.4: no round-1 leak verdict for a LIT/IDEA unit; a missing verdict is not 'acceptable'")
        return super().stage_reframe(state)


# ---------------------------------------------------------------------- zero-call carry
def _frame_cutoffs(pdir, units=None):
    out = {}
    for f in sorted(Path(pdir).glob("units/*/frame/frame.json")):
        u = f.parent.parent.name
        if units is None or u in units:
            out[u] = read_json(f)["cutoff_date"]
    return out


def cmd_carry_paper(root, from_root, papers, with_unit=None, lookup=None):
    root, from_root = Path(root), Path(from_root)
    done = []
    for pid in papers:
        s, d = from_root / "papers" / pid, root / "papers" / pid
        if d.exists():
            raise ProtocolError("paper already present in the v8.4 root: " + pid)
        st = read_json(s / "state.json")
        used = _frame_cutoffs(s)
        d.mkdir(parents=True)
        for item in s.iterdir():
            if item.name in ("units", "state.json"):
                continue
            (shutil.copytree if item.is_dir() else shutil.copyfile)(item, d / item.name)
        if with_unit:
            shutil.copytree(s / "units" / with_unit, d / "units" / with_unit)
        fd = v83.stamp_manifest(d, lookup, how="carry-paper from " + str(s))
        bad = {u: c for u, c in used.items() if c != fd["public_cutoff"]}
        if bad:
            shutil.rmtree(d)
            raise ProtocolError("%s: recorded public cutoff %s differs from the frames' cutoff %s; not carried"
                                % (pid, fd["public_cutoff"], bad))
        stages = {k: v for k, v in st["stages"].items() if k != "units"}
        write_json(d / "state.json", {**st, "stages": stages, "carried_from": str(s), "carried_at": utc_now(),
                                      "carried_stages": sorted(stages), "carried_unit": with_unit})
        done.append({"paper": pid, "first_disclosure": fd, "frame_cutoffs": used, "with_unit": with_unit})
    return done


def cmd_rejudge_final(factory, papers, unit="IDEA"):
    """1 model call per unit (v8.4 leak judge); the adjudicator is not called again."""
    out = []
    for pid in papers:
        state = factory.unit_state(pid, unit)
        wdir = factory.wdir(state)
        st = state["stages"]
        if not state.get("carried_unit_rejudge_ready"):
            for s in ("leak_judge2", "repair_adjudication"):
                if s not in st:
                    raise ProtocolError("%s %s: stage %s missing" % (pid, unit, s))
            for name in ("leak_judge2", "leak_judge2_ws"):
                if (wdir / name).exists():
                    (wdir / name).rename(wdir / (name + ".v82"))
            ov = wdir / "repair_adjudication" / "controller_leak_override.json"
            if ov.exists():
                ov.rename(ov.with_name("controller_leak_override.v82.json"))
            for s in ("leak_judge2", "repair_adjudication"):
                state.setdefault("history", []).append({"stage": s, **st.pop(s), "set_aside": utc_now(),
                                                        "reason": "v8.4 rejudge-final (leak rule O2); v8.2 record kept as *.v82"})
            state["carried_unit_rejudge_ready"] = True
            factory._save(state)
        factory._judge(state, "leak_judge2", "repair", "probe2")
        verdict = factory._verdict(state, "leak_judge2")
        adj = read_json(wdir / "repair_adjudication" / "review_adjudication.json")
        prev = next(h for h in reversed(state["history"]) if h["stage"] == "repair_adjudication")
        if adj["action"] == "drop":
            status, note = "dropped", "adjudicator action drop (kept; not a leak-gate decision)"
        elif factory._leaky(verdict):
            status, note = "dropped", "controller leak gate (v8.4 verdict %s): adjudicator %s -> drop" % (verdict["verdict"], adj["action"])
            write_json(wdir / "repair_adjudication" / "controller_leak_override.json",
                       {"at": utc_now(), "adjudicator_action": adj["action"], "controller_action": "drop",
                        "rule": "factory v8.4 leak gate (rejudge-final)", "leak_verdict": "leak_judge2/leak_verdict.json"})
        else:
            status, note = DONE, "v8.4 rejudge-final: leak verdict %s; adjudicator action %s kept (no new adjudicator call)" \
                % (verdict["verdict"], adj["action"])
        factory._record(state, "repair_adjudication", status, prev.get("artifacts"), prev.get("calls", []),
                        [n for n in prev.get("notes", []) if not n.startswith("controller leak gate")] + [note])
        state.pop("carried_unit_rejudge_ready", None)
        factory._save(state)
        out.append({"paper": pid, "unit": unit, "verdict": verdict["verdict"], "criteria": verdict.get("criteria_hit"),
                    "match": verdict.get("prediction_match"), "repair_adjudication": status})
    return out


def open_factory(root, max_calls=0, native=None):
    from mrhbench import factory_sources
    from mrhbench import factory_runtime
    from mrhbench.factory import CallBudget
    root = Path(root)
    return FactoryV84(root, native_factory=native or factory_v5.native_factory(root), sources=factory_sources,
                      runtime=factory_runtime, budget=CallBudget(max_calls))


for _m in (factory_v5, factory_v6, v8, v81, v82, v83):
    _m.open_factory = open_factory


def main():
    import argparse
    if len(sys.argv) > 1 and sys.argv[1] in ("carry-paper", "rejudge-final"):
        p = argparse.ArgumentParser()
        p.add_argument("cmd")
        p.add_argument("--root", required=True)
        p.add_argument("--from-root")
        p.add_argument("--papers", required=True)
        p.add_argument("--with-unit")
        p.add_argument("--max-calls", type=int, default=0)
        a = p.parse_args()
        papers = a.papers.split(",")
        if a.cmd == "carry-paper":
            res = cmd_carry_paper(a.root, a.from_root, papers, a.with_unit)
        else:
            res = cmd_rejudge_final(open_factory(a.root, a.max_calls), papers)
        print(json.dumps({a.cmd: res}, ensure_ascii=False, indent=1))
        return
    v83.main()


if __name__ == "__main__":
    main()
