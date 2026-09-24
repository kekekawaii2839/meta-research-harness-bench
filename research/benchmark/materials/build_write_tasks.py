"""Extract author-reported table facts and build two distinct WRITE dev packages.

Requires beautifulsoup4 for source HTML extraction (not for protocol execution).
No author code, source paper prose, figure or fabricated run-level data is copied
into public inputs. Numeric facts retain exact table/row/column provenance.
"""
from __future__ import annotations

import re
import sys
from decimal import Decimal
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import file_hash, read_json, write_json
from mrhbench.materials import check_task
from mrhbench.rubrics import rubric

METHODS = ("Source", "TTT", "BN-Adapt", "FR", "RSD", "SSA (ours)", "Oracle")
SOURCE_URL = "https://arxiv.org/html/2410.03263v1#S4.T4"
PAPER_ID = "iclr2025-SXtl7NRyE5"


def extract_table(source: Path):
    soup = BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser")
    table = soup.find(id="S4.T4")
    if table is None:
        raise ValueError("Pinned source table missing")
    trs = table.select("tr")
    headers = [c.get_text(" ", strip=True) for c in trs[0].find_all(["td", "th"], recursive=False)][1:]
    if len(headers) != 14 or headers[-1] != "Mean":
        raise ValueError("Unexpected source table structure")
    rows, found = [], set()
    for tr in trs[1:]:
        cells = tr.find_all(["td", "th"], recursive=False)
        method = cells[0].get_text(" ", strip=True)
        if method not in METHODS:
            continue
        if method in found or len(cells) != 15:
            raise ValueError("Duplicate/malformed source row")
        found.add(method)
        for j, cell in enumerate(cells[1:]):
            math = cell.find("math")
            if math is None:
                raise ValueError("Expected numeric MathML cell")
            value = math["alttext"].replace("\\mathbf", "").replace("{", "").replace("}", "").strip()
            if not re.fullmatch(r"-?\d+\.\d{3}", value):
                raise ValueError("Unexpected cell syntax; do not guess numeric value")
            rows.append({"cell_id": f"t4-r{METHODS.index(method)+1:02d}-c{j+1:02d}", "method": method,
                         "condition": headers[j], "r2": float(value), "reported_decimal": value,
                         "kind": "author_reported_mean" if j == 13 else "author_reported_condition_value",
                         "source_locator": {"table": "S4.T4", "row": method, "column": headers[j]},
                         "replicate_values_available": False, "uncertainty_available_in_this_input": False})
    if found != set(METHODS):
        raise ValueError("Required method absent")
    return headers, rows


def build():
    source_root = ROOT.parent / "source_cache/benchmark_materials/first_snapshot"
    records = read_json(source_root / "manifest.json")["sources"]
    source_record = next(r for r in records if r["source_id"] == "ssa-paper-v1")
    source = source_root / source_record["file"]
    if file_hash(source) != source_record["sha256"]:
        raise ValueError("Pinned paper changed")
    headers, rows = extract_table(source)
    input_data = {
        "origin": "author_reported_table_not_maintainer_rerun", "source_url": SOURCE_URL,
        "paper_version": "arxiv-v1", "source_sha256": source_record["sha256"],
        "extraction": "MathML alttext numeric cells; 7 explicitly selected methods, all 13 conditions and reported means",
        "metric": {"name": "R2", "direction": "higher_is_better", "unit": "dimensionless", "negative_values_valid": True},
        "rows": rows,
    }
    # Original fact cards, not source prose or a reconstructed author trajectory.
    facts = {
        "scope": "Regression test-time adaptation; the numeric evidence supplied here concerns corrupted UTKFace age prediction only.",
        "method_facts": [
            {"id": "M1", "fact": "A source-trained feature extractor feeds a fixed linear regression head w.T z + b.", "source_locator": "S3.SS2"},
            {"id": "M2", "fact": "Source feature covariance supplies leading eigenvectors V and positive eigenvalues lambda; project centered features as V(z-mu_source).", "source_locator": "S3.SS2"},
            {"id": "M3", "fact": "Per-axis target batch means and variances are aligned to source moments (0, lambda) with a weighted symmetric Gaussian KL objective; alpha_d = 1 + abs(w.T v_d).", "source_locator": "S3.SS2"},
            {"id": "M4", "fact": "Source data are unavailable during target adaptation; source statistics were obtained beforehand. Target labels are not adaptation inputs.", "source_locator": "S3.SS1 and S3.SS2"},
            {"id": "M5", "fact": "Adaptation updates only the feature extractor's normalization affine scale and shift parameters (gamma, beta); other model parameters, including the regression head, remain fixed.", "source_locator": "S3.SS2 immediately after Eq.8"},
        ],
        "evaluation_facts": [
            {"id": "E1", "fact": "UTKFace target images use 13 corruption types at severity 5. Predict age; R2 is higher-better and may be negative.", "source_locator": "S4.SS1 and S4.T4"},
            {"id": "E2", "fact": "Source is the unadapted comparator. Oracle has target-label access and is not a same-information competitor.", "source_locator": "S4.SS2"},
            {"id": "E3", "fact": "The supplied cells are rounded author-reported aggregate values, not independent experimental repetitions.", "source_locator": "S4.T4; input construction boundary"},
        ],
        "unknown_or_excluded": ["Per-run observations and sampling uncertainty are not supplied.", "No supplied compute measurements, independent reproduction or test of causality.", "No full algorithm implementation or claim of licensed reuse of the author's proprietary repository.", "No other dataset table is included; do not import inconsistent summaries from elsewhere."],
        "bibliography": [{"citation_id": "source-study", "url": "https://arxiv.org/abs/2410.03263v1", "version": "v1", "usage": "Source of fixed facts, not prose to reproduce"}],
    }
    facts["unknown_or_excluded"] = [{"id": f"U{i+1}", "fact": value, "source_locator": "public input construction boundary, not a claim about all author assets"}
                                    for i, value in enumerate(facts["unknown_or_excluded"])]
    by_key = {(r["method"], r["condition"]): Decimal(r["reported_decimal"]) for r in rows}
    private = {
        "kind": "maintainer_derived_evaluation_checks_not_author_trajectory",
        "source_url": SOURCE_URL, "source_sha256": source_record["sha256"],
        "cell_count": len(rows), "method_count": 7, "condition_count": 13,
        "numeric_checks": {
            "ssa_reported_mean": str(by_key[("SSA (ours)", "Mean")]),
            "ssa_minus_source_mean": str(by_key[("SSA (ours)", "Mean")] - by_key[("Source", "Mean")]),
            "ssa_minus_rsd_mean": str(by_key[("SSA (ours)", "Mean")] - by_key[("RSD", "Mean")]),
            "ssa_minus_fr_pixelate": str(by_key[("SSA (ours)", "Pixelate")] - by_key[("FR", "Pixelate")]),
            "negative_cell_count": sum(r["r2"] < 0 for r in rows),
            "mean_rounding_residuals": {m: float(sum(by_key[(m, c)] for c in headers[:-1]) / Decimal(13) - by_key[(m, "Mean")]) for m in METHODS},
        },
        "scientific_cautions": [
            "SSA has the highest reported mean among the selected non-oracle methods, not every condition: FR is higher on Pixelate.",
            "Displayed equality at three decimals is not evidence of equal population performance.",
            "An absolute R2 difference is not a percentage improvement; averaging R2 values is not pooling predictions to recompute global R2.",
            "No significance, confidence interval, paired-run uncertainty, compute advantage or causal mechanism is established by this table.",
            "Oracle uses additional information; clearly distinguish it if shown. This is a selected comparison, not proof of global state of the art.",
        ],
        "input_grounding": "All diagnoses can be grounded in released facts/cells; scorer notes still remain private and are not forwarded verbatim.",
        "source_consistency_note": "Table1 and Table4 show different Source UTKFace summaries; this task deliberately uses ONLY Table4. No silent reconciliation or cross-table merge.",
    }
    for kind, folder, task_id in [("WRITE_CONTENT", "ssa_write_content", "dev-write-content-001"), ("WRITE_EVIDENCE", "ssa_write_evidence", "dev-write-evidence-001")]:
        package = ROOT / "materials" / folder
        write_json(package / "public/numeric_evidence.json", input_data)
        write_json(package / "public/research_facts.json", facts)
        evidence = {**private, "task_type": kind, "judge_status": "pending_actual_model_trajectory_acceptance"}
        write_json(package / "private/evaluation.json", evidence)
        if kind == "WRITE_CONTENT":
            prompt = "Write a coherent, technically faithful methods-and-findings passage (approximately 350–550 words) for the scoped study using only the supplied research facts and numeric evidence. Explain the fixed approach, its information boundaries, the supported comparison and limitations. Select an appropriate organization; do not discover new claims or invent missing details. Cite source fact/cell IDs through an accompanying claim-to-source map. No figure, whole-paper PDF or new experiment is required."
            outputs = {"required": ["research_passage", "claim_source_map"], "claim_source_map": "Associate central technical/numeric statements with fact IDs or cell IDs. Mark missing facts as unknown; no need to mimic source prose."}
        else:
            prompt = "Prepare a compact paper-ready evidence package for the supplied comparison: a table retaining all supplied methods/conditions and reported means, at least one informative figure with a caption, concise results text, and generation code. Choose the visual encoding. Preserve three-decimal source values in the table, retain meaningful negative values, and distinguish the oracle. Give a cell-linked data ledger for program checks; ledger consistency alone is not visual acceptance. No new experiments or fabricated uncertainty."
            outputs = {"required": ["table", "figure", "caption_and_results_text", "generation_code", "displayed_values.json"],
                       "displayed_values.json": "JSON list of {cell_id, value}; one entry for every supplied source cell. Represents table values, not fabricated raw runs. Derived display quantities must be separately labelled and traced to inputs.",
                       "rendering": "Provide a viewable PNG/JPEG rendering as well as editable or vector source as appropriate. No predetermined chart geometry."}
        assets = [{"asset_id": a, "path": path, "visibility": v, "sha256": file_hash(package / path)} for a, path, v in [
            ("numeric-evidence", "public/numeric_evidence.json", "public"), ("research-facts", "public/research_facts.json", "public"), ("evaluation", "private/evaluation.json", "private")]]
        task = {"schema_version": "0.1", "task_id": task_id, "task_type": kind, "paper_id": PAPER_ID, "split": "development",
                "public": {"task_id": task_id, "task_type": kind, "prompt": prompt, "inputs": ["numeric-evidence", "research-facts"], "output_contract": outputs,
                           "resources": {"gpu_allowed": False, "network": "disabled", "data_access": "fixed public assets only", "development_wall_time_seconds": 600, "budget_status": "candidate_development_cap_not_formal"},
                           "tools": ["model_client", "artifact_read_write", "cpu_python_execution"], "public_rubric": rubric(kind)},
                "private": {"evidence_asset_ids": ["evaluation"], "formal_eligible": False}, "assets": assets,
                "gates": {
                    "source_semantics": {"status": "passed", "evidence": "Root inspected fixed source table header/rows and method/setup passages; parser requires all 98 exact MathML cells. Task only claims author-reported evidence, not independent research verification."},
                    "rights": {"status": "pending", "evidence": "Public package contains transcribed numerical facts and original short fact cards only; no author source code/full paper/figure. Paper's arXiv nonexclusive license does not itself authorize broad redistribution. Public release review remains pending."},
                    "input_leakage": {"status": "pending", "evidence": "WRITE legitimately receives fixed findings; input excludes target prose/figure and private evaluation. Needs independent role/package audit."},
                    "runtime": {"status": "pending", "evidence": "Source extraction and numeric program checks available; no end-to-end generation/rendering runtime acceptance yet. No GPU needed."},
                    "judge_behavior": {"status": "pending", "evidence": "Distinct rules exist; actual trajectory inspection pending separately for each WRITE type."},
                }}
        check_task(task, package)
        write_json(package / "task.json", task)
        print(task_id, len(rows), "reported cells; formal gates pending")


if __name__ == "__main__":
    build()
