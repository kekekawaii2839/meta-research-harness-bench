"""Source-only native-agent material construction; candidates are never self-approved.

This module is orchestration/validation, not an agent loop or execution sandbox.
The controller supplies a native Codex caller. A fresh directory is required for
each constructor/reviewer invocation. No model calls occur during preparation.
"""
from __future__ import annotations

from pathlib import Path
import math
import shutil

from .io import ProtocolError, contained, digest, file_hash, read_json, write_json
from .source_evidence_index import build_evidence_index

TASK_TYPES = {"LIT", "IDEA", "EXP", "WRITE_CONTENT", "WRITE_EVIDENCE"}
FACT_KINDS = {"source_fact", "source_result", "maintainer_scope", "unknown"}


def validate_environment(env: dict, output_root: Path) -> dict:
    if env.get("gpu") is not False or env.get("network") != "none" or env.get("runtime_verified") is not False:
        raise ProtocolError("Generated CPU environment cannot self-certify runtime")
    if not env.get("scientific_rationale") or not isinstance(env.get("dependencies"), list):
        raise ProtocolError("Environment needs dependency list and scientific rationale")
    resources = env.get("resources", {})
    for key in ("cpus", "memory_mb", "disk_mb", "pids_limit", "wall_seconds"):
        value = resources.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ProtocolError("Invalid generated package resource " + key)
    dockerfile = contained(output_root, env.get("dockerfile", "environment/image/Dockerfile"), must_exist=True)
    smoke = contained(output_root, env.get("smoke_test", "environment/smoke.py"), must_exist=True)
    context = dockerfile.parent
    if smoke.is_relative_to(context):
        raise ProtocolError("Task smoke must be mounted separately, never baked into dependency image")
    files = [p for p in context.rglob("*") if p.is_file()]
    if {p.relative_to(context).as_posix() for p in files} - {"Dockerfile", "requirements.txt", ".dockerignore"}:
        raise ProtocolError("Image context must contain dependency definitions only")
    text = dockerfile.read_text(encoding="utf8")
    if any(line.strip().upper().startswith(("ADD ", "COPY .", "COPY /")) for line in text.splitlines()):
        raise ProtocolError("Unbounded image input instruction refused")
    return {"runtime_verified": False, "build_context": context.relative_to(output_root).as_posix(),
            "dockerfile_sha256": file_hash(dockerfile), "smoke_sha256": file_hash(smoke),
            "resource_status": "candidate_pending_actual_cpu_container_smoke",
            "security_notice": "Structural check is not Dockerfile code security audit"}


def validate_job(job: dict, workspace: Path) -> None:
    if job.get("schema_version") != "material-job-1" or not job.get("paper_id"):
        raise ProtocolError("Invalid material job identity")
    if not job.get("sources") or not job.get("requested_task_types"):
        raise ProtocolError("Job needs sources and requested task types")
    if not set(job["requested_task_types"]) <= TASK_TYPES:
        raise ProtocolError("Unknown requested task type")
    seen = set()
    for row in job["sources"]:
        if row["source_id"] in seen or not row.get("url") or not row.get("version"):
            raise ProtocolError("Source identity/version incomplete or duplicated")
        seen.add(row["source_id"])
        source = contained(workspace, row["local_path"], must_exist=True)
        if not source.is_file() or file_hash(source) != row["sha256"]:
            raise ProtocolError("Original source missing or changed")
    env = job["environment_candidate"]
    if env.get("gpu") is not False or env.get("network") != "none" or not env.get("scientific_rationale"):
        raise ProtocolError("Pilot environment must be CPU-only with justified resources")
    for key in ("cpus", "memory_mb", "disk_mb", "pids_limit", "wall_seconds"):
        value = env.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ProtocolError("Invalid per-package resource " + key)


def prepare_material_job(job: dict, workspace: Path, destination: Path, templates: Path) -> dict:
    """Publish a new maintainer construction job, not an executor TaskView."""
    validate_job(job, workspace)
    if destination.exists():
        raise ProtocolError("Construction requires fresh workspace")
    destination.mkdir(parents=True)
    published = []
    for i, row in enumerate(job["sources"]):
        src = contained(workspace, row["local_path"], must_exist=True)
        name = "sources/%03d-%s" % (i, src.name)
        target = contained(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        published.append({k: row[k] for k in ("source_id", "url", "version", "sha256", "role")})
        published[-1]["path"] = name
        if file_hash(target) != row["sha256"]:
            raise ProtocolError("Source changed during publication")
        if row["role"] == "paper_html":
            write_json(destination / ("source_navigation/%03d.json" % i),
                build_evidence_index(target.read_text(encoding="utf8"), row["source_id"], row["sha256"]), exclusive=True)
    prepopulated = []
    for row in job.get("prepopulated_output_files", []):
        # Controller-fetched binary/data files the file-tool-only constructor cannot copy itself (factory v3).
        src = contained(workspace, row["from"], must_exist=True)
        if not src.is_file() or file_hash(src) != row["sha256"]:
            raise ProtocolError("Prepopulated file missing or changed: " + row["from"])
        target = contained(destination, "output/" + row["to"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        prepopulated.append({"path": row["to"], "sha256": row["sha256"], "bytes": target.stat().st_size,
                             "provenance": row.get("provenance")})
    request = {"schema_version": "construction-request-1", "job_id": job["job_id"],
               "paper_id": job["paper_id"], "requested_task_types": job["requested_task_types"],
               "scope_request": job["scope_request"], "sources": published,
               "first_disclosure": job["first_disclosure"],
               "environment_candidate": job["environment_candidate"],
               "acceptance_status": "candidate_only_no_self_acceptance",
               **({"prepopulated_output_files": prepopulated} if prepopulated else {}),
               "output_path": "output/package.json"}
    write_json(destination / "request.json", request, exclusive=True)
    for name in ("material_constructor.txt", "material_package.schema.json"):
        shutil.copyfile(templates / name, destination / name)
    inventory = [{"path": p.relative_to(destination).as_posix(), "sha256": file_hash(p), "bytes": p.stat().st_size}
                 for p in sorted(destination.rglob("*")) if p.is_file()]
    manifest = {"job_id": job["job_id"], "request_hash": digest(request), "files": inventory,
                "published_bytes": sum(x["bytes"] for x in inventory), "model_invoked": False,
                "not_executor_release": True, "os_isolation_verified": False}
    write_json(destination / "publication.json", manifest, exclusive=True)
    return manifest


def validate_package(package: dict, output_root: Path, source_manifest: list[dict]) -> dict:
    """Deterministic gate only; cannot certify scientific fidelity or no leakage."""
    if package.get("schema_version") != "material-package-1" or package.get("status") != "candidate":
        raise ProtocolError("Generated package must remain a candidate")
    sources = {r["source_id"]: r for r in source_manifest}
    facts = {}
    for fact in package.get("facts", []):
        if not fact.get("fact_id") or fact["fact_id"] in facts or fact.get("kind") not in FACT_KINDS:
            raise ProtocolError("Invalid or duplicate fact identity/kind")
        if not fact.get("statement") or not isinstance(fact.get("allowed_stages"), list) or not set(fact["allowed_stages"]) <= TASK_TYPES:
            raise ProtocolError("Fact missing content or stage applicability")
        refs = fact.get("evidence", [])
        if fact["kind"] in {"source_fact", "source_result"} and not refs:
            raise ProtocolError("Source claim requires original evidence")
        for ref in refs:
            if ref.get("source_id") not in sources or not ref.get("locator"):
                raise ProtocolError("Unknown source or empty locator")
            if ref.get("source_sha256") != sources[ref["source_id"]]["sha256"]:
                raise ProtocolError("Evidence source hash differs from original")
        facts[fact["fact_id"]] = fact
    coverage = package.get("coverage", [])
    if {r.get("task_type") for r in coverage} != TASK_TYPES or len(coverage) != len(TASK_TYPES):
        raise ProtocolError("Explicit five-type coverage matrix required")
    for row in coverage:
        if row.get("status") not in {"candidate", "unsupported", "deferred"} or not row.get("reason"):
            raise ProtocolError("Coverage cannot self-certify acceptance")
    task_ids = set()
    for task in package.get("tasks", []):
        if task.get("task_type") not in TASK_TYPES or task.get("task_id") in task_ids or not task.get("task_id"):
            raise ProtocolError("Invalid task identity/type")
        task_ids.add(task["task_id"])
        if task.get("paper_id") != package.get("paper_id") or task.get("split") != "development":
            raise ProtocolError("Paper grouping/development boundary violated")
        for key in ("input_fact_ids", "private_fact_ids"):
            if any(f not in facts for f in task.get(key, [])):
                raise ProtocolError("Task references unknown fact")
        for fact_id in task.get("input_fact_ids", []):
            if task["task_type"] not in facts[fact_id]["allowed_stages"]:
                raise ProtocolError("Stage-ineligible fact in public input")
            if task["task_type"] in {"LIT", "IDEA"} and facts[fact_id].get("discloses_target_contribution") is not False:
                raise ProtocolError("Target contribution/unknown disclosure in discovery input")
        asset_paths = {}
        for asset in task.get("assets", []):
            if asset.get("visibility") not in {"public", "private"}:
                raise ProtocolError("Explicit asset visibility required")
            if asset.get("path", "").startswith(("output/", "sources/")):
                raise ProtocolError("Asset paths are relative to output/: use assets/..., not output/... or original sources/...")
            if asset["path"] in asset_paths:
                raise ProtocolError("Duplicate task asset path")
            p = contained(output_root, asset["path"], must_exist=True)
            if not p.is_file() or file_hash(p) != asset["sha256"]:
                raise ProtocolError("Generated asset missing/changed")
            asset_paths[asset["path"]] = asset
        for source_id in task.get("private_source_ids", []):
            if source_id not in sources:
                raise ProtocolError("Private reference uses unknown original source ID")
        if not task.get("input_contract") or not task.get("output_contract") or not task.get("verification_plan"):
            raise ProtocolError("Task needs input/output/verifier contracts")
        for file in task["input_contract"].get("files", []):
            if not isinstance(file, dict) or file.get("path") not in asset_paths:
                raise ProtocolError("Input files must reference manifest assets relative to output/")
            asset = asset_paths[file["path"]]
            if file.get("sha256") != asset["sha256"] or asset["visibility"] != "public" or file.get("visibility") != "public":
                raise ProtocolError("Input file contract differs from public asset manifest")
    if not task_ids or not facts:
        raise ProtocolError("Empty package cannot enter pilot review")
    environment = validate_environment(package.get("environment", {}), output_root)
    return {"structural_gate": "passed", "scientific_gate": "pending_independent_review", "environment": environment,
            "fact_count": len(facts), "task_count": len(task_ids), "formal_accepted": False}


def prepare_review(construction: Path, destination: Path, templates: Path) -> dict:
    """New context with raw sources + artifacts, never constructor reasoning/chat."""
    request = read_json(construction / "request.json")
    for source in request["sources"]:
        p = contained(construction, source["path"], must_exist=True)
        if file_hash(p) != source["sha256"]:
            raise ProtocolError("Constructor altered original source; review cannot use it")
    package = read_json(construction / "output/package.json")
    result = validate_package(package, construction / "output", request["sources"])
    if destination.exists():
        raise ProtocolError("Reviewer requires fresh workspace")
    destination.mkdir(parents=True)
    for folder in ("sources", "output", "source_navigation"):
        # All files checked through contained: links/reparse points are refused.
        for p in sorted((construction / folder).rglob("*")):
            if p.is_file():
                rel = p.relative_to(construction).as_posix()
                checked = contained(construction, rel, must_exist=True)
                target = contained(destination, rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(checked, target)
    shutil.copyfile(construction / "request.json", destination / "request.json")
    shutil.copyfile(templates / "material_reviewer.txt", destination / "material_reviewer.txt")
    write_json(destination / "structural_check.json", result, exclusive=True)
    return result


def stage_repair_candidate(prior_job: Path, destination: Path, *, adjudicated_notes=None) -> dict:
    """One explicit repair, copying only prior candidate artifacts, not its chat.

    Caller has already staged original sources and the NEW prompt/schema into
    destination. No prior file is edited or treated as ground truth.
    """
    old = prior_job / "constructor/output"
    if not old.is_dir() or destination.resolve().is_relative_to(prior_job.resolve()):
        raise ProtocolError("Repair requires prior candidate and separate new workspace")
    rows = []
    for p in sorted(old.rglob("*")):
        if p.is_file():
            rel = p.relative_to(old).as_posix()
            checked = contained(old, rel, must_exist=True)
            target = contained(destination, "previous_candidate/" + rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(checked, target)
            rows.append({"path": "previous_candidate/" + rel, "sha256": file_hash(target), "bytes": target.stat().st_size})
    if not rows:
        raise ProtocolError("No prior generated artifacts available for explicit repair")
    receipt_path = prior_job / "receipt.json"
    receipt = read_json(receipt_path) if receipt_path.exists() else {}
    notes = {"schema_version": "material-repair-1", "mode": "one_explicit_repair_no_automatic_loop",
             "prior_status": receipt.get("status", "unknown_or_interrupted"), "prior_error": receipt.get("error"),
             "candidate_files": rows, "source_of_truth": "request.json and immutable original sources, not previous_candidate",
             "instructions": [
                 "Read NEW material_constructor.txt and material_package.schema.json; old candidate is untrusted, not accepted.",
                 "Produce a complete NEW output/; never edit previous_candidate/ or sources/.",
                 "All task asset paths relative to output/ (assets/...), not output/assets/...; original sources are private_source_ids, not assets.",
                 "allowed_stages=[] is legitimate private-only; never put those facts in public input_fact_ids.",
                 "Preserve source numerical semantics, update hashes after any repair, retain required source license notices.",
                 "Public EXP specification must be self-contained: equations, fixed states, positive/constant steps if source requires, rank/shape assumptions, truth evaluation-only where applicable.",
                 "Hypotheses must preserve scoped research meaning, not tautological instability or invented unlabelled claims; mark maintainer choices and source evidence.",
                 "WRITE_EVIDENCE must require a renderable scientific visual artifact with caption, generation code, source-linked numeric manifest and concise interpretation, not merely Markdown-table transcription. Authentic extra methods/cells are allowed; never force the older subset.",
                 "WRITE_CONTENT must supply enough accurate method facts/equations for its requested scope (including weighting/alignment mechanism when essential), or narrow that scope explicitly. Do not require long self-contained/reproducible methodology from four brief fact cards or make the solver invent missing details.",
                 "Place Dockerfile inside NEW output/environment/image/ and smoke at output/environment/smoke.py; do not retain environment/ outside output/.",
                 "Smoke must exercise actual public starting resources/data as well as dependencies, never the target algorithm; do not pull Docker.",
                 "Full benchmark runtime integration/model-call budgets remain pending; a valid material package is not an accepted runnable benchmark."
             ]}
    if adjudicated_notes is not None:
        if not isinstance(adjudicated_notes, list) or any(not isinstance(x, str) or not x.strip() for x in adjudicated_notes):
            raise ProtocolError("Adjudicated repair notes must be nonempty text items")
        notes["maintainer_adjudicated_notes"] = adjudicated_notes
        notes["instructions"].append("Apply maintainer_adjudicated_notes, verifying every scientific change against original sources; these notes are not a source of scientific truth.")
    write_json(destination / "repair_request.json", notes, exclusive=True)
    return notes


def pilot_coverage(packages: list[dict]) -> list[dict]:
    return [{"paper_id": p["paper_id"], "task_type": row["task_type"], "status": row["status"], "reason": row["reason"]}
            for p in packages for row in p["coverage"]]
