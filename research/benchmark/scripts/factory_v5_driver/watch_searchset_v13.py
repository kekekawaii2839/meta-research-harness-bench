"""Watcher for searchset_v13_v84.py: one line per event (model call started/finished, 429, unit stage change, done).
Zero model calls; reads the ledger, the v8.4 state files and the driver log."""
import json, time, sys
from pathlib import Path

LEDGER = Path(r"C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark/audit/development_call_ledger.json")
ROOT = Path(r"D:/mrhbench-local-pilot/factory-v8_4/papers")
LOG = Path(r"D:/mrhbench-local-pilot/factory-v8_4/searchset-v13.log")
DONE = Path(r"D:/mrhbench-local-pilot/factory-v8_4/searchset-v13.done")
PAPERS = ["iclr2025-QFO1asgas2", "iclr2025-4OaO3GjP7k", "iclr2025-qpXctF2aLZ", "iclr2025-qgsXsqahMq", "iclr2025-SyVPiehSbg"]
START = int(sys.argv[1]) if len(sys.argv) > 1 else 3391
seen_calls, seen_stage, log_pos = {}, {}, 0
started = False
if LOG.exists():  # re-armed watcher: do not replay old log lines
    log_pos = len(LOG.read_text(encoding="utf8", errors="replace"))


def say(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def load(p):
    for _ in range(5):
        try:
            return json.loads(p.read_text(encoding="utf8"))
        except Exception:
            time.sleep(1)
    return None


while True:
    led = load(LEDGER)
    if led:
        for a in led["attempts"][START:]:
            key = (a["status"], bool(a.get("usage")))
            if seen_calls.get(a["id"]) == key:
                continue
            first = a["id"] not in seen_calls
            seen_calls[a["id"]] = key
            d = str(a.get("artifact_directory", ""))
            pid = next((p[9:13] for p in PAPERS if p in d), "?")
            blob = json.dumps(a)
            if "provider_rate_limit" in blob or "HTTP 429" in blob or '"api_error_status": 429' in blob or "session limit" in blob.lower():
                say("RATE LIMIT call %d %s %s" % (a["id"], a["role"], pid))
            elif a["status"] not in ("reserved", "completed"):
                say("call %d %s %s %s" % (a["id"], a["role"], pid, a["status"]))
            elif a["status"] == "completed" and a["id"] % 10 == 0:
                say("progress: ledger call %d completed (%d since start)" % (a["id"], a["id"] - START))
    for p in PAPERS:
        for st in [ROOT / p / "state.json"] + sorted((ROOT / p / "units").glob("*/state.json")):
            s = load(st) if st.exists() else None
            if not s:
                continue
            for k, v in s.get("stages", {}).items():
                tag = (str(st), k)
                status = v.get("status")
                if seen_stage.get(tag) == status:
                    continue
                first_pass = tag not in seen_stage and not started
                seen_stage[tag] = status
                if first_pass or status == "in_progress":
                    continue
                # report only outcomes worth acting on: unit compiled, anything not completed/skipped, paper adjudication
                if status in ("completed", "skipped") and k not in ("compile", "adjudication", "bg_screen", "leak_judge", "leak_judge2"):
                    continue
                unit = st.parent.name if st.parent.parent.name == "units" else "paper"
                note = "; ".join(v.get("notes", []))[:160]
                say("%s %s %s: %s %s" % (p[9:13], unit, k, status, note))
    if LOG.exists():
        text = LOG.read_text(encoding="utf8", errors="replace")
        for line in text[log_pos:].splitlines():
            if line.startswith(("=== ", "HALT", "SEARCHSET", "SKIP", "Traceback")):
                say("LOG " + line[:200])
        log_pos = len(text)
    started = True
    if DONE.exists():
        say("DONE")
        sys.exit(0)
    time.sleep(30)
