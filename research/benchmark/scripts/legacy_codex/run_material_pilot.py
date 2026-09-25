"""Explicit local two-paper construction/review pilot; real calls use shared ledger."""
import argparse
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.costs import CallLedger
from mrhbench.io import read_json, write_json
from mrhbench.material_batch import run_batch
from mrhbench.native_codex import NativeCodexRunner

ROOT = Path(__file__).resolve().parents[2]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--codex-binary", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True, help="New independent batch directory; not source workspace")
    p.add_argument("--jobs", type=Path, default=ROOT / "materials/pilot_v2/jobs")
    p.add_argument("--job", choices=["ssa", "iv"], help="Optional single-paper pilot")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--constructor-model", default="gpt-6-luna")
    p.add_argument("--repair-from", type=Path, help="Prior batch root; ONE explicit fresh repair per selected job, no historical rewrite")
    p.add_argument("--repair-notes", type=Path, help="Optional JSON mapping job IDs to explicitly adjudicated repair notes")
    p.add_argument("--permission-profile", choices=[":workspace", ":danger-full-access"], default=":workspace")
    p.add_argument("--timeout", type=int, default=1200, help="Construction call walltime, not experiment task budget")
    args = p.parse_args()
    paths = [args.jobs / (args.job + ".json")] if args.job else sorted(args.jobs.glob("*.json"))
    jobs = [read_json(path) for path in paths]
    common = dict(binary=args.codex_binary, reasoning_effort="medium", ledger=CallLedger(ROOT / "audit/development_call_ledger.json"),
                  audit_root=ROOT / "audit/material_native_v2", permission_profile=args.permission_profile,
                  timeout_seconds=args.timeout)
    result = run_batch(jobs, workspace=ROOT.parents[1], batch_root=args.output, templates=ROOT / "prompts",
                       constructor=NativeCodexRunner(model=args.constructor_model, **common),
                       reviewer=NativeCodexRunner(model="gpt-5.6-sol", **common), max_workers=args.workers, max_jobs=2,
                       repair_from=args.repair_from, repair_notes=read_json(args.repair_notes) if args.repair_notes else None)
    write_json(args.output / "batch_result.json", result)
    print({"jobs": [{"job_id": r["job_id"], "status": r["status"]} for r in result["jobs"]], "formal_accepted": False})

if __name__ == "__main__":
    main()
