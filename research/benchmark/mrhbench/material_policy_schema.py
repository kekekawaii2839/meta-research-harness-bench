"""Derive admissible policy citations from actual policy, not a fixed A-I range.

Use only for a NEW execution version. This never edits past schemas or results.
Schema validity cannot establish that a cited rule supports the model's finding.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import re
import jsonschema
from .io import ProtocolError, digest, write_json


def rule_ids(policy_bytes):
    text = policy_bytes.decode("utf-8")
    sections = re.findall(r"^## ([A-Z])\.\s+", text, re.MULTILINE)
    numbered = re.findall(r"^([A-Z][1-9][0-9]*)\.\s+", text, re.MULTILINE)
    if not sections or not numbered or len(set(sections)) != len(sections) or len(set(numbered)) != len(numbered):
        raise ProtocolError("Policy needs unique explicit sections and numbered rules")
    if {r[0] for r in numbered} - set(sections):
        raise ProtocolError("Numbered rule has no declared policy section")
    # Sections such as H contain the adjudication rule in unnumbered prose.
    unnumbered = set(sections) - {r[0] for r in numbered}
    return sorted(set(numbered) | unnumbered)


def bind_policy_rules(base_schema, policy_bytes):
    """Replace every policy_rules item constraint with the actual defined IDs."""
    result = deepcopy(base_schema)
    ids = rule_ids(policy_bytes)
    locations = []

    def walk(node, path):
        if isinstance(node, dict):
            properties = node.get("properties", {})
            if "policy_rules" in properties:
                field = properties["policy_rules"]
                if field.get("type") != "array" or field.get("items", {}).get("type") != "string":
                    raise ProtocolError("Unsupported policy_rules schema shape")
                field["items"] = {"type": "string", "enum": ids}
                locations.append(path + "/properties/policy_rules/items")
            for k, v in node.items():
                walk(v, path + "/" + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + "/" + str(i))
    walk(result, "")
    if not locations:
        raise ProtocolError("No policy_rules citation field found")
    jsonschema.Draft202012Validator.check_schema(result)
    return result, {"schema_version": "material-policy-schema-binding-1",
        "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "base_schema_digest": digest(base_schema), "bound_schema_digest": digest(result),
        "permitted_citations": ids, "locations": locations,
        "semantic_citation_support_verified": False,
        "historical_results_relabelled": False}


def publish_bound_schema(base_schema, policy_path, destination):
    """Exclusive new schema+binding; requires a fresh destination directory."""
    destination = Path(destination)
    if destination.exists():
        raise ProtocolError("Policy schema publication requires a new destination")
    bound, receipt = bind_policy_rules(base_schema, Path(policy_path).read_bytes())
    destination.mkdir(parents=True)
    write_json(destination / "review_adjudication.schema.json", bound, exclusive=True)
    write_json(destination / "policy_schema_binding.json", receipt, exclusive=True)
    return receipt
