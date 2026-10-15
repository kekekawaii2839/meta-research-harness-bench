"""Judge v3.10 = judge v3.9.1 + controller-enforced consistency (2026-10-13; user approved: reject, not auto-cap).

v3.9 acceptance (rejudge-v39-review-A.json): ~30% cheaper than v3.6 at list price with error count equal to a v3.6
repeat (5 vs 5), but the remaining errors were lenient: an EXP with no results got conclusion_credibility 2 (rule 17
broken while the rationale said no conclusion was supported), a fidelity 4 next to a fidelity defect noted under
another dimension, one double charge, and notation-check counts that did not add up. v3.10 adds:
  rule 21 + G4  EXP no-results cap: when every required non-code deliverable of the unit's checks.json "files" check
                is missing in controller-output-checks, test_validity, rigor and conclusion_credibility must be <= 1;
  rule 22 + G5  a dimension named in serious_issues.affected_dimensions cannot score 4;
  rule 23       defect attribution table (each defect charged to one dimension; complements rule 10);
  rule 24 + G6  notation check id "notation-c<N>-r<M>" with N + M equal to the number of symbol-check candidates;
  IDEA          public reference (background report) records join the required complete reads.
A failed gate rejects the judgment (no score, no retry). Rubric, anchors, schema and repo validators are unchanged.
"""
import json
import re

import judge_v39

VERSION = "native-judge-claude-v3.10"
CHECKS_SPEC = None  # set by the caller: the unit's checks.json "checks" list (controller trusted configuration)
_V39_MAKE_PROMPT = judge_v39.make_prompt
_V39_GATES = judge_v39.gates
_V39_REQUIRED = judge_v39.required_reads

V310_RULES = '''
21. No-results cap (controller-enforced). For EXP, when controller-output-checks shows every required non-code
   deliverable missing, test_validity, rigor and conclusion_credibility cannot exceed 1: honest reporting of a run
   that produced no results is not a supported scientific conclusion.
22. Consistency (controller-enforced). A dimension named in serious_issues.affected_dimensions cannot score 4. If any
   rationale identifies a defect that rule 23 assigns to dimension X, list it in serious_issues with X among its
   affected_dimensions; X then cannot be 4.
23. Defect attribution (charge each defect to the one dimension below; rule 10 still applies).
   WRITE_CONTENT: content that contradicts, overstates or understates the sources, or presents a hypothetical as fact
   -> fidelity; required content or conditions absent -> completeness; undefined or clashing notation, unclear
   organisation -> comprehensibility; wrong or missing claim-to-source mapping -> traceability.
   WRITE_EVIDENCE: wrong values or encodings -> fidelity; missing panels, units or conditions -> completeness;
   unreadable, overlapping, clipped or occluded rendering -> comprehensibility; data/code/render correspondence or
   provenance gaps -> traceability.
   EXP: changed method/object or untested hypothesis -> test_validity; confounds, missing controls or uncertainty,
   selective reporting -> rigor; code/config/result mismatch or unverified execution claims -> execution_credibility;
   overclaim or verdicts inconsistent with the evidence -> conclusion_credibility; budget misuse ->
   resource_reasonableness.
   IDEA: unsupported motivation -> grounding_value; unclear difference from known work -> substantive_difference;
   ambiguity or inconsistency -> specificity_coherence; resource or access obstacles -> feasibility; untestable,
   circular or uncovered predictions -> hypothesis_quality.
   LIT: unsupported or misattributed claims -> factual_citation_accuracy; missing strands or counterevidence ->
   evidence_coverage; unfair or confused comparisons -> comparative_synthesis; gap not following from the evidence ->
   gap_grounding.
24. Notation check id (controller-enforced). Name the rule-19 check "notation-c<N>-r<M>", where N candidates were
   confirmed and M refuted, and N + M equals the total number of candidates listed in controller-symbol-check
   (candidate_undefined + candidate_used_before_definition + style_clashes, over all files).'''


def required_reads(task_type, records):
    must = _V39_REQUIRED(task_type, records)
    if task_type == "IDEA":
        # public Markdown inputs (task statement and background report), not schemas or checker scripts
        must += sorted(r["evidence_id"] for r in records if r["evidence_id"].startswith("reference-") and r["visibility"] == "public"
                       and r["media_type"] == "text/plain" and len(r["content"]) <= 60000 and r["evidence_id"] not in must
                       and r["content"].partition("\n")[2].lstrip().startswith("#"))
    return must


def make_prompt(task_id, task_type, session, listed):
    text = _V39_MAKE_PROMPT(task_id, task_type, session, listed)
    anchor = "do not restate the evidence."
    if text.count(anchor) != 1:
        raise ProtocolError("v3.9 rule 20 not found once")
    return text.replace(anchor, anchor + V310_RULES)


class ProtocolError(Exception):
    pass


def no_results(records):
    if not CHECKS_SPEC:
        return None
    spec = next((c for c in CHECKS_SPEC if c.get("id") == "files"), None)
    paths = (spec or {}).get("paths") or (spec or {}).get("files") or []
    result_paths = [p for p in paths if not str(p).endswith(".py")]
    rec = next((r for r in records if r["evidence_id"] == "controller-output-checks"), None)
    if not result_paths or rec is None:
        return False
    res = next((r for r in json.loads(rec["content"])["results"] if r["id"] == "files"), None)
    missing = set((res or {}).get("detail", {}).get("missing", []))
    return all(p in missing for p in result_paths)


def gates(task_type, records, session, judgment):
    report = _V39_GATES(task_type, records, session, judgment)
    dims = judgment.get("dimensions") or {}
    nr = no_results(records) if task_type == "EXP" else False
    over = [d for d in ("test_validity", "rigor", "conclusion_credibility") if nr and dims.get(d, {}).get("score", 0) > 1]
    report["G4_no_results_cap"] = {"no_results": nr, "dimensions_above_1": over, "passed": not over}
    named = sorted({d for i in judgment.get("serious_issues", []) for d in i.get("affected_dimensions", [])
                    if dims.get(d, {}).get("score") == 4})
    report["G5_consistency"] = {"dimensions_4_named_in_serious_issues": named, "passed": not named}
    g6 = {"required": False, "passed": True}
    sym = next((r for r in records if r["evidence_id"] == "controller-symbol-check"), None)
    if report.get("G3_notation_check", {}).get("required"):
        files = json.loads(sym["content"])["files"].values()
        files = list(files)
        total = sum(len(f["candidate_undefined"]) + len(f["candidate_used_before_definition"]) + len(f["style_clashes"]) for f in files)
        # v3.10.2: lists were capped (40 undefined) while candidate_undefined_count gave the full number; accept either total
        total_full = sum(f.get("candidate_undefined_count", len(f["candidate_undefined"])) + len(f["candidate_used_before_definition"]) + len(f["style_clashes"]) for f in files)
        ids = [str(c.get("check_id", "")) for c in judgment.get("checks", []) if str(c.get("check_id", "")).lower().startswith("notation")]
        m = [re.fullmatch(r"notation-c(\d+)-r(\d+)", i.lower()) for i in ids]
        ok = any(x and int(x.group(1)) + int(x.group(2)) in (total, total_full) for x in m)
        g6 = {"required": True, "candidates_total": total, "candidates_total_full": total_full, "check_ids": ids, "passed": ok}
    report["G6_notation_count"] = g6
    return report


def run_native_judge(**kw):
    saved = (judge_v39.make_prompt, judge_v39.gates, judge_v39.required_reads, judge_v39.VERSION)
    judge_v39.make_prompt, judge_v39.gates, judge_v39.required_reads, judge_v39.VERSION = make_prompt, gates, required_reads, VERSION
    try:
        return judge_v39.run_native_judge(**kw)
    finally:
        judge_v39.make_prompt, judge_v39.gates, judge_v39.required_reads, judge_v39.VERSION = saved


# ---- v3.10.1 (2026-10-13): short receipt references ------------------------------------------------------------
from pathlib import Path  # noqa: E402
import judge_v38  # noqa: E402
import mrhbench.native_judge as _nj  # noqa: E402

SERVER_V3101 = Path(__file__).resolve().with_name("bounded_mcp_v310.py")
RULE25 = '''
25. Short refs. Every evidence_read result carries a short "ref" (R1, R2, ...). In every refs list cite these short
   refs exactly as returned (preferred) or full receipt_ids; the controller maps each R<n> to its receipt. A ref that
   was never returned is rejected like an unknown receipt.'''


def ref_map(events):
    out = {}
    for e in events:
        if e.get("kind") == "evidence_read" and e["receipt_id"] not in out.values():
            out["R%d" % (len(out) + 1)] = e["receipt_id"]
    return out


def translate_refs(value, mapping):
    if isinstance(value, dict):
        return {k: ([mapping.get(r, r) if isinstance(r, str) and re.fullmatch(r"R\d+", r) else r for r in v]
                    if k == "refs" and isinstance(v, list) else translate_refs(v, mapping)) for k, v in value.items()}
    if isinstance(value, list):
        return [translate_refs(x, mapping) for x in value]
    return value


_ORIG_VALIDATE = getattr(_nj, "_v3101_orig_validate", _nj.validate_native_result)
_nj._v3101_orig_validate = _ORIG_VALIDATE


def _validate_with_refs(task_type, response, session, **kw):
    return _ORIG_VALIDATE(task_type, translate_refs(response, ref_map(session.events)), session, **kw)


_V310_MAKE_PROMPT = make_prompt


def make_prompt_3101(task_id, task_type, session, listed):
    text = _V310_MAKE_PROMPT(task_id, task_type, session, listed)
    anchor = "(candidate_undefined + candidate_used_before_definition + style_clashes, over all files)."
    if text.count(anchor) != 1:
        raise ProtocolError("v3.10 rule 24 not found once")
    text = text.replace(anchor, anchor + RULE25)
    if task_type == "LIT" and VERSION >= "native-judge-claude-v3.10.3":
        text = text.replace(anchor + RULE25, anchor + RULE25 + RULE26_LIT)
    return text


VERSION = "native-judge-claude-v3.10.1"


def run_native_judge(**kw):  # noqa: F811  (v3.10.1 supersedes the v3.10 entry point)
    saved = (judge_v39.make_prompt, judge_v39.gates, judge_v39.required_reads, judge_v39.VERSION, judge_v38.SERVER, _nj.validate_native_result)
    judge_v39.make_prompt, judge_v39.gates, judge_v39.required_reads, judge_v39.VERSION = make_prompt_3101, gates, required_reads, VERSION
    judge_v38.SERVER, _nj.validate_native_result = SERVER_V3101, _validate_with_refs
    try:
        return judge_v39.run_native_judge(**kw)
    finally:
        (judge_v39.make_prompt, judge_v39.gates, judge_v39.required_reads, judge_v39.VERSION, judge_v38.SERVER,
         _nj.validate_native_result) = saved


VERSION = "native-judge-claude-v3.10.2"  # v3.10.2: symbol-check lists uncapped; G6 accepts the full candidate count

# ---- v3.10.3 (2026-10-14, user "v3.10.3可以做"): LIT prompt clarification only ----------------------------------
# Two of the first six v1.3 LIT judgments were rejected because the public feedback cited library records
# (lit-full-*, lit-citation-bundle), which are private; the existing instruction only said "public feedback must be
# independently supported by public receipts". Scoring rules, anchors, schema, gates and validators are unchanged.
RULE26_LIT = '''
26. Feedback refs (LIT). The library records lit-full-*, lit-citation-bundle, lit-library-catalog and lit-source-index
   are private judge evidence: cite them in judgment refs as needed, but never in any feedback refs. Support each
   feedback issue with public receipts only (the submission files, task, public references, controller checks and
   platform trace); you may name the cited document id and anchor in the feedback text.'''
VERSION = "native-judge-claude-v3.10.3"


def revalidate(output, task_type, checks_spec):
    """Zero-call: re-run audit/validation/gates of an existing v3.10.x judge output with the current controller code."""
    global CHECKS_SPEC
    CHECKS_SPEC = checks_spec
    saved = (judge_v39.gates, judge_v39.required_reads, judge_v39.VERSION, _nj.validate_native_result)
    judge_v39.gates, judge_v39.required_reads, judge_v39.VERSION, _nj.validate_native_result = gates, required_reads, VERSION, _validate_with_refs
    try:
        return judge_v39.revalidate(output, task_type)
    finally:
        judge_v39.gates, judge_v39.required_reads, judge_v39.VERSION, _nj.validate_native_result = saved
