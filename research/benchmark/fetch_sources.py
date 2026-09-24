"""Fetch a specified allowlisted source manifest into a new immutable local snapshot.

No recursive crawling, credential handling, or execution of downloaded assets.
"""
from __future__ import annotations

import argparse
import urllib.request
import urllib.parse
from pathlib import Path

from mrhbench.io import ProtocolError, file_hash, read_json, utc_now, write_json

ALLOWED_HOSTS = {"arxiv.org", "export.arxiv.org", "api.github.com", "raw.githubusercontent.com", "proceedings.mlr.press", "openreview.net"}
MAX_BYTES = 30 * 1024 * 1024


def check_url(url):
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS or p.username or p.password:
        raise ProtocolError("Source URL is outside the explicit primary-source allowlist")


def fetch(spec: dict, output: Path):
    if output.exists():
        raise ProtocolError("Fetch snapshot directory must be new")
    for source in spec["sources"]:
        check_url(source["url"])
        if not source["source_id"].replace("_", "").replace("-", "").isalnum():
            raise ProtocolError("Unsafe source ID")
    if len({s["source_id"] for s in spec["sources"]}) != len(spec["sources"]):
        raise ProtocolError("Duplicate source IDs")
    output.mkdir(parents=True)
    records = []
    for source in spec["sources"]:
        row = {**source, "fetched_at_utc": utc_now(), "role": "maintainer_only_original_source", "redistribution_review": "pending"}
        try:
            request = urllib.request.Request(source["url"], headers={"User-Agent": "MetaResearchMaterialAudit/0.1"})
            with urllib.request.urlopen(request, timeout=45) as response:
                check_url(response.url)
                payload = response.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES:
                    raise ProtocolError("Source exceeds explicit download bound")
                row["content_type"] = response.headers.get("Content-Type")
                row["resolved_url"] = response.url
            target = output / (source["source_id"] + ".source")
            target.write_bytes(payload)
            row.update(status="fetched", file=target.name, sha256=file_hash(target), bytes=len(payload))
        except Exception as exc:
            row.update(status="fetch_failed", error=f"{type(exc).__name__}: {exc}")
        records.append(row)
        write_json(output / "manifest.json", {"schema_version": "0.1", "sources": records})
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = fetch(read_json(args.spec), args.output)
    for row in rows:
        print(row["source_id"], row["status"], row.get("bytes", row.get("error")))
