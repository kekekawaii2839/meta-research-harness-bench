"""Factory v8.2 full build of new ICLR 2025 Oral papers that replace Poster papers in the search set (user 2026-10-12:
"B吧，但先不一次性全执行，我们按顺序先替换3篇，替换原本修复需要最多的3篇paper"). Step 1: Xo0Q1N7CGk, GMwRl2e9Y1,
kbjJ9ZOakb replace l11DZY5Nxu, 1vrpdV9U3i, cyPMEXdqQ2 (search_set_v1_2_membership.json). Each paper runs every stage from
fetch to compile (EXP/WC/WE in the v7 flow, LIT/IDEA in the v8.2 flow), up to 3 papers in parallel, no new paper after the
first provider rate limit (restart manually; --retry-platform resumes interrupted units)."""
import json, subprocess, sys, threading
from concurrent.futures import ThreadPoolExecutor
PY = r"D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe"
ROOT = r"D:/mrhbench-local-pilot/factory-v8_2"
STAGES = ("fetch,source_audit,adjudication,background,repo_files,external_data,area_brief,bg_screen,units,"
          "frame,construct,probe,leak_judge,review_adjudication,reframe,repair,probe2,leak_judge2,repair_adjudication,"
          "repair2,repair2_adjudication,runtime,compile")
PAPERS = sys.argv[1:] or ["iclr2025-Xo0Q1N7CGk", "iclr2025-GMwRl2e9Y1", "iclr2025-kbjJ9ZOakb"]
CAP = 55
halt = threading.Event()
lock = threading.Lock()


def one(pid):
    if halt.is_set():
        print("SKIP (halted)", pid, flush=True); return
    with lock:
        print("=== start", pid, "max-calls", CAP, flush=True)
    r = subprocess.run([PY, "-X", "utf8", "-u", "factory_v8_2.py", "run", "--root", ROOT, "--papers", pid,
                        "--stages", STAGES, "--max-calls", str(CAP), "--retry-platform"], capture_output=True, text=True, encoding="utf8")
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
    list(pool.map(one, PAPERS))
print("HALT newpapers: provider rate limit" if halt.is_set() else "NEWPAPERS DONE", flush=True)
