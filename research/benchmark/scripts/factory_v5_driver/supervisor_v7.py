"""Overnight supervisor for factory-v7 construction (user decision 2026-10-05: expand until 25 papers built under the
v5+ pipeline standard have material packages; auto-resume after provider 429 allowed tonight).

Loop: wait for the v7 validation run; keep up to 3 papers active (unfinished v7 papers first, then the next approved
papers in selection-rank order that were never started in any factory root); run factory_v7 with --workers;
when a run halts on a provider 429, wait (20 -> 40 -> 80 -> 90 min) and resume with --retry-platform (failed calls stay
in the ledger). Stops when 25 papers have >=1 valid compiled unit (factory-v5/v6/v7), when the ledger has < 30 calls
left, after 12 consecutive 429 halts, or after 3 iterations without any ledger or state progress. Never kills runs.
"""
from pathlib import Path
import glob
import json
import os
import subprocess
import sys
import time

PILOT = Path(r"D:/mrhbench-local-pilot")
DRIVER = PILOT / "factory-v5-driver"
V7 = PILOT / "factory-v7"
LEDGER = Path(r"C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark/audit/development_call_ledger.json")
PY = r"D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe"
TARGET, ACTIVE, MIN_LEFT = 25, 3, 30
STAGES = ("fetch,source_audit,adjudication,background,repo_files,external_data,units,construct,review_adjudication,"
          "repair,repair_adjudication,repair2,repair2_adjudication,runtime,compile")
TERMINAL = {"dropped", "blocked_source", "failed_needs_attribution"}
LOG = V7 / "supervisor.log"


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    with open(LOG, "a", encoding="utf8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def rj(p):
    try:
        return json.load(open(p, encoding="utf8"))
    except Exception:
        return None


def ledger():
    d = rj(LEDGER)
    return d["used_attempts"], d["authorized_maximum"]


def unit_info(udir):
    s = rj(Path(udir) / "state.json")
    if not s:
        return "pending"
    st = s["stages"]
    if "withdrawn" in st:
        return "terminal"
    if st.get("compile", {}).get("status") == "completed":
        return "compiled"
    if any(v["status"] in TERMINAL for k, v in st.items() if k != "pilot"):
        return "terminal"
    return "unfinished"


def paper_info(pdir):
    """(done, n_compiled) for one paper directory."""
    s = rj(Path(pdir) / "state.json")
    if not s:
        return False, 0
    units = [unit_info(u) for u in glob.glob(str(Path(pdir) / "units" / "*")) if os.path.isdir(u)]
    n = sum(1 for u in units if u == "compiled")
    st = s["stages"]
    if any(v["status"] in TERMINAL for k, v in st.items() if k != "units"):
        return True, n
    if "units" in st:
        # done when every requested unit has a state and is compiled or terminal (the paper-level "units" stage can stay
        # in_progress after its last unit finished)
        req = (rj(Path(pdir) / "background_decision.json") or {}).get("requested_task_types") or []
        info = {os.path.basename(u): unit_info(u) for u in glob.glob(str(Path(pdir) / "units" / "*")) if os.path.isdir(u)}
        if req and all(info.get(t) in ("compiled", "terminal") for t in req):
            return True, n
    return False, n


def complete_count():
    n = 0
    for root in ("factory-v5", "factory-v6", "factory-v7"):
        for p in glob.glob(str(PILOT / root / "papers" / "iclr2025-*")):
            if ".failed" in p or ".stopped" in p:
                continue
            if paper_info(p)[1] > 0:
                n += 1
    return n


def started_ids():
    ids = set()
    for p in glob.glob(str(PILOT / "factory-v*" / "papers" / "*")) + glob.glob(str(PILOT / "factory-efficiency*" / "inputs" / "*")):
        ids.add(os.path.basename(p).split(".")[0].lower())
    return ids


def snapshot():
    used, _ = ledger()
    states = {}
    for p in glob.glob(str(V7 / "papers" / "iclr2025-*")):
        states[os.path.basename(p)] = json.dumps([rj(Path(p) / "state.json")] +
                                                 [rj(Path(u) / "state.json") for u in sorted(glob.glob(str(Path(p) / "units" / "*")))], sort_keys=True)
    return used, states


def factory_running():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*factory_v7.py*run*' }).Count"],
                       capture_output=True, text=True)
    try:
        return int((r.stdout or "0").strip() or 0) > 0
    except ValueError:
        return True


def main():
    log("supervisor start; target %d papers" % TARGET)
    while factory_running():  # a factory_v7 run started by an earlier supervisor instance may still be going
        time.sleep(60)
    while not (V7 / "run-val-001.done").exists():
        time.sleep(60)
    sel = sorted(json.load(open(V7 / "selection.json", encoding="utf8"))["papers"], key=lambda x: x["rank"])
    wait, consecutive_429, stale, last = 20, 0, 0, None
    it = 0
    while True:
        it += 1
        done_n = complete_count()
        used, cap = ledger()
        left = cap - used
        log("iteration %d: complete papers %d/%d, ledger %d/%d (%d left)" % (it, done_n, TARGET, used, cap, left))
        if done_n >= TARGET:
            log("STOP: target reached"); break
        if left < MIN_LEFT:
            log("STOP: ledger budget nearly exhausted"); break
        active = [os.path.basename(p) for p in sorted(glob.glob(str(V7 / "papers" / "iclr2025-*"))) if not paper_info(p)[0]]
        started = started_ids()
        for p in sel:
            if len(active) >= ACTIVE or done_n + len(active) >= TARGET + 1:
                break
            if p["project_id"].lower() not in started and p["project_id"] not in active:
                active.append(p["project_id"])
        if not active:
            log("STOP: no papers left to run"); break
        max_calls = max(5, min(150, left - MIN_LEFT))
        tag = "run-sup-%s-%03d" % (time.strftime("%m%d%H%M"), it)
        log("run %s: papers %s, max-calls %d" % (tag, ",".join(active), max_calls))
        with open(V7 / (tag + ".log"), "w", encoding="utf8") as out:
            subprocess.run([PY, "-X", "utf8", "-u", str(DRIVER / "factory_v7.py"), "run", "--root", str(V7), "--papers", ",".join(active),
                            "--stages", STAGES, "--max-calls", str(max_calls), "--retry-platform", "--workers", str(len(active))],
                           cwd=str(DRIVER), stdout=out, stderr=subprocess.STDOUT)
        text = (V7 / (tag + ".log")).read_text(encoding="utf8", errors="replace")
        halted_429 = "rate/session limit" in text or "HTTP 429" in text
        now = snapshot()
        if now == last:
            stale += 1
        else:
            stale = 0
        last = now
        if stale >= 3:
            log("STOP: 3 iterations without progress"); break
        if halted_429:
            consecutive_429 += 1
            if consecutive_429 > 12:
                log("STOP: too many consecutive 429 halts"); break
            log("provider 429: waiting %d min before resuming" % wait)
            time.sleep(wait * 60)
            wait = min(90, wait * 2)
        else:
            consecutive_429, wait = 0, 20
    log("supervisor end: complete papers %d, ledger %s" % (complete_count(), ledger()))


if __name__ == "__main__":
    main()
