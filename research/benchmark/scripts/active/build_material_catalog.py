"""Normalize source snapshots and role-specific task assets without flattening them.

This is a maintainer-only catalogue. NEVER give it to a builder/executor: it links
target source identities, public inputs and private references across stages.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.io import ProtocolError, file_hash, read_json, write_json
from mrhbench.materials import load_task, validate_split

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parents[1]


def build_catalog():
    sources = defaultdict(list)
    source_ids = set()
    separate_background_manifests = []
    cache = WORKSPACE / "research/source_cache/benchmark_materials"
    overlays = {}
    for row in read_json(ROOT / "materials/source_manifest_overlays.json")["overlays"]:
        overlays[row["manifest"]] = row
    for manifest in sorted(cache.glob("*/manifest.json")):
        data = read_json(manifest)
        overlay = overlays.get(manifest.relative_to(WORKSPACE).as_posix())
        if overlay is not None and overlay["sha256"] != file_hash(manifest):
            raise ProtocolError("Source manifest overlay hash mismatch: " + str(manifest))
        if "sources" not in data:
            if data.get("raw_source_role") != "maintainer_owned_service_cache" or not isinstance(data.get("fetched"), list):
                raise ProtocolError("Unknown source manifest schema: " + str(manifest))
            separate_background_manifests.append({
                "path": manifest.relative_to(WORKSPACE).as_posix(), "sha256": file_hash(manifest),
                "reason": "Separately audited R2 background service cache; not a target paper package.",
                "included_in_legacy_counts": False,
            })
            continue
        for row in data["sources"]:
            if row["source_id"] in source_ids:
                raise ProtocolError("Ambiguous source ID across snapshots")
            source_ids.add(row["source_id"])
            path = manifest.parent / row["file"] if row.get("file") else None
            if row["status"] == "fetched" and (path is None or not path.is_file() or file_hash(path) != row["sha256"]):
                raise ProtocolError("Source manifest does not match actual source bytes")
            if "paper_id" in row:
                paper_id, kind = row["paper_id"], row["kind"]
            elif overlay is not None:
                paper_id, kind = overlay["paper_id"], row.get("kind", overlay["default_kind"])
            else:
                raise ProtocolError("Source row lacks paper_id and no hash-bound overlay: " + str(manifest))
            sources[paper_id].append({
                "source_id": row["source_id"], "role": kind, "url": row["url"], "version": row["version"],
                "sha256": row.get("sha256"), "retrieval_status": row["status"],
                "local_path": path.relative_to(WORKSPACE).as_posix() if path else None,
                "source_manifest": manifest.relative_to(WORKSPACE).as_posix(),
                "source_manifest_sha256": file_hash(manifest), "visibility": "maintainer_only",
                "redistribution_status": "not_automatically_cleared_by_public_access",
            })
    tasks = [load_task(p) for p in sorted((ROOT / "materials").glob("*/task.json"))]
    paths = {read_json(p)["task_id"]: p for p in sorted((ROOT / "materials").glob("*/task.json"))}
    validate_split(tasks)
    by_paper = defaultdict(list)
    for task in tasks:
        by_paper[task["paper_id"]].append(task)
    background = {k: v for k, v in sources.items() if k.startswith("background-arxiv-")}
    packages = []
    for paper_id in sorted((set(sources) - set(background)) | set(by_paper)):
        task_rows = []
        for task in by_paper.get(paper_id, []):
            path = paths[task["task_id"]]
            task_rows.append({"task_id": task["task_id"], "task_type": task["task_type"], "split": task["split"],
                              "task_manifest": path.relative_to(WORKSPACE).as_posix(), "task_manifest_sha256": file_hash(path),
                              "gates": task["gates"], "role_specific_assets": task["assets"]})
        packages.append({
            "schema_version": "0.1", "package_id": "material-" + paper_id, "paper_id": paper_id,
            "grouping": "source_paper_no_cross_paper_merge", "raw_sources": sources[paper_id], "tasks": task_rows,
            "first_public_disclosure": {"verified": False, "date": None, "reason": "Pinned arXiv version alone does not exclude earlier project/repository/report disclosure; required before historical LIT/IDEA acceptance."},
            "rights": {"blanket_clearance": False, "policy": "Judge each raw asset and derived task's rights gate separately; repository rights do not cover a paper or linked datasets."},
            "gpu_execution": "deferred_gpu_environment_for_gpu_dependent_research; CPU-only task checks tracked separately",
            "material_state": "development_constructed" if task_rows else "source_acquired_no_task_constructed",
            "not_author_original_trajectory": True,
        })
    return {"schema_version": "0.1", "visibility": "maintainer_only_do_not_export_to_builder_or_executor",
            "packages": packages, "shared_background_sources": background,
            "separate_background_manifests": separate_background_manifests,
            "counts": {"source_paper_packages": len(packages), "constructed_task_count": len(tasks),
                       "shared_background_papers": len(background),
                       "constructed_source_paper_count": len(by_paper), "task_types_constructed": sorted({t["task_type"] for t in tasks}),
                       "formal_accepted_tasks": sum(t["split"] != "development" and all(g["status"] == "passed" for g in t["gates"].values()) for t in tasks)},
            "limitations": ["Legacy top-level task catalogue only: nested pilot_v3 candidates and separately managed R2 corpus are not counted.", "Not the full candidate pool audit; see coverage.json for all 30 candidates.", "No inferred paper quality, absent material or source rights from task coverage."]}


if __name__ == "__main__":
    catalog = build_catalog()
    write_json(ROOT / "materials/material_packages.json", catalog)
    print(catalog["counts"])
