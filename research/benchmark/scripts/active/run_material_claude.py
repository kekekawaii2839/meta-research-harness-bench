"""Claude-native material construction/review batch (user decision 2026-09-24, AGENTS §0.2.13).

Constructor and reviewer are separate fresh ClaudeNativeRunner sessions with the
`material_workspace` profile (file tools only, --restricted: no shell, file access
confined to the published workspace). Real calls use the shared development ledger.
Candidates are never formally accepted here.
"""
import argparse
from pathlib import Path

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.claude_transport import ClaudeNativeRunner
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, read_json, write_json
from mrhbench.material_batch import MATERIAL_PROMPT_SUFFIX, run_batch

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True, help="New batch directory outside any tree holding AGENTS.md")
    p.add_argument("--jobs", type=Path, default=ROOT / "materials/next_batch_v2/jobs")
    p.add_argument("--roles", type=Path, default=ROOT / "config/role_transport_claude_v1.json")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--timeout", type=int, default=1800, help="Construction call walltime, not experiment task budget")
    p.add_argument("--repair-from", type=Path, help="Prior batch root; ONE explicit repair per job")
    p.add_argument("--repair-notes", type=Path, help="Root-adjudicated notes mapping job IDs to text items")
    args = p.parse_args()
    roles = read_json(args.roles)
    spec = roles.get("constructor") or roles["builder"]
    jobs = [read_json(path) for path in sorted(args.jobs.glob("*.json"))]
    if not jobs:
        raise ProtocolError("No approved jobs")
    common = dict(binary=Path(roles["claude_binary_default"]), model=spec["model"], reasoning_effort=spec["effort"],
                  ledger=CallLedger(ROOT / "audit/development_call_ledger.json"),
                  audit_root=args.output.resolve() / "native_calls", timeout_seconds=args.timeout, tool_profile="material_workspace")
    result = run_batch(jobs, workspace=ROOT.parents[1], batch_root=args.output, templates=ROOT / "prompts",
                       constructor=ClaudeNativeRunner(**common), reviewer=ClaudeNativeRunner(**common),
                       max_workers=args.workers, max_jobs=len(jobs), controller_hash_fill=True,
                       repair_from=args.repair_from, repair_notes=read_json(args.repair_notes) if args.repair_notes else None,
                       prompt_suffix=MATERIAL_PROMPT_SUFFIX)
    write_json(args.output / "batch_result.json", result)
    print({"jobs": [{"job_id": r["job_id"], "status": r["status"]} for r in result["jobs"]], "formal_accepted": False})


if __name__ == "__main__":
    main()
