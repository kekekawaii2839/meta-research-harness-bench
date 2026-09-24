"""Controller-owned historical corpus service; not an OS/network sandbox.

Only document IDs and page numbers cross the tool interface. Source paths and
private metadata never do. Full PDF text is read from the locally pinned source;
do not bundle these copyrighted PDFs wholesale in public task releases.
"""
from __future__ import annotations

from pathlib import Path
from html.parser import HTMLParser
from datetime import date
import re

from .io import ProtocolError, contained, digest, file_hash
from .materials import FrozenCorpus


class _Metadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name", "").startswith("citation_"):
            self.values[attrs["name"]] = attrs.get("content", "")


def original_abstract(document: dict, workspace: Path) -> dict:
    """Extract exact original metadata, never the legacy task-directed digest."""
    row = dict(document)
    name = row.get("abstract_source_path")
    if name is None:
        name = row["pdf_source_path"].replace("-paper.source", "-abstract.source")
    path = contained(workspace, name, must_exist=True)
    expected = row.get("abstract_sha256") or row["published_evidence"]["sha256"]
    if file_hash(path) != expected:
        raise ProtocolError("Pinned abstract source changed")
    parser = _Metadata()
    parser.feed(path.read_text(encoding="utf8"))
    text = parser.values.get("citation_abstract")
    title = parser.values.get("citation_title")
    published = parser.values.get("citation_date", "").replace("/", "-")
    if not text or title != row["title"] or published != row["published_date"]:
        raise ProtocolError("Original abstract/title/date not verified")
    row.update(text=text, text_kind="verbatim_pinned_source_abstract",
               abstract_source_path=name, abstract_sha256=expected)
    return row


class SharedCorpusView:
    """Per-task filtered view of ONE global corpus. No per-task relevance ranking.

    Only approved original abstracts enter search. The controller must supply all
    target aliases/cross-split answer exclusions: title hiding is not isolation.
    Unknown publication/disclosure evidence fails closed, not a guessed date.
    """
    def __init__(self, documents, cutoff, excluded_papers, *, excluded_aliases=(), allowed_versions=None):
        limit = date.fromisoformat(cutoff)
        excluded = set(excluded_papers) | set(excluded_aliases)
        self.docs, seen = {}, set()
        eligible = []
        for row in documents:
            if row["document_id"] in seen:
                raise ProtocolError("Duplicate global document identity")
            seen.add(row["document_id"])
            if row.get("text_kind") != "verbatim_pinned_source_abstract" or not row.get("published_evidence"):
                raise ProtocolError("Shared corpus requires verified original abstract and version evidence")
            identity = {row["paper_id"], *row.get("paper_aliases", [])}
            if identity & excluded or row.get("index_approved") is not True:
                continue
            if row.get("disclosure_status") != "verified_background_version":
                continue
            if date.fromisoformat(row["published_date"]) > limit:
                continue
            if allowed_versions is not None and row["version"] not in allowed_versions.get(row["paper_id"], []):
                continue
            eligible.append(row)
        # Exactly one eligible version per canonical paper. Publication date and
        # explicit integer revision break ties, not arbitrary string ordering.
        newest = {}
        for row in eligible:
            key = row["paper_id"]
            rank = (row["published_date"], row.get("version_number", 1))
            if key not in newest or rank > newest[key][0]:
                newest[key] = rank, row
        fields = ("document_id", "paper_id", "title", "version", "source_url", "published_date", "text")
        for _, row in newest.values():
            self.docs[row["document_id"]] = {k: row[k] for k in fields}

    def search(self, query, limit=10):
        if not isinstance(query, str) or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ProtocolError("Invalid search request")
        terms = set(re.findall(r"\w+", query.lower()))
        hits = []
        for key, doc in self.docs.items():
            body = doc["title"] + " " + doc["text"]
            score = sum(body.lower().count(t) for t in terms)
            if score:
                hits.append((score, key, {"document_id": key, "title": doc["title"], "version": doc["version"],
                                        "snippet": doc["text"][:500]}))
        return [x[2] for x in sorted(hits, key=lambda x: (-x[0], x[1]))[:limit]]

    def read(self, document_id):
        if document_id not in self.docs:
            raise ProtocolError("Document not available in this task view")
        return dict(self.docs[document_id])


class LiteratureService:
    def __init__(self, documents: list[dict], workspace: Path, cutoff: str, excluded_papers: set[str], *, trace=None,
                 shared=False, excluded_aliases=(), allowed_versions=None):
        self.workspace = workspace.resolve(strict=True)
        if shared:
            # The whole corpus is controller-private. Policy filtering precedes
            # all returned titles/snippets/body; no affiliation labels returned.
            documents = [original_abstract(d, self.workspace) for d in documents]
            self.corpus = SharedCorpusView(documents, cutoff, excluded_papers,
                                           excluded_aliases=excluded_aliases, allowed_versions=allowed_versions)
        else:
            # Historical compatibility is explicit; old frozen runs are not
            # rewritten. Even legacy live calls no longer return authored hints.
            filtered = FrozenCorpus(documents, cutoff, excluded_papers)
            documents = [original_abstract(d, self.workspace) for d in documents if d["document_id"] in filtered.docs]
            self.corpus = FrozenCorpus(documents, cutoff, excluded_papers)
        self.records = {d["document_id"]: dict(d) for d in documents if d["document_id"] in self.corpus.docs}
        self.trace = trace
        self._readers = {}

    def _record(self, tool: str, args: dict, result: dict | list):
        if self.trace is not None:
            self.trace.append(tool, {"args": args, "result_hash": digest(result)})
        return result

    def search(self, query: str, limit: int = 10):
        return self._record("literature.search", {"query": query, "limit": limit}, self.corpus.search(query, limit))

    def read(self, document_id: str):
        result = self.corpus.read(document_id)
        result["text_kind"] = "verbatim_pinned_source_abstract"
        result["full_text_access"] = "literature.read_page(document_id, page_number); one-based PDF page"
        return self._record("literature.read", {"document_id": document_id}, result)

    def read_page(self, document_id: str, page_number: int):
        # The same policy filter as search/read is checked BEFORE any source access.
        self.corpus.read(document_id)
        if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
            raise ProtocolError("PDF page number must be a positive integer")
        row = self.records[document_id]
        source = contained(self.workspace, row["pdf_source_path"], must_exist=True)
        cache = (self.workspace / "research/source_cache/benchmark_materials").resolve(strict=True)
        if not source.is_relative_to(cache) or file_hash(source) != row["pdf_sha256"]:
            raise ProtocolError("Pinned PDF source changed or outside source cache")
        if document_id not in self._readers:
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise ProtocolError("Corpus infrastructure requires a Python with pypdf; this is not solver failure") from exc
            reader = PdfReader(source)
            if not 1 <= len(reader.pages) <= 200:
                raise ProtocolError("Source PDF page count outside development service limits")
            self._readers[document_id] = reader
        reader = self._readers[document_id]
        if page_number > len(reader.pages):
            raise ProtocolError("Page outside pinned source")
        text = reader.pages[page_number - 1].extract_text()
        if not text or len(text) > 50000:
            raise ProtocolError("PDF extraction unavailable/too large; no silent truncation or fabricated text")
        result = {"document_id": document_id, "version": row["version"], "source_url": row["source_url"],
                  "source_sha256": row["pdf_sha256"], "page_number": page_number, "page_count": len(reader.pages),
                  "page_text_hash": digest(text), "text": text,
                  "extraction_notice": "PDF text extraction is not visual verification of figures/equations; ambiguity requires source rendering."}
        return self._record("literature.read_page", {"document_id": document_id, "page_number": page_number}, result)


def retrieval_diagnostics(*, retrieved, read, adopted, documents, private_roles):
    """Descriptive counts only, not a frozen score or automatic relevance verdict."""
    papers = {d["document_id"]: d["paper_id"] for d in documents}
    stages = {}
    for name, ids in (("retrieved", retrieved), ("read", read), ("adopted", adopted)):
        unknown = sorted(set(ids) - papers.keys())
        unique = {papers[i] for i in ids if i in papers}
        stages[name] = {"paper_count": len(unique), "unknown_document_ids": unknown,
                        "role_counts": {role: len(unique & {p for p, r in private_roles.items() if r == role})
                                        for role in ("core", "background", "confusable", "unrelated")},
                        "unlabelled_paper_count": len(unique - private_roles.keys())}
    return {"stages": stages, "semantic_relevance_check": "required", "primary_score": None,
            "confusable_citation_is_not_automatic_error": True,
            "unrelated_is_reviewed_no_role_not_penalty": True}
