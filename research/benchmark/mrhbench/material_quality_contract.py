"""Evidence-bound, fail-closed *structural* contracts for material review.

The controller must inventory the entire solver-visible projection (including
facts, metadata, paths and notices), not merely changed files. Receipts attest
claimed review coverage; neither hashes nor this validator establish that the
model really read the evidence or that its scientific judgement is correct.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from pathlib import Path

import jsonschema

from .io import ProtocolError, digest, write_json


CHECKS = {
    "identity": "Review all public surfaces for target title, authors, repository, venue and distinctive method identity, including filenames and notices.",
    "author_scale": "Review author results, figure values and experiment-scale or recipe hints; apply the full current policy and task-specific exceptions, not keywords.",
    "target_implementation": "Review target implementations, trained target weights, target contribution disclosure and over-scaffolding under the task-specific policy.",
    "core_science": "Check method fidelity, assumptions, hypotheses, provenance and scientifically valid CPU scope against source evidence, not just the repair diff.",
    "io": "Check the complete task input/output contract and compatibility of published files and interfaces.",
    "resource": "Check declared resources, rationale, runtime evidence and any changes; absence of measured evidence is not a successful runtime validation.",
}
VERSION = "material-quality-contract-1"
WHOLE_SURFACE_CHECKS = frozenset(("identity", "author_scale", "target_implementation"))


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _inventory(value):
    if (not isinstance(value, dict) or not value
            or any(not isinstance(k, str) or not k.strip() or not _sha(v) for k, v in value.items())):
        raise ProtocolError("Public inventory must be a nonempty surface-id to SHA256 mapping")
    return dict(sorted(value.items()))


def build_contract(policy_path: Path, *, project_id: str, round_no: int,
                   public_inventory: dict, package_sha256: str,
                   role: str = "adjudicator") -> dict:
    """Bind exact policy bytes and controller-supplied full public projection."""
    if not isinstance(project_id, str) or not project_id.strip():
        raise ProtocolError("Exact nonempty original project_id required")
    if type(round_no) is not int or round_no < 1:
        raise ProtocolError("Round must be a positive integer, not a boolean")
    if role not in ("constructor", "material_reviewer", "adjudicator"):
        raise ProtocolError("Unknown quality-contract role")
    if not _sha(package_sha256):
        raise ProtocolError("Exact package SHA256 required")
    policy = Path(policy_path).read_bytes()
    if not policy.strip():
        raise ProtocolError("Empty policy cannot authorize review")
    policy.decode("utf-8")  # Preserve bytes/CRLF, but require readable published text.
    value = {
        "schema_version": VERSION, "project_id": project_id, "round": round_no,
        "role": role, "policy_sha256": hashlib.sha256(policy).hexdigest(),
        "policy_bytes": len(policy), "package_sha256": package_sha256,
        "public_inventory": _inventory(public_inventory), "checks": dict(CHECKS),
        "scope": "entire_current_public_projection_including_unchanged_surfaces",
        "assurance": "coverage_claims_only_not_scientific_acceptance",
    }
    return {**value, "contract_sha256": digest(value)}


def verify_contract(contract: dict, policy_path: Path, *, public_inventory: dict,
                    package_sha256: str) -> None:
    """Reject stale policy/package/public bytes and altered contract semantics."""
    try:
        expected = build_contract(policy_path, project_id=contract["project_id"],
                                  round_no=contract["round"], role=contract["role"],
                                  public_inventory=public_inventory,
                                  package_sha256=package_sha256)
    except (KeyError, TypeError) as exc:
        raise ProtocolError("Malformed quality contract") from exc
    if contract != expected:
        raise ProtocolError("Quality contract differs from current policy/package/public inventory")


def publish_contract(directory: Path, contract: dict, policy_path: Path) -> dict:
    """Publish policy bytes and compact JSON contract without overwriting files.

    Publication does not claim the caller's inventory is complete. The release
    builder must establish that separately before this function is called.
    """
    verify_contract(contract, policy_path, public_inventory=contract["public_inventory"],
                    package_sha256=contract["package_sha256"])
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    policy_out = directory / "quality_policy.md"
    contract_out = directory / "quality_contract.json"
    schema_out = directory / "quality_coverage.schema.json"
    if any(path.exists() for path in (policy_out, contract_out, schema_out)):
        raise ProtocolError("Quality publication is immutable; use a new role workspace")
    with policy_out.open("xb") as stream:
        stream.write(Path(policy_path).read_bytes())
    write_json(contract_out, contract, exclusive=True)
    write_json(schema_out, coverage_schema(contract), exclusive=True)
    return {"policy": str(policy_out), "contract": str(contract_out), "schema": str(schema_out)}


def coverage_schema(contract: dict) -> dict:
    """Exact role/current-package receipt; all six checks are always required."""
    surfaces = sorted(contract["public_inventory"])
    item = {
        "type": "object", "additionalProperties": False,
        "required": ["status", "scope", "evidence", "rationale"],
        "properties": {
            "status": {"enum": ["clear", "issue", "unknown", "not_applicable"]},
            "evidence": {"type": "array", "minItems": 1, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["surface_id", "locator", "observation"],
                "properties": {
                    "surface_id": {"enum": surfaces},
                    "locator": {"type": "string", "pattern": "\\S"},
                    "observation": {"type": "string", "pattern": "\\S"},
                },
            }},
            "rationale": {"type": "string", "pattern": "\\S"},
        },
    }
    check_properties = {key: deepcopy(item) for key in CHECKS}
    for key, check in check_properties.items():
        if key in WHOLE_SURFACE_CHECKS:
            check["properties"]["scope"] = {"const": "entire_bound_public_inventory"}
        else:
            check["properties"]["scope"] = {"const": "selected_surfaces"}
            check["properties"]["inspected_surface_ids"] = {
                "type": "array", "items": {"enum": surfaces}, "minItems": 1, "uniqueItems": True}
            check["required"].append("inspected_surface_ids")
    return {
        "type": "object", "additionalProperties": False,
        "required": ["contract_sha256", "policy_sha256", "checks"],
        "properties": {
            "contract_sha256": {"const": contract["contract_sha256"]},
            "policy_sha256": {"const": contract["policy_sha256"]},
            "checks": {"type": "object", "additionalProperties": False,
                       "required": list(CHECKS),
                       "properties": check_properties},
        },
    }


def bound_output_schema(base_schema: dict, contract: dict, *,
                        identity_field: str = "project_id") -> dict:
    """Bind exact identity and (when present) round without adding output fields.

    Reviewer schema can use paper_id and omit round. Coverage is a separately
    schema-bound sidecar so the existing role output format remains unchanged.
    """
    schema = deepcopy(base_schema)
    props = schema.get("properties", {})
    if (identity_field not in ("project_id", "paper_id") or schema.get("type") != "object"
            or identity_field not in props):
        raise ProtocolError("Base output schema must declare the requested identity field")
    props[identity_field] = {"allOf": [props[identity_field], {"const": contract["project_id"]}]}
    required = [identity_field]
    if "round" in props:
        props["round"] = {"allOf": [props["round"], {"const": contract["round"]}]}
        required.append("round")
    elif identity_field == "project_id":
        raise ProtocolError("Adjudicator output schema must declare round")
    schema["required"] = list(dict.fromkeys(schema.get("required", []) + required))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def validate_coverage(coverage: dict, contract: dict, *, action: str | None = None) -> dict:
    """Leakage checks cover every surface; other checks may assess subsets.

    An inapplicable check still cites evidence for inapplicability. This does not
    require a scientific or resource judgement on every unrelated file.
    """
    try:
        jsonschema.Draft202012Validator(coverage_schema(contract)).validate(coverage)
    except jsonschema.ValidationError as exc:
        raise ProtocolError("Quality coverage schema invalid: " + exc.message) from exc
    accounted = set()
    for name, check in coverage["checks"].items():
        inspected = (set(contract["public_inventory"]) if name in WHOLE_SURFACE_CHECKS
                     else set(check["inspected_surface_ids"]))
        if name in WHOLE_SURFACE_CHECKS and inspected != set(contract["public_inventory"]):
            raise ProtocolError("Whole-public-surface check is incomplete: " + name)
        if any(e["surface_id"] not in inspected for e in check["evidence"]):
            raise ProtocolError("Evidence refers to a surface not inspected for " + name)
        accounted.update(inspected)
    missing = set(contract["public_inventory"]) - accounted
    if missing:
        raise ProtocolError("Public surfaces missing from coverage: " + ", ".join(sorted(missing)))
    unresolved = [name for name, check in coverage["checks"].items()
                  if check["status"] in ("issue", "unknown")]
    if action in ("pass", "pass_partial", "pass_with_pending_runtime") and unresolved:
        raise ProtocolError("Cannot pass unresolved full-package checks: " + ", ".join(unresolved))
    return {"structural_contract_valid": True, "unresolved_checks": unresolved,
            "scientific_acceptance": "not_established_by_this_validator"}


def validate_output(output: dict, base_schema: dict, contract: dict, policy_path: Path,
                    *, coverage: dict, public_inventory: dict, package_sha256: str,
                    identity_field: str = "project_id", action: str | None = None) -> dict:
    """Validate receipt integrity; pass still requires independent semantic audit.

    Conservative v1 disallows pass_partial too if any full-package check is
    unknown/issue. Releasing an excluded subset needs its own freshly inventoried
    contract, not a pass that hides defects on an unreviewed projection.
    """
    verify_contract(contract, policy_path, public_inventory=public_inventory,
                    package_sha256=package_sha256)
    try:
        jsonschema.Draft202012Validator(bound_output_schema(
            base_schema, contract, identity_field=identity_field)).validate(output)
    except jsonschema.ValidationError as exc:
        raise ProtocolError("Quality output schema invalid: " + exc.message) from exc
    if "round" in output and type(output["round"]) is not int:
        raise ProtocolError("Output round must be an exact integer")
    decision_field = "decision" if identity_field == "paper_id" else "action"
    if decision_field not in output:
        raise ProtocolError("Missing role decision field: " + decision_field)
    decision = output[decision_field]
    if action is not None and action != decision:
        raise ProtocolError("Caller decision differs from authoritative role output")
    return validate_coverage(coverage, contract, action=decision)


def contract_prompt() -> str:
    return (
        "Read quality_policy.md IN FULL and quality_contract.json before reviewing. "
        "The current policy applies to the entire current public projection, including "
        "unchanged files, facts, metadata, filenames, interfaces and notices; prior review "
        "is evidence, never a waiver. Write quality_coverage.json using the sidecar schema; "
        "record all six checks with concrete "
        "locators and observations. A diff can prioritize source investigation, not skip "
        "these whole-package checks. Identity, author_scale and target_implementation "
        "must each cover all public surfaces, even unchanged ones. Core_science, io and "
        "resource may cover relevant subsets. For the three whole-surface checks use "
        "scope='entire_bound_public_inventory' (the contract hash binds the full inventory), "
        "without repeating IDs. For the other checks use scope='selected_surfaces' plus "
        "inspected_surface_ids. Every evidence surface_id must be in the bound inventory "
        "and in the selected subset when applicable. Explain and cite evidence for "
        "not_applicable; never falsely attest inspection of irrelevant files. "
        "Unknown evidence is unknown, not clear. Apply the "
        "full policy and task-specific exceptions semantically; do not substitute a keyword "
        "scan. Use the exact original project_id and integer round from the contract, "
        "never concatenate job_id or normalize identity. Coverage claims are auditable "
        "evidence, not automatic scientific acceptance."
    )
