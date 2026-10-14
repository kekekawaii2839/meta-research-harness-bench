"""Factory v8 pilot (user-approved plan 2026-10-06): rebuild 4 withdrawn LIT/IDEA units with the v8 flow, one unit at a
time; stop at the first provider rate limit (no automatic retry)."""
import json, subprocess, sys
PY = r"D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe"
ROOT = r"D:/mrhbench-local-pilot/factory-v8"
STAGES = "area_brief,frame,construct,probe,leak_judge,review_adjudication,reframe,repair,probe2,leak_judge2,repair_adjudication,runtime,compile"
UNITS = [("iclr2025-n8h1z588eu", "LIT"), ("iclr2025-YOc5t8PHf2", "LIT"), ("iclr2025-BdmVgLMvaf", "IDEA"), ("iclr2025-5qg6JPSgCj", "IDEA")]
for pid, unit in UNITS:
    print("=== v8 pilot", pid, unit, flush=True)
    r = subprocess.run([PY, "-X", "utf8", "-u", "factory_v8.py", "run", "--root", ROOT, "--papers", pid, "--units", unit,
                        "--stages", STAGES, "--max-calls", "14"], capture_output=True, text=True, encoding="utf8")
    print(r.stdout[-3000:], r.stderr[-2000:], flush=True)
    try:
        out = json.loads(r.stdout)
    except Exception:
        print("HALT pilot: unparsable run output", flush=True); break
    if out.get("halted"):
        print("HALT pilot: provider rate limit", flush=True); break
print("PILOT DONE", flush=True)
