"""Predeclared aggregation. Never use prose quality or cost to compensate EXP quality."""
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from .io import ProtocolError, numeric

DIMENSIONS = {
    "LIT": ("factual_citation_accuracy", "evidence_coverage", "comparative_synthesis", "gap_grounding"),
    "IDEA": ("grounding_value", "substantive_difference", "specificity_coherence", "feasibility", "hypothesis_quality"),
    "EXP": ("test_validity", "rigor", "execution_credibility", "conclusion_credibility", "resource_reasonableness"),
    "WRITE_CONTENT": ("fidelity", "completeness", "comprehensibility", "traceability"),
    "WRITE_EVIDENCE": ("fidelity", "completeness", "comprehensibility", "traceability"),
}
TASK_TYPES = tuple(DIMENSIONS)


def validate_grade(task_type: str, result: dict) -> float:
    if task_type not in DIMENSIONS:
        raise ProtocolError("Unknown task type")
    if result.get("status") not in ("scored", "model_failed"):
        raise ProtocolError("Unresolved infrastructure/material/judge failures cannot silently enter aggregation")
    grades = result.get("dimension_scores", {})
    if set(grades) != set(DIMENSIONS[task_type]):
        raise ProtocolError("Dimension set does not match task type")
    for name, value in grades.items():
        numeric(value, name, 0, 4)
        if not float(value).is_integer():
            raise ProtocolError("Individual judge grades must be anchored integer levels 0–4")
    # Aggregation reads quality grades, not a judge-written overall score.
    primary = DIMENSIONS[task_type][:4] if task_type == "EXP" else DIMENSIONS[task_type]
    return mean(grades[k] for k in primary)


def aggregate(tasks: list[dict], results: list[dict], *, require_all_modules: bool = True) -> dict:
    expected = {t["task_id"]: t for t in tasks}
    if len(expected) != len(tasks):
        raise ProtocolError("Duplicate manifest task IDs")
    indexed = {r["task_id"]: r for r in results}
    if len(indexed) != len(results) or set(indexed) != set(expected):
        raise ProtocolError("Exactly one result for every frozen task is required; no dropping failed tasks")
    grouped = defaultdict(lambda: defaultdict(list))
    per_task = {}
    for task_id, task in expected.items():
        kind, paper = task["task_type"], task["paper_id"]
        result = indexed[task_id]
        if result.get("task_type") != kind or result.get("paper_id") != paper:
            raise ProtocolError("Result identity disagrees with manifest")
        q = validate_grade(kind, result)
        per_task[task_id] = q
        grouped[kind][paper].append(q)
    paper_scores = {kind: {paper: mean(values) for paper, values in papers.items()} for kind, papers in grouped.items()}
    type_scores = {kind: mean(papers.values()) for kind, papers in paper_scores.items()}
    modules = {k: type_scores[k] for k in ("LIT", "IDEA", "EXP") if k in type_scores}
    if all(k in type_scores for k in ("WRITE_CONTENT", "WRITE_EVIDENCE")):
        modules["WRITE"] = mean(type_scores[k] for k in ("WRITE_CONTENT", "WRITE_EVIDENCE"))
    complete = set(type_scores) == set(TASK_TYPES)
    if require_all_modules and not complete:
        raise ProtocolError("No full benchmark total without all four modules and both WRITE types")
    return {"task_scores": per_task, "paper_scores": paper_scores, "task_type_scores": type_scores,
            "module_scores": modules, "total_quality": mean(modules.values()) if complete else None,
            "scale": [0, 4], "complete_coverage": complete,
            "aggregation": "tasks-within-paper / papers-within-type / WRITE-types / four-modules-equal"}


def version_summary(checkpoints: list[dict], builder_selected: str) -> dict:
    if not checkpoints or len({x["version_id"] for x in checkpoints}) != len(checkpoints):
        raise ProtocolError("Nonempty unique checkpoint list required")
    ordered = sorted(checkpoints, key=lambda x: x["round"])
    if [x["round"] for x in ordered] != list(range(len(ordered))):
        raise ProtocolError("Expected contiguous H0..HR rounds")
    if any(x["version_id"] != f"H{x['round']}" for x in ordered):
        raise ProtocolError("Version identity does not match round")
    for x in ordered:
        numeric(x["test_total_quality"], "test score", 0, 4)
    by_id = {x["version_id"]: x for x in ordered}
    if builder_selected not in by_id:
        raise ProtocolError("Builder must select a submitted checkpoint")
    best = max(ordered, key=lambda x: (x["test_total_quality"], -x["round"]))
    return {"initial": ordered[0], "builder_selected": by_id[builder_selected], "test_best": best,
            "test_best_selection": "post_hoc_test_oracle_not_unbiased_generalization",
            "selection_tie_rule": "earliest_round", "curve": ordered}
