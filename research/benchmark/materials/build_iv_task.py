"""Assemble the inspected source-backed EXP development package, not a formal split.

Source notebook and paper remain private immutable snapshots. The public package
contains no author result arrays, plots, target implementation or full paper.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import file_hash, read_json, write_json
from mrhbench.materials import check_task


def build():
    package = ROOT / "materials/iv_analysis"
    cache = ROOT.parent / "source_cache/benchmark_materials/iv_snapshot"
    manifest = read_json(cache / "manifest.json")
    records = {r["source_id"]: r for r in manifest["sources"]}
    for row in records.values():
        if row["status"] != "fetched" or file_hash(cache / row["file"]) != row["sha256"]:
            raise ValueError("Source snapshot missing or altered")
    (package / "public/LICENSE.source.txt").write_bytes((cache / "iv-license.source").read_bytes())
    evidence = {
        "kind": "maintainer_constructed_evaluation_evidence_not_author_trajectory",
        "source_paper": "iclr2025-QfhU3ZC2g1",
        "source_versions": [{"source_id": r["source_id"], "url": r["url"], "version": r["version"], "sha256": r["sha256"]} for r in records.values()],
        "scope": "Section 3.2 / Appendix C.2 numerical coupled-gradient analysis only; no Transformer training claim",
        "source_mapping": [
            {"public_item": "structural_model_and_generator", "source": "iv-simulation", "location": "cells[4].source: generate_data", "transformation": "Generator RNG instead of legacy RNG; same distribution, not identical samples"},
            {"public_item": "fixed_update_semantics", "source": "iv-simulation", "location": "cells[3].source and cells[4].source: beta update before Theta update", "cross_check": "iv-paper-v1 S3.SS2 equations 8a/8b both use t states"},
            {"public_item": "H1_and_H2", "source": "iv-paper-v1", "location": "S3.SS2 and A3.SS2", "transformation": "maintainer-scoped, empirically testable hypotheses; neither author-verbatim nor supplied outcomes"},
        ],
        "judgment_checks": [
            {"id": "method_old_states", "criterion": "Both updates use old states; beta-first imperative code is equivalent. Using new Theta changes method.", "publicly_groundable": True},
            {"id": "optimization_not_estimation", "criterion": "Convergence target is sample 2SLS. Distance to beta_true alone does not test H1.", "publicly_groundable": True},
            {"id": "conditions", "criterion": "Rank, actual step scaling and spectral diagnostic checked on actual data; no transplant of author numeric thresholds to new seeds.", "publicly_groundable": True},
            {"id": "rate_limits", "criterion": "Finite transient, nonmonotonicity, finite precision and repeated-rate polynomial factors may matter. Do not require exact equality to Lambda^t or assume every stable-looking trace establishes asymptotic big-O.", "publicly_groundable": True},
            {"id": "uncertainty", "criterion": "Evidence must distinguish one-dataset optimization behavior from repeated-sample generality. Paired comparisons or equivalently justified designs accepted; no mandatory author grid.", "publicly_groundable": True},
            {"id": "negative_evidence", "criterion": "Faithful informative counterexamples, failures or qualified negative findings can earn high quality. No need to match the author's conclusion.", "publicly_groundable": True},
            {"id": "scope", "criterion": "No extrapolation to trained Transformer efficacy or universal theorem from finite numerical outcomes.", "publicly_groundable": True},
        ],
        "source_cautions": [
            "Author notebook prints 'MSE' for Euclidean norm, and labels a norm-to-truth plot 'bias'. Judge the computed quantity, not those names; expected norm error is not statistical bias norm.",
            "Author cell 4 draws new data for different iteration counts. This is a source workflow, not a requirement to reproduce its unpaired design.",
            "No author reference numeric score or plotted curve is a unique gold answer.",
            "Scope does not establish a mathematically universal exponential-rate claim; adverse evidence must not be penalized for contradicting source rhetoric.",
        ],
        "runtime_evidence": "research/benchmark/audit/iv_starting_resources.json",
        "judge_acceptance": "pending_actual_trajectory_review",
    }
    write_json(package / "private/evaluation.json", evidence)
    asset_rows = []
    for id, name, visibility in [
        ("proposal", "public/proposal.txt", "public"),
        ("baseline", "public/baseline.py", "public"),
        ("source-license", "public/LICENSE.source.txt", "public"),
        ("evaluation", "private/evaluation.json", "private"),
    ]:
        asset_rows.append({"asset_id": id, "path": name, "visibility": visibility, "sha256": file_hash(package / name)})
    task_id = "dev-exp-001"
    rubric = {
        "test_validity": "Test both fixed hypotheses with informative experiments faithful to the supplied method.",
        "rigor": "Account for conditioning, transients, numerical limits, fair comparisons and uncertainty; report selection and deviations.",
        "execution_credibility": "Supply code, actual run/configuration records and reproducible numeric evidence.",
        "conclusion_credibility": "Match each conclusion to evidence and conditions, accepting negative or qualified findings without overclaiming.",
        "resource_reasonableness": "Obtain informative evidence within task resources; recorded separately from the equal-weight first-four science score.",
    }
    task = {
        "schema_version": "0.1", "task_id": task_id, "task_type": "EXP", "paper_id": "iclr2025-QfhU3ZC2g1", "split": "development",
        "public": {
            "task_id": task_id, "task_type": "EXP",
            "prompt": "Investigate the coupled estimator in the proposal, implementing the fixed method and testing both H1 and H2. Design, run and analyze your own informative CPU experiments. Submit evidence-linked conclusions, not a separate research report. Supplied infrastructure is a starting point, not a completed experimental plan.",
            "inputs": ["proposal", "baseline", "source-license"],
            "output_contract": {
                "required_artifacts": ["implementation", "experiment_configs", "run_outputs", "analysis_code", "hypothesis_evidence_map"],
                "hypothesis_evidence_map": "For H1 and H2: hypothesis_id, experiment_ids, artifact references, short conclusion, uncertainty, limitations and unperformed work. No standalone report required.",
                "trust": "Self-written logs are submission artifacts; platform tool records provide independent execution evidence.",
            },
            "resources": {"device": "CPU", "gpu_allowed": False, "python_dependencies": ["numpy"], "development_wall_time_seconds": 600, "budget_status": "candidate_development_cap_not_frozen_formal_budget", "network": "disabled", "allowed_data": "supplied generator and documented variations preserving the proposal model"},
            "tools": ["model_client", "artifact_read_write", "cpu_python_execution"],
            "public_rubric": {"scale": [0, 4], "dimensions": rubric},
        },
        "private": {"evidence_asset_ids": ["evaluation"], "formal_eligible": False, "source_disclosure_note": "MIT attribution names the author. EXP method is intentionally disclosed; metadata masking is not a contamination guarantee. LIT/IDEA must never receive this package."},
        "assets": asset_rows,
        "gates": {
            "source_semantics": {"status": "passed", "evidence": "Root directly inspected pinned notebook cells 3/4 and paper equations 8a/8b; source_mapping and explicit scoped hypotheses in private/evaluation.json. Not an independent scientific validation."},
            "rights": {"status": "passed", "evidence": "MIT source license preserved for adapted generator; original task prose and baseline, no author full paper/figures/results redistributed. This is an asset-level record, not legal advice."},
            "input_leakage": {"status": "pending", "evidence": "Public source whitelist omits target code, original plots/results and private cautions. Still requires independent input-package audit and fresh-agent access test."},
            "runtime": {"status": "pending", "evidence": "CPU baseline tested in audit/iv_starting_resources.json; full solver/resource-bound run and isolated runner not yet verified. GPU-dependent Transformer experiments deferred, not substituted."},
            "judge_behavior": {"status": "pending", "evidence": "No actual task-specific judge/solver trajectory acceptance yet."},
        },
    }
    check_task(task, package)
    write_json(package / "task.json", task)
    print("Constructed dev-exp-001; formal acceptance remains gated.")


if __name__ == "__main__":
    build()
