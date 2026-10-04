"""Controller check for LIT submissions: do cited anchor-style locators exist in the cited library document?

Citations are collected from (a) JSON deliverables: any object holding "locator" plus an item id key
(library_id / doc_id / document_id / library_item_id / item_id), and (b) Markdown deliverables: inline
"[<id> §<locator>]" / "[<id>, <locator>]". Ids are library document ids (doc-<arXiv id>v<n>) or task-local
library ids (e.g. L07) mapped through the task's public library manifest (library_id -> arxiv_id + version).
Only arXiv-HTML anchor locators (S2, S2.SS1.p3, A1.p2 ...) and "abstract" (resolved only if the executor actually
read that document's abstract) are checked; anchor-like locators that are not markers ("§1") count as unresolved against the controller's own
text extraction (the same [§...] markers the executor saw); other locator styles (headings, "Table 2") are
reported as unchecked, not failed. A flag for the judge, not a score. No model calls.
"""
from pathlib import Path
import json
import re

import factory_library as fl

ID_KEYS = ("library_id", "doc_id", "document_id", "library_item_id", "item_id")
INLINE = re.compile(r"\[\s*(L\d{2}|doc-[\w.\-/]+?v\d+)\s*(?:,|;)?\s*§?\s*([^\]\n]{1,60}?)\s*\]")
ANCHOR = re.compile(r"(?:S|A)\d+(?:\.(?:SS|SSS|p)\d+)*")
_text_cache = {}


def _walk(v, out):
    if isinstance(v, dict):
        ids = [v[k] for k in ID_KEYS if isinstance(v.get(k), str)]
        if ids and isinstance(v.get("locator"), str):
            out.append((ids[0], v["locator"]))
        for x in v.values():
            _walk(x, out)
    elif isinstance(v, list):
        for x in v:
            _walk(x, out)


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
                m[it["library_id"]] = ("doc-%s%s" % (it["arxiv_id"], ver if ver.startswith("v") else ("v" + ver if ver else "")))
    return m


def _doc_text(library_root, doc_id, records):
    if doc_id in _text_cache:
        return _text_cache[doc_id]
    row = records.get(doc_id)
    text = None
    if row and row.get("fulltext_kind") == "arxiv_html":
        text = fl.html_text((Path(library_root) / row["html_source_path"]).read_text(encoding="utf8"))
    _text_cache[doc_id] = (text, bool(row))
    return _text_cache[doc_id]


SECTION_LIKE = re.compile(r"(?:S|A|SS|p)?\d+(?:\.\w+)*", re.I)


def _abstracts_read(out_root):
    """document ids whose abstract the executor actually read (successful literature.read in the broker RPCs)."""
    seen = set()
    for f in sorted((Path(out_root).parent / "broker").glob("rpc-*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf8"))
        except Exception:
            continue
        a = (r.get("request") or {}).get("arguments") or {}
        if a.get("name") == "literature.read" and (r.get("response") or {}).get("ok"):
            doc = (a.get("arguments") or {}).get("document_id")
            if isinstance(doc, str):
                seen.add(doc)
    return seen


def check(out_root, public_root, library_root):
    records = {d["document_id"]: d for d in json.loads((Path(library_root) / "corpus.json").read_text(encoding="utf8"))["documents"]}
    read_abstracts = _abstracts_read(out_root)
    lmap = _manifest_map(public_root)
    cites = []
    for p in sorted(Path(out_root).rglob("*")):
        if p.suffix == ".json":
            try:
                _walk(json.loads(p.read_text(encoding="utf8")), cites)
            except Exception:
                pass
        elif p.suffix in (".md", ".txt"):
            cites += INLINE.findall(p.read_text(encoding="utf8", errors="replace"))
    resolved, unresolved, unchecked, unknown_doc = 0, [], 0, []
    for cid, loc in dict.fromkeys((c.strip(), l.strip()) for c, l in cites):
        doc = lmap.get(cid, cid)
        token = loc.lstrip("§ ").split()[0].rstrip(",;.") if loc.strip() else ""
        if token.lower() != "abstract" and not ANCHOR.fullmatch(token):
            if loc.strip().startswith("§") or SECTION_LIKE.fullmatch(token):
                unresolved.append({"id": cid, "doc": doc, "locator": loc,
                                   "note": "anchor-like locator that is not a marker of the controller text (e.g. '§1' for '[§S1]')"})
            else:
                unchecked += 1
            continue
        text, known = _doc_text(library_root, doc, records)
        if not known:
            unknown_doc.append({"id": cid, "resolved_doc": doc, "locator": loc})
            continue
        if token.lower() == "abstract":
            if doc in read_abstracts:
                resolved += 1
            else:
                unresolved.append({"id": cid, "doc": doc, "locator": loc, "note": "abstract cited but never read by the executor"})
        elif text is not None and ("[§%s]" % token) in text:
            resolved += 1
        else:
            unresolved.append({"id": cid, "doc": doc, "locator": loc,
                               "note": "no such anchor marker in the controller text" if text is not None else "no full text in library"})
    total = resolved + len(unresolved) + len(unknown_doc)
    return (None if total == 0 else not unresolved and not unknown_doc), {
        "anchor_citations_checked": total, "resolved": resolved, "unresolved": unresolved[:40], "unresolved_count": len(unresolved),
        "unknown_document": unknown_doc[:20], "non_anchor_locators_unchecked": unchecked,
        "note": "checked against the controller's extraction of the pinned library HTML (the markers the executor saw)"}
