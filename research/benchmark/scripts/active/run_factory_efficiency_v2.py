"""Freeze offline, then explicitly run ONE new real paired-trial arm."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mrhbench.factory_efficiency_v2 import freeze, run_arm


def main():
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    frozen = sub.add_parser("freeze")
    frozen.add_argument("--cases", type=Path, default=ROOT / "audit/factory_efficiency_v2_cases_v1.json")
    frozen.add_argument("--roles", type=Path, default=ROOT / "config/role_transport_claude_v2.json")
    frozen.add_argument("--ledger", type=Path, default=ROOT / "audit/development_call_ledger.json")
    run = sub.add_parser("run")
    run.add_argument("--root", type=Path, required=True)
    run.add_argument("--case", required=True)
    run.add_argument("--arm", choices=["old", "incremental"], required=True)
    args = parser.parse_args()
    out = (freeze(args.cases, ROOT, args.roles, args.ledger) if args.command == "freeze"
           else run_arm(args.root, args.case, args.arm))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
