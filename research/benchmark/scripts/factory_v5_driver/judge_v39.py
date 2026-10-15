"""Judge v3.9 = judge v3.8 + cheaper required reading + a controller notation check (2026-10-13).

v3.8 acceptance (rejudge-v38-review-A.json): fewer errors than a v3.6 repeat (3 vs 5) and correct LIT/no-results
grading, but two WRITE_CONTENT comprehensibility 4s still rested on false universal claims ("symbols are defined
before use") and cost was only ~8% below v3.6 at list price (55% cache writes driven by required reading, 28% output).
v3.9 changes (rubric, anchors, rules 1-18, schema and repo validators unchanged):
  * private reference judge views: each private reference-* record that is a JSON document gets a deterministic
    compact view (drops source_manifest, private_source_ids, per-fact source evidence locators/hashes, allowed_stages,
    formal_accepted; a fact statement identical to public text is replaced by "(= public task fact <id>)"). The view
    is listed and required; the original stays readable by id but is unlisted. Measured: required reading -29%.
  * controller-symbol-check (program_check, public): heuristic notation candidates from symbol_check.py.
  * rule 19 notation check (+ gate G3 for WRITE_CONTENT: a check whose check_id starts with "notation" must exist
    when the symbol check reports candidates); rule 20 concise output.
  * MCP_TIMEOUT=120000 for the CLI (two "MCP server did not connect" platform failures on 56MB LIT manifests).
"""
from pathlib import Path
import json
import os

import judge_v37
import judge_v38
import symbol_check
from judge_v37 import evidence_record

VERSION = "native-judge-claude-v3.9"
DROP = {"evidence", "source_sha256", "allowed_stages", "formal_accepted", "source_manifest", "private_source_ids"}
_V37_PREPARE = judge_v37.prepare_records
_V38_MAKE_PROMPT = judge_v38.make_prompt
_V38_GATES = judge_v38.gates

V39_RULES = '''
19. Notation. controller-symbol-check lists HEURISTIC candidates (possibly undefined symbols, symbols used before
   their definition, letters used in two styles). Before grading comprehensibility, fidelity or completeness of a
   deliverable that has candidates, confirm or refute every candidate against the deliverable (and the task's
   notation list) and record ONE check whose check_id starts with "notation", naming the confirmed problems and
   the number refuted. Never state that all symbols are defined unless every candidate was refuted. Charge a
   confirmed problem according to the anchors (a localized undefined symbol is a localized weakness; a clash
   matters only if it creates real ambiguity). The controller rejects a WRITE_CONTENT judgment without that check.
20. Concise output. Dimension rationale <= 120 words, check rationale <= 60 words, at most 6 feedback issues with
   each field <= 60 words. State the decisive evidence and cite receipts; do not restate the evidence.'''


def _strip(v):
    if isinstance(v, dict):
        return {k: _strip(x) for k, x in v.items() if k not in DROP}
    if isinstance(v, list):
        return [_strip(x) for x in v]
    return v


def judge_view(record, public_text):
    head, _, body = record["content"].partition("\n")
    try:
        doc = json.loads(body)
    except Exception:
        return None
    view = _strip(doc)
    replaced = []
    for key in ("input_facts_with_evidence", "private_facts"):
        for f in view.get(key, []) if isinstance(view, dict) else []:
            if isinstance(f, dict) and isinstance(f.get("statement"), str) and len(f["statement"]) > 40 and f["statement"] in public_text:
                f["statement"] = "(= public task fact %s; identical text)" % f.get("fact_id")
                replaced.append(f.get("fact_id"))
    note = ("%s [judge view of %s: deterministic compaction; dropped fields %s (source provenance the judge cannot use); "
            "%d fact statements identical to public task text replaced by their fact id; the original record stays "
            "readable by evidence_id]" % (head, record["evidence_id"], sorted(DROP), len(replaced)))
    return evidence_record(record["evidence_id"] + "-judge-view", "reference", note + "\n" + json.dumps(view, ensure_ascii=False, indent=0),
                           visibility="private")


def prepare_records(records, task_type, run_dir):
    records, listed, report = _V37_PREPARE(records, task_type, run_dir)
    public_text = " ".join(r["content"] for r in records if r["visibility"] == "public" and r["media_type"] == "text/plain")
    replaced, saved = [], 0
    for r in list(records):
        if r["evidence_id"].startswith("reference-") and r["visibility"] == "private" and not r["evidence_id"].endswith("-judge-view"):
            v = judge_view(r, public_text)
            if v is not None and len(v["content"]) < len(r["content"]):
                records.append(v)
                replaced.append(r["evidence_id"])
                saved += len(r["content"]) - len(v["content"])
    sym = symbol_check.check(Path(run_dir) / "artifacts")
    if sym["files"]:
        records.append(evidence_record("controller-symbol-check", "program_check", json.dumps(sym, ensure_ascii=False, indent=1)))
    all_ids = {r["evidence_id"] for r in records}
    base = set(listed) if listed is not None else all_ids
    base |= {r["evidence_id"] for r in records if r["evidence_id"].endswith("-judge-view") or r["evidence_id"] == "controller-symbol-check"}
    listed = sorted(base - set(replaced))
    report.update(judge_view_replaced=replaced, judge_view_chars_saved=saved, symbol_check=bool(sym["files"]))
    return records, listed, report


def required_reads(task_type, records):
    ids = {r["evidence_id"] for r in records}
    must = [k for k in judge_v38._V38_REQUIRED(task_type, records) if k + "-judge-view" not in ids]
    if "controller-symbol-check" in ids:
        must.append("controller-symbol-check")
    return must


def make_prompt(task_id, task_type, session, listed):
    text = _V38_MAKE_PROMPT(task_id, task_type, session, listed)
    j = text.index("Required complete reads for this task:")
    k = text.index("\n", j)  # end of the v3.8 required-reads line
    return text[:k] + V39_RULES + text[k:]


def gates(task_type, records, session, judgment):
    report = _V38_GATES(task_type, records, session, judgment)
    sym = next((r for r in records if r["evidence_id"] == "controller-symbol-check"), None)
    need = False
    if sym is not None and task_type == "WRITE_CONTENT":
        files = json.loads(sym["content"])["files"].values()
        need = any(f["candidate_undefined"] or f["candidate_used_before_definition"] or f["style_clashes"] for f in files)
    has = any(str(c.get("check_id", "")).lower().startswith("notation") for c in judgment.get("checks", []))
    report["G3_notation_check"] = {"required": need, "present": has, "passed": (not need) or has}
    return report


def run_native_judge(**kw):
    os.environ.setdefault("MCP_TIMEOUT", "120000")
    saved = (judge_v37.prepare_records, judge_v38.make_prompt, judge_v38.gates, judge_v38.required_reads, judge_v38.VERSION)
    judge_v37.prepare_records, judge_v38.make_prompt, judge_v38.gates, judge_v38.required_reads, judge_v38.VERSION = (
        prepare_records, make_prompt, gates, required_reads, VERSION)
    try:
        return judge_v38.run_native_judge(**kw)
    finally:
        judge_v37.prepare_records, judge_v38.make_prompt, judge_v38.gates, judge_v38.required_reads, judge_v38.VERSION = saved


if not hasattr(judge_v38, "_V38_REQUIRED"):
    judge_v38._V38_REQUIRED = judge_v38.required_reads


# ---- v3.9.1 (2026-10-13): CLI "tool_progress" stream events are benign progress notices for slow MCP tools ------
BENIGN_STREAM_EVENTS = ({"event": "tool_progress"},)
import mrhbench.claude_transport as _ct  # noqa: E402
_ORIG_PARSE = getattr(_ct, "_v391_orig_parse", _ct.parse_stream)
_ct._v391_orig_parse = _ORIG_PARSE


def parse_stream(text):
    parsed = _ORIG_PARSE(text)
    parsed["unknown"] = [u for u in parsed["unknown"] if u not in BENIGN_STREAM_EVENTS]
    return parsed


_ct.parse_stream = parse_stream


def revalidate(output, task_type):
    """Zero-call: re-run the post-call audit/validation/gates of an existing v3.9 judge output (e.g. after a stream
    audit rejected only benign events). The model's candidate judgment and the tool state are used unchanged."""
    import mrhbench.native_judge as nj
    from mrhbench.claude_transport import assess_claude_admissibility, OUTPUT_TOOL
    from mrhbench.io import read_json, write_json
    out = Path(output)
    manifest = read_json(out / "evidence_manifest.json")
    records, state = manifest["records"], read_json(out / "tool_state.json")
    call = read_json(out / "native_call.json")
    parsed = parse_stream((Path(call["audit_directory"]) / "events.jsonl").read_text(encoding="utf8"))
    allowed = ["mcp__mrhbench__" + t for t in manifest["allowed_tools"]] + [OUTPUT_TOOL]
    audit = assess_claude_admissibility(parsed, allowed_tools=allowed, tool_state=state)
    write_json(out / "native_tool_audit.v391.json", audit)
    if audit["status"] != "development_admissible":
        return {"status": "awaiting_native_tool_review", "native_tool_audit": audit}
    verified, missing = nj.verify_stream_image_delivery(parsed, records, state)
    if missing:
        return {"status": "awaiting_image_delivery_review"}
    judge_v37.PAGE_MAX = judge_v38.PAGE_MAX
    restored = nj.restore_session(records, state, verified_image_receipts=verified)
    validated = nj.validate_native_result(task_type, read_json(out / "candidate_judgment.json"), restored)
    validated["native_tool_admissibility_status"] = audit["status"]
    validated["judge_version"] = VERSION + ".1-revalidated"
    saved_req = judge_v38.required_reads
    judge_v38.required_reads = required_reads
    try:
        report = gates(task_type, records, nj.restore_session(records, state, verified_image_receipts=verified), validated["judgment"])
    finally:
        judge_v38.required_reads = saved_req
    write_json(out / "v38_gates.json", report)
    if not all(g["passed"] for g in report.values()):
        return {"status": "rejected_by_controller_gate", "gates": report, "candidate_quality": validated.get("quality")}
    validated["v38_gates"] = report
    write_json(out / "result.json", validated)
    return validated
