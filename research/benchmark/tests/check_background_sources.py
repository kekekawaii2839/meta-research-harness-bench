"""Actual pinned PDF/date/tool smoke checks, no research execution or judge score."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import ProtocolError, read_json, utc_now, write_json
from mrhbench.literature import LiteratureService


def run():
    rows = read_json(ROOT / "materials/background_corpus.json")["documents"]
    service = LiteratureService(rows, ROOT.parents[1], "2024-09-01", {"iclr2025-SXtl7NRyE5"})
    checks = []
    for row in rows:
        first = service.read_page(row["document_id"], 1)
        arxiv = row["document_id"].removeprefix("doc-")
        version_verified = bool(re.search(re.escape(arxiv) + r"v1", first["text"]))
        if not version_verified:
            raise AssertionError("PDF v1 stamp not found: " + row["document_id"])
        pages = [service.read_page(row["document_id"], p) for p in row["support_pages"]]
        public = service.read(row["document_id"])
        if "pdf_source_path" in public or "published_evidence" in public:
            raise AssertionError("Maintenance metadata leaked")
        checks.append({"document_id": row["document_id"], "passed": True, "version_stamp_verified": True,
                       "source_sha256": first["source_sha256"], "page_count": first["page_count"],
                       "support_pages": [{"page": p["page_number"], "text_hash": p["page_text_hash"]} for p in pages]})
    # Fact-changing boundary found through primary-source inspection.
    tent = service.read_page("doc-2006.10726", 3)["text"]
    if "regressors with predictive variance" not in tent:
        raise AssertionError("Critical probabilistic-regression qualification missing from source")
    denied = LiteratureService(rows, ROOT.parents[1], "2014-01-01", set())
    if denied.search("adaptation"):
        raise AssertionError("Future corpus documents leaked")
    try:
        denied.read_page("doc-2006.10726", 3)
    except ProtocolError:
        pass
    else:
        raise AssertionError("Read bypassed cutoff")
    write_json(ROOT / "audit/background_source_checks.json", {"kind": "source_version_and_tool_checks_not_judge_acceptance", "created_at": utc_now(),
               "checks": checks, "all_passed": True, "cutoff_read_bypass_rejected": True, "tent_regression_qualification_verified": True,
               "gpu_used": False, "model_calls": 0, "limits": ["8-paper coverage is not a formal corpus", "No target earliest-disclosure proof", "Text extraction is not PDF visual inspection", "Network sandbox not verified"]})
    print("8 pinned PDFs and support pages checked; historical read filtering verified; no GPU/model calls.")


if __name__ == "__main__":
    run()
