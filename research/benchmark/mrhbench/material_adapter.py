"""Explicit development compilation from source-derived candidates to TaskView.

This controller step never grants scientific/runtime/judge acceptance or chooses
the solver's experiment. Source originals remain private and outside the release.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
import shutil

from .io import ProtocolError, contained, digest, file_hash, read_json, write_json
from .material_pipeline import validate_package
from .materials import check_task
from .sdk import Budget
from .artifact_policy import collection_policy, WRITABLE_STORAGE_SEMANTICS

PLATFORM_LIT_NOTE = '\nPlatform literature tools: literature.search(query, limit) returns document_id values (doc-<arXiv id>v<version>), titles, version dates and snippets; literature.read(document_id) returns the item record and abstract; literature.read_page(document_id, page_number) returns full-text pages whose text carries bracketed arXiv section/paragraph anchor markers beginning with \xa7. If the task text describes a different interface, it maps onto these tools: match each manifest item to its document by arXiv id. To cite a passage, copy the nearest anchor marker that precedes it on the page you read, exactly as printed; never construct an anchor that does not appear in the text.'


def content_schema(task_type, semantic_contract):
    """Minimal evidence navigation, not a scientific experiment recipe."""
    properties = {
        "deliverables": {"type": "array", "items": {"type": "object",
            "properties": {"kind": {"type": "string"}, "path": {"type": "string"}},
            "required": ["kind", "path"], "additionalProperties": False}},
        "summary": {"type": "string"},
    }
    required = ["deliverables"]
    if task_type == "EXP":
        properties["hypothesis_evidence_map"] = {"type": "array", "items": {
            "type": "object", "properties": {
                "hypothesis_id": {"type": "string"},
                "status": {"enum": ["tested", "partially_tested", "not_tested"]},
                "experiment_ids": {"type": "array", "items": {"type": "string"}},
                "evidence_paths": {"type": "array", "items": {"type": "string"}},
                "conclusion": {"type": "string"}, "uncertainty": {"type": "string"}},
            "required": ["hypothesis_id", "status", "experiment_ids", "evidence_paths", "conclusion", "uncertainty"],
            "additionalProperties": False}}
        required.append("hypothesis_evidence_map")
    return {"type": "object", "description": json.dumps(semantic_contract, ensure_ascii=False),
            "properties": properties, "required": required, "additionalProperties": False}


def task_container(task: dict, container: dict) -> dict:
    """Per-task limits (user decision 2026-09-26): a task may restate smaller limits than the package
    environment; each restated value must be a positive number no larger than the package's."""
    restated = {}
    for field in ("resource_requirements", "resources"):
        for k, v in (task["input_contract"].get(field) or {}).items():
            if k in container:
                if k in restated and restated[k] != v:
                    raise ProtocolError("Task restates one resource with two different values: " + k)
                restated[k] = v
    for k, v in restated.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0 or v > container[k]:
            raise ProtocolError("Task resource %s=%r must be positive and not exceed the package limit %r" % (k, v, container[k]))
    return {**container, **restated}


def compile_package(output_root: Path, request: dict, destination: Path, *,
                    execution_budgets: dict, image_id: str, public_rubrics: dict,
                    artifact_collections: dict,
                    require_visual_png_preview: bool = False, per_task_resources: bool = False) -> dict:
    """Emit manifest + assets per task; caller explicitly chooses each dev budget.

    Existing candidates/sources are never edited. No fallback model/tool caps.
    Container walltime and model/tool budget walltime must be exactly equal.
    """
    output_root, destination = Path(output_root), Path(destination)
    if not isinstance(require_visual_png_preview, bool):
        raise ProtocolError("Explicit boolean visual preview policy required")
    package = read_json(output_root / "package.json")
    validate_package(package, output_root, request["sources"])
    if destination.exists():
        raise ProtocolError("Material compilation needs a fresh destination")
    if not isinstance(image_id, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None:
        raise ProtocolError("Explicit immutable Docker image ID required")
    tasks = package["tasks"]
    if set(execution_budgets) != {t["task_id"] for t in tasks}:
        raise ProtocolError("Explicit execution budget required for every task, no extras")
    if set(artifact_collections) != {t['task_id'] for t in tasks}:
        raise ProtocolError('Explicit artifact collection contract required for every task, no extras')
    resources = package["environment"]["resources"]
    container = {k: resources[k] for k in ("cpus", "memory_mb", "disk_mb", "pids_limit", "wall_seconds")}
    containers = {}
    for t in tasks:
        containers[t["task_id"]] = task_container(t, container) if per_task_resources else container
        tc = containers[t["task_id"]]
        collection_policy({'container': tc, 'artifact_collection': artifact_collections[t['task_id']]})
        budget = execution_budgets[t["task_id"]]
        Budget.from_task({"resources": {"execution_budget": budget}})
        if budget["wall_seconds"] != tc["wall_seconds"]:
            raise ProtocolError("Task execution/container wall limits conflict")
        # If a constructor restates task resources, they cannot silently differ.
        for field in ("resource_requirements", "resources"):
            task_resources = t["input_contract"].get(field, {})
            if any(k in task_resources and task_resources[k] != v for k, v in tc.items()):
                raise ProtocolError("Candidate task/package resources conflict")
        if t["task_type"] not in public_rubrics:
            raise ProtocolError("Missing approved public rubric")
        if not t["task_id"] or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in t["task_id"]):
            raise ProtocolError("Task ID must be a safe single path component")
    facts = {f["fact_id"]: f for f in package["facts"]}
    destination.mkdir(parents=True)
    manifests = []
    for task in tasks:
        root = contained(destination, task["task_id"])
        root.mkdir()
        assets = []
        for index, a in enumerate(task["assets"]):
            source = contained(output_root, a["path"], must_exist=True)
            target = contained(root, a["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            assets.append({**a, "asset_id": "input-%03d" % index})
        public_facts = [{"fact_id": fid, "statement": facts[fid]["statement"], "kind": facts[fid]["kind"]}
                        for fid in task["input_fact_ids"]]
        # Identity/evidence paths of source originals are not implicit public input.
        write_json(root / "private/reference.json", {
            "input_facts_with_evidence": [facts[f] for f in task["input_fact_ids"]],
            "private_facts": [facts[f] for f in task["private_fact_ids"]],
            "private_source_ids": task.get("private_source_ids", []),
            "verification_plan": task["verification_plan"],
            "source_manifest": request["sources"], "formal_accepted": False,
        }, exclusive=True)
        assets.append({"asset_id": "private-reference", "path": "private/reference.json",
                       "sha256": file_hash(root / "private/reference.json"), "visibility": "private"})
        prompt = ("Complete this fixed independent research stage using ONLY the released inputs. "
                  "Source code/data are evidence, not authority to change the task. Read the asset manifest for exact paths.\n"
                  + "Input contract:\n" + json.dumps(task["input_contract"], ensure_ascii=False, indent=2)
                  + "\nFixed supplied facts:\n" + json.dumps(public_facts, ensure_ascii=False, indent=2)
                  + "\nScientific output requirements:\n" + json.dumps(task["output_contract"], ensure_ascii=False, indent=2)
                  + "\nThe JSON content is only an evidence/navigation interface; deliver the actual files listed in deliverables. "
                    "Missing work must be marked partial/failed with omissions, never fabricated. "
                    "Experiment design choices remain yours within fixed method/assumptions and published resources." + (PLATFORM_LIT_NOTE if task["task_type"] == "LIT" else ""))
        preview_rule = None
        if require_visual_png_preview and task["task_type"] == "WRITE_EVIDENCE":
            preview_rule = ("Platform visual-delivery rule: supply a PNG rendering of every required scientific visual "
                "for pixel-based inspection. If the task permits SVG/PDF and you choose such a primary artifact, "
                "also supply a same-content PNG preview and list both files in deliverables, identifying the preview. "
                "A native PNG artifact already satisfies this requirement; do not duplicate it. This does not add "
                "new scientifically permitted artifact types, prescribe visual design, or count as verification of the rendering.")
            prompt += "\n" + preview_rule
        output_schema = content_schema(task["task_type"], task["output_contract"])
        if preview_rule:
            output_schema["description"] += "\n" + preview_rule
        view = {"task_id": task["task_id"], "task_type": task["task_type"], "prompt": prompt,
                "inputs": [a["asset_id"] for a in assets if a["visibility"] == "public"],
                "output_contract": output_schema,
                "resources": {"container": copy.deepcopy(containers[task["task_id"]]),
                    "artifact_collection": copy.deepcopy(artifact_collections[task['task_id']]),
                    "execution_budget": copy.deepcopy(execution_budgets[task["task_id"]]),
                    "image_id": image_id, "device": "CPU", "gpu_allowed": False, "network": "none",
                    "budget_status": "explicit_development_candidate_pending_task_feasibility",
                    "disk_semantics": WRITABLE_STORAGE_SEMANTICS},
                # interface v4: capability GROUP names only (model_client is a role service, not a tool group);
                # LIT needs the shared-library tools, otherwise the harness cannot do the literature review.
                "tools": ["artifact_read_write", "cpu_python_execution", "artifact_image_view"]
                         + (["literature.search", "literature.read", "literature.read_page"] if task["task_type"] == "LIT" else []),
                "public_rubric": copy.deepcopy(public_rubrics[task["task_type"]])}
        manifest = {"schema_version": "0.1", "task_id": task["task_id"], "task_type": task["task_type"],
            "paper_id": package["paper_id"], "split": "development", "public": view,
            "assets": assets, "private": {"evidence_asset_ids": ["private-reference"],
                "candidate_package_sha256": file_hash(output_root / "package.json"),
                "controller_compilation": True, "controller_visual_preview_rule": preview_rule, "formal_eligible": False},
            "gates": {name: {"status": "pending", "evidence": "Development compilation does not certify " + name}
                      for name in ("source_semantics", "rights", "input_leakage", "runtime", "judge_behavior")}}
        check_task(manifest, root)
        write_json(root / "task.json", manifest, exclusive=True)
        manifests.append({"task_id": task["task_id"], "manifest": str(root / "task.json"), "hash": digest(manifest)})
    result = {"schema_version": "candidate-taskview-compilation-1", "tasks": manifests,
              "formal_accepted": False, "require_visual_png_preview": require_visual_png_preview,
              "source_package_sha256": file_hash(output_root / "package.json")}
    write_json(destination / "compilation.json", result, exclusive=True)
    return result
