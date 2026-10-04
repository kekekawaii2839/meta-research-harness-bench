"""Bounded v3 paired trial: complete common quality policy, opt-in incremental edit.

No real calls at import/freeze, no retries or result normalization. Scientific
acceptance and CPU runtime remain independent gates, not schema inference.
"""
from pathlib import Path
import shutil
import time
import re
import jsonschema
from .material_policy_schema import bind_policy_rules, rule_ids
from .bounded_ledger import BoundedCallLedger
from .claude_transport import ClaudeNativeRunner
from .io import ProtocolError, read_json, write_json, file_hash, utc_now
from .material_batch import MATERIAL_PROMPT_SUFFIX, run_batch
from .material_quality_runner import QualityBoundRunner
from .factory_efficiency import identity, verify_files, case_inventory, adjudicate, cost_summary

OVERLAYS = {
    "material_efficiency_v1/repair.txt": "material_efficiency_v3/repair.txt",
    "material_efficiency_v1/review.txt": "material_efficiency_v3/review.txt",
    "factory_v4/policy.md": "material_efficiency_v3/policy.md",
    "factory_v4/adjudicator_review.txt": "material_efficiency_v3/adjudicator_review.txt",
}


def _verify_policy_schema(schema, policy_bytes):
    """Probe every defined ID, and reject an undefined ID at every citation field.

    This checks policy/schema compatibility only. F4 proposal consistency can
    be clear while runtime is pending; neither this probe nor sidecar is runtime.
    """
    ids = rule_ids(policy_bytes)
    checked = []
    def walk(node):
        if isinstance(node, dict):
            if "policy_rules" in node.get("properties", {}):
                item = node["properties"]["policy_rules"]["items"]
                for rule in ids:
                    jsonschema.validate(rule, item)
                invalid = "UNDEFINED_POLICY_RULE"
                try:
                    jsonschema.validate(invalid, item)
                except jsonschema.ValidationError:
                    pass
                else:
                    raise ProtocolError("Undefined policy rule accepted")
                if item.get("enum") != ids:
                    raise ProtocolError("Policy schema has nonexact rule inventory")
                checked.append(True)
            for value in node.values(): walk(value)
        elif isinstance(node, list):
            for value in node: walk(value)
    walk(schema)
    if not checked:
        raise ProtocolError("No policy citation field checked")


def _inventory(case):
    result = case_inventory(case)
    result["projection_record"] = identity(case["projection_record_path"])
    return result


def _validate_selection(cases, used):
    if cases.get("protocol_version") != 3:
        raise ProtocolError("Explicit v3 protocol required")
    if (cases.get("ledger_baseline"), cases.get("ledger_stop_at"), cases.get("pair_max_calls"),
        cases.get("model"), cases.get("effort")) != (608, 625, 12, "claude-opus-5-5", "medium"):
        raise ProtocolError("Selection differs from approved v3 protocol")
    if used != cases["ledger_baseline"]:
        raise ProtocolError("Actual ledger differs from selected baseline")
    if cases.get("prospective_max_calls") != 5:
        raise ProtocolError("C allowance must be five, without increasing original 625 cap")
    approval = read_json(Path(cases["approval_record_path"]))
    expected = {"protocol_version": 3, "ledger_baseline": 608, "ledger_stop_at": 625,
                "pair_max_calls": 12, "prospective_max_calls": 5, "authorized_to_freeze": True}
    if any(approval.get(k) != v for k, v in expected.items()):
        raise ProtocolError("Missing explicit matching v3 freeze authorization")
    verify_files(cases.get("frozen_inputs", []))
    rows = cases["cases"]
    if len(rows) != 2 or [c["order"] for c in rows] != [["old", "incremental"], ["incremental", "old"]]:
        raise ProtocolError("Two fixed counterbalanced cases required")
    ids = [c["case_id"] for c in rows]
    if len(set(ids)) != 2 or any(not re.fullmatch(r"[a-zA-Z0-9_-]+", x) for x in ids):
        raise ProtocolError("Unsafe or duplicate case id")
    for case in rows:
        if type(case.get("round_no")) is not int or case["round_no"] < 1:
            raise ProtocolError("Explicit positive round required")
        job = read_json(Path(case["job_path"]))
        if job["job_id"] != case["job_id"]:
            raise ProtocolError("Job identity differs from selection")
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", case["job_id"]):
            raise ProtocolError("Unsafe job id")
        verify_files(case["frozen_inputs"])
        _inventory(case)


def freeze(cases_path, benchmark, roles_path, ledger_path):
    benchmark, cases_path, roles_path, ledger_path = [Path(p).resolve() for p in (benchmark, cases_path, roles_path, ledger_path)]
    cases, ledger, roles = read_json(cases_path), read_json(ledger_path), read_json(roles_path)
    _validate_selection(cases, ledger["used_attempts"])
    if any(a["status"] == "reserved" for a in ledger["attempts"]):
        raise ProtocolError("Freeze requires no outstanding model reservations")
    if ledger["authorized_maximum"] < cases["ledger_stop_at"]:
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
    manifest = {"schema_version": "factory-efficiency-execution-2", "protocol_version": 3, "at": utc_now(),
        "benchmark": str(benchmark), "cases": identity(destination / "cases.json"),
        "original_cases": identity(cases_path), "approval_record": identity(cases["approval_record_path"]), "files": files, "overlays": overlays,
        "case_inventories": {c["case_id"]: _inventory(c) for c in cases["cases"]},
        "binary": identity(roles["claude_binary_default"]), "roles_path": str(roles_path),
        "policy_schema_binding": identity(binding_target), "ledger_path": str(ledger_path), "ledger_baseline_observed": ledger["used_attempts"],
        "timeout_seconds": 1800, "rounds": {c["case_id"]: c["round_no"] for c in cases["cases"]},
        "allowed_actions": ["pass", "pass_partial", "drop"], "automatic_retry": False,
        "execution_ready": True, "quality_policy": identity(destination / "snapshot/prompts/factory_v4/policy.md"),
        "comparison": "Both arms use complete v3 policy and independent scientific review. Incremental differs only by seeded output and navigation prompts. Overlay paths are compatibility adapters, not original v1/v4 bytes."}
    write_json(destination / "manifest.json", manifest, exclusive=True)
    return manifest


def verify_execution(root):
    root = Path(root).resolve()
    manifest = read_json(root / "execution/manifest.json")
    if manifest.get("schema_version") != "factory-efficiency-execution-2" or manifest.get("protocol_version") != 3:
        raise ProtocolError("Not a v3 execution")
    verify_files([manifest["cases"], manifest["original_cases"], manifest["binary"], manifest["quality_policy"]])
    verify_files(manifest["files"])
    verify_files([r["snapshot"] for r in manifest["files"]])
    for row in manifest["overlays"]:
        verify_files([row["source"], row["snapshot"]])
    verify_files([manifest["policy_schema_binding"], manifest["approval_record"]])
    policy = Path(manifest["quality_policy"]["path"]).read_bytes()
    schema = read_json(root / "execution/snapshot/prompts/factory_v4/review_adjudication.schema.json")
    _verify_policy_schema(schema, policy)
    binding = read_json(Path(manifest["policy_schema_binding"]["path"]))
    expected, receipt = bind_policy_rules(read_json(Path(manifest["benchmark"]) / "prompts/factory_v4/review_adjudication.schema.json"), policy)
    if schema != expected or binding != receipt:
        raise ProtocolError("Generated policy schema/binding differs from source")
    cases = read_json(Path(manifest["cases"]["path"]))
    if Path(cases["experiment_root"]).resolve() != root:
        raise ProtocolError("Experiment root changed")
    verify_files(cases.get("frozen_inputs", []))
    for case in cases["cases"]:
        verify_files(case["frozen_inputs"])
        if _inventory(case) != manifest["case_inventories"][case["case_id"]]:
            raise ProtocolError("Frozen transitive inputs or membership changed")
    return manifest, cases


def check_order(root, cases, case_id, arm):
    root = Path(root)
    sequence = [(c["case_id"], a) for c in cases["cases"] for a in c["order"]]
    if (case_id, arm) not in sequence:
        raise ProtocolError("Unknown case/arm")
    pos = sequence.index((case_id, arm))
    for cid, previous in sequence[:pos]:
        path = root / "arms" / cid / previous / "result.json"
        if not path.is_file() or read_json(path).get("status") != "completed":
            raise ProtocolError("Prior arm not completed; no automatic retry or continuation")
    if pos >= 2:
        first = cases["cases"][0]
        gate = read_json(root / "audits" / (first["case_id"] + ".json"))
        expected = {a: file_hash(root / "arms" / first["case_id"] / a / "result.json") for a in first["order"]}
        if (gate.get("case_id") != first["case_id"] or gate.get("allow_next_case") is not True
            or gate.get("quality_passed") is not True or gate.get("result_hashes") != expected
            or not gate.get("reviewer") or not gate.get("findings")
            or type(gate.get("review_seconds")) not in (int, float) or gate["review_seconds"] < 0
            or set(gate.get("runtime_evidence", {})) != set(first["order"])
            or not gate.get("independent_evidence")):
            raise ProtocolError("Second pair needs complete evidence-bound independent quality/runtime gate")
        verify_files(gate["independent_evidence"])
        verify_files(list(gate["runtime_evidence"].values()))
        for record in gate["runtime_evidence"].values():
            if read_json(Path(record["path"])).get("status") != "passed":
                raise ProtocolError("Runtime gate not passed")


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
                inner = runner_factory(role, ledger, arm_root)
            else:
                inner = ClaudeNativeRunner(binary=Path(manifest["binary"]["path"]), model=cases["model"],
                                      reasoning_effort=cases["effort"], ledger=ledger,
                                      audit_root=arm_root / "native_calls" / role,
                                      timeout_seconds=manifest["timeout_seconds"], tool_profile="material_workspace")
            return QualityBoundRunner(inner, policy_path=templates / "factory_v4/policy.md",
                project_id=read_json(Path(case["job_path"]))["paper_id"], round_no=case["round_no"])
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
