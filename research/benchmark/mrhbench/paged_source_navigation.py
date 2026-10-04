"""Opt-in bounded navigation copies; never replace sources or claim model reads.

Large indivisible units fail explicitly rather than truncating scientific text.
Existing frozen publication/runner paths are deliberately not changed here.
"""
import json
from pathlib import Path

from .incremental_repair import _safe_path, _disjoint
from .io import ProtocolError, read_json, file_hash, digest


def _encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf8")


def publish_pages(navigation, source, destination, *, max_page_bytes=16000):
    navigation, source = _safe_path(Path(navigation)), _safe_path(Path(source))
    destination = _safe_path(Path(destination))
    if type(max_page_bytes) is not int or not 1024 <= max_page_bytes <= 16000:
        raise ProtocolError("Page bound must be 1024..16000 bytes")
    if destination.exists():
        raise ProtocolError("Fresh destination required")
    _disjoint(navigation, destination)
    _disjoint(source, destination)
    nav = read_json(navigation)
    if (nav.get("schema_version") != "source-navigation-1"
            or nav.get("source_sha256") != file_hash(source)
            or not isinstance(nav.get("units"), list)
            or any(not isinstance(u, dict) for u in nav["units"])):
        raise ProtocolError("Verified original source and complete navigation units required")
    metadata = {k: v for k, v in nav.items() if k != "units"}
    pages, current, start = [], [], 0

    def frame(units, first):
        return {"schema_version": "source-navigation-page-1", "unit_start": first,
                "unit_end_exclusive": first + len(units), "units": units}

    for unit in nav["units"]:
        if len(_encode(frame(current + [unit], start))) > max_page_bytes:
            if current:
                pages.append(frame(current, start))
                start += len(current)
                current = []
            if len(_encode(frame([unit], start))) > max_page_bytes:
                raise ProtocolError("Indivisible unit exceeds page bound; original retained, no truncated publication")
        current.append(unit)
    if current or not pages:
        pages.append(frame(current, start))
    payloads = {f"page-{i:04d}.json": _encode(page) for i, page in enumerate(pages)}
    import hashlib
    manifest = {"schema_version": "paged-source-navigation-1", "metadata": metadata,
                "original_navigation_sha256": file_hash(navigation),
                "navigation_digest": digest(nav), "unit_count": len(nav["units"]),
                "max_page_bytes": max_page_bytes, "model_read_verified": False,
                "notice": "Derived navigation, not independent evidence. Read selected complete pages and verify against original source. No summary or omitted units.",
                "pages": [{"path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                           "bytes": len(raw), "unit_start": page["unit_start"],
                           "unit_end_exclusive": page["unit_end_exclusive"]}
                          for (name, raw), page in zip(payloads.items(), pages)]}
    payloads["index.json"] = _encode(manifest)
    if any(len(raw) > max_page_bytes for raw in payloads.values()):
        raise ProtocolError("Index or metadata exceeds page bound; no partial publication")
    destination.mkdir(parents=True)
    for name, raw in payloads.items():
        with (destination / name).open("xb") as handle:
            handle.write(raw)
    return manifest


def verify_pages(destination, navigation, source):
    """Reassemble all units exactly; no skipped, repeated or stale page accepted."""
    root = _safe_path(Path(destination))
    nav = read_json(_safe_path(Path(navigation)))
    source = _safe_path(Path(source))
    manifest = read_json(_safe_path(root / "index.json"))
    if (manifest.get("schema_version") != "paged-source-navigation-1"
            or manifest["original_navigation_sha256"] != file_hash(navigation)
            or manifest["metadata"].get("source_sha256") != file_hash(source)):
        raise ProtocolError("Navigation/source identity changed")
    expected = {"index.json"} | {f"page-{i:04d}.json" for i in range(len(manifest["pages"]))}
    if {p.name for p in root.iterdir()} != expected:
        raise ProtocolError("Page directory membership changed")
    units = []
    for i, row in enumerate(manifest["pages"]):
        if row["path"] != f"page-{i:04d}.json":
            raise ProtocolError("Page order/path changed")
        path = _safe_path(root / row["path"])
        if file_hash(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
            raise ProtocolError("Page bytes changed")
        page = read_json(path)
        if (page["schema_version"] != "source-navigation-page-1"
                or page["unit_start"] != row["unit_start"] or page["unit_start"] != len(units)
                or page["unit_end_exclusive"] != row["unit_end_exclusive"]
                or page["unit_end_exclusive"] != len(units) + len(page["units"])):
            raise ProtocolError("Missing or duplicated units")
        units.extend(page["units"])
    reconstructed = {**manifest["metadata"], "units": units}
    if reconstructed != nav or digest(reconstructed) != manifest["navigation_digest"] or len(units) != manifest["unit_count"]:
        raise ProtocolError("Navigation content changed")
    bound = manifest["max_page_bytes"]
    if type(bound) is not int or not 1024 <= bound <= 16000 or any(p.stat().st_size > bound for p in root.iterdir()):
        raise ProtocolError("Published read bound exceeded")
    return {"lossless": True, "units": len(units), "pages": len(manifest["pages"]), "model_read_verified": False}
