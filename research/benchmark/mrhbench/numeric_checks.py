"""Trusted numeric checks, not a scientific or visual score.

Never executes submitted generation code. A matching ledger must still be checked
against actual table/figure renderings by the evidence judge and trusted runner.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .io import ProtocolError, digest


def _finite_decimal(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ProtocolError("Not a numeric value")
    try:
        d = Decimal(str(value))
    except InvalidOperation as exc:
        raise ProtocolError("Invalid numeric value") from exc
    if not d.is_finite():
        raise ProtocolError("Nonfinite numeric value")
    return d


def check_display_ledger(source: dict, submitted: object) -> dict:
    """Validate retained source cells at requested three-decimal table precision.

    Material problems raise; submission problems produce explicit check failures
    for the judge rather than being dropped or turned into infrastructure errors.
    """
    expected = {}
    for row in source["rows"]:
        if row["cell_id"] in expected:
            raise ProtocolError("Material has duplicate source cell IDs")
        value = _finite_decimal(row["reported_decimal"])
        if value != _finite_decimal(row["r2"]):
            raise ProtocolError("Material numeric serialization disagrees")
        expected[row["cell_id"]] = value
    findings = []
    if not isinstance(submitted, list):
        findings.append({"check_id": "ledger_format", "state": "fail", "detail": "Expected a list of displayed cell values"})
        submitted = []
    seen = set()
    for i, row in enumerate(submitted):
        label = f"submitted-row-{i}"
        if not isinstance(row, dict) or set(row) != {"cell_id", "value"} or not isinstance(row["cell_id"], str):
            findings.append({"check_id": label, "state": "fail", "detail": "Malformed ledger entry"})
            continue
        id = row["cell_id"]
        if id in seen:
            findings.append({"check_id": label, "state": "fail", "detail": "Duplicate displayed cell", "cell_id": id})
            continue
        seen.add(id)
        if id not in expected:
            findings.append({"check_id": label, "state": "fail", "detail": "Unknown source cell", "cell_id": id})
            continue
        try:
            value = _finite_decimal(row["value"])
            passed = abs(value - expected[id]) <= Decimal("0.0000005")
            detail = "Matches supplied three-decimal value" if passed else "Disagrees with supplied value"
        except ProtocolError:
            passed, detail = False, "Nonfinite or nonnumeric submitted value"
        findings.append({"check_id": label, "state": "pass" if passed else "fail", "cell_id": id, "detail": detail})
    for id in sorted(set(expected) - seen):
        findings.append({"check_id": "missing-" + id, "state": "fail", "cell_id": id, "detail": "Required source cell absent"})
    return {"kind": "trusted_program_numeric_check_not_final_grade", "source_digest": digest(source),
            "all_passed": all(x["state"] == "pass" for x in findings), "checks": findings,
            "not_verified": ["ledger_matches_rendered_table", "visual_truthfulness", "scientific_interpretation", "generation_code_reexecution", "error_bar_provenance"]}
