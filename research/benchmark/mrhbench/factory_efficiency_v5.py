"""Explicit fresh paired process comparison: baseline618, six calls, stop624.

New execution only. Frozen historical artifacts and budgets remain unchanged.
Each invocation runs one arm; no automatic retry or continuation after drop.
"""
from pathlib import Path
import shutil
import time
import re
import math
from .io import ProtocolError, read_json, write_json, file_hash, utc_now, contained
from .costs import CallLedger
from .bounded_ledger import BoundedCallLedger
from .claude_transport import ClaudeNativeRunner
from .material_batch import MATERIAL_PROMPT_SUFFIX, run_batch
from .material_quality_runner import QualityBoundRunner
from .material_identity_runner import IdentityBoundRunner
from .paged_navigation_runner import PagedNavigationRunner
from .material_decision_guidance import DecisionGuidanceRunner
from .evidence_read_batching import EvidenceReadBatchingRunner
from .material_policy_schema import bind_policy_rules
from .factory_efficiency import identity, verify_files, case_inventory, adjudicate, cost_summary
from .factory_efficiency_v4 import OVERLAYS, _verify_policy_schema, _inventory, validate_release_review


def _validate_selection(cases, used):
    expected = {"protocol_version": 5, "ledger_baseline": 618, "phase_max_calls": 6,
        "phase_stop_at": 624, "goal_stop_at": 700, "model": "claude-opus-5-5", "effort": "medium"}
    if any(cases.get(k) != v for k, v in expected.items()) or used != 618:
        raise ProtocolError("v5 requires exact approved 618→624 phase within goal700")
    verify_files([cases["goal_authorization"], cases["phase_authorization"]])
    goal = read_json(Path(cases["goal_authorization"]["path"]))
    phase = read_json(Path(cases["phase_authorization"]["path"]))
    if (goal.get("schema_version") != "goal-call-authorization-1"
        or goal.get("goal_absolute_stop_at") != 700 or not goal.get("user_answer")
        or goal.get("automatic_retry") is not False or goal.get("first_429_stops_batch") is not True):
        raise ProtocolError("Explicit unchanged goal700 authorization required")
    if len(cases.get("cases", [])) != 1:
        raise ProtocolError("Exactly one fresh pair required")
    case = cases["cases"][0]
    if (case.get("classification") != "fresh_validation" or case.get("round_no") != 2
        or case.get("order") != ["incremental", "old"]
        or not re.fullmatch(r"[a-zA-Z0-9_-]+", case.get("case_id", ""))
        or not re.fullmatch(r"[a-zA-Z0-9_.-]+", case.get("job_id", ""))):
        raise ProtocolError("Fresh round2 case and explicit incremental→old order required")
    job = read_json(Path(case["job_path"]))
    for source in job["sources"]:
        path = contained(Path(case["workspace"]), source["local_path"], must_exist=True)
        if file_hash(path) != source["sha256"]:
            raise ProtocolError("Declared job source hash does not match actual source")
    prior = read_json(Path(case["prior_batch"]) / case["job_id"] / "constructor/output/package.json")
    if job.get("requested_task_types") != ["WRITE_CONTENT"] or [t.get("task_type") for t in prior.get("tasks", [])] != ["WRITE_CONTENT"]:
        raise ProtocolError("This fresh phase is restricted to one WRITE_CONTENT task")
    wanted = {"protocol_version": 5, "authorized_to_freeze": True, "ledger_baseline": 618,
        "phase_stop_at": 624, "phase_max_calls": 6, "classification": "fresh_validation",
        "goal_authorization": cases["goal_authorization"], "case_id": case["case_id"],
        "job_id": case["job_id"], "order": case["order"]}
    if any(phase.get(k) != v for k, v in wanted.items()):
        raise ProtocolError("Exact new phase freeze authorization required")
    verify_files(cases.get("frozen_inputs", [])); verify_files(case["frozen_inputs"])
    _inventory(case)


def freeze(cases_path, benchmark, roles_path, ledger_path):
    benchmark, cases_path, roles_path, ledger_path = [Path(p).resolve() for p in (benchmark, cases_path, roles_path, ledger_path)]
    cases, ledger, roles = read_json(cases_path), CallLedger(ledger_path)._read(), read_json(roles_path)
    _validate_selection(cases, ledger["used_attempts"])
    if any(a["status"] == "reserved" for a in ledger["attempts"]):
        raise ProtocolError("Freeze requires no outstanding model reservations")
    if ledger["authorized_maximum"] < cases["phase_stop_at"]:
        raise ProtocolError("Global authorization insufficient")
    if any(roles[r][k] != cases[k] for r in ("constructor", "judge") for k in ("model", "effort")):
        raise ProtocolError("Role model/effort mismatch")
    root = Path(cases["experiment_root"]).resolve()
    for parent in (root, *root.parents):
        if any((parent / n).exists() for n in ("AGENTS.md", "CLAUDE.md")):
            raise ProtocolError("Experiment root inherits maintainer instructions")
    destination = root / "execution"
    destination.mkdir(parents=True, exist_ok=False)
    paths = set((benchmark / "mrhbench").rglob("*.py"))
    paths.update(p for p in (benchmark / "prompts").rglob("*") if p.is_file())
    paths.update((benchmark / "scripts/active").glob("*.py"))
    paths.add(roles_path)
    files = []
    for path in sorted(paths):
        target = destination / "snapshot" / path.relative_to(benchmark)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        files.append({**identity(path), "snapshot": identity(target)})
    overlays = []
    for target_rel, source_rel in OVERLAYS.items():
        source = benchmark / "prompts" / source_rel
        target = destination / "snapshot/prompts" / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        original = identity(target) if target.exists() else None
        shutil.copyfile(source, target)
        overlays.append({"source": identity(source), "original_snapshot": original, "snapshot": identity(target)})
        for row in files:
            if row["snapshot"]["path"] == str(target.resolve()):
                row["snapshot"] = identity(target)
                row["overlaid_from"] = source_rel
    # A generated schema is an explicit fresh overlay, never a historical edit.
    schema_source = benchmark / "prompts/factory_v4/review_adjudication.schema.json"
    policy_source = benchmark / "prompts/material_efficiency_v3/policy.md"
    schema, schema_binding = bind_policy_rules(read_json(schema_source), policy_source.read_bytes())
    _verify_policy_schema(schema, policy_source.read_bytes())
    schema_target = destination / "snapshot/prompts/factory_v4/review_adjudication.schema.json"
    original_schema = identity(schema_target)
    write_json(schema_target, schema)
    binding_target = destination / "policy_schema_binding.json"
    write_json(binding_target, schema_binding, exclusive=True)
    overlays.append({"source": identity(schema_source), "original_snapshot": original_schema,
        "snapshot": identity(schema_target), "generated_from_policy": identity(policy_source),
        "binding": identity(binding_target)})
    for row in files:
        if row["snapshot"]["path"] == str(schema_target.resolve()):
            row["snapshot"] = identity(schema_target)
            row["generated_policy_schema"] = True
    shutil.copyfile(cases_path, destination / "cases.json")
    manifest = {"schema_version": "factory-efficiency-v5-execution-1", "protocol_version": 5, "at": utc_now(),
        "benchmark": str(benchmark), "cases": identity(destination / "cases.json"),
        "original_cases": identity(cases_path), "goal_authorization": cases["goal_authorization"], "phase_authorization": cases["phase_authorization"], "files": files, "overlays": overlays,
        "case_inventories": {c["case_id"]: _inventory(c) for c in cases["cases"]},
        "binary": identity(roles["claude_binary_default"]), "roles_path": str(roles_path),
        "policy_schema_binding": identity(binding_target), "ledger_path": str(ledger_path), "ledger_baseline_observed": ledger["used_attempts"],
        "timeout_seconds": 1800, "rounds": {c["case_id"]: c["round_no"] for c in cases["cases"]},
        "allowed_actions": ["pass", "pass_partial", "drop"], "automatic_retry": False,
        "execution_ready": True, "quality_policy": identity(destination / "snapshot/prompts/factory_v4/policy.md"),
        "comparison": "Fresh process-bundle comparison. Both arms share unchanged v3 science policy, identity, paged navigation and decision guidance. Incremental additionally seeds prior output and receives read-batching advice. Not isolated constructor causality; original historical failures remain unchanged."}
    write_json(destination / "manifest.json", manifest, exclusive=True)
    return manifest


def verify_execution(root):
    root=Path(root).resolve()
    manifest=read_json(root/"execution/manifest.json")
    if manifest.get("schema_version")!="factory-efficiency-v5-execution-1":
        raise ProtocolError("Not a v5 execution")
    verify_files([manifest[k] for k in ("cases","original_cases","binary","quality_policy",
        "goal_authorization","phase_authorization","policy_schema_binding")])
    verify_files(manifest["files"]);verify_files([x["snapshot"] for x in manifest["files"]])
    for row in manifest["overlays"]:verify_files([row["source"],row["snapshot"]])
    cases=read_json(Path(manifest["cases"]["path"]))
    # Re-validate the approved frozen baseline, not today's evolving ledger count.
    _validate_selection(cases,618)
    if Path(cases["experiment_root"]).resolve()!=root:
        raise ProtocolError("v5 root changed")
    for case in cases["cases"]:
        if _inventory(case)!=manifest["case_inventories"][case["case_id"]]:
            raise ProtocolError("Frozen v5 input changed")
    policy=Path(manifest["quality_policy"]["path"]).read_bytes()
    schema=read_json(root/"execution/snapshot/prompts/factory_v4/review_adjudication.schema.json")
    expected,binding=bind_policy_rules(read_json(Path(manifest["benchmark"])/"prompts/factory_v4/review_adjudication.schema.json"),policy)
    if schema!=expected or read_json(Path(manifest["policy_schema_binding"]["path"]))!=binding:
        raise ProtocolError("Frozen policy/schema mismatch")
    return manifest,cases


def check_order(root, cases, case_id, arm):
    root = Path(root)
    case = cases["cases"][0]
    if case_id != case["case_id"] or arm not in case["order"]:
        raise ProtocolError("Unknown v5 case/arm")
    if arm == "incremental":
        return
    previous = root / "arms" / case_id / "incremental/result.json"
    result = read_json(previous)
    if (result.get("status") != "completed" or result.get("adjudication", {}).get("decision", {}).get("action") not in {"pass", "pass_partial"}):
        raise ProtocolError("Failed/drop first arm stops spending; no automatic continuation")
    output = result["adjudication"]["output"]
    verify_files([output])
    if read_json(Path(output["path"])) != result["adjudication"]["decision"]:
        raise ProtocolError("First adjudication changed")
    gate = read_json(root / "audits" / (case_id + ".incremental_gate.json"))
    seconds = gate.get("review_seconds")
    if (gate.get("schema_version") != "factory-efficiency-v5-arm-gate-1"
        or gate.get("case_id") != case_id or gate.get("arm") != "incremental"
        or gate.get("allow_next_arm") is not True or gate.get("quality_passed") is not True
        or gate.get("result") != identity(previous) or not gate.get("reviewer")
        or not gate.get("findings") or type(seconds) not in (int, float)
        or not math.isfinite(seconds) or seconds < 0):
        raise ProtocolError("Second arm requires bound independent quality/runtime/release gate")
    science_identity = gate["science_review"]
    verify_files([science_identity])
    science = read_json(Path(science_identity["path"]))
    package = previous.parent / "batch" / case["job_id"] / "constructor/output/package.json"
    if (science.get("schema_version") != "independent-material-science-review-1"
        or science.get("decision") != "pass" or science.get("case_id") != case_id
        or science.get("arm") != "incremental" or science.get("package") != identity(package)
        or science.get("arm_result") != identity(previous)
        or science.get("release_record") != gate["release_record"]
        or science.get("scope") != "full_candidate_and_necessary_original_sources"
        or science.get("independent_of_material_roles") is not True
        or not science.get("reviewer") or not science.get("findings")
        or science.get("blocking_findings") != [] or not science.get("evidence_bindings")):
        raise ProtocolError("Independent source-based science review must bind first candidate")
    verify_files(science["evidence_bindings"])
    job = read_json(Path(case["job_path"]))
    required = [identity(package)] + [identity(contained(Path(case["workspace"]), s["local_path"], must_exist=True)) for s in job["sources"]]
    if any(e not in science["evidence_bindings"] for e in required):
        raise ProtocolError("Science audit must bind package and original source inventory")
    validate_release_review(root, case, "incremental", gate["runtime_record"],
        gate["release_record"], gate["release_review"])


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
                                  stop_at=cases["phase_stop_at"],
                                  experiment_root=root, arm_root=arm_root, arm_maximum=3)
        # Fail before creating an arm when a previous call was uncertain/rate-limited.
        with ledger._locked():
            ledger._check_reservation(ledger._read(), str(arm_root / "native_calls"))
        arm_root.mkdir(parents=True, exist_ok=False)
        start = time.monotonic()
        row = {"case_id": case_id, "arm": arm, "started_at": utc_now(), "status": "started",
               "execution_manifest": identity(root / "execution/manifest.json"), "formal_accepted": False,
               "classification": case["classification"], "identity_map_sha256": case["identity_map"]["sha256"],
               "manual_review_seconds": None}
        write_json(arm_root / "started.json", row, exclusive=True)
        templates = root / "execution/snapshot/prompts"
        def runner(role):
            if runner_factory is not None:
                inner = runner_factory(role, ledger, arm_root)
            else:
                inner = ClaudeNativeRunner(binary=Path(manifest["binary"]["path"]), model=cases["model"],
                                      reasoning_effort=cases["effort"], ledger=ledger,
                                      audit_root=arm_root / "native_calls" / role,
                                      timeout_seconds=manifest["timeout_seconds"], tool_profile="material_workspace")
            if arm == "incremental":
                inner = EvidenceReadBatchingRunner(inner)
            inner = DecisionGuidanceRunner(inner)
            quality = QualityBoundRunner(inner, policy_path=templates / "factory_v4/policy.md",
                project_id=read_json(Path(case["job_path"]))["paper_id"], round_no=case["round_no"])
            return PagedNavigationRunner(IdentityBoundRunner(quality, map_identity=case["identity_map"]))
        try:
            job = read_json(Path(case["job_path"]))
            if job["job_id"] != case["job_id"]:
                raise ProtocolError("Frozen job identity mismatch")
            notes = read_json(Path(case["notes_path"]))
            if case.get("notes_key") is not None:
                notes = notes[case["notes_key"]]
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
