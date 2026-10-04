"""Explicit prepare or one diagnostic adjudication; never run another repair arm."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from mrhbench.material_adjudication_continuation import prepare,run
p=argparse.ArgumentParser(__doc__);sub=p.add_subparsers(dest='command',required=True)
a=sub.add_parser('prepare');a.add_argument('--root',type=Path,required=True);a.add_argument('--destination',type=Path,required=True);a.add_argument('--authorization',type=Path,required=True)
a=sub.add_parser('run');a.add_argument('--destination',type=Path,required=True)
if __name__=='__main__':
    args=p.parse_args();result=prepare(args.root,args.destination,args.authorization) if args.command=='prepare' else run(args.destination)
    print(json.dumps(result,ensure_ascii=False,indent=2))
