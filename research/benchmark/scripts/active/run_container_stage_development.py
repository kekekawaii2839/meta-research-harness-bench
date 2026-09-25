"""CLI for mrhbench.stage_controller.run_stage (one frozen harness + one CPU stage + one judge turn)."""
import argparse
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.io import read_json, ProtocolError
from mrhbench.stage_controller import run_stage


def main():
    p=argparse.ArgumentParser()
    for key in ('package','harness','output','binary'):p.add_argument('--'+key,required=True)
    p.add_argument('--skip-judge',action='store_true');p.add_argument('--context-policy',type=Path);p.add_argument('--roles',type=Path);a=p.parse_args()
    if a.roles and a.context_policy:raise ProtocolError('Codex context policy and Claude roles are exclusive')
    print(run_stage(a.package,a.harness,a.output,a.binary,a.skip_judge,read_json(a.context_policy) if a.context_policy else None,read_json(a.roles) if a.roles else None))


if __name__=='__main__':
    main()
