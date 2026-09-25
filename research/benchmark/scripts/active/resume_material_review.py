"""Resume a Claude construction batch whose structural gate failed only on sentinel hashes.

The failed batch stays untouched. Each completed constructor workspace is copied into a
NEW batch directory, the trusted controller fills sentinel sha256 values from the actual
bytes (never executing constructor-written code), the deterministic gate runs, and a fresh
reviewer session reviews the candidate. No constructor call is repeated.
"""
import argparse
import shutil
from pathlib import Path

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.claude_transport import ClaudeNativeRunner
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, contained, digest, file_hash, read_json, write_json
from mrhbench.material_batch import CONTROLLER_FILL, fill_sentinel_hashes
from mrhbench.material_pipeline import prepare_review

ROOT = Path(__file__).resolve().parents[2]
# Exact placeholders the two constructors wrote in batch material-claude-20260924-001 (no hash tool available).
SENTINELS = (CONTROLLER_FILL, "PENDING-run-tools/fill_asset_hashes.py", "UNCOMPUTED-no-hash-tool")


def copy_tree(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for p in sorted(source.rglob("*")):
        if p.is_file():
            rel = p.relative_to(source).as_posix()
            target = contained(destination, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(contained(source, rel, must_exist=True), target)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--failed-batch", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--roles", type=Path, default=ROOT / "config/role_transport_claude_v1.json")
    p.add_argument("--timeout", type=int, default=1800)
    a = p.parse_args()
    if a.output.exists():
        raise ProtocolError("Fresh resume batch required")
    roles = read_json(a.roles)
    spec = roles["constructor"]
    prior = read_json(a.failed_batch / "batch_result.json")
    reviewer = ClaudeNativeRunner(binary=Path(roles["claude_binary_default"]), model=spec["model"], reasoning_effort=spec["effort"],
                                  ledger=CallLedger(ROOT / "audit/development_call_ledger.json"), audit_root=a.output.resolve() / "native_calls",
                                  timeout_seconds=a.timeout, tool_profile="material_workspace")
    results = []
    for job in prior["jobs"]:
        row = {"job_id": job["job_id"], "resumed_from": str(a.failed_batch.resolve()), "prior_status": job["status"],
               "prior_constructor_call": (job.get("constructor") or {}).get("call_id"), "formal_accepted": False}
        try:
            if job["status"] != "failed_needs_attribution" or not job.get("constructor") or job["constructor"].get("status") != "completed":
                raise ProtocolError("Only completed constructions that failed the gate are resumable")
            source = a.failed_batch / job["job_id"] / "constructor"
            staged = a.output / job["job_id"] / "constructor"
            copy_tree(source, staged)
            row["copied_tree_sha256"] = digest(sorted((q.relative_to(staged).as_posix(), file_hash(q)) for q in staged.rglob("*") if q.is_file()))
            row["controller_hash_fill"] = fill_sentinel_hashes(staged / "output", SENTINELS)
            review_dir = a.output / job["job_id"] / "reviewer"
            row["structural_check"] = prepare_review(staged, review_dir, ROOT / "prompts")
            row["reviewer"] = reviewer.run(workspace=review_dir, prompt=(ROOT / "prompts/material_reviewer.txt").read_text(encoding="utf8"),
                                           role="material_reviewer")
            review = read_json(review_dir / "review.json")
            if review.get("schema_version") != "material-review-1" or review.get("paper_id") != read_json(staged / "request.json")["paper_id"]:
                raise ProtocolError("Invalid independent review identity")
            if review.get("decision") not in {"pass_with_pending_runtime", "revise", "reject"}:
                raise ProtocolError("Reviewer cannot grant formal acceptance")
            row["status"] = review["decision"]
        except Exception as exc:
            row["status"] = "failed_needs_attribution"
            row["error"] = {"type": type(exc).__name__, "message": str(exc)}
        results.append(row)
        write_json(a.output / "batch_result.json", {"jobs": results, "formal_accepted": False, "automatic_retry": False})
        print({"job_id": row["job_id"], "status": row["status"]}, flush=True)


if __name__ == "__main__":
    main()
