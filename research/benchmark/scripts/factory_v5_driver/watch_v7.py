"""Prints one line per new event: ledger every +5, non-completed calls, terminal/compiled stages, run done. Polls 60 s."""
import json, glob, os, sys, time
L = r"C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark/audit/development_call_ledger.json"
since, done_file = int(sys.argv[1]), sys.argv[2]
seen, last = set(), since
def emit(s):
    if s not in seen:
        seen.add(s); print(s, flush=True)
while True:
    try:
        d = json.load(open(L, encoding="utf8"))
        n = d["used_attempts"]; inflight = sum(1 for x in d["attempts"] if x["status"] == "reserved")
        if n >= last + 5:
            last = n; print("ledger at %d (in flight %d)" % (n, inflight), flush=True)
        for x in d["attempts"]:
            if x["id"] > since and x["status"] not in ("completed", "reserved"):
                emit("call %s %s %s" % (x["id"], x["role"], x["status"]))
        for f in glob.glob(r"D:/mrhbench-local-pilot/factory-v7/papers/*/state.json") + glob.glob(r"D:/mrhbench-local-pilot/factory-v7/papers/*/units/*/state.json"):
            s = json.load(open(f, encoding="utf8"))
            w = f.replace("\\", "/").split("papers/")[-1].replace("/state.json", "")
            for k, v in s["stages"].items():
                if k != "pilot" and v["status"] in ("failed_needs_attribution", "dropped", "blocked_source"):
                    emit("END %s %s %s %s" % (w, k, v["status"], (v.get("notes") or [""])[-1][:90]))
                if k == "compile" and v["status"] == "completed":
                    emit("COMPILED " + w)
    except Exception as e:
        print("watch error", type(e).__name__, e, flush=True)
    if os.path.exists(done_file):
        print("run done", flush=True); break
    time.sleep(60)
