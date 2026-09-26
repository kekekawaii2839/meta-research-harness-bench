"""Token consumption audit across material factory roots (0 model calls). See mrhbench/factory_costs.py.

Example:
  python scripts/active/factory_cost_audit.py --root v1=D:/mrhbench-local-pilot/factory-v1 \
      --root v4=D:/mrhbench-local-pilot/factory-v4 --out D:/mrhbench-local-pilot/cost-audit
"""
import argparse
from pathlib import Path

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.factory_costs import audit, markdown
from mrhbench.io import write_json

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", action="append", required=True, help="label=path of a factory root (repeatable)")
    p.add_argument("--ledger", type=Path, default=ROOT / "audit/development_call_ledger.json")
    p.add_argument("--out", type=Path, help="directory for cost_audit.json and cost_audit.md")
    a = p.parse_args()
    roots = [tuple(r.split("=", 1)) if "=" in r else (Path(r).name, r) for r in a.root]
    report = audit(roots, a.ledger)
    text = markdown(report)
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        write_json(a.out / "cost_audit.json", report)
        (a.out / "cost_audit.md").write_text(text, encoding="utf8")
    print(text)


if __name__ == "__main__":
    main()
