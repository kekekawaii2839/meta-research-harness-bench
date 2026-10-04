"""Controller-only OpenReview full-text fetch through the official API (openreview-py), with the user's own account.

User decision 2026-10-01: OpenReview is the primary full-text source (camera-ready PDF); the user supplied an
OpenReview login for this purpose. Credentials live in C:/Users/li_ha/.openreview/credentials.json (outside the git
repo), are read only here, are never printed, logged, written to any record, or passed to any model session; the
API token stays in memory. Records contain only the paper id, URL, byte size, SHA-256 and "fetched via OpenReview
API with the user's account". Exceptions are re-raised without their message text so nothing secret can leak.
"""
from pathlib import Path
import hashlib
import json
import time

CREDENTIALS = Path(r"C:/Users/li_ha/.openreview/credentials.json")
BASEURL = "https://api2.openreview.net"
_client = None


class OpenReviewFetchError(RuntimeError):
    pass


def client():
    global _client
    if _client is None:
        import openreview
        try:
            c = json.loads(CREDENTIALS.read_text(encoding="utf8"))
            _client = openreview.api.OpenReviewClient(baseurl=BASEURL, username=c["username"], password=c["password"])
        except Exception as e:  # never surface the message (could echo request data)
            raise OpenReviewFetchError("OpenReview login failed (%s)" % type(e).__name__) from None
        finally:
            c = None
    return _client


def fetch_pdf(forum_id, dest: Path, pause=2.0):
    """Download the submission PDF for an OpenReview forum id to dest; returns a provenance record."""
    try:
        data = client().get_pdf(forum_id)
    except OpenReviewFetchError:
        raise
    except Exception as e:
        raise OpenReviewFetchError("OpenReview PDF fetch failed for %s (%s)" % (forum_id, type(e).__name__)) from None
    if not isinstance(data, (bytes, bytearray)) or not data.startswith(b"%PDF"):
        raise OpenReviewFetchError("OpenReview returned non-PDF content for %s" % forum_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    time.sleep(pause)  # be polite to the API
    return {"source": "openreview_api", "forum_id": forum_id, "url": "https://openreview.net/pdf?id=" + forum_id,
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "access": "fetched via the OpenReview API with the user's own account (user decision 2026-10-01)",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def pdf_text(pdf_path: Path) -> bytes:
    """Controller-side text extraction (pypdf) with explicit page markers. Added because the Claude CLI Read tool
    refused unencrypted OpenReview PDFs as 'password-protected' (2026-10-01); the PDF stays the original source and
    this text is a derived, hash-bound view of it."""
    from pypdf import PdfReader, __version__ as pypdf_version
    r = PdfReader(str(pdf_path))
    parts = ["[controller text extraction of %s with pypdf %s; %d pages; page markers are controller-added; layout, "
             "figures and some math may be lost: verify against the PDF where precision matters]\n"
             % (pdf_path.name, pypdf_version, len(r.pages))]
    for i, page in enumerate(r.pages, 1):
        parts.append("\n=== page %d ===\n" % i)
        parts.append(page.extract_text() or "")
    return "".join(parts).encode("utf8")


def submission_date(forum_id):
    """YYYY-MM-DD when the OpenReview submission became public (note odate; cdate is the private creation time,
    pdate the decision). Earliest-disclosure bound when it precedes arXiv v1 (2026-10-02 background cutoff fix)."""
    try:
        note = client().get_note(forum_id)
    except OpenReviewFetchError:
        raise
    except Exception as e:
        raise OpenReviewFetchError("OpenReview note fetch failed for %s (%s)" % (forum_id, type(e).__name__)) from None
    fields = {k: getattr(note, k, None) for k in ("cdate", "odate", "pdate")}
    if not isinstance(fields["odate"], int):
        raise OpenReviewFetchError("OpenReview note has no public date (odate) for %s" % forum_id)
    return time.strftime("%Y-%m-%d", time.gmtime(fields["odate"] / 1000)), fields
