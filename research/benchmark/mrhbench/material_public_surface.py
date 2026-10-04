"""Candidate public-surface inventory for independent quality review, not acceptance.

Mirrors the scientific fields projected by material_adapter; source locators,
private verification plans and private facts are deliberately not public fields.
Final compiled TaskViews still need their own release audit.
"""
from pathlib import Path
from .io import ProtocolError, contained, digest, file_hash, read_json


def public_surface(output_root):
    root = Path(output_root)
    package = read_json(root / "package.json")
    facts = {}
    for fact in package["facts"]:
        if fact["fact_id"] in facts:
            raise ProtocolError("Duplicate fact in public-surface inventory")
        facts[fact["fact_id"]] = fact
    records = {}

    def add(key, value):
        if key in records:
            raise ProtocolError("Duplicate public surface")
        records[key] = {"sha256": digest(value), "value": value}

    seen = set()
    for task in package["tasks"]:
        tid = task["task_id"]
        if tid in seen:
            raise ProtocolError("Duplicate task in public-surface inventory")
        seen.add(tid)
        prefix = "task:" + tid + ":"
        add(prefix + "identity", {"task_id": tid, "task_type": task["task_type"]})
        for field in ("input_contract", "output_contract"):
            add(prefix + field, task[field])
        public_paths = set()
        for asset in task["assets"]:
            if asset["visibility"] != "public":
                continue
            path = asset["path"]
            if path in public_paths:
                raise ProtocolError("Duplicate public asset")
            public_paths.add(path)
            target = contained(root, path, must_exist=True)
            actual = file_hash(target)
            if actual != asset["sha256"]:
                raise ProtocolError("Public asset hash mismatch")
            # Both the displayed filename and actual bytes are bound; binaries
            # remain review obligations rather than silently skipped text.
            add(prefix + "asset:" + path, {"path": path, "sha256": actual,
                                           "bytes": target.stat().st_size})
        for item in task["input_contract"].get("files", []):
            if item["path"] not in public_paths:
                raise ProtocolError("Input contract references non-public asset")
        seen_facts = set()
        for fid in task["input_fact_ids"]:
            if fid in seen_facts or fid not in facts:
                raise ProtocolError("Unknown/duplicate public fact")
            seen_facts.add(fid)
            fact = facts[fid]
            if task["task_type"] not in fact["allowed_stages"]:
                raise ProtocolError("Stage-ineligible public fact")
            add(prefix + "fact:" + fid, {k: fact[k] for k in ("fact_id", "statement", "kind")})
        add(prefix + "resource_overrides", task.get("resources", {}))
    add("environment:resources", package["environment"]["resources"])
    return {"schema_version": "material-public-surface-1",
            "package_sha256": file_hash(root / "package.json"), "records": records,
            "inventory": {k: v["sha256"] for k, v in records.items()},
            "scientific_acceptance": False,
            "scope": "Candidate scientific public surface; not final compiled release certification."}
