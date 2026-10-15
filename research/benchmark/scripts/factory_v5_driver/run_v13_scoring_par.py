"""Parallel continuation of run_v13_scoring.py (user 2026-10-14: "可以最多两个任务并行着跑").

Same plan, task order, skip rule, per-task process (pilot_v310.py) and 429 stop as run_v13_scoring.py; up to WORKERS
pilots at once. A task is claimed by creating <out>.claim atomically before it starts, so two workers (or a second
instance) never run the same task. An out dir without a result and without a live claim is an interrupted run from an
earlier process: renamed <dir>.interrupted-N / .ratelimited-N and rerun, as in the serial runner.
After the first provider rate limit since start, no new task is started; tasks already running finish.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import subprocess
import sys
import threading

import run_v13_scoring as R

WORKERS = 2
lock = threading.Lock()


def main():
    plan = json.loads((R.B / "v1_3-v3102-plan.json").read_text(encoding="utf8"))
    start = R.ledger()["used_attempts"]
    summary_p = R.B / "v1_3-v3102-summary.json"
    summary = json.loads(summary_p.read_text(encoding="utf8")) if summary_p.exists() else {"rejudge": {}, "pilot": {}}
    halted = threading.Event()
    tasks = sorted(plan["pilot"], key=lambda x: (R.ORDER[x["type"]], x["paper"]))
    it = iter(tasks)

    def claim_next():
        with lock:
            for t in it:
                unit = Path(t["unit"].split("@", 1)[0])
                out = R.OUT / (unit.parents[1].name + "__" + unit.name)
                res = out / "judge_run_result.json"
                if res.exists() and json.loads(res.read_text(encoding="utf8")).get("status") != "not_judged_executor_rate_limited":
                    continue
                claim = out.with_name(out.name + ".claim")
                try:
                    fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except FileExistsError:
                    continue
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                if out.exists():
                    tag = "ratelimited" if res.exists() else "interrupted"
                    n = 1
                    while out.with_name(out.name + ".%s-%d" % (tag, n)).exists():
                        n += 1
                    out.rename(out.with_name(out.name + ".%s-%d" % (tag, n)))
                return t, out, claim
        return None

    def worker(wid):
        while not halted.is_set():
            if R.limited(start):
                halted.set()
                print("HALT v1.3 scoring: provider rate limit", R.limited(start), flush=True)
                return
            got = claim_next()
            if not got:
                return
            t, out, claim = got
            try:
                print("=== pilot", t["paper"], t["type"], "ledger", R.ledger()["used_attempts"], "worker", wid, flush=True)
                p = subprocess.run([R.PY, "-X", "utf8", "-u", str(R.DRIVER / "pilot_v310.py"), t["unit"], str(R.OUT)],
                                   capture_output=True, text=True, encoding="utf8")
                row = next((json.loads(l[7:]) for l in p.stdout.splitlines() if l.startswith("RESULT ")),
                           {"status": "no_result", "stderr": p.stderr[-1500:]})
                with lock:
                    summary["pilot"][t["task_id"]] = {**t, **row}
                    summary_p.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf8", newline="")
                print("PILOT", t["paper"], t["type"], row.get("judge_status") or row.get("status"), row.get("quality"), flush=True)
            finally:
                claim.unlink(missing_ok=True)

    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(worker, range(WORKERS)))
    if not halted.is_set():
        print("V13-SCORING DONE", flush=True)


if __name__ == "__main__":
    os.chdir(R.DRIVER)
    sys.exit(main())
