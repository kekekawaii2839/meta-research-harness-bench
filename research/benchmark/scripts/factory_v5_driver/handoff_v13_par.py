"""Hand the v1.3 scoring run from the serial runner to the parallel one (user 2026-10-14) at a task boundary.

Waits until the serial runner logs the start of its next pilot (the one after the running task), then immediately kills
the serial run's process tree (cmd -> python -> pilot_v310 child) and its session container, so the next pilot is
stopped before (or right at) its first model call; reports any ledger reservation left open; removes a done marker
written by the killed cmd; and starts scheduled task mrh-v13-scoring-par. Zero model calls by itself."""
import json
import subprocess
import time
from pathlib import Path

LOG = Path(r"D:/mrhbench-local-pilot/v13-scoring.log")
DONE = Path(r"D:/mrhbench-local-pilot/v13-scoring.done")
LEDGER = Path(r"C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark/audit/development_call_ledger.json")


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, errors="replace").stdout


lines0 = LOG.read_text(encoding="utf8", errors="replace").splitlines()
n0 = len(lines0)
print("waiting; last line:", lines0[-1], flush=True)
while True:
    lines = LOG.read_text(encoding="utf8", errors="replace").splitlines()
    new = [l for l in lines[n0:] if l.startswith("=== pilot")]
    if new:
        break
    time.sleep(1)
used_at_switch = json.loads(LEDGER.read_text(encoding="utf8"))["used_attempts"]
cmd_pids = ps("(Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'run_v13_scoring.cmd' }).ProcessId").split()
for pid in cmd_pids:
    subprocess.run(["taskkill", "/F", "/T", "/PID", pid], capture_output=True)
print("killed serial tree", cmd_pids, "at", time.strftime("%H:%M:%S"), "next pilot was:", new[0], "ledger", used_at_switch, flush=True)
for line in lines[n0:]:
    print("  log:", line, flush=True)
time.sleep(3)
cont = subprocess.run(["docker", "ps", "-q", "--filter", "label=mrhbench.session-owner"], capture_output=True, text=True).stdout.split()
for c in cont:
    subprocess.run(["docker", "rm", "-f", c], capture_output=True)
print("removed containers", cont, flush=True)
if DONE.exists():
    DONE.unlink()
    print("removed done marker written by the killed cmd", flush=True)
led = json.loads(LEDGER.read_text(encoding="utf8"))
open_ = [(a["id"], a["role"], a["artifact_directory"]) for a in led["attempts"] if a["status"] == "reserved"]
print("ledger now", led["used_attempts"], "open reservations", open_, flush=True)
print(subprocess.run(["schtasks", "/Run", "/TN", "mrh-v13-scoring-par"], capture_output=True, text=True, errors="replace").stdout.strip(), flush=True)
print("HANDOFF DONE", flush=True)
