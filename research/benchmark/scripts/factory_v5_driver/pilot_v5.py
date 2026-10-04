"""P11 pilot runner for factory-v5 compiled tasks (development only, one attempt per task, no retry).

Same flow as mrhbench.stage_controller.run_stage (container harness -> evidence -> Claude native judge) with two
additions that avoid editing the repo:
  * LIT tasks use the shared library v4 service (factory_library.SharedLibraryService) from the unit's private
    lit_corpus_configuration.json;
  * controller deterministic output checks (output_checks.py, the unit's checks.json) run on the collected
    artifacts before the judge and are appended as a program_check evidence record (not a score).
Executor transport and judge come from an explicit role file. Every call enters the shared ledger.
"""
from pathlib import Path
import argparse
import importlib.metadata
import json
import sys

BENCH = Path(r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import platform_patches  # noqa: E402,F401  (must precede every mrhbench import)
import judge_v36 as judge_v35  # noqa: E402  (judge v3.6 = v3.5 + rules 7-10; platform failure summary; repo native_judge.py unmodified)

import mrhbench.stage_controller as sc  # noqa: E402
from mrhbench.io import ProtocolError, read_json, write_json, file_hash  # noqa: E402
from output_checks import run_checks  # noqa: E402
import factory_library as fl  # noqa: E402

LEDGER = BENCH / "audit/development_call_ledger.json"


def _executor(roles, ledger, output, view, binary):
    spec = roles["executor"]
    timeout = view["resources"]["execution_budget"]["wall_seconds"]
    if spec.get("transport") == "openai_wrapper" or spec.get("transport") == "openai_compatible":
        from mrhbench.openai_compat_transport import OpenAICompatTransport
        return OpenAICompatTransport(base_url=spec["base_url"], api_key_file=spec["api_key_file"], model=spec["model"],
                                     reasoning_effort=spec["effort"], ledger=ledger, audit_root=output / "executor_calls",
                                     timeout_seconds=timeout)
    from mrhbench.claude_transport import ClaudeJSONTransport
    return ClaudeJSONTransport(binary=Path(binary), model=spec["model"], reasoning_effort=spec["effort"], ledger=ledger,
                               audit_root=output / "executor_calls", timeout_seconds=timeout)


class _DryRunProvider:
    """Zero-call stub: every model request fails immediately (no ledger entry)."""
    def complete(self, *args, **kwargs):
        raise RuntimeError("dry run: no model call")


def run_task(unit_dir, harness, output, roles_path, dry_run=False, release="release-v2"):
    unit_dir, output, roles_path, harness = Path(unit_dir), Path(output), Path(roles_path), Path(harness)
    package = next(p for p in (unit_dir / release / "compiled").iterdir() if p.name.startswith("task-"))
    roles = read_json(roles_path)
    sc.validate_roles(roles)
    task = sc.load_task(package / "task.json")
    sc.validate_application_schema(task["public"]["output_contract"])
    collection = sc.collection_policy(task["public"]["resources"])
    output.mkdir(parents=True)
    write_json(output / "controller_environment.json", {"python": sys.executable, "version": sys.version,
               "dependencies": {"jsonschema": importlib.metadata.version("jsonschema")},
               "harness_sha256": file_hash(harness), "platform_patches": platform_patches.APPLIED, "roles_sha256": file_hash(roles_path), "pilot_runner_sha256": file_hash(Path(__file__))})
    sc.export_task(task, package, output / "public", audience="development_executor")
    view = read_json(output / "public/task.json")
    literature = None
    cfg_path = unit_dir / "lit_corpus_configuration.json"
    if task["task_type"] == "LIT":
        cfg = read_json(cfg_path)
        lib = Path(cfg["library_root"])
        if file_hash(lib / "corpus.json") != cfg["corpus_sha256"]:
            raise ProtocolError("Frozen shared library v4 changed")
        literature = fl.SharedLibraryService(lib, cfg["cutoff"], cfg["excluded_papers"], excluded_aliases=cfg["excluded_aliases"])
    ledger = sc.CallLedger(LEDGER)
    write_json(output / "role_configuration.json", roles, exclusive=True)
    binary = roles["claude_binary_default"]
    provider = _DryRunProvider() if dry_run else _executor(roles, ledger, output, view, binary)
    result = sc.run_container_harness(harness=Path(harness), public_root=output / "public", image_id=view["resources"]["image_id"],
                                      provider=provider, output=output / "execution", literature=literature,
                                      max_artifact_bytes=collection["max_total_bytes"], max_artifact_files=collection["max_entries"])
    records = sc.evidence_for_run(task, package, output / "public", output / "execution")
    if literature is not None:
        records.extend(sc.build_literature_judge_evidence(literature, allow_incomplete=True))
    import output_checks as _oc
    _oc.LIBRARY_ROOT = read_json(unit_dir / "lit_corpus_configuration.json")["library_root"] if (unit_dir / "lit_corpus_configuration.json").is_file() else None
    checks = run_checks(read_json(unit_dir / "checks.json")["checks"], output / "execution/artifacts", output / "public", image_id=view["resources"]["image_id"])
    write_json(output / "output_checks.json", checks, exclusive=True)
    records.append(sc.evidence_record("controller-output-checks", "program_check", json.dumps(checks, ensure_ascii=False, indent=1)))
    records.append(judge_v35.summary_record(sc, output / "execution"))
    write_json(output / "evidence.json", records)
    if dry_run:
        return {"task_type": task["task_type"], "submission_status": result["status"], "evidence_records": len(records),
                "checks_hard_failed": checks["hard_failed"], "literature_docs": len(literature.corpus.docs) if literature else None, "dry_run": True}
    task_calls = [x for x in read_json(LEDGER)["attempts"] if str(output.resolve()) in str(x.get("artifact_directory", ""))]
    if any("provider_rate_limit" in json.dumps(x) or "HTTP 429" in json.dumps(x) for x in task_calls):
        judge = {"status": "not_judged_executor_rate_limited", "note": "executor hit a provider 429; the partial run is a platform outcome, not scored"}
        write_json(output / "judge_run_result.json", judge)
        return {"task_type": task["task_type"], "task_id": task["task_id"], "submission_status": result["status"],
                "checks_hard_failed": checks["hard_failed"], "checks_flags": checks["flags_raised"], "judge_status": judge["status"],
                "quality": None, "dimension_scores": None, "output": str(output), "formal": False}
    from mrhbench.claude_transport import ClaudeNativeRunner
    j = roles["judge"]
    runner = ClaudeNativeRunner(binary=Path(binary), model=j["model"], reasoning_effort=j["effort"], ledger=ledger,
                                audit_root=output / "judge_calls", timeout_seconds=j.get("timeout_seconds", 600))
    try:
        judge = sc.run_native_judge(runner=runner, task_id=task["task_id"], task_type=task["task_type"], records=records,
                                    output=output / "judge", python_binary=Path(sys.executable),
                                    controller_output_inventory=sc.output_inventory_for_run(task["task_type"], output / "execution"))
    except Exception as exc:
        judge = {"status": "judge_attempt_failed", "error_type": type(exc).__name__, "message": str(exc)[:500]}
    write_json(output / "judge_run_result.json", judge)
    return {"task_type": task["task_type"], "task_id": task["task_id"], "submission_status": result["status"],
            "checks_hard_failed": checks["hard_failed"], "checks_flags": checks["flags_raised"],
            "judge_status": judge.get("status"), "quality": judge.get("quality"), "dimension_scores": judge.get("dimension_scores"),
            "output": str(output), "formal": False, "manual_trajectory_review_required": True}


def judge_only(unit_dir, output, roles_path, release):
    """Finish an interrupted task whose execution completed: evidence + checks + judge, no re-execution."""
    unit_dir, output, roles_path = Path(unit_dir), Path(output), Path(roles_path)
    if not (output / "execution/submission.json").is_file() or (output / "judge_run_result.json").exists():
        raise ProtocolError("judge-only needs a completed execution and no existing judgment")
    package = next(p for p in (unit_dir / release / "compiled").iterdir() if p.name.startswith("task-"))
    roles = read_json(roles_path)
    task = sc.load_task(package / "task.json")
    view = read_json(output / "public/task.json")
    literature = None
    if task["task_type"] == "LIT":
        cfg = read_json(unit_dir / "lit_corpus_configuration.json")
        literature = fl.SharedLibraryService(Path(cfg["library_root"]), cfg["cutoff"], cfg["excluded_papers"], excluded_aliases=cfg["excluded_aliases"])
    records = sc.evidence_for_run(task, package, output / "public", output / "execution")
    if literature is not None:
        records.extend(sc.build_literature_judge_evidence(literature, allow_incomplete=True))
    import output_checks as _oc
    _oc.LIBRARY_ROOT = read_json(unit_dir / "lit_corpus_configuration.json")["library_root"] if (unit_dir / "lit_corpus_configuration.json").is_file() else None
    checks = run_checks(read_json(unit_dir / "checks.json")["checks"], output / "execution/artifacts", output / "public", image_id=view["resources"]["image_id"])
    write_json(output / "output_checks.json", checks, exclusive=True)
    records.append(sc.evidence_record("controller-output-checks", "program_check", json.dumps(checks, ensure_ascii=False, indent=1)))
    records.append(judge_v35.summary_record(sc, output / "execution"))
    write_json(output / "evidence.json", records)
    write_json(output / "judge_only_note.json", {"reason": "controller process reaped for low host memory after execution finished; judged without re-execution", "retry_of_execution": False})
    from mrhbench.claude_transport import ClaudeNativeRunner
    j = roles["judge"]
    runner = ClaudeNativeRunner(binary=Path(roles["claude_binary_default"]), model=j["model"], reasoning_effort=j["effort"], ledger=sc.CallLedger(LEDGER),
                                audit_root=output / "judge_calls", timeout_seconds=j.get("timeout_seconds", 600))
    try:
        judge = sc.run_native_judge(runner=runner, task_id=task["task_id"], task_type=task["task_type"], records=records, output=output / "judge",
                                    python_binary=Path(sys.executable), controller_output_inventory=sc.output_inventory_for_run(task["task_type"], output / "execution"))
    except Exception as exc:
        judge = {"status": "judge_attempt_failed", "error_type": type(exc).__name__, "message": str(exc)[:500]}
    write_json(output / "judge_run_result.json", judge)
    return {"task_type": task["task_type"], "submission_status": read_json(output / "execution/submission.json")["status"],
            "checks_hard_failed": checks["hard_failed"], "checks_flags": checks["flags_raised"], "judge_status": judge.get("status"),
            "quality": judge.get("quality"), "dimension_scores": judge.get("dimension_scores"), "output": str(output)}


def rejudge(unit_dir, output, roles_path, release, tag=None):
    """Re-judge a finished run with the current judge (v3.5) into <output>/<tag>/; the original judgment is kept."""
    unit_dir, output, roles_path = Path(unit_dir), Path(output), Path(roles_path)
    tag = tag or "rejudge-" + judge_v35.VERSION.rsplit("-", 1)[-1].replace(".", "")
    dest = output / tag
    if not (output / "execution/submission.json").is_file() or dest.exists():
        raise ProtocolError("rejudge needs a completed execution and a new destination")
    dest.mkdir()
    package = next(p for p in (unit_dir / release / "compiled").iterdir() if p.name.startswith("task-"))
    roles = read_json(roles_path)
    task = sc.load_task(package / "task.json")
    view = read_json(output / "public/task.json")
    if view["task_id"] != task["task_id"]:
        raise ProtocolError("release does not match the run's task")
    # the evidence the original judge received (incl. literature pages the executor read), minus the old checks record
    records = [r for r in read_json(output / "evidence.json") if r["evidence_id"] not in ("controller-output-checks", "controller-platform-failure-summary")]
    import output_checks as _oc
    _oc.LIBRARY_ROOT = read_json(unit_dir / "lit_corpus_configuration.json")["library_root"] if (unit_dir / "lit_corpus_configuration.json").is_file() else None
    checks = run_checks(read_json(unit_dir / "checks.json")["checks"], output / "execution/artifacts", output / "public", image_id=view["resources"]["image_id"])
    write_json(dest / "output_checks.json", checks, exclusive=True)
    records.append(sc.evidence_record("controller-output-checks", "program_check", json.dumps(checks, ensure_ascii=False, indent=1)))
    records.append(judge_v35.summary_record(sc, output / "execution"))
    write_json(dest / "evidence.json", records)
    write_json(dest / "rejudge_note.json", {"reason": "current judge rules + platform failure summary + current generic checks (P11 reviews)",
                                            "judge_version": judge_v35.VERSION, "original_judgment_kept": str(output / "judge_run_result.json"),
                                            "retry_of_execution": False})
    from mrhbench.claude_transport import ClaudeNativeRunner
    j = roles["judge"]
    runner = ClaudeNativeRunner(binary=Path(roles["claude_binary_default"]), model=j["model"], reasoning_effort=j["effort"], ledger=sc.CallLedger(LEDGER),
                                audit_root=dest / "judge_calls", timeout_seconds=j.get("timeout_seconds", 600))
    try:
        judge = sc.run_native_judge(runner=runner, task_id=task["task_id"], task_type=task["task_type"], records=records, output=dest / "judge",
                                    python_binary=Path(sys.executable), controller_output_inventory=sc.output_inventory_for_run(task["task_type"], output / "execution"))
    except Exception as exc:
        judge = {"status": "judge_attempt_failed", "error_type": type(exc).__name__, "message": str(exc)[:500]}
    write_json(dest / "judge_run_result.json", judge)
    return {"task_type": task["task_type"], "judge_status": judge.get("status"), "quality": judge.get("quality"),
            "dimension_scores": judge.get("dimension_scores"), "output": str(dest)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--units", required=True, help="comma-separated unit dirs")
    ap.add_argument("--harness", required=True)
    ap.add_argument("--harness-sha256", required=True)
    ap.add_argument("--roles", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--release", default="release-v2")
    ap.add_argument("--paper-prefix", action="store_true", help="name task dirs <paper>__<unit> (several papers in one run)")
    a = ap.parse_args()
    if file_hash(Path(a.harness)) != a.harness_sha256:
        raise ProtocolError("Frozen H0 hash mismatch")
    out = Path(a.out)
    rows = []
    start = read_json(LEDGER)["used_attempts"]
    for u in a.units.split(","):
        rel = a.release
        if "@" in u:  # per-unit release: <unit dir>@<release dir name>
            u, rel = u.split("@", 1)
        since = read_json(LEDGER)["attempts"][start:]
        limited = [x.get("id") for x in since if "provider_rate_limit" in json.dumps(x) or "HTTP 429" in json.dumps(x)]
        if limited and not a.dry_run:
            rows.append({"unit": u, "status": "not_started_after_rate_limit", "rate_limited_calls": limited})
            write_json(out / "pilot_summary.json", {"rows": rows, "retry": False})
            print(json.dumps(rows[-1]))
            continue
        u = Path(u)
        try:
            rows.append(run_task(u, a.harness, out / ((u.parents[1].name + "__" + u.name) if a.paper_prefix else u.name), a.roles, dry_run=a.dry_run, release=rel))
        except Exception as exc:
            rows.append({"unit": str(u), "status": "stage_failed", "error": "%s: %s" % (type(exc).__name__, str(exc)[:500])})
        write_json(out / "pilot_summary.json", {"rows": rows, "retry": False})
        print(json.dumps(rows[-1], ensure_ascii=False))


if __name__ == "__main__":
    main()
