"""Judge v3.8 = judge v3.7.1 evidence access with verification restored (2026-10-13).

v3.7 acceptance (rejudge-v37-review-A.json): ~65% fewer raw input tokens, but grading drifted lenient — upgrades rested
on unchecked universal statements ("every symbol is defined"), a no-results EXP left the 0 anchor, and private
evaluator guidance was skipped. Reading volume was NOT lower; verification depth was. v3.8 keeps v3.7 A/C/D and rule
15 and changes:
  * pages up to 12000 characters (v3.7: 24000); parallel reads only to open known records;
  * rule 16 verification pass and rule 17 absent-results anchor (prompt);
  * controller gates (deterministic, applied after the unchanged repo validators; a failed gate rejects the judgment
    with no score, like any other validator rejection):
      G1 complete reads: task, every private reference-* record, every submission text record <= 60000 chars, and
         (LIT) lit-citation-bundle must be read to the end;
      G2 targeted support: every dimension graded 3 or 4 cites at least one image receipt or one text receipt whose
         range is <= 6000 characters.
Rubric, anchors, rules 1-15, output schema and repo validators are unchanged. The repo is not modified.
"""
from pathlib import Path
import sys

import judge_v37
from judge_v37 import ProtocolError, write_json

VERSION = "native-judge-claude-v3.8"
PAGE_MAX = 12000
TARGETED_MAX = 6000
SUBMISSION_FULL_READ_MAX = 60000
SERVER = Path(__file__).resolve().with_name("bounded_mcp_v38.py")
judge_v37.PAGE_MAX = PAGE_MAX  # read_chars bound in this process (receipt replay)
_V37_MAKE_PROMPT = judge_v37.make_prompt

RULE11_V37 = '''11. Pages hold up to 24000 characters. When you already know several pages or records you need, request them
   together as parallel evidence_read calls in one turn instead of one per turn; the 80-call cap still applies.'''
RULE11_V38 = '''11. Pages hold up to 12000 characters. When you start, you may open several records you already know you need as
   parallel evidence_read calls in one turn; afterwards read the specific ranges your verification requires.'''
V38_RULES = '''
16. Verification pass (mandatory). After reading and before grading, for every dimension you intend to grade 3 or 4,
   re-read the specific passage(s) supporting each positive claim in its rationale with a targeted evidence_read of
   at most 6000 characters starting at the relevant place (or the image/tile receipt), and cite those targeted
   receipts in that dimension. A universal statement ("every symbol is defined", "each location contains the fact",
   "all citations support their claims") requires checking every instance; otherwise state it only for what you
   checked and lower confidence. The controller rejects a 3 or 4 whose refs contain no targeted receipt.
17. Absent results. When the solver produced none of the results a dimension evaluates (for example no experiment
   finished, no figure was produced), that dimension's 0 anchor applies unless you cite specific delivered evidence
   that meets the 1 anchor and say which anchor text it meets. Plans, code that never produced results and
   self-reports are not results.
18. Required complete reads. The controller rejects the judgment unless you read to the end: the task, every private
   reference record, every submission text record of at most 60000 characters, and (LIT) lit-citation-bundle.'''


def make_prompt(task_id, task_type, session, listed):
    text = _V37_MAKE_PROMPT(task_id, task_type, session, listed)
    if text.count(RULE11_V37) != 1:
        raise ProtocolError("v3.7 rule 11 not found once")
    text = text.replace(RULE11_V37, RULE11_V38)
    text = text.replace("pages of up to 24000 characters", "pages of up to 12000 characters")
    if "24000" in text:
        raise ProtocolError("stale 24000 page bound in v3.8 prompt")
    anchor = "Never construct an id."
    if text.count(anchor) != 1:
        raise ProtocolError("v3.7.1 rule 15 not found once")
    must = required_reads(task_type, list(session.records.values()))
    listing = chr(10) + "   Required complete reads for this task: " + ", ".join(must) + "."
    return text.replace(anchor, anchor + V38_RULES + listing)


def required_reads(task_type, records):
    by_id = {r["evidence_id"]: r for r in records}
    must = ["task"] + sorted(k for k, r in by_id.items() if k.startswith("reference-") and r["visibility"] == "private")
    must += sorted(k for k, r in by_id.items() if r["origin"] == "submission" and r["media_type"] == "text/plain"
                   and len(r["content"]) <= SUBMISSION_FULL_READ_MAX)
    if task_type == "LIT" and "lit-citation-bundle" in by_id:
        must.append("lit-citation-bundle")
    return must


def _covered(receipts, eid, length):
    spans = sorted((r["start_char"], r["end_char"]) for r in receipts.values() if r["evidence_id"] == eid and "start_char" in r)
    end = 0
    for a, b in spans:
        if a > end:
            break
        end = max(end, b)
    return end >= length


def gates(task_type, records, session, judgment):
    by_id = {r["evidence_id"]: r for r in records}
    must = required_reads(task_type, records)
    unread = [k for k in must if not _covered(session.receipts, k, len(by_id[k]["content"]))]
    untargeted = []
    for dim, entry in (judgment.get("dimensions") or {}).items():
        if entry["score"] < 3:
            continue
        ok = False
        for ref in entry["refs"]:
            r = session.receipts.get(ref)
            if r is None:
                continue
            if r["media_type"].startswith("image/") or ("start_char" in r and r["end_char"] - r["start_char"] <= TARGETED_MAX):
                ok = True
                break
        if not ok:
            untargeted.append(dim)
    return {"G1_required_complete_reads": {"required": must, "not_read_to_end": unread, "passed": not unread},
            "G2_targeted_support": {"dimensions_3_or_4_without_targeted_receipt": untargeted, "passed": not untargeted}}


def run_native_judge(*, runner, task_id, task_type, records, output, python_binary, controller_output_inventory=None, run_dir=None, dry_run=False):
    # reuse the v3.7 runner with the v3.8 prompt and server; gates are applied to the validated result
    saved = (judge_v37.make_prompt, judge_v37.SERVER, judge_v37.VERSION)
    judge_v37.make_prompt, judge_v37.SERVER, judge_v37.VERSION = make_prompt, SERVER, VERSION
    try:
        result = judge_v37.run_native_judge(runner=runner, task_id=task_id, task_type=task_type, records=records, output=output,
                                            python_binary=python_binary, controller_output_inventory=controller_output_inventory,
                                            run_dir=run_dir, dry_run=dry_run)
    finally:
        judge_v37.make_prompt, judge_v37.SERVER, judge_v37.VERSION = saved
    if dry_run or result.get("status") != "scored":
        return result
    import json
    import mrhbench.native_judge as nj
    from mrhbench.io import read_json
    out = Path(output)
    manifest = read_json(out / "evidence_manifest.json")
    state = read_json(out / "tool_state.json")
    session = nj.restore_session(manifest["records"], state)
    report = gates(task_type, manifest["records"], session, result["judgment"])
    write_json(out / "v38_gates.json", report)
    if not all(g["passed"] for g in report.values()):
        return {"status": "rejected_by_controller_gate", "gates": report, "candidate_quality": result.get("quality"),
                "candidate_dimension_scores": result.get("dimension_scores"), "judge_version": VERSION,
                "automatic_scientific_zero": False}
    result["v38_gates"] = report
    return result
