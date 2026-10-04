"""Conditionally run the preselected GETS unit, at most eight native sessions.

New controller only: existing paired-trial execution freeze is not modified.
No automatic retry, continuation, replacement paper/unit, or benchmark pilot.
"""
import json
import shutil
import time
from pathlib import Path
import jsonschema

from .bounded_ledger import BoundedCallLedger
from .claude_transport import ClaudeNativeRunner
from .efficiency_metrics import summarize_calls
from .factory import CallBudget, Factory, UNIT_ORDER
from .factory_efficiency import identity, validate_adjudication, verify_execution, verify_files
from .io import ProtocolError, contained, file_hash, read_json, utc_now, write_json
from .material_batch import MATERIAL_PROMPT_SUFFIX, run_batch

IDENTITY_CONTRACT = ("Controller identity contract: output project_id must exactly equal {value}, taken from {source}. "
                     "Do not concatenate job_id, task/unit identifiers, paths, or any suffix. "
                     "This is an output-schema identity requirement, not a scientific judgement.\n")


def tree(root):
    return [identity(contained(root, p.relative_to(root).as_posix(), must_exist=True))
            for p in sorted(root.rglob("*")) if p.is_file()]


def known_identity_failure(root, case, arm, row):
    """Diagnostic exception only. Never modify/relabel the failed paired result."""
    if (row.get("status") != "failed_needs_attribution" or row.get("error") != {
            "type": "ProtocolError", "message": "Adjudication identity/round/action invalid"}):
        raise ProtocolError("Only the known combined-id adjudication failure can be gated")
    base = read_json(root / "execution/manifest.json")
    arm_root = root / "arms" / case["case_id"] / arm
    ledger = read_json(Path(base["ledger_path"]))
    attempts = [a for a in ledger["attempts"] if Path(a.get("artifact_directory", "")).resolve().is_relative_to(arm_root.resolve())]
    if (len(attempts) != 3 or attempts != row.get("ledger_attempts")
            or [a.get("role") for a in attempts] != ["constructor", "material_reviewer", "adjudicator"]
            or any(a.get("status") != "completed" or a.get("metadata", {}).get("failure_class") for a in attempts)):
        raise ProtocolError("Identity exception requires exactly three completed authoritative transport attempts")
    ws = arm_root / "adjudicator"
    request, job = read_json(ws / "request.json"), read_json(Path(case["job_path"]))
    if request.get("paper_id") != job["paper_id"] or request.get("job_id") != job["job_id"]:
        raise ProtocolError("Identity diagnostic request differs from frozen job")
    combined = job["paper_id"] + "/" + job["job_id"]
    out = read_json(ws / "review_adjudication.json")
    if out.get("project_id") != combined:
        raise ProtocolError("Not the original combined paper_id/job_id error")
    jsonschema.validate(out, read_json(root / "execution/snapshot/prompts/factory_v4/review_adjudication.schema.json"))
    validate_adjudication(out, project_id=combined, round_no=base["rounds"][case["case_id"]],
                          allowed=base["allowed_actions"], review=read_json(ws / "review.json"),
                          package=read_json(ws / "output/package.json"))
    return [identity(ws / name) for name in ("request.json", "review_adjudication.json", "review.json", "output/package.json")]


def check_gates(root, cases):
    identities = []
    for case in cases["cases"]:
        path = root / "audits" / (case["case_id"] + ".json")
        gate = read_json(path)
        exceptions = gate.get("allow_known_identity_failure_arms", [])
        if not isinstance(exceptions, list) or len(set(exceptions)) != len(exceptions) or set(exceptions) - set(case["order"]):
            raise ProtocolError("Invalid explicitly allowed identity-failure arms")
        hashes = {}
        for arm in case["order"]:
            result = root / "arms" / case["case_id"] / arm / "result.json"
            row = read_json(result)
            if row.get("status") != "completed":
                if arm not in exceptions:
                    raise ProtocolError("Prospective phase requires completed pairs or explicit known-identity diagnostic gate")
                identities.extend(known_identity_failure(root, case, arm, row))
            elif arm in exceptions:
                raise ProtocolError("Identity exception cannot relabel a completed arm")
            hashes[arm] = file_hash(result)
        if (gate.get("case_id") != case["case_id"] or gate.get("allow_prospective") is not True
                or gate.get("result_hashes") != hashes or not gate.get("reviewer")
                or not gate.get("findings") or type(gate.get("review_seconds")) not in (int, float)
                or gate["review_seconds"] < 0):
            raise ProtocolError("Missing evidence-bound prospective quality/cost permission")
        identities.append(identity(path))
    return identities


class ProspectiveFactory(Factory):
    def runner(self, role):
        inner = super().runner(role)
        class IdentityBound:
            def run(self, **kwargs):
                if role == "adjudicator":
                    ws = Path(kwargs["workspace"])
                    if (ws / "request.json").is_file():
                        source, field = "request.json", "paper_id"
                    else:
                        source, field = "candidate.json", "project_id"
                    expected = read_json(ws / source)[field]
                    kwargs["prompt"] += "\n" + IDENTITY_CONTRACT.format(value=json.dumps(expected), source=source + " " + field)
                return inner.run(**kwargs)
        return IdentityBound()

    def max_repair_rounds(self, state):
        return 1

    def _batch(self, state, batch_root, repair_from=None, repair_notes=None, job_name="job.json"):
        if batch_root.exists():
            raise ProtocolError("Prospective batch is one-shot; no continuation/retry")
        job = self.build_job(state)
        write_json(self.wdir(state) / job_name, job, exclusive=True)
        self.check_prompts()
        self.budget.take(2)
        result = run_batch([job], workspace=self.paper_dir(state["project_id"]), batch_root=batch_root,
                           templates=self.templates, constructor=self.runner("constructor"), reviewer=self.runner("material_reviewer"),
                           max_workers=1, max_jobs=1, controller_hash_fill=True,
                           prompt_suffix=MATERIAL_PROMPT_SUFFIX + (self.factory_templates / "constructor_addendum.txt").read_text(encoding="utf8"),
                           repair_from=repair_from, repair_notes=repair_notes, incremental_repair=repair_from is not None)
        return job, result["jobs"][0]


def freeze_prospective(root):
    """Zero calls/fetches. Requires actual completed paired audit decisions."""
    root = Path(root).resolve()
    base, cases = verify_execution(root)
    gates = check_gates(root, cases)
    prospective = cases["prospective"]
    if prospective["paper"] != "iclr2025-qgsXsqahMq" or prospective["max_calls"] != 8:
        raise ProtocolError("Prospective selection/budget changed")
    origin = Path(prospective["source_dir"])
    if file_hash(origin / "sources/manifest.json") != prospective["source_manifest_sha256"]:
        raise ProtocolError("Preselected original source manifest changed")
    original_factory = origin.parent.parent
    candidates = [json.loads(line) for line in (original_factory / "pool/candidates.jsonl").read_text(encoding="utf8").splitlines() if line.strip()]
    chosen = [c for c in candidates if c["project_id"] == prospective["paper"]]
    if len(chosen) != 1:
        raise ProtocolError("Preselected candidate missing or duplicated")
    out = root / "prospective"
    ledger = BoundedCallLedger(Path(base["ledger_path"]), baseline=593, stop_at=613,
                              experiment_root=root, arm_root=out, arm_maximum=8)
    with ledger._locked():
        ledger._check_reservation(ledger._read(), str(out / "native_calls"))
    out.mkdir(exist_ok=False)
    factory_root = out / "factory"
    paper = factory_root / "papers" / prospective["paper"]
    for src in tree(origin / "sources"):
        relative = Path(src["path"]).relative_to(origin)
        target = paper / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src["path"], target)
    write_json(factory_root / "selection.json", {"papers": [{"project_id": prospective["paper"]}]})
    write_json(factory_root / "selection_approval.json", {
        "selection_sha256": file_hash(factory_root / "selection.json"),
        "basis": "User goal preselected GETS; paired quality/cost gate passed; not general selection approval"})
    (factory_root / "pool").mkdir()
    (factory_root / "pool/candidates.jsonl").write_text(json.dumps(chosen[0], ensure_ascii=False) + "\n", encoding="utf8")
    config = read_json(original_factory / "factory.json")
    config.update(continue_truncated=False, exp_second_repair=False, structural_gate_to_repair=False,
                  prospective_single_unit=True, prospective_model_limit=8)
    write_json(factory_root / "factory.json", config)
    write_json(paper / "state.json", {"schema_version": "factory-paper-state-1", "project_id": prospective["paper"],
        "title": chosen[0]["title"], "flags": [], "stages": {"fetch": {"status": "completed", "calls": [],
        "artifacts": {"source_manifest": "sources/manifest.json"}, "finished_at": utc_now(),
        "notes": ["Copied exact preselected fetched sources; no historical audits or candidate outputs copied."]}}})
    benchmark = Path(base["benchmark"])
    new_files = [benchmark / "mrhbench/efficiency_prospective.py", benchmark / "scripts/active/run_efficiency_prospective.py"]
    snapshots = []
    for path in new_files:
        target = out / "controller_snapshot" / path.name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(path, target)
        snapshots.append({"original": identity(path), "copy": identity(target)})
    manifest = {"schema_version": "efficiency-prospective-1", "at": utc_now(), "paper": prospective["paper"],
                "base_execution": identity(root / "execution/manifest.json"), "gates": gates,
                "drivers": snapshots, "original_sources": tree(origin / "sources"),
                "sources": tree(paper / "sources"), "factory_inputs": [identity(factory_root / p) for p in (
                    "factory.json", "selection.json", "selection_approval.json", "pool/candidates.jsonl")],
                "priority": list(UNIT_ORDER), "maximum_calls": 8, "ledger_stop_at": 613,
                "identity_contract_amendment": IDENTITY_CONTRACT,
                "comparison_boundary": "Any gated paired identity failure remains failed; its observed cost is not equal-successful-pipeline savings proof. Prospective uses an explicit identity instruction amendment, not normalization.",
                "protocol_delta": "Single repair only, no truncation continuation or structural-gate repair bypass; deterministic failure stops.",
                "runtime_compile": True, "pilot": False}
    write_json(out / "manifest.json", manifest, exclusive=True)
    return manifest


def verify_prospective(root):
    base, cases = verify_execution(root)
    manifest = read_json(root / "prospective/manifest.json")
    check_gates(root, cases)
    verify_files([manifest["base_execution"]] + manifest["gates"] + manifest["factory_inputs"])
    verify_files([r[k] for r in manifest["drivers"] for k in ("original", "copy")])
    origin = Path(cases["prospective"]["source_dir"])
    paper = root / "prospective/factory/papers" / manifest["paper"]
    if tree(origin / "sources") != manifest["original_sources"] or tree(paper / "sources") != manifest["sources"]:
        raise ProtocolError("Prospective original source bytes/membership changed")
    return base, cases, manifest


def choose_unit(adjudication, background):
    allowed = set(adjudication["requested_task_types"])
    effective = set(background["requested_task_types"])
    if effective - allowed:
        raise ProtocolError("Background handling added unadjudicated task types")
    return next((unit for unit in UNIT_ORDER if unit in effective), None)


def run_phase(root, phase, *, runner_factory=None, sources=None, runtime=None):
    """One-shot source phase (2 sessions), then unit phase (at most 6)."""
    root = Path(root).resolve()
    if phase not in {"source", "unit"}:
        raise ProtocolError("Only source/unit phases allowed; no P11")
    base, cases, manifest = verify_prospective(root)
    out = root / "prospective"
    lock = root / ".paired-controller.lock"
    with lock.open("x", encoding="utf8") as handle:
        handle.write(utc_now())
    try:
        if phase == "unit":
            previous = read_json(out / "source_result.json")
            if previous["status"] != "completed":
                raise ProtocolError("Successful source phase required; no retries")
            verify_files(previous["source_stage_files"])
        write_json(out / (phase + "_started.json"), {"at": utc_now()}, exclusive=True)
        ledger = BoundedCallLedger(Path(base["ledger_path"]), baseline=593, stop_at=613,
                                  experiment_root=root, arm_root=out, arm_maximum=8)
        def runner(role):
            if runner_factory is not None:
                return runner_factory(role, ledger, out)
            return ClaudeNativeRunner(binary=Path(base["binary"]["path"]), model=cases["model"], reasoning_effort=cases["effort"],
                                      ledger=ledger, audit_root=out / "native_calls" / role,
                                      timeout_seconds=1800, tool_profile="material_workspace")
        if sources is None:
            from . import factory_sources as sources
        if runtime is None:
            from . import factory_runtime as runtime
        factory = ProspectiveFactory(out / "factory", templates=root / "execution/snapshot/prompts",
                                     runner_factory=runner, sources=sources, runtime=runtime, budget=CallBudget(2 if phase == "source" else 6))
        paper_id = manifest["paper"]
        paper = factory.paper_dir(paper_id)
        state = factory.state(paper_id)
        start = time.monotonic()
        before = ledger._read()["used_attempts"]
        row = {"phase": phase, "started_at": utc_now(), "status": "started", "formal_accepted": False}
        try:
            if phase == "source":
                factory._run_stages(state, ("source_audit", "adjudication"), ("source_audit", "adjudication"), False)
                row["source_stage_files"] = tree(paper / "source_audit") + tree(paper / "adjudication") + [identity(paper / "state.json")]
                row["status"] = "completed" if state["stages"].get("adjudication", {}).get("status") == "completed" else "stopped"
            else:
                prep = ("background", "repo_files", "external_data")
                factory._run_stages(state, prep, prep, False)
                if any(state["stages"].get(s, {}).get("status") not in {"completed", "skipped"} for s in prep):
                    row["status"] = "stopped"
                else:
                    unit = choose_unit(read_json(paper / "adjudication/adjudication.json"), read_json(paper / "background_decision.json"))
                    if unit is None:
                        raise ProtocolError("No supported unit remains; paper substitution prohibited")
                    row["selected_unit"] = unit
                    write_json(out / "selected_unit.json", {"unit": unit, "priority": list(UNIT_ORDER),
                        "adjudication": identity(paper / "adjudication/adjudication.json"),
                        "background": identity(paper / "background_decision.json"),
                        "downstream_files": tree(paper / "background") + tree(paper / "repo_files") + tree(paper / "external_data")}, exclusive=True)
                    ustate = factory.unit_state(paper_id, unit)
                    stages = ("construct", "review_adjudication", "repair", "repair_adjudication", "runtime", "compile")
                    factory._run_stages(ustate, stages, stages, False)
                    row["unit_state"] = ustate
                    row["status"] = "completed" if ustate["stages"].get("compile", {}).get("status") == "completed" else "stopped"
            row["paper_state"] = state
        except Exception as exc:
            row.update(status="failed_needs_attribution", error={"type": type(exc).__name__, "message": str(exc)})
        finally:
            attempts = [a for a in ledger._read()["attempts"][before:]
                        if Path(a.get("artifact_directory", "")).resolve().is_relative_to(out)]
            row.update(finished_at=utc_now(), pipeline_seconds=time.monotonic() - start,
                       costs=summarize_calls(Path(base["ledger_path"]), [a["id"] for a in attempts]) if attempts else
                       {"call_count": 0, "note": "No native sessions launched in this phase; token usage not inferred."})
            write_json(out / (phase + "_result.json"), row, exclusive=True)
        return row
    finally:
        lock.unlink()
