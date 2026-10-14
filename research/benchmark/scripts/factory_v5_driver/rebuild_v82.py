"""Factory v8.2 rebuild of the 7 search-set-v1 papers whose withdrawn/dropped LIT/IDEA units had not started in
factory-v8_1 (user 2026-10-11: "做8.2"). Same scheduling as rebuild_v81: up to 3 papers in parallel, each with only its own
units, no new paper after the first provider rate limit (restart manually with --retry-platform semantics)."""
import json, subprocess, threading
from concurrent.futures import ThreadPoolExecutor
PY = r"D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe"
ROOT = r"D:/mrhbench-local-pilot/factory-v8_2"
STAGES = ("area_brief,bg_screen,frame,construct,probe,leak_judge,review_adjudication,reframe,repair,probe2,leak_judge2,"
          "repair_adjudication,runtime,compile")
JOBS = {"iclr2025-YOc5t8PHf2": "IDEA", "iclr2025-aXuWowhIYt": "IDEA", "iclr2025-cyPMEXdqQ2": "IDEA",
        "iclr2025-msEr27EejF": "LIT,IDEA", "iclr2025-n8h1z588eu": "IDEA", "iclr2025-pdF86dyoS6": "LIT,IDEA",
        "iclr2025-v1B4aet9ct": "LIT,IDEA"}
halt = threading.Event()
lock = threading.Lock()


def one(pid):
    if halt.is_set():
        print("SKIP (halted)", pid, flush=True); return
    units = JOBS[pid]
    cap = 2 + 14 * len(units.split(","))
    with lock:
        print("=== start", pid, units, "max-calls", cap, flush=True)
    r = subprocess.run([PY, "-X", "utf8", "-u", "factory_v8_2.py", "run", "--root", ROOT, "--papers", pid, "--units", units,
                        "--stages", STAGES, "--max-calls", str(cap), "--retry-platform"], capture_output=True, text=True, encoding="utf8")
    try:
        out = json.loads(r.stdout)
    except Exception:
        out = {"halted": "unparsable output"}
    with lock:
        print("=== done", pid, "calls", out.get("calls_taken"), "halted", out.get("halted"), flush=True)
        print(r.stdout[-1500:], r.stderr[-1500:], flush=True)
    if out.get("halted"):
        halt.set()


with ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(one, list(JOBS)))
print("HALT rebuild: provider rate limit" if halt.is_set() else "REBUILD DONE", flush=True)
