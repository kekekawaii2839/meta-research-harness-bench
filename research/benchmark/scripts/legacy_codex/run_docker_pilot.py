"""Build the two inspected CPU candidate environments sequentially; no model calls."""
import argparse
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.docker_pilot import build_package, measure
from mrhbench.io import write_json

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--batch",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--base-digest",required=True)
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    workspace=Path(__file__).resolve().parents[4]
    measure(workspace,a.output/"storage_before.json","after_base_pull_before_package_images")
    results=[]
    for slug,files in [("iv",["assets/base_resources.py","assets/NOTICE.txt"]),
                       ("ssa",["assets/table4_utkface.csv","assets/table4_manifest.json"])]:
        try:
            result=build_package(workspace=workspace,candidate=a.batch/(slug+"-pilot-v2")/"constructor/output",
                destination=a.output/slug,base_digest=a.base_digest,slug=slug,public_files=files)
        except Exception as e:
            result={"slug":slug,"status":"failed_environment_pilot","error":str(e),"formal_accepted":False}
        results.append(result);print(result,flush=True)
        write_json(a.output/"result.json",{"packages":results,"formal_accepted":False})
    measure(workspace,a.output/"storage_final.json","after_two_package_environment_smokes")
    raise SystemExit(0 if all(r.get("smoke_passed") is True for r in results) else 1)
