"""Judge v3.7 = judge v3.6 grading rules + cheaper, better-targeted evidence access (2026-10-13).

Motivation (12 Oral judge traces, 10.87M judge input tokens): per-turn context is resent every tool turn, so
cost ~ turns x context. Two wastes dominated: (A) the LIT prompt inventory listed all ~600 preloaded library
documents (~70k tokens resent every turn) although the judge read 2-3 of them; (B) one 6000-character page per
turn forced long serial read chains (Xo0Q EXP 36 turns). v3.7 changes evidence ACCESS only; rubric, anchors,
rules 1-10, output schema and every controller validator are unchanged:
  A. LIT: the prompt/evidence_inventory list every record except library full texts not touched by the solver
     and not named by evaluator guidance; all library records stay readable by evidence_id. A compact catalog
     record (lit-library-catalog) and a locator-only search tool (evidence_search) replace the giant listing.
  B. Pages up to 24000 characters; several evidence_read calls may be issued in parallel in one turn.
  C. Per-call model-action-* and tool platform-rpc-* records are merged (content unchanged) into one
     platform-action-timeline record with an offset index; the Codex-era hash paragraph is shortened.
  D. LIT: lit-citation-bundle, a controller extraction of the passage at every solver citation anchor
     (with exact offsets in the cited library record), so citation support is checked for all citations.
Import AFTER platform_patches/judge_v36. The repo (native_judge.py, bounded_mcp.py, judging.py) is not modified;
judging.EvidenceSession.read_chars is patched in-process (controller and the v3.7 MCP server process).
"""
from pathlib import Path
import copy
import json
import re
import sys

import judge_v36
import mrhbench.native_judge as nj
import mrhbench.judging as judging
from mrhbench.io import ProtocolError, digest, write_json, read_json
from mrhbench.judge_runner import evidence_record

VERSION = "native-judge-claude-v3.7.1"  # v3.7.1: refs must be evidence_read receipts (search results are not citable)
PAGE_MAX = 24000
SERVER = Path(__file__).resolve().with_name("bounded_mcp_v37.py")


# ---- B: larger pages (same receipts/offset semantics; only the per-page bound changes) -------------------------
def _read_chars_v37(self, evidence_id, *, start_char=0, max_chars=None):
    if max_chars is None:
        max_chars = PAGE_MAX
    if evidence_id not in self.records:
        raise ProtocolError("Evidence unavailable in this role")
    row = self.records[evidence_id]
    if row["media_type"] != "text/plain":
        if start_char != 0:
            raise ProtocolError("Images cannot be character-paginated")
        return self.read(evidence_id)
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (start_char, max_chars)):
        raise ProtocolError("Character offsets and bounds must be integers")
    text = row["content"]
    if not (0 <= start_char < len(text) or start_char == 0 and not text) or not 1 <= max_chars <= PAGE_MAX:
        raise ProtocolError("Invalid character page")
    end_char = min(len(text), start_char + max_chars)
    chunk = text[start_char:end_char]
    if self.text_chars + len(chunk) > self.max_text_chars:
        raise ProtocolError("Explicit evidence text-read budget exhausted")
    self.text_chars += len(chunk)
    base = {"evidence_id": evidence_id, "source_sha256": row["sha256"], "media_type": row["media_type"],
            "start_char": start_char, "end_char": end_char, "content": chunk}
    receipt_id = digest(base)
    self.receipts[receipt_id] = {k: v for k, v in base.items() if k != "content"}
    self.events.append({"kind": "evidence_read", "receipt_id": receipt_id, **self.receipts[receipt_id]})
    return {"receipt_id": receipt_id, **base, "next_char": end_char if end_char < len(text) else None,
            "total_chars": len(text), "complete_record": start_char == 0 and end_char == len(text)}


judging.EvidenceSession.read_chars = _read_chars_v37


# ---- C: one platform action timeline ---------------------------------------------------------------------------
def _seq(rec):
    try:
        v = json.loads(rec["content"])
    except Exception:
        return 10 ** 9
    s = v.get("sequence") if "sequence" in v else (v.get("request") or {}).get("sequence")
    return s if isinstance(s, int) else 10 ** 9


def merge_timeline(records):
    parts = [r for r in records if r["evidence_id"].startswith("model-action-")
             or re.fullmatch(r"platform-rpc-\d+", r["evidence_id"])]
    if not parts:
        return records
    parts.sort(key=lambda r: (_seq(r), 0 if r["evidence_id"].startswith("model-action-") else 1, r["evidence_id"]))
    lead = ("platform-action-timeline: the executor model actions (formerly records model-action-*) and the broker "
            "tool RPC records (formerly platform-rpc-*) merged in broker sequence order. Each entry's content is "
            "byte-identical to the former record. Index: entry, sequence, kind, former record id, and the "
            "start_char/end_char of the entry body in THIS record (read a range with evidence_read).\n")
    line = "%4d seq=%6s %-12s %-24s start_char=%09d end_char=%09d\n"
    bodies = []
    for i, r in enumerate(parts):
        kind = "model_action" if r["evidence_id"].startswith("model-action-") else "tool_rpc"
        bodies.append((i + 1, _seq(r), kind, r["evidence_id"],
                       "\n### entry %d | sequence %s | %s | former %s\n" % (i + 1, _seq(r), kind, r["evidence_id"]), r["content"]))
    head_len = len(lead) + sum(len(line % (n, s, k, e, 0, 0)) for n, s, k, e, _, _ in bodies) + 1
    pos, index, body = head_len, [], []
    for n, s, k, e, hdr, content in bodies:
        start = pos + len(hdr)
        end = start + len(content)
        index.append(line % (n, s, k, e, start, end))
        body.append(hdr + content + "\n")
        pos = end + 1
    text = lead + "".join(index) + "\n" + "".join(body)
    assert len(lead) + len("".join(index)) + 1 == head_len
    for (n, s, k, e, hdr, content), row in zip(bodies, index):
        a, b = int(row.split("start_char=")[1][:9]), int(row.split("end_char=")[1][:9])
        if text[a:b] != content:
            raise ProtocolError("timeline offset construction error")
    merged = {id(r) for r in parts}
    keep = [r for r in records if id(r) not in merged]
    return keep + [evidence_record("platform-action-timeline", "platform_trace", text)]


# ---- A + D: LIT listing, catalog and citation bundle --------------------------------------------------------------
DOC = re.compile(r"doc-[\w.\-/]+?v\d+")
ARXIV = re.compile(r"(?<![\w.])(\d{4}\.\d{4,5})(?:v\d+)?(?![\w])")
INLINE = re.compile(r"\[\s*(L\d{2}|doc-[\w.\-/]+?v\d+)\s*(?:,|;)?\s*§?\s*([^\]\n]{1,60}?)\s*\]")
ID_KEYS = ("library_id", "doc_id", "document_id", "library_item_id", "item_id")
PASSAGE_MAX = 2500


def _lit_index(records):
    row = next((r for r in records if r["evidence_id"] == "lit-source-index"), None)
    return json.loads(row["content"])["documents"] if row else None


def _citations(artifacts_dir):
    """(claim_id, statement, doc_or_lib_id, locator, source_file) for every solver citation."""
    out = []

    def walk(v, ctx, fname):
        if isinstance(v, dict):
            if isinstance(v.get("statement"), str) or isinstance(v.get("claim_id"), str):
                ctx = (v.get("claim_id"), v.get("statement"))
            ids = [v[k] for k in ID_KEYS if isinstance(v.get(k), str)]
            if ids and isinstance(v.get("locator"), str):
                out.append((ctx[0], ctx[1], ids[0], v["locator"], fname))
            for x in v.values():
                walk(x, ctx, fname)
        elif isinstance(v, list):
            for x in v:
                walk(x, ctx, fname)

    for p in sorted(Path(artifacts_dir).rglob("*")):
        if "h0_notes" in p.parts:
            continue
        if p.suffix == ".json":
            try:
                walk(json.loads(p.read_text(encoding="utf8")), (None, None), p.name)
            except Exception:
                pass
        elif p.suffix in (".md", ".txt"):
            text = p.read_text(encoding="utf8", errors="replace")
            for m in INLINE.finditer(text):
                a = max(text.rfind("\n", 0, m.start()), text.rfind(". ", 0, m.start()))
                b = text.find("\n", m.end())
                sentence = text[a + 1 if a >= 0 else 0: b if b >= 0 else len(text)].strip()[:600]
                out.append((None, sentence, m.group(1), m.group(2), p.name))
    return out


def _manifest_map(public_root):
    m = {}
    for p in Path(public_root).rglob("*manifest*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf8"))
        except Exception:
            continue
        for it in d.get("items", []) if isinstance(d, dict) else []:
            if isinstance(it, dict) and it.get("library_id") and it.get("arxiv_id"):
                ver = str(it.get("version") or "")
                m[it["library_id"]] = "doc-%s%s" % (it["arxiv_id"], ver if ver.startswith("v") else ("v" + ver if ver else ""))
    return m


def citation_bundle(records, index, run_dir):
    by_doc = {d["document_id"]: d for d in index}
    content = {r["evidence_id"]: r["content"] for r in records if r["evidence_id"].startswith("lit-full-")}
    lmap = _manifest_map(Path(run_dir).parent / "public")
    entries = []
    for n, (cid, statement, raw_id, loc, fname) in enumerate(_citations(Path(run_dir) / "artifacts"), 1):
        doc = lmap.get(raw_id.strip(), raw_id.strip())
        token = loc.strip().lstrip("§ ").split()[0].rstrip(",;.") if loc.strip() else ""
        e = {"entry": n, "source_file": fname, "claim_id": cid, "claim_or_sentence": statement, "cited_id": raw_id,
             "document_id": doc, "locator": loc}
        meta = by_doc.get(doc)
        if meta is None:
            e.update(status="document_not_in_library")
            entries.append(e)
            continue
        eid = meta["evidence_id"]
        e.update(evidence_id=eid, title=meta.get("title"))
        text = content.get(eid, "")
        marker = "[§%s]" % token
        i = text.find(marker) if token else -1
        if i < 0:
            e.update(status="marker_not_found",
                     note="no '%s' marker in the cited library record; see controller-output-checks locators" % marker)
        else:
            j = text.find("[§", i + len(marker))
            end = min(len(text), j if j > 0 else len(text), i + PASSAGE_MAX)
            e.update(status="marker_found", start_char=i, end_char=end, passage_truncated=(j < 0 or j > i + PASSAGE_MAX) and end - i >= PASSAGE_MAX,
                     passage=text[i:end])
        entries.append(e)
    lead = {"schema_version": "lit-citation-bundle-1",
            "what": ("Controller extraction (no model): for every citation the solver wrote (JSON 'locator' citations "
                     "and inline [doc §anchor] citations in Markdown) the passage of the cited library record that "
                     "starts at the cited anchor marker and runs to the next marker (at most %d characters). "
                     "start_char/end_char address the cited lit-full-* record, so the same range can be read there." % PASSAGE_MAX),
            "not": ("Not a judgement of support and not evidence that the solver read the passage. An 'abstract' locator "
                    "resolves to the [§abstract] marker; controller-output-checks separately reports whether the solver "
                    "actually read cited abstracts."),
            "citations": len(entries), "marker_found": sum(e.get("status") == "marker_found" for e in entries),
            "entries": entries}
    return evidence_record("lit-citation-bundle", "reference", json.dumps(lead, ensure_ascii=False, indent=1), visibility="private")


def lit_listing(records, index, run_dir):
    """Library evidence ids to list: solver-touched (broker literature.* RPCs), solver-cited, guidance-named."""
    by_doc = {d["document_id"]: d["evidence_id"] for d in index}
    by_arxiv = {}
    for d, eid in by_doc.items():
        m = re.match(r"doc-(.+?)v\d+$", d)
        if m:
            by_arxiv.setdefault(m.group(1), []).append(eid)
    touched, cited, named = set(), set(), set()
    for f in sorted((Path(run_dir) / "broker").glob("rpc-*.json")):
        r = read_json(f)
        a = (r.get("request") or {}).get("arguments") or {}
        if str(a.get("name", "")).startswith("literature."):
            for d in DOC.findall(json.dumps(r)):
                if d in by_doc:
                    touched.add(by_doc[d])
    lmap = _manifest_map(Path(run_dir).parent / "public")
    for _, _, raw, _, _ in _citations(Path(run_dir) / "artifacts"):
        d = lmap.get(raw.strip(), raw.strip())
        if d in by_doc:
            cited.add(by_doc[d])
    for r in records:
        if r["origin"] == "reference" and r["evidence_id"].startswith("reference-"):
            for d in DOC.findall(r["content"]):
                if d in by_doc:
                    named.add(by_doc[d])
            for a in ARXIV.findall(r["content"]):
                named.update(by_arxiv.get(a, []))
    return touched, cited, named


def catalog_record(index):
    lines = ["lit-library-catalog: every library document preloaded for the judge (the shared library view of this "
             "task). Columns: evidence_id | title | version | published_date | pages. Each evidence_id is readable "
             "with evidence_read; lit-source-index gives per-page start_char/end_char offsets; evidence_search finds "
             "text positions. Listing here is not evidence that the solver saw a document."]
    for d in index:
        lines.append("%s | %s | %s | %s | %s" % (d["evidence_id"], (d.get("title") or "").replace("\n", " "), d.get("version"),
                                               d.get("published_date"), len(d.get("pages") or [])))
    return evidence_record("lit-library-catalog", "reference", "\n".join(lines) + "\n", visibility="private")


def prepare_records(records, task_type, run_dir):
    """Returns (records, listed_evidence_ids, report)."""
    records = merge_timeline(copy.deepcopy(records))
    report = {"timeline_merged": any(r["evidence_id"] == "platform-action-timeline" for r in records)}
    listed = None
    index = _lit_index(records) if task_type == "LIT" else None
    if index:
        records.append(catalog_record(index))
        records.append(citation_bundle(records, index, run_dir))
        touched, cited, named = lit_listing(records, index, run_dir)
        keep = touched | cited | named
        listed = sorted(r["evidence_id"] for r in records if not r["evidence_id"].startswith("lit-full-") or r["evidence_id"] in keep)
        report.update(library_documents=len(index), listed_library_documents=len(keep),
                      solver_touched=len(touched), solver_cited=len(cited), guidance_named=len(named))
    return records, listed, report


# ---- prompt ---------------------------------------------------------------------------------------------------------
V37_RULES = '''
Additional evidence-access rules (judge v3.7; grading rules 1-10 are unchanged):
11. Pages hold up to 24000 characters. When you already know several pages or records you need, request them
   together as parallel evidence_read calls in one turn instead of one per turn; the 80-call cap still applies.
12. platform-action-timeline merges the executor model actions and broker tool RPC records in sequence order; its
   index gives each entry's start_char/end_char, so read only the entries you need.
13. Library documents: the inventory lists the library full texts the solver searched, read or cited and those
   named by evaluator guidance. Every other library document is still readable by its evidence_id: find it in
   lit-library-catalog or locate text with evidence_search (a locator, not citable evidence; read the range and
   cite that receipt). Do not treat a document's absence from the inventory as absence from the library.
14. LIT citations: lit-citation-bundle gives, for every solver citation, the passage at the cited anchor of the
   cited library record with exact offsets. Check the support of each cited claim against its passage (read the
   surrounding record range when context matters); marker_not_found entries are unresolved locators.
15. Every entry in any refs list must be a receipt_id string exactly as returned by an evidence_read call in this
   session; copy it character for character. evidence_search and evidence_inventory return no receipts and can
   never be cited. To support an absence or search finding, cite the receipts of the records you actually read
   and describe the search (query, scope, result) in the rationale or uncertainty. Never construct an id.'''

_REPL = [
    ("Call evidence_read one page at a time and read\neach result completely.",
     "Read each evidence_read result completely; you may issue several\nevidence_read calls in parallel in one turn."),
    ("Do not dump entire\ninventories and many pages together.",
     "Request only pages you need, but batch\nthe reads you already know you need."),
    ("Use the source index's start_char/end_char offsets to read selected PDF-page text\nin <=6000-character chunks.",
     "Use lit-library-catalog, evidence_search and the source index's start_char/end_char\noffsets to locate passages; read them in pages of up to 24000 characters."),
]
_HASH_START = "Hash identity semantics:"
_HASH_END = "attribute only what the record supports.\n"
_HASH_NEW = ("Hash identity semantics: inventory sha256 and evidence_read source_sha256 hash the canonical JSON of the\n"
             "content string, not raw file bytes; never compare them with raw file hashes. An unexplained same-scope\n"
             "identity conflict is an evidence limitation, not automatically a solver error.\n")


class _Listed:
    def __init__(self, session, listed):
        self.records, self._s, self._listed = session.records, session, listed

    def inventory(self):
        inv = self._s.inventory()
        return inv if self._listed is None else [x for x in inv if x["evidence_id"] in self._listed]


def make_prompt(task_id, task_type, session, listed):
    text = nj.make_prompt(task_id, task_type, _Listed(session, listed), transport="claude")
    for old, new in _REPL:
        want = (1 if task_type == "LIT" else 0) if old.startswith("Use the source") else 1
        if text.count(old) != want:
            raise ProtocolError("Judge policy text changed; review v3.7 replacements: " + old[:40])
        text = text.replace(old, new)
    a, b = text.find(_HASH_START), text.find(_HASH_END)
    if a < 0 or b < a or text.count(_HASH_START) != 1:
        raise ProtocolError("Judge hash paragraph changed; review v3.7")
    text = text[:a] + _HASH_NEW + text[b + len(_HASH_END):]
    if text.count(judge_v36.V36_RULES) != 1:
        raise ProtocolError("v3.6 rules not found once in prompt")
    return text.replace(judge_v36.V36_RULES, judge_v36.V36_RULES + V37_RULES)


# ---- run (mirror of native_judge.run_native_judge / _run_claude_judge with the v3.7 server) ---------------------
def run_native_judge(*, runner, task_id, task_type, records, output, python_binary, controller_output_inventory=None, run_dir=None, dry_run=False):
    from mrhbench.claude_transport import ClaudeNativeRunner, parse_stream, assess_claude_admissibility, OUTPUT_TOOL
    if run_dir is None:
        raise ProtocolError("v3.7 needs the execution directory")
    if any(r["evidence_id"] == nj.OUTPUT_INVENTORY_ID for r in records):
        raise ProtocolError("Reserved controller inventory must be supplied via trusted parameter")
    records, listed, report = prepare_records(records, task_type, run_dir)
    if controller_output_inventory is not None:
        records.append(evidence_record(nj.OUTPUT_INVENTORY_ID, "platform_trace",
                                       json.dumps(nj.validate_output_inventory(controller_output_inventory), ensure_ascii=False, indent=2), visibility="public"))
        if listed is not None:
            listed = sorted(set(listed) | {nj.OUTPUT_INVENTORY_ID})
    output = Path(output)
    if output.exists():
        raise ProtocolError("Native judge output must be new")
    output.mkdir(parents=True)
    (output / "empty_workspace").mkdir()
    session = judging.EvidenceSession(records, max_text_chars=600000)
    tools = ["evidence_inventory", "evidence_read", "evidence_search"]
    manifest = {"records": records, "state_path": str((output / "tool_state.json").resolve()), "max_tool_calls": 80,
                "max_text_chars": 600000, "container": None, "allowed_tools": tools, "listed_evidence_ids": listed}
    write_json(output / "evidence_manifest.json", manifest)
    write_json(output / "v37_evidence_report.json", {**report, "judge_version": VERSION, "page_max_chars": PAGE_MAX,
                                                      "records": len(records), "listed": None if listed is None else len(listed)})
    prompt = make_prompt(task_id, task_type, session, None if listed is None else set(listed))
    (output / "prompt.txt").write_text(prompt, encoding="utf8")
    sys.path.insert(0, str(SERVER.parent))
    import bounded_mcp_v37
    bounded_mcp_v37.BoundedToolsV37(manifest)  # zero-cost manifest preflight before any paid call
    if dry_run:
        return {"status": "dry_run", "prompt_chars": len(prompt), "records": len(records),
                "listed": None if listed is None else len(listed), **report}
    servers = {"mrhbench": {"command": str(python_binary), "args": [str(SERVER), "--manifest", str((output / "evidence_manifest.json").resolve())],
                            "enabled_tools": tools}}
    bounded = ClaudeNativeRunner(binary=runner.binary, model=runner.model, reasoning_effort=runner.effort, ledger=runner.ledger,
                                 audit_root=runner.audit_root, timeout_seconds=runner.timeout, tool_profile="bounded_mcp", mcp_servers=servers)
    result = bounded.run(workspace=output / "empty_workspace", prompt=prompt, role="judge", output_schema=nj.claude_output_schema(task_type))
    write_json(output / "native_call.json", result)
    response = result["response"]
    write_json(output / "candidate_judgment.json", response)
    state = read_json(output / "tool_state.json")
    parsed = parse_stream((Path(result["audit_directory"]) / "events.jsonl").read_text(encoding="utf8"))
    tool_audit = assess_claude_admissibility(parsed, allowed_tools=bounded.allowed_tools() + [OUTPUT_TOOL], tool_state=state)
    write_json(output / "native_tool_audit.json", tool_audit)
    if tool_audit["status"] != "development_admissible":
        return {"status": "awaiting_native_tool_review", "native_call": result, "candidate": response,
                "automatic_scientific_zero": False, "native_tool_audit": tool_audit}
    verified, missing = nj.verify_stream_image_delivery(parsed, records, state)
    write_json(output / "image_delivery.json", {"verified_in_exact_stream": verified, "not_found_in_stream": missing,
               "caveat": "CLI-side resizing before the API request is not excluded; visual claims still require trajectory review."})
    downscaled = nj.downscaled_deliveries(parsed["events"], records, state, missing) if missing else {}
    if downscaled:
        write_json(output / "image_delivery_downscaled.json", {"receipts": downscaled,
                   "meaning": "Delivered as a faithful uniform downscale of the released image (not exact bytes); detail below the delivered resolution was not visible unless full-resolution tiles were read."})
    if set(missing) - set(downscaled):
        return {"status": "awaiting_image_delivery_review", "native_call": result, "candidate": response}
    restored = nj.restore_session(records, state, verified_image_receipts=verified + sorted(downscaled))
    validated = nj.validate_native_result(task_type, response, restored)
    validated["native_tool_admissibility_status"] = tool_audit["status"]
    validated["judge_version"] = VERSION
    write_json(output / "result.json", validated)
    return validated
