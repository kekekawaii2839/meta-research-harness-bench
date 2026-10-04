import json, glob, os, sys
sys.path.insert(0, r"C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark")
from mrhbench.factory import STAGE_PATHS
for sf in glob.glob(r"D:/mrhbench-local-pilot/factory-v6/papers/*/state.json") + [u + "/state.json" for u in glob.glob(r"D:/mrhbench-local-pilot/factory-v6/papers/*/units/*")]:
    d = os.path.dirname(sf); s = json.load(open(sf, encoding="utf8")) if os.path.exists(sf) else {"stages": {}}
    for stage, paths in STAGE_PATHS.items():
        if stage in s["stages"]:
            continue
        for p in paths:
            if os.path.exists(os.path.join(d, p)):
                print("ORPHAN", d.split("papers")[-1], stage, p)
