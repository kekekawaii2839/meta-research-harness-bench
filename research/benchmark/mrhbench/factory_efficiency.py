"""One-shot paired repair trials. No retries, model-driven scheduling, or P11.

Freezing is an integrity contract for this local controller, not OS isolation or
a signature. Role workspaces contain only the normal published material inputs.
"""
from pathlib import Path
import shutil
import time

import jsonschema

from .bounded_ledger import BoundedCallLedger
from .claude_transport import ClaudeNativeRunner
from .io import ProtocolError, contained, file_hash, read_json, utc_now, write_json
from .material_batch import MATERIAL_PROMPT_SUFFIX, _check_inputs, _input_snapshot, run_batch


def identity(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": file_hash(path), "bytes": path.stat().st_size}


def verify_files(rows):
    for row in rows:
        if identity(row["path"]) != {k: row[k] for k in ("path", "sha256", "bytes")}:
            raise ProtocolError("Frozen file changed: " + row["path"])


def case_inventory(case):
    """All transitive reads and prior-tree membership, including optional receipt."""
    job = read_json(Path(case["job_path"]))
    prior = Path(case["prior_batch"]) / case["job_id"]
    paths = {Path(case["job_path"]), Path(case["notes_path"])}
    paths.update(contained(Path(case["workspace"]), s["local_path"], must_exist=True) for s in job["sources"])
    paths.update(contained(Path(case["workspace"]), s["from"], must_exist=True) for s in job.get("prepopulated_output_files", []))
    paths.update(p for p in (prior / "constructor/output").rglob("*") if p.is_file())
    optional = [prior / "receipt.json", prior / "reviewer/review.json"]
    paths.update(p for p in optional if p.is_file())
    return {"files": [identity(p) for p in sorted(paths)],
            "absent_optional": [str(p.resolve()) for p in optional if not p.exists()]}


def freeze(cases_path, benchmark, roles_path, ledger_path):
    """Zero-call, exclusive execution freeze; existing case selection is immutable."""
    cases_path, benchmark, roles_path = map(lambda p: Path(p).resolve(), (cases_path, benchmark, roles_path))
    cases = read_json(cases_path)
    if (cases["ledger_baseline"], cases["ledger_stop_at"], cases["pair_max_calls"],
            cases["model"], cases["effort"]) != (593, 613, 12, "claude-opus-5-5", "medium"):
        raise ProtocolError("Experiment does not match approved bounded protocol")
    for case in cases["cases"]:
        verify_files(case["frozen_inputs"])
    factory_config = Path(cases["cases"][0]["workspace"]).parent.parent / "factory.json"
    historical_config = read_json(factory_config)
    for name, sha in historical_config["prompt_hashes"].items():
        if file_hash(benchmark / "prompts" / name) != sha:
            raise ProtocolError("Original v4 prompt changed: " + name)
    root = Path(cases["experiment_root"]).resolve()
    for parent in (root, *root.parents):
        if any((parent / n).exists() for n in ("AGENTS.md", "CLAUDE.md")):
            raise ProtocolError("Experiment root inherits maintainer instructions")
    roles = read_json(roles_path)
    if roles["constructor"]["model"] != cases["model"] or roles["constructor"]["effort"] != cases["effort"]:
        raise ProtocolError("Role model/effort mismatch")
    ledger = read_json(Path(ledger_path))
    if ledger["used_attempts"] != cases["ledger_baseline"] or any(a["status"] == "reserved" for a in ledger["attempts"]):
        raise ProtocolError("Freeze requires clean pre-trial ledger baseline")
    destination = root / "execution"
    destination.mkdir(parents=True, exist_ok=False)
    paths = set((benchmark / "mrhbench").rglob("*.py"))
    paths.update(p for p in (benchmark / "prompts").rglob("*") if p.is_file())
    paths.add(benchmark / "scripts/active/run_factory_efficiency.py")
    paths.add(roles_path)
    files = []
    for path in sorted(paths):
        rel = path.relative_to(benchmark)
        target = destination / "snapshot" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        files.append({**identity(path), "snapshot": identity(target)})
    shutil.copyfile(cases_path, destination / "cases.json")
    manifest = {"schema_version": "factory-efficiency-execution-1", "at": utc_now(),
                "benchmark": str(benchmark), "cases": identity(destination / "cases.json"),
                "original_cases": identity(cases_path), "files": files,
                "historical_factory_config": identity(factory_config),
                "case_inventories": {c["case_id"]: case_inventory(c) for c in cases["cases"]},
                "binary": identity(roles["claude_binary_default"]), "roles_path": str(roles_path),
                "ledger_path": str(Path(ledger_path).resolve()), "timeout_seconds": 1800,
                "rounds": {cases["cases"][0]["case_id"]: 3, cases["cases"][1]["case_id"]: 2},
                "allowed_actions": ["pass", "pass_partial", "drop"],
                "base_prompt_policy": "Both arms use unchanged material templates plus v4 constructor addendum; diffusion is a controlled new comparison, not a replay of historical prompt.",
                "execution_ready": True, "automatic_retry": False}
    write_json(destination / "manifest.json", manifest, exclusive=True)
    return manifest


def verify_execution(root):
    root = Path(root)
    manifest = read_json(root / "execution/manifest.json")
    verify_files([manifest["cases"], manifest["original_cases"], manifest["binary"], manifest["historical_factory_config"]])
    verify_files(manifest["files"])
    verify_files([r["snapshot"] for r in manifest["files"]])
    cases = read_json(Path(manifest["cases"]["path"]))
    if Path(cases["experiment_root"]).resolve() != root.resolve():
        raise ProtocolError("Experiment root changed")
    for case in cases["cases"]:
        verify_files(case["frozen_inputs"])
        if case_inventory(case) != manifest["case_inventories"][case["case_id"]]:
            raise ProtocolError("Transitive case input/membership changed")
    return manifest, cases


def check_order(root, cases, case_id, arm):
    sequence = [(c["case_id"], a) for c in cases["cases"] for a in c["order"]]
    if (case_id, arm) not in sequence:
        raise ProtocolError("Unknown case/arm")
    pos = sequence.index((case_id, arm))
    for prior_case, prior_arm in sequence[:pos]:
        result = Path(root) / "arms" / prior_case / prior_arm / "result.json"
        if not result.is_file() or read_json(result).get("status") != "completed":
            raise ProtocolError("Frozen order requires completed prior arm, no automatic recovery")
    if pos >= 2:
        first = cases["cases"][0]
        gate = read_json(Path(root) / "audits" / (first["case_id"] + ".json"))
        expected = {a: file_hash(Path(root) / "arms" / first["case_id"] / a / "result.json") for a in first["order"]}
        if (gate.get("case_id") != first["case_id"] or gate.get("allow_next_case") is not True
                or gate.get("result_hashes") != expected or not gate.get("reviewer")
                or not gate.get("findings") or not isinstance(gate.get("review_seconds"), (int, float))
                or isinstance(gate.get("review_seconds"), bool) or gate["review_seconds"] < 0):
            raise ProtocolError("Second case requires explicit evidence-bound local audit")


def validate_adjudication(out, *, project_id, round_no, allowed, review, package):
    if out["project_id"] != project_id or out["round"] != round_no or out["action"] not in allowed:
        raise ProtocolError("Adjudication identity/round/action invalid")
    indexed = [x["finding_index"] for x in out["finding_decisions"] if x["finding_index"] is not None]
    if sorted(indexed) != list(range(len(review.get("findings", [])))):
        raise ProtocolError("Every reviewer finding needs exactly one decision")
    excluded = out.get("excluded_task_ids") or []
    if out["action"] == "pass_partial":
        task_ids = {t["task_id"] for t in package["tasks"]}
        if not excluded or set(excluded) - task_ids or set(excluded) >= task_ids:
            raise ProtocolError("Invalid partial pass task exclusions")
    elif excluded:
        raise ProtocolError("Task exclusions require partial pass")
    if out["action"] == "repair" and not out["repair_notes"]:
        raise ProtocolError("Repair needs notes")


def adjudicate(review_dir, ws, templates, runner, project_id, round_no, allowed):
    ws.mkdir(parents=True, exist_ok=False)
    folders = ("sources", "output", "source_navigation")
    names = ("review.json", "structural_check.json", "request.json")
    for folder in folders:
        for source in sorted((review_dir / folder).rglob("*")):
            if source.is_file():
                rel = source.relative_to(review_dir).as_posix()
                target = contained(ws, rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(contained(review_dir, rel, must_exist=True), target)
    for name in names:
        shutil.copyfile(review_dir / name, ws / name)
    for name in ("policy.md", "review_adjudication.schema.json"):
        shutil.copyfile(templates / name, ws / name)
    write_json(ws / "round.json", {"round": round_no, "allowed_actions": allowed})
    protected = folders + names + ("policy.md", "review_adjudication.schema.json", "round.json")
    snapshot = _input_snapshot(ws, protected)
    result = runner.run(workspace=ws, prompt=(templates / "adjudicator_review.txt").read_text(encoding="utf8"), role="adjudicator")
    _check_inputs(ws, protected, snapshot, "Adjudicator")
    out = read_json(ws / "review_adjudication.json")
    jsonschema.validate(out, read_json(templates / "review_adjudication.schema.json"))
    validate_adjudication(out, project_id=project_id, round_no=round_no, allowed=allowed,
                          review=read_json(ws / "review.json"), package=read_json(ws / "output/package.json"))
    return {"call": result, "decision": out, "output": identity(ws / "review_adjudication.json"), "input_snapshot": snapshot}


def cost_summary(attempts):
    keys = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens")
    # Native Claude input_tokens excludes cache reads/writes; retain each component.
    totals = {k: sum(a["usage"][k] for a in attempts) if attempts and all(a.get("usage") is not None and k in a["usage"] for a in attempts) else None for k in keys}
    totals["total_input_tokens"] = sum(totals[k] for k in keys[:3]) if all(totals[k] is not None for k in keys[:3]) else None
    walls = [a.get("wall_seconds") for a in attempts]
    return {"calls": len(attempts), "call_ids": [a["id"] for a in attempts], "usage": totals,
            "model_session_seconds": sum(walls) if walls and all(x is not None for x in walls) else None,
            "failed_calls": sum(a["status"] != "completed" for a in attempts), "dollar_cost": None}


def run_arm(root, case_id, arm, *, runner_factory=None):
    """Run exactly one new arm; a failed/uncertain arm is never resumed."""
    root = Path(root).resolve()
    manifest, cases = verify_execution(root)
    lock = root / ".paired-controller.lock"
    with lock.open("x", encoding="utf8") as handle:
        handle.write(utc_now())
    try:
        check_order(root, cases, case_id, arm)
        case = next(c for c in cases["cases"] if c["case_id"] == case_id)
        arm_root = root / "arms" / case_id / arm
        if arm_root.exists():
            raise ProtocolError("Existing arm: no retry, inspect original evidence")
        ledger = BoundedCallLedger(Path(manifest["ledger_path"]), baseline=cases["ledger_baseline"],
                                  stop_at=cases["ledger_baseline"] + cases["pair_max_calls"],
                                  experiment_root=root, arm_root=arm_root, arm_maximum=3)
        # Fail before creating an arm when a previous call was uncertain/rate-limited.
        with ledger._locked():
            ledger._check_reservation(ledger._read(), str(arm_root / "native_calls"))
        arm_root.mkdir(parents=True, exist_ok=False)
        start = time.monotonic()
        row = {"case_id": case_id, "arm": arm, "started_at": utc_now(), "status": "started",
               "execution_manifest": identity(root / "execution/manifest.json"), "formal_accepted": False,
               "manual_review_seconds": None}
        write_json(arm_root / "started.json", row, exclusive=True)
        templates = root / "execution/snapshot/prompts"
        def runner(role):
            if runner_factory is not None:
                return runner_factory(role, ledger, arm_root)
            return ClaudeNativeRunner(binary=Path(manifest["binary"]["path"]), model=cases["model"],
                                      reasoning_effort=cases["effort"], ledger=ledger,
                                      audit_root=arm_root / "native_calls" / role,
                                      timeout_seconds=manifest["timeout_seconds"], tool_profile="material_workspace")
        try:
            job = read_json(Path(case["job_path"]))
            if job["job_id"] != case["job_id"]:
                raise ProtocolError("Frozen job identity mismatch")
            notes = read_json(Path(case["notes_path"]))[case["notes_key"]]
            batch = run_batch([job], workspace=Path(case["workspace"]), batch_root=arm_root / "batch",
                              templates=templates, constructor=runner("constructor"), reviewer=runner("material_reviewer"),
                              max_workers=1, max_jobs=1, repair_from=Path(case["prior_batch"]),
                              repair_notes={job["job_id"]: notes}, controller_hash_fill=True,
                              prompt_suffix=MATERIAL_PROMPT_SUFFIX + (templates / "factory_v4/constructor_addendum.txt").read_text(encoding="utf8"),
                              incremental_repair=arm == "incremental")
            row["batch"] = batch
            item = batch["jobs"][0]
            if item["status"] not in {"pass_with_pending_runtime", "revise", "reject"}:
                raise ProtocolError("Constructor/reviewer pipeline failed; no automatic retry")
            review_dir = arm_root / "batch" / job["job_id"] / "reviewer"
            row["adjudication"] = adjudicate(review_dir, arm_root / "adjudicator", templates / "factory_v4",
                                            runner("adjudicator"), job["paper_id"], manifest["rounds"][case_id], manifest["allowed_actions"])
            row["status"] = "completed"
        except Exception as exc:
            row.update(status="failed_needs_attribution", error={"type": type(exc).__name__, "message": str(exc)})
        finally:
            state = ledger._read()
            attempts = [a for a in state["attempts"][cases["ledger_baseline"]:]
                        if Path(a.get("artifact_directory", "")).resolve().is_relative_to(arm_root)]
            row.update(cost=cost_summary(attempts), finished_at=utc_now(), complete_pipeline_seconds=time.monotonic() - start,
                       ledger_used=state["used_attempts"], ledger_attempts=attempts)
            write_json(arm_root / "result.json", row, exclusive=True)
        return row
    finally:
        lock.unlink()
