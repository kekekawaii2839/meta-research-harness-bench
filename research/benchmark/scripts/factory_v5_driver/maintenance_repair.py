"""Post-pilot maintenance repair of one compiled factory-v5 unit (material fixes found by the P11 trajectory review).

The standard pipeline path, not a hand edit: the controller writes the defect as a repair request (author
"controller_pilot_review"), then the unit gets one more incremental repair round exactly like a normal round:
constructor (edits a byte copy of the current final package) -> independent reviewer -> adjudicator (pass/drop only),
all through the v5 quality/identity/paging/decision wrappers, then the runtime gate and a release-v5 compile from the
repaired output. 3 model calls. The previous batches, releases and runs are kept; a drop leaves release-v4 in place.
Usage: python maintenance_repair.py <paper_id>:<UNIT> <notes.txt>
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import platform_patches  # noqa: E402,F401  (must precede every mrhbench import)
import recompile_v5_platform_notes as rv5  # noqa: E402  (applies the release-v5 prompt patches in-process)
import factory_v5  # noqa: E402
from mrhbench.io import read_json, write_json, ProtocolError  # noqa: E402

BATCH, ADJ, REQ = "maint1", "maint1_adjudication", "maint1_request"


def resume_adjudication(target):
    """The repair batch completed but the adjudicator call failed (e.g. provider 429): keep the failed attempt
    renamed, rerun only adjudication -> runtime -> compile (1 model call). The paid batch is not repeated."""
    pid, unit = target.split(":")
    factory_v5.ROUND_OF_BATCH[BATCH] = 3
    f = factory_v5.open_factory(Path(r"D:/mrhbench-local-pilot/factory-v5"), max_calls=1)
    state = f.unit_state(pid, unit)
    wdir = f.wdir(state)
    if state["stages"].get(BATCH, {}).get("status") != "completed" or state["stages"].get(ADJ, {}).get("status") == "completed":
        raise ProtocolError("resume needs a completed maintenance batch and no completed adjudication")
    if (wdir / ADJ).exists():
        n = 1
        while (wdir / ("%s.failed-%d" % (ADJ, n))).exists():
            n += 1
        (wdir / ADJ).rename(wdir / ("%s.failed-%d" % (ADJ, n)))
    finish(f, state, target, wdir)


def finish(f, state, target, wdir):
    out = f._review_adjudication(state, ADJ, BATCH, 3)
    print("adjudication:", out["action"], out.get("drop_reason"))
    if out["action"] not in ("pass", "pass_partial"):
        return
    final = wdir / BATCH / f.job_id(state) / "constructor" / "output"
    record = f.runtime.verify_runtime(final, read_json(final / "package.json"), wdir / "runtime-maint1", package_slug=f.package_slug(state))
    print("runtime:", record["status"], record.get("reasons"))
    if record["status"] != "passed":
        return
    release = next(r for r in ("release-v5", "release-v6", "release-v7") if not (wdir / r).exists())
    rv5.main([target], final_override=str(final), runtime_record=str(wdir / "runtime-maint1" / "runtime_record.json"), release=release)


def main(target, notes_path):
    pid, unit = target.split(":")
    factory_v5.ROUND_OF_BATCH[BATCH] = 3
    f = factory_v5.open_factory(Path(r"D:/mrhbench-local-pilot/factory-v5"), max_calls=3)
    state = f.unit_state(pid, unit)
    if state["stages"].get("compile", {}).get("status") != "completed":
        raise ProtocolError("maintenance repair needs a compiled unit")
    wdir = f.wdir(state)
    if (wdir / BATCH).exists() or (wdir / REQ).exists():
        raise ProtocolError("maintenance round already started for this unit")
    source = next(b for b in ("repair2", "repair", "construct") if state["stages"].get(b, {}).get("status") == "completed")
    notes = [n.strip() for n in Path(notes_path).read_text(encoding="utf8").split("\n\n") if n.strip()]
    write_json(wdir / REQ / "review_adjudication.json", {
        "schema_version": "factory-review-adjudication-1", "project_id": state["project_id"], "round": 3,
        "finding_decisions": [], "action": "repair", "repair_notes": notes, "drop_reason": None, "excluded_task_ids": [],
        "author": "controller_pilot_review", "source_batch": source,
        "evidence": "D:/mrhbench-local-pilot/p11-sonnet46low-review-{A,B}.json (independent P11 trajectory review)"}, exclusive=True)
    f._repair(state, BATCH, source, REQ, "job_maint1.json")
    rec = state["stages"][BATCH]
    print("repair batch:", rec["status"], rec.get("notes"))
    if rec["status"] != "completed":
        return
    finish(f, state, target, wdir)


if __name__ == "__main__":
    if sys.argv[1] == "--resume-adjudication":
        resume_adjudication(sys.argv[2])
    else:
        main(sys.argv[1], sys.argv[2])
