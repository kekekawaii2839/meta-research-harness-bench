"""Search set v1.3 scoring with judge v3.10.2, option B (user 2026-10-13: "B吧"; ledger cap 4320).

Step 1: the 17 re-judgments of existing runs (rejudge_v38.py --judge v310), 1 call each.
Step 2: the 61 full pilots (pilot_v310.py), one OS process per task (bounded memory), cheapest task types first.
Stops before starting anything new after the first provider rate limit (429) since this run started; restart the task
later (finished tasks are skipped; an interrupted pilot directory is renamed <dir>.interrupted-N and rerun).
Plan: D:/mrhbench-local-pilot/v1_3-v3102-plan.json. Summary: D:/mrhbench-local-pilot/v1_3-v3102-summary.json.
"""
from pathlib import Path
import json
import subprocess
import sys

PY = r"D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe"
DRIVER = Path(__file__).resolve().parent
B = Path(r"D:/mrhbench-local-pilot")
OUT = B / "p11-v13-v3102"
LEDGER = Path(r"C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark/audit/development_call_ledger.json")
ORDER = {"IDEA": 0, "WRITE_CONTENT": 1, "WRITE_EVIDENCE": 2, "EXP": 3, "LIT": 4}


def ledger():
    return json.loads(LEDGER.read_text(encoding="utf8"))


def limited(start):
    return [a["id"] for a in ledger()["attempts"][start:]
            if "provider_rate_limit" in json.dumps(a) or "HTTP 429" in json.dumps(a)]


def main():
    plan = json.loads((B / "v1_3-v3102-plan.json").read_text(encoding="utf8"))
    start = ledger()["used_attempts"]
    summary_p = B / "v1_3-v3102-summary.json"
    summary = json.loads(summary_p.read_text(encoding="utf8")) if summary_p.exists() else {"rejudge": {}, "pilot": {}}

    def save():
        summary_p.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf8", newline="")

    # step 1: re-judgments
    todo = []
    for r in plan["rejudge"]:
        run = r["pair"].split("=", 1)[1].split("#", 1)[0]
        if (Path(run) / "rejudge-v310" / "judge_run_result.json").exists():
            continue
        todo.append(r["pair"])
    if todo:
        print("=== rejudge", len(todo), flush=True)
        p = subprocess.run([PY, "-X", "utf8", "-u", str(DRIVER / "rejudge_v38.py"), "--judge", "v310", "--summary",
                            str(B / "v1_3-v3102-rejudge-summary.json")] + todo, capture_output=True, text=True, encoding="utf8")
        for line in p.stdout.splitlines():
            try:
                row = json.loads(line)
                summary["rejudge"][row["run"]] = row
                print("REJUDGE", row["run"], row.get("status"), row.get("quality"), flush=True)
            except Exception:
                pass
        if p.returncode:
            print("rejudge stderr:", p.stderr[-1500:], flush=True)
        save()
    # step 2: pilots
    for t in sorted(plan["pilot"], key=lambda x: (ORDER[x["type"]], x["paper"])):
        if limited(start):
            print("HALT v1.3 scoring: provider rate limit", limited(start), flush=True)
            save()
            return
        unit = Path(t["unit"].split("@", 1)[0])
        out = OUT / (unit.parents[1].name + "__" + unit.name)
        res = out / "judge_run_result.json"
        if res.exists() and json.loads(res.read_text(encoding="utf8")).get("status") != "not_judged_executor_rate_limited":
            continue
        if out.exists():  # interrupted, or the executor hit a 429 (platform outcome, not a score): keep it, rerun
            tag = "ratelimited" if res.exists() else "interrupted"
            n = 1
            while out.with_name(out.name + ".%s-%d" % (tag, n)).exists():
                n += 1
            out.rename(out.with_name(out.name + ".%s-%d" % (tag, n)))
        print("=== pilot", t["paper"], t["type"], "ledger", ledger()["used_attempts"], flush=True)
        p = subprocess.run([PY, "-X", "utf8", "-u", str(DRIVER / "pilot_v310.py"), t["unit"], str(OUT)],
                           capture_output=True, text=True, encoding="utf8")
        row = next((json.loads(l[7:]) for l in p.stdout.splitlines() if l.startswith("RESULT ")),
                   {"status": "no_result", "stderr": p.stderr[-1500:]})
        summary["pilot"][t["task_id"]] = {**t, **row}
        print("PILOT", t["paper"], t["type"], row.get("judge_status") or row.get("status"), row.get("quality"), flush=True)
        save()
    print("V13-SCORING DONE", flush=True)


if __name__ == "__main__":
    main()
