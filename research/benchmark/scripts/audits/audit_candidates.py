"""Index-level material audit of existing candidates; does NOT certify task readiness."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.io import file_hash, read_json, write_json
from mrhbench.scoring import TASK_TYPES
from mrhbench.materials import load_task


def audit(workspace: Path) -> dict:
    index = workspace / "research/aiml/iclr2025_pilot/pilot30.json"
    cache = workspace / "research/source_cache/iclr2025_pilot/repos"
    records = read_json(index)
    constructed = {}
    material_root = workspace / "research/benchmark/materials"
    for path in sorted(material_root.glob("*/task.json")):
        task = load_task(path)
        constructed.setdefault((task["paper_id"], task["task_type"]), []).append((path, task))
    rows = []
    for project in records:
        assets = []
        for repo in project.get("repositories", []):
            slug = repo.get("canonical_slug") or repo.get("slug")
            if not slug:
                continue
            directory = cache / slug.replace("/", "__")
            for name in ("repo.json", "README.txt"):
                path = directory / name
                if path.is_file():
                    assets.append({"kind": "repository_metadata" if name == "repo.json" else "repository_readme",
                                   "repository": slug, "path": path.relative_to(workspace).as_posix(), "sha256": file_hash(path),
                                   "source_url": repo.get("url"), "version_status": "legacy_mutable_snapshot_not_commit_pinned"})
        licenses = [r.get("license_spdx") for r in project.get("repositories", [])]
        cells = {}
        for kind in TASK_TYPES:
            cells[kind] = {
                "status": "review_needed" if assets else "unknown",
                "available_asset_roles": sorted({a["kind"] for a in assets}),
                "missing_or_unverified": {
                    "LIT": ["historical_background_corpus", "earliest_public_disclosure", "independent_pre_cutoff_facts", "judge_calibration"],
                    "IDEA": ["reviewed_pre_cutoff_background", "proposal_independent_input", "private_evaluation_context", "judge_calibration"],
                    "EXP": ["accurate_proposal_hypotheses", "runnable_sanitized_start", "data_and_compute_access", "evidence_verifier", "judge_calibration"],
                    "WRITE_CONTENT": ["verified_research_fact_package", "writing_scope", "source_fact_alignment", "judge_calibration"],
                    "WRITE_EVIDENCE": ["verified_numeric_results", "metric_and_aggregation_definitions", "numeric_verifier", "visual_judge_calibration"],
                }[kind],
                "task_constructed": False, "scientific_acceptance": False,
                "evidence": "Index and cached metadata/README existence only; no inference of absence or readiness from title/keywords.",
            }
            packages = constructed.get((project["project_id"], kind), [])
            if packages:
                cells[kind].update(
                    task_constructed=True,
                    evidence="Constructed development packages are hash-checked; gate evidence is recorded per task, not inferred from software test success.",
                    constructed_tasks=[{"task_id": t["task_id"], "manifest": p.relative_to(workspace).as_posix(),
                                        "manifest_sha256": file_hash(p), "split": t["split"], "gates": t["gates"]} for p, t in packages],
                    missing_or_unverified=sorted({g for _, t in packages for g, value in t["gates"].items() if value["status"] != "passed"}),
                )
        rows.append({"paper_id": project["project_id"], "title": project["title"], "conference": "ICLR2025",
                     "recorded_decision": project["decision"], "conference_url": project["conference_url"],
                     "openreview_url": project["openreview_url"], "source_index_hash": file_hash(index),
                     "source_event_id": project["source_event_id"], "split": "development_candidate_unassigned",
                     "assets": assets, "reported_repository_licenses": licenses,
                     "redistribution_clearance": "not_established_by_repository_metadata", "runtime_verified": False,
                     "coverage": cells})
    return {"schema_version": "0.1", "audit_type": "candidate_inventory_with_explicit_constructed_task_evidence",
            "not_a_task_readiness_or_scientific_quality_audit": True, "source_index": index.relative_to(workspace).as_posix(),
            "source_index_sha256": file_hash(index), "candidate_count": len(rows),
            "constructed_task_count": sum(len(v) for v in constructed.values()), "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] / "materials/coverage.json")
    args = parser.parse_args()
    out = audit(args.workspace.resolve())
    write_json(args.output, out)
    print(f"Inventoried {out['candidate_count']} source-paper candidates; scientific readiness NOT certified.")
