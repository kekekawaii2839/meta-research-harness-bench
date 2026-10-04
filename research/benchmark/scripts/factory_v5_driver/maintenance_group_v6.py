"""Run maintenance repairs for a list of units sequentially in one process; stop the group at the first provider 429
(or any unit whose maintenance batch did not complete for a platform reason). Usage: maintenance_group_v6.py t1 t2 ..."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import maintenance_repair_v6 as m
import factory_v6
from mrhbench.io import read_json
for t in sys.argv[1:]:
    print("=== maintenance", t, flush=True)
    try:
        m.cmd_run(t.split("@")[0], rebuild=t.endswith("@rebuild"))
    except Exception as e:
        print("ERROR", t, type(e).__name__, e, flush=True)
    pid, unit = t.split("@")[0].split(":")
    st = factory_v6.open_factory(m.ROOT).unit_state(pid, unit)["stages"]
    statuses = {k: v["status"] for k, v in st.items() if k.startswith("maint")}
    print("STATE", t, statuses, "compile:", st.get("compile", {}).get("status"), flush=True)
    if any(v == "platform_rate_limited" for v in statuses.values()):
        print("HALT group: provider rate limit", flush=True)
        break
