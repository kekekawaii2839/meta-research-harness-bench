"""R2 shared literature library v4: merge factory-fetched background works into ONE global corpus.

Zero model calls. The v3 corpus (18 pilot backgrounds, PDF full text) is copied byte-for-byte; every
factory background (arXiv abs page + arXiv HTML full text, chosen version strictly before that paper's
cutoff) is added as (arxiv id, version) documents. Files are content-addressed under the library root.

Runtime service = subclasses of the existing LiteratureService / SharedCorpusView, so the existing judge
evidence builder (isinstance checks + original_abstract metadata verification) works unchanged:
  * cutoff filtering uses the ACTUAL fetched version date (`version_date`), strictly before the task cutoff
    (the abs page's citation_date is the v1 date and only serves the pinned-metadata check);
  * HTML full text is served as deterministic ~6000-character pages (math kept as LaTeX alttext);
  * v3 PDF documents keep the original page-based reader.
Nothing here is a relevance label: the corpus is shared across tasks and not curated per question.
"""
from pathlib import Path
from html.parser import HTMLParser
from datetime import date
import argparse
import html as htmlmod
import json
import math
import re
import shutil
import sys

BENCH = Path(r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
REPO = BENCH.parents[1]
sys.path.insert(0, str(BENCH))

from mrhbench.io import ProtocolError, contained, digest, file_hash, read_json, write_json  # noqa: E402
from mrhbench.literature import LiteratureService, SharedCorpusView, original_abstract  # noqa: E402

V3_CORPUS = BENCH / "materials/pilot_v3/literature_v3/shared_background_corpus.json"
PAGE_CHARS = 6000


# ----------------------------------------------------------------------------- HTML text
# arXiv (LaTeXML) section/paragraph anchors are kept in page text as [§S2.p3] so readers can cite a locator.
ANCHOR = re.compile(r"(?:S|A)\d+(?:\.(?:SS|SSS|p)\d+)*")


class _Text(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "button", "svg"}
    BLOCK = {"p", "div", "section", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "table", "figcaption", "br", "blockquote", "pre"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.math = [], 0, 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "math":
            alt = dict(attrs).get("alttext")
            if not self.skip:
                self.out.append(" $" + alt + "$ " if alt else " [math] ")
            self.math += 1
        elif tag in self.BLOCK and not self.skip:
            self.out.append("\n")
            a = dict(attrs)
            if tag in ("section", "div") and ANCHOR.fullmatch(a.get("id") or ""):
                self.out.append("[§%s] " % a["id"])
            elif tag == "div" and "ltx_abstract" in (a.get("class") or "").split():
                self.out.append("[§abstract] ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "math" and self.math:
            self.math -= 1
        elif tag in self.BLOCK and not self.skip:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip and not self.math:
            self.out.append(data)


def html_text(raw: str) -> str:
    p = _Text()
    p.feed(raw)
    text = "".join(p.out)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*(\n\s*)+", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def paginate(text: str, size=PAGE_CHARS):
    """Deterministic pages at paragraph/line boundaries, never splitting inside a line unless unavoidable."""
    pages, cur = [], ""
    for line in text.split("\n"):
        while len(line) > size:
            if cur:
                pages.append(cur)
                cur = ""
            pages.append(line[:size])
            line = line[size:]
        if len(cur) + len(line) + 1 > size and cur:
            pages.append(cur)
            cur = ""
        cur = (cur + "\n" + line) if cur else line
    if cur:
        pages.append(cur)
    return pages


class _Meta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name", "").startswith("citation_"):
            self.values.setdefault(a["name"], a.get("content", ""))


def abs_meta(path: Path):
    p = _Meta()
    p.feed(path.read_text(encoding="utf8"))
    return p.values


# ----------------------------------------------------------------------------- build
def _fetch_pdf(arx, ver, out):
    """Network only (no model). Stored where the inherited PDF page reader accepts it."""
    from mrhbench.factory_sources import requests_http
    url = "https://arxiv.org/pdf/%sv%d" % (arx, ver)
    try:
        status, final, headers, body = requests_http(url, 60 * 1024 * 1024)
    except Exception:
        return None
    if status != 200 or not body.startswith(b"%PDF"):
        return None
    rel = "research/source_cache/benchmark_materials/factory_library_v4/%sv%d.pdf" % (arx, ver)
    dst = out / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(body)
    return rel, file_hash(dst), url


def _pdf_unreadable(path: Path):
    """Return a reason when the inherited PDF page reader would refuse some page (same limits:
    1-200 pages, every page non-empty extracted text of at most 50000 characters), else None.
    A document the judge evidence builder cannot preload completely is skipped at build time,
    never truncated (zero model calls)."""
    from pypdf import PdfReader
    try:
        reader = PdfReader(path)
        n = len(reader.pages)
        if not 1 <= n <= 200:
            return "PDF page count %d outside reader limits" % n
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if not text or len(text) > 50000:
                return "PDF page %d text extraction empty or over 50000 characters" % i
    except Exception as exc:  # malformed PDF
        return "PDF unreadable: %s" % type(exc).__name__
    return None


def _copy_addressed(src: Path, root: Path, suffix: str):
    sha = file_hash(src)
    rel = "files/%s%s" % (sha, suffix)
    dst = root / rel
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    if file_hash(dst) != sha:
        raise ProtocolError("Library file content mismatch: " + rel)
    return rel, sha


def build(factory_roots, out: Path):
    if out.exists():
        raise ProtocolError("Library version root exists; a new version needs a new directory")
    out.mkdir(parents=True)
    docs, skipped, seen, skipped_keys = [], [], {}, set()
    # 1. v3 seed documents, byte-identical files at their original relative paths.
    v3 = read_json(V3_CORPUS)
    for row in v3["documents"]:
        for key in ("abstract_source_path", "pdf_source_path"):
            src = REPO / row[key]
            dst = out / row[key]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        row = {**row, "version_date": row["published_date"], "fulltext_kind": "pdf", "library_origin": "shared_background_v3"}
        row.setdefault("version_number", 1)
        docs.append(row)
        seen[(row["paper_id"], row["version"])] = row["document_id"]
    # 2. benchmark target arXiv ids (for cross-task exclusion flags).
    targets = {}
    for froot in factory_roots:
        for m in Path(froot).glob("papers/*/sources/manifest.json"):
            if ".failed-" in str(m):
                continue
            a = (read_json(m).get("arxiv") or {}).get("id")
            if a:
                targets[a] = read_json(m)["project_id"]
    # 3. factory backgrounds.
    for froot in factory_roots:
        for bgm in sorted(Path(froot).glob("papers/*/background/manifest.json")):
            if ".failed-" in str(bgm):
                continue
            pdir = bgm.parent.parent
            man = read_json(bgm)
            by_id = {s["source_id"]: s for s in man["sources"]}
            for req in man["requests"]:
                if req.get("status") != "found":
                    continue
                arx, ver = req["arxiv_id"], req["chosen_version"]
                paper_id, version = "background-arxiv-" + arx, "arxiv-v%d" % ver
                key = (paper_id, version)
                srcs = [by_id[s] for s in req["source_ids"] if s in by_id]
                absr = next((s for s in srcs if s["role"].endswith("abs_page")), None)
                html = next((s for s in srcs if "paper" in s["role"] and s["local_path"].endswith(".html")), None)
                where = "%s:%s" % (pdir.name, req["request_id"])
                if key in seen:
                    continue
                if absr is None:
                    if key not in skipped_keys:
                        skipped.append({"from": where, "arxiv": arx, "version": ver, "reason": "no abs page: metadata cannot be verified"})
                        skipped_keys.add(key)
                    continue
                apath = pdir / absr["local_path"]
                hpath = pdir / html["local_path"] if html else None
                if file_hash(apath) != absr["sha256"] or (hpath and file_hash(hpath) != html["sha256"]):
                    raise ProtocolError("Background source bytes changed: " + where)
                meta = abs_meta(apath)
                vdate = next((v["date"] for v in req["versions"] if v["version"] == ver), None)
                if not meta.get("citation_abstract") or not meta.get("citation_title") or not meta.get("citation_date") or not vdate:
                    skipped.append({"from": where, "arxiv": arx, "version": ver, "reason": "abs page lacks citation_title/abstract/date or version date unknown"})
                    continue
                if date.fromisoformat(vdate) >= date.fromisoformat(req["cutoff_date"]):
                    raise ProtocolError("Fetched background version not before its own cutoff: " + where)
                text = html_text(hpath.read_text(encoding="utf8", errors="strict")) if hpath else ""
                pdf = None
                if len(text) < 2000:
                    # arXiv has no HTML rendering for this version (placeholder page): use the version's PDF instead.
                    pdf = _fetch_pdf(arx, ver, out)
                    if pdf is None:
                        if key not in skipped_keys:
                            skipped.append({"from": where, "arxiv": arx, "version": ver, "reason": "no HTML full text and PDF fetch failed"})
                            skipped_keys.add(key)
                        continue
                    bad = _pdf_unreadable(out / pdf[0])
                    if bad:
                        if key not in skipped_keys:
                            skipped.append({"from": where, "arxiv": arx, "version": ver, "reason": "no HTML full text; " + bad})
                            skipped_keys.add(key)
                        continue
                arel, asha = _copy_addressed(apath, out, ".abs.html")
                hrel, hsha = _copy_addressed(hpath, out, ".paper.html") if pdf is None else (None, None)
                row = {"document_id": "doc-%sv%d" % (arx, ver), "paper_id": paper_id, "paper_aliases": [arx],
                       "title": meta["citation_title"], "version": version, "version_number": ver,
                       "published_date": meta["citation_date"].replace("/", "-"), "version_date": vdate,
                       "source_url": "https://arxiv.org/abs/%sv%d" % (arx, ver),
                       "abstract_source_path": arel, "abstract_sha256": asha,
                       "published_evidence": {"url": absr["url"], "sha256": asha,
                                              "locator": "citation_* meta (citation_date = v1); version date from controller version history"},
                       **({"html_source_path": hrel, "html_sha256": hsha, "fulltext_kind": "arxiv_html"} if pdf is None else
                          {"pdf_source_path": pdf[0], "pdf_sha256": pdf[1], "fulltext_kind": "pdf", "pdf_url": pdf[2],
                           "fulltext_note": "arXiv provides no HTML for this version; controller fetched the version PDF"}),
                       "text": meta["citation_abstract"], "text_kind": "verbatim_pinned_source_abstract",
                       "disclosure_status": "verified_background_version", "index_approved": True,
                       "benchmark_target_project_id": targets.get(arx),
                       "library_origin": "factory_background:" + where}
                docs.append(row)
                seen[key] = row["document_id"]
    corpus = {"schema_version": "shared-background-4", "documents": docs, "skipped": skipped,
              "factory_roots": [str(r) for r in factory_roots], "seed": {"path": str(V3_CORPUS), "sha256": file_hash(V3_CORPUS)},
              "version_policy": "one document per (arXiv id, fetched version); task view keeps the newest version strictly before the task cutoff",
              "ranking": "deterministic_lexical_abstract_baseline_not_validated_retrieval_quality",
              "rights": "service_only_no_blanket_redistribution_permission",
              "relevance_labels": "none_in_corpus", "formal_material_accepted": False}
    write_json(out / "corpus.json", corpus, exclusive=True)
    return corpus


# ----------------------------------------------------------------------------- runtime service
class VersionDatedCorpusView(SharedCorpusView):
    """Same policy as SharedCorpusView, but the cutoff applies to the actual fetched version date,
    strictly before the cutoff (exclusive), and benchmark-target flags are excluded for the given ids."""
    def __init__(self, documents, cutoff, excluded_papers, *, excluded_aliases=(), allowed_versions=None):
        limit = date.fromisoformat(cutoff)
        keep = [d for d in documents if date.fromisoformat(d.get("version_date") or d["published_date"]) < limit]
        super().__init__(keep, cutoff, excluded_papers, excluded_aliases=excluded_aliases, allowed_versions=allowed_versions)
        by_id = {d["document_id"]: d for d in keep}
        for k, doc in self.docs.items():
            doc["version_date"] = by_id[k].get("version_date") or doc["published_date"]
        # BM25 index over title + verbatim abstract (the only text search sees); computed once per task view.
        self._tf, self._len = {}, {}
        df = {}
        for k, doc in self.docs.items():
            toks = re.findall(r"\w+", (doc["title"] + " " + doc["text"]).lower())
            tf = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            self._tf[k], self._len[k] = tf, len(toks)
            for t in tf:
                df[t] = df.get(t, 0) + 1
        n = max(len(self.docs), 1)
        self._idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self._avg = (sum(self._len.values()) / n) if self.docs else 1.0

    def search(self, query, limit=10):
        """BM25 (k1=1.2, b=0.75) over title+abstract; results carry version and version_date."""
        if not isinstance(query, str) or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ProtocolError("Invalid search request")
        terms = set(re.findall(r"\w+", query.lower()))
        k1, b = 1.2, 0.75
        hits = []
        for key, doc in self.docs.items():
            tf, dl = self._tf[key], self._len[key]
            score = sum(self._idf[t] * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * dl / self._avg)) for t in terms if t in tf)
            if score > 0:
                hits.append((score, key, {"document_id": key, "title": doc["title"], "version": doc["version"],
                                          "version_date": doc["version_date"], "snippet": doc["text"][:500]}))
        return [x[2] for x in sorted(hits, key=lambda x: (-x[0], x[1]))[:limit]]


class SharedLibraryService(LiteratureService):
    def __init__(self, library_root, cutoff, excluded_papers=(), *, excluded_aliases=(), trace=None):
        root = Path(library_root).resolve(strict=True)
        corpus = read_json(root / "corpus.json")
        documents = [original_abstract(d, root) for d in corpus["documents"]]
        self.workspace = root
        self.corpus = VersionDatedCorpusView(documents, cutoff, set(excluded_papers), excluded_aliases=excluded_aliases)
        self.records = {d["document_id"]: dict(d) for d in documents if d["document_id"] in self.corpus.docs}
        self.trace = trace
        self._readers = {}
        self._html_pages = {}

    def read(self, document_id):
        # HTML-backed documents: same record as LiteratureService.read, but the page note must not say "PDF page"
        # (the result is completed before it is recorded, so the trace hash matches what the executor receives).
        if self.records.get(document_id, {}).get("fulltext_kind") != "arxiv_html":
            return super().read(document_id)
        result = self.corpus.read(document_id)  # policy check, as in LiteratureService.read
        result["text_kind"] = "verbatim_pinned_source_abstract"
        result["full_text_access"] = ("literature.read_page(document_id, page_number); one-based controller pages of the "
                                      "pinned arXiv HTML text (not PDF pages); page text carries bracketed anchor markers")
        return self._record("literature.read", {"document_id": document_id}, result)

    def read_page(self, document_id, page_number):
        self.corpus.read(document_id)  # policy before any source access
        row = self.records[document_id]
        if row.get("fulltext_kind") != "arxiv_html":
            return super().read_page(document_id, page_number)
        if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
            raise ProtocolError("Page number must be a positive integer")
        if document_id not in self._html_pages:
            source = contained(self.workspace, row["html_source_path"], must_exist=True)
            if file_hash(source) != row["html_sha256"]:
                raise ProtocolError("Pinned HTML source changed")
            self._html_pages[document_id] = paginate(html_text(source.read_text(encoding="utf8")))
        pages = self._html_pages[document_id]
        if page_number > len(pages):
            raise ProtocolError("Page outside pinned source")
        text = pages[page_number - 1]
        result = {"document_id": document_id, "version": row["version"], "source_url": row["source_url"],
                  "source_sha256": row["html_sha256"], "page_number": page_number, "page_count": len(pages),
                  "page_text_hash": digest(text), "text": text,
                  "extraction_notice": ("Controller text extraction of the pinned arXiv HTML, split into ~%d-character pages; "
                                        "math is shown as LaTeX alttext; figures are not rendered. Page numbers are controller "
                                        "pages, not PDF pages. Bracketed markers beginning with § in this page text are the arXiv "
                                        "HTML section/paragraph anchors of the text that follows (S=section, SS=subsection, "
                                        "p=paragraph, A=appendix). To cite a passage, copy the nearest marker that precedes it on "
                                        "this page exactly; never construct an anchor that does not appear in the text." % PAGE_CHARS)}
        return self._record("literature.read_page", {"document_id": document_id, "page_number": page_number}, result)


def task_configuration(library_root, *, cutoff, target_project_id, target_arxiv_id):
    """Private per-task corpus configuration for a LIT task (controller-side, never solver-visible)."""
    root = Path(library_root)
    return {"schema_version": "lit-corpus-configuration-4", "library_root": str(root),
            "corpus_sha256": file_hash(root / "corpus.json"), "cutoff": cutoff, "cutoff_semantics": "version_date strictly before cutoff",
            "excluded_papers": ["background-arxiv-" + target_arxiv_id],
            "excluded_aliases": [target_arxiv_id, target_project_id, target_project_id.split("-", 1)[-1]]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--factory-roots", nargs="+", required=True)
    a = ap.parse_args()
    c = build([Path(r) for r in a.factory_roots], Path(a.out))
    print(json.dumps({"documents": len(c["documents"]), "skipped": len(c["skipped"])}, indent=1))


if __name__ == "__main__":
    main()
