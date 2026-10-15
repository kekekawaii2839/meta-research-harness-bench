"""Search set v1.3 construction in factory-v8.4 (user 2026-10-13: "批准，记得做好monitor"; +180 calls, ledger cap 3575).

Jobs (up to 3 papers in parallel; no new job after the first provider rate limit; restart manually, --retry-platform
resumes interrupted units; a unit already finished costs 0 calls):
  A2 rebuild (paper stages carried from factory-v5 with carry-paper; area_brief/bg_screen are new for these papers):
    iclr2025-qpXctF2aLZ, iclr2025-qgsXsqahMq, iclr2025-SyVPiehSbg -> LIT,IDEA (v8.4 flow)
  New Oral papers (fetch -> compile; EXP/WC/WE in the v7 flow, LIT/IDEA in the v8.4 flow):
    iclr2025-4OaO3GjP7k, iclr2025-QFO1asgas2
Per-job call caps sum to 180 (A2 28 each, new papers 48 each); the ledger cap is the hard limit.
"""
import json, subprocess, sys, threading
from concurrent.futures import ThreadPoolExecutor
PY = r"D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe"
ROOT = r"D:/mrhbench-local-pilot/factory-v8_4"
UNIT_STAGES = ("frame,construct,probe,leak_judge,review_adjudication,reframe,repair,probe2,leak_judge2,repair_adjudication,"
               "repair2,repair2_adjudication,runtime,compile")
A2_STAGES = "area_brief,bg_screen,units," + UNIT_STAGES
NEW_STAGES = ("fetch,source_audit,adjudication,background,repo_files,external_data,area_brief,bg_screen,units," + UNIT_STAGES)
# Run 2 (after the 2026-10-13 17:21 provider 429): caps = what remains of each job's run-1 share (QFO1 48-26, 4OaO 48-21,
# qgsX 28-17 +3 from qpXc's unused 4), so the total stays within the approved +180; qpXc finished (24 calls).
JOBS = [("iclr2025-QFO1asgas2", None, NEW_STAGES, 22), ("iclr2025-4OaO3GjP7k", None, NEW_STAGES, 27),
        ("iclr2025-qgsXsqahMq", "LIT,IDEA", A2_STAGES, 14), ("iclr2025-SyVPiehSbg", "LIT,IDEA", A2_STAGES, 28)]
only = set(sys.argv[1:])
halt = threading.Event()
lock = threading.Lock()


def one(job):
    pid, units, stages, cap = job
    if only and pid not in only:
        return
    if halt.is_set():
        print("SKIP (halted)", pid, flush=True)
        return
    with lock:
        print("=== start", pid, units or "all units", "max-calls", cap, flush=True)
    cmd = [PY, "-X", "utf8", "-u", "factory_v8_4.py", "run", "--root", ROOT, "--papers", pid, "--stages", stages,
           "--max-calls", str(cap), "--retry-platform"] + (["--units", units] if units else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf8")
    try:
        out = json.loads(r.stdout)
    except Exception:
        out = {"halted": "unparsable output"}
    with lock:
        print("=== done", pid, "calls", out.get("calls_taken"), "halted", out.get("halted"), flush=True)
        print(r.stdout[-2500:], r.stderr[-2500:], flush=True)
    if out.get("halted"):
        halt.set()


with ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(one, JOBS))
print("HALT searchset-v13: provider rate limit" if halt.is_set() else "SEARCHSET-V13 DONE", flush=True)
