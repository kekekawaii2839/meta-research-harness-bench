"""Run the already planned old arm after a known final identity failure.

Scheduling-only amendment, explicitly recorded before any session. It does not
retry, repair, overwrite, or mark the failed incremental result successful.
The original frozen engine and role prompts remain byte-identical.
"""
import json
import shutil
import sys
from pathlib import Path

BENCHMARK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCHMARK))
from mrhbench import factory_efficiency as engine
from mrhbench.io import ProtocolError, read_json, write_json, utc_now


def validate_known_terminal(root, manifest, cases):
    case = cases["cases"][1]
    if case["case_id"] != "diffusion_science_code_repair" or case["order"] != ["incremental", "old"]:
        raise ProtocolError("This narrow amendment only permits the originally planned Diffusion old arm")
    prior = root / "arms" / case["case_id"] / "incremental"
    result = read_json(prior / "result.json")
    if result.get("status") != "failed_needs_attribution" or result.get("error") != {
            "type": "ProtocolError", "message": "Adjudication identity/round/action invalid"}:
        raise ProtocolError("Not the audited terminal identity failure")
    ids = result["cost"]["call_ids"]
    if ids != [600, 601, 602]:
        raise ProtocolError("Unrecognised attempts, do not retry an uncertain operation")
    ledger = read_json(Path(manifest["ledger_path"]))
    if ledger["used_attempts"] != 602:
        raise ProtocolError("Amendment requires the observed clean terminal boundary")
    if any(ledger["attempts"][i-1]["status"] != "completed" for i in ids):
        raise ProtocolError("An underlying transport call is uncertain or failed")
    out = read_json(prior / "adjudicator/review_adjudication.json")
    job = read_json(Path(case["job_path"]))
    if out["project_id"] != job["paper_id"] + "/" + job["job_id"]:
        raise ProtocolError("Not the observed combined-identity error")
    # Validate the other fields on an in-memory diagnostic copy only. Never
    # publish this as a corrected response or change the authoritative failure.
    engine.validate_adjudication({**out, "project_id": job["paper_id"]},
        project_id=job["paper_id"], round_no=manifest["rounds"][case["case_id"]],
        allowed=manifest["allowed_actions"], review=read_json(prior / "adjudicator/review.json"),
        package=read_json(prior / "adjudicator/output/package.json"))
    return prior


def main():
    root = Path("D:/mrhbench-local-pilot/factory-efficiency-20260926-001")
    manifest, cases = engine.verify_execution(root)
    prior = validate_known_terminal(root, manifest, cases)
    original_check = engine.check_order
    # The existing first-pair quality gate still applies.
    original_check(root, cases, "diffusion_science_code_repair", "incremental")
    snapshot = root / "execution_amendments/terminal_pair_v1.py"
    snapshot.parent.mkdir(exist_ok=True)
    with snapshot.open("xb") as stream:
        stream.write(Path(__file__).read_bytes())
    write_json(root / "audits/diffusion_terminal_continuation_v1.json", {
        "at": utc_now(), "scope": "Scheduling only: permit planned other arm after a known terminal failure",
        "script": engine.identity(Path(__file__)), "snapshot": engine.identity(snapshot),
        "base_execution": engine.identity(root / "execution/manifest.json"),
        "unchanged_failed_result": engine.identity(prior / "result.json"),
        "failed_result_remains_failed": True, "retry": False,
        "extra_calls_beyond_original_plan": 0, "remaining_old_arm_maximum": 3,
        "comparability_limit": "Incremental workflow failed its identity gate; numerical costs are not proof of equivalent successful completion."}, exclusive=True)

    def terminal_order(actual_root, actual_cases, case_id, arm):
        if (case_id, arm) != ("diffusion_science_code_repair", "old"):
            return original_check(actual_root, actual_cases, case_id, arm)
        validate_known_terminal(actual_root, manifest, actual_cases)
        return original_check(actual_root, actual_cases, case_id, "incremental")

    # Process-local scheduling adapter; scientific execution stays in the
    # verified frozen engine. No other invocation is dispatched by this script.
    engine.check_order = terminal_order
    try:
        result = engine.run_arm(root, "diffusion_science_code_repair", "old")
    finally:
        engine.check_order = original_check
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
