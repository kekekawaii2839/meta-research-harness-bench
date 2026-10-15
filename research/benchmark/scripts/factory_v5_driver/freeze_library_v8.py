"""T17: freeze shared-library-v8 as the search-set v1.3 literature library and point every v1.3 LIT task at it
(user 2026-10-13: "ok先做你说的这两件事"; zero model calls).

1. FROZEN.json in the library root: corpus.json sha256 + sha256 of every library file (sorted manifest digest),
   document count, source factory roots, decision. A copy goes to research/benchmark/audit/.
2. For each v1.3 LIT unit (list from D:/mrhbench-local-pilot/v1_3-rejudge-pilot-estimate.json): back up
   lit_corpus_configuration.json (*.pre-t17.20261013) and rewrite library_root/corpus_sha256/library_version_note; every
   other field (cutoff, cutoff basis, exclusions) is kept. Units without a config (factory-v8 YOc5/n8h1 LIT) get one built
   by the factory-v8.1 compile rule with the cutoff their frame used (frame.json cutoff_date).
Usage: python freeze_library_v8.py [--dry]
"""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import sys

LIB = Path(r"D:/mrhbench-local-pilot/shared-library-v8")
AUDIT = Path(r"C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark/audit/search_set_v1_3_library_freeze.json")
EST = Path(r"D:/mrhbench-local-pilot/v1_3-rejudge-pilot-estimate.json")
NOTE = "frozen search-set v1.3 library (T17, 2026-10-13); all harness versions evaluated on search set v1.3 use this library"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(dry):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    corpus = json.loads((LIB / "corpus.json").read_text(encoding="utf8"))
    corpus_sha = sha_file(LIB / "corpus.json")
    files = sorted(p for p in LIB.rglob("*") if p.is_file() and p.name != "FROZEN.json")
    manifest = [[str(p.relative_to(LIB)).replace("\\", "/"), sha_file(p)] for p in files]
    manifest_sha = hashlib.sha256(json.dumps(manifest).encode()).hexdigest()
    frozen = {"name": "shared-library-v8", "frozen_at": now, "status": "frozen for search set v1.3 (T17)",
              "decision": "user 2026-10-13 (AGENTS.md T17): freeze the search-set library after all v1.3 tasks were built",
              "corpus_sha256": corpus_sha, "documents": len(corpus["documents"]), "skipped": corpus["skipped"],
              "factory_roots": corpus["factory_roots"], "files": len(manifest),
              "file_manifest_sha256": manifest_sha, "file_manifest_rule": "sha256 of JSON list of [relative path, sha256] sorted by path",
              "build": "factory_library.py build (zero model calls); log D:/mrhbench-local-pilot/shared-library-v8-build.log",
              "rule": "do not modify; a new library needs a new directory and invalidates LIT score comparability"}
    est = json.loads(EST.read_text(encoding="utf8"))
    lit = [t for t in est["tasks"] if t["type"] == "LIT"]
    changes = []
    for t in lit:
        u = Path(t["unit"])
        cfg_p = u / "lit_corpus_configuration.json"
        if cfg_p.exists():
            cfg = json.loads(cfg_p.read_text(encoding="utf8"))
            created = False
        else:
            pdir = u.parents[1]
            frame = json.loads((u / "frame" / "frame.json").read_text(encoding="utf8"))
            job = json.loads((u / "job.json").read_text(encoding="utf8"))
            arx = (json.loads((pdir / "sources" / "manifest.json").read_text(encoding="utf8")).get("arxiv") or {}).get("id")
            pid = pdir.name
            cfg = {"schema_version": "lit-corpus-configuration-4", "cutoff": frame["cutoff_date"],
                   "cutoff_basis": {**(job.get("first_disclosure") or {}).get("basis", {}), "source": "frame.json cutoff_date (factory-v8 unit, no 14-day offset)"},
                   "cutoff_semantics": "version_date strictly before cutoff (cutoff = the date the unit's public frame states)",
                   "excluded_papers": ["background-arxiv-" + arx] if arx else [],
                   "excluded_aliases": [a for a in (arx, pid, pid.split("-", 1)[1]) if a]}
            created = True
        old = (cfg.get("library_root"), cfg.get("corpus_sha256"))
        cfg.update(library_root=str(LIB), corpus_sha256=corpus_sha, library_version_note=NOTE)
        changes.append({"paper": t["paper"], "unit": str(u), "created": created, "old_library": old[0],
                        "cutoff": cfg["cutoff"], "excluded_aliases": cfg["excluded_aliases"]})
        if not dry:
            if cfg_p.exists():
                bak = u / "lit_corpus_configuration.json.pre-t17.20261013"
                if bak.exists():
                    raise SystemExit("backup exists: " + str(bak))
                shutil.copyfile(cfg_p, bak)
            cfg_p.write_text(json.dumps(cfg, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf8", newline="")
    frozen["lit_tasks"] = changes
    if not dry:
        for p in (LIB / "FROZEN.json", AUDIT):
            if p.exists():
                raise SystemExit("exists: " + str(p))
            p.write_text(json.dumps(frozen, ensure_ascii=False, indent=1) + "\n", encoding="utf8", newline="")
        (LIB / "file_manifest.json").write_text(json.dumps(manifest), encoding="utf8", newline="") if not (LIB / "file_manifest.json").exists() else None
    print(json.dumps({"corpus_sha256": corpus_sha, "documents": len(corpus["documents"]), "files": len(manifest),
                      "lit_tasks": len(changes), "created": sum(c["created"] for c in changes),
                      "old_libraries": sorted({str(c["old_library"]) for c in changes})}, indent=1))


if __name__ == "__main__":
    main("--dry" in sys.argv)
