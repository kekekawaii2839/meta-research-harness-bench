"""Watcher for run_v13_scoring.py (zero model calls): prints new result lines of v13-scoring.log, a progress line every
10 ledger calls, rate limits, and an alarm when no run_v13_scoring.py process exists while the done marker is absent
(the 2026-10-13 23:58 run was terminated externally without any log line)."""
import json
import subprocess
import sys
import time
from pathlib import Path

LOG = Path(r"D:/mrhbench-local-pilot/v13-scoring.log")
DONE = Path(r"D:/mrhbench-local-pilot/v13-scoring.done")
LEDGER = Path(r"C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark/audit/development_call_ledger.json")
KEYS = ("REJUDGE", "PILOT", "HALT", "DONE", "Traceback", "Error", "=== pilot", "=== rejudge")


def say(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def alive():
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\").CommandLine"],
                         capture_output=True, text=True, errors="replace").stdout
    return "run_v13_scoring.py" in out or "run_v13_scoring_par.py" in out


pos = LOG.stat().st_size if LOG.exists() else 0
last_progress = None
missing = 0
RL_SEEN = set()
try:
    START_ID = json.loads(LEDGER.read_text(encoding="utf8"))["used_attempts"]
except Exception:
    START_ID = 0
SUMS = [Path(r"D:/mrhbench-local-pilot/v1_3-v3102-rejudge-summary.json"), Path(r"D:/mrhbench-local-pilot/v1_3-v3102-retry-summary.json")]
seen_rows = {}
for sp in SUMS:  # do not replay rows that exist when the watcher starts
    try:
        seen_rows[sp] = len(json.loads(sp.read_text(encoding="utf8"))["rows"])
    except Exception:
        seen_rows[sp] = 0
while True:
    for sp in SUMS:
        try:
            rows = json.loads(sp.read_text(encoding="utf8"))["rows"]
        except Exception:
            continue
        for r in rows[seen_rows[sp]:]:
            say("REJUDGE %s %s quality %s (v3.6 %s)%s" % (str(r.get("run"))[9:], r.get("status"), r.get("quality"),
                r.get("quality_v36_original"), (" " + str(r.get("message"))[:80]) if r.get("message") else ""))
        seen_rows[sp] = len(rows)
    if LOG.exists() and LOG.stat().st_size > pos:
        with open(LOG, "rb") as f:
            f.seek(pos)
            chunk = f.read().decode("utf8", errors="replace")
        pos = LOG.stat().st_size
        for line in chunk.splitlines():
            if any(k in line for k in KEYS):
                say(line[:240])
    try:
        led = json.loads(LEDGER.read_text(encoding="utf8"))
        used = led["used_attempts"]
        if last_progress is None:
            last_progress = used
        if used >= last_progress + 10:
            last_progress = used
            say("progress: ledger %d" % used)
        for a in led["attempts"][-3:]:
            b = json.dumps(a)
            if a["id"] > START_ID and a["id"] not in RL_SEEN and ("provider_rate_limit" in b or "HTTP 429" in b):
                RL_SEEN.add(a["id"])
                say("RATE LIMIT call %d" % a["id"])
    except Exception:
        pass
    if DONE.exists():
        say("FINISHED")
        sys.exit(0)
    missing = 0 if alive() else missing + 1
    if missing >= 2:
        say("ALARM: run_v13_scoring.py is not running and no done marker")
        sys.exit(1)
    time.sleep(30)
