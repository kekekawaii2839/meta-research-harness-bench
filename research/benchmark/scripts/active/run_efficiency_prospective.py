"""Conditional prospective unit, after both paired quality/cost audits pass."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mrhbench.efficiency_prospective import freeze_prospective, run_phase


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("command", choices=["freeze", "source", "unit"])
    args = parser.parse_args()
    result = freeze_prospective(args.root) if args.command == "freeze" else run_phase(args.root, args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
