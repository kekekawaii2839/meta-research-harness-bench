"""Zero-call plan for search set v1.3 scoring with judge v3.10.2, option B (user 2026-10-13).

From D:/mrhbench-local-pilot/v1_3-rejudge-pilot-estimate.json:
  * pilot (full P11 run, executor + judge v3.10.2): category pilot_never_run, plus every LIT task (library changed to v8);
  * rejudge (judge v3.10.2 on an existing run's evidence): pilot_again_prompt_changed + rejudge_only (non-LIT);
    an existing v3.10.x judgment on the same evidence (<run>/rejudge-v310, from the judge acceptance) is REUSED (0 calls).
Writes D:/mrhbench-local-pilot/v1_3-v3102-plan.json.
"""
import json
from pathlib import Path

B = Path(r"D:/mrhbench-local-pilot")
est = json.loads((B / "v1_3-rejudge-pilot-estimate.json").read_text(encoding="utf8"))


def quality(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf8")).get("quality")
    except Exception:
        return None


pilot, rejudge, reuse = [], [], []
for t in est["tasks"]:
    spec = "%s@%s" % (t["unit"].replace("\\", "/"), t["release"])
    if t["category"] == "pilot_never_run" or t["type"] == "LIT":
        pilot.append({"task_id": t["task_id"], "paper": t["paper"], "type": t["type"], "unit": spec})
        continue
    runs = [Path(r) for r in t["runs"]]
    done = [r for r in runs if quality(r / "rejudge-v310" / "judge_run_result.json") is not None]
    if done:
        reuse.append({"task_id": t["task_id"], "paper": t["paper"], "type": t["type"], "run": str(done[-1]),
                      "quality": quality(done[-1] / "rejudge-v310" / "judge_run_result.json")})
        continue
    # newest v3.6 judgment: prefer a rejudge-v36 subdir (current checks) over the run root
    cands = []
    for r in runs:
        if quality(r / "rejudge-v36" / "judge_run_result.json") is not None:
            cands.append((r.stat().st_mtime, str(r) + "#rejudge-v36"))
        elif quality(r / "judge_run_result.json") is not None:
            cands.append((r.stat().st_mtime, str(r)))
    if not cands:
        pilot.append({"task_id": t["task_id"], "paper": t["paper"], "type": t["type"], "unit": spec, "note": "no judged run"})
        continue
    rejudge.append({"task_id": t["task_id"], "paper": t["paper"], "type": t["type"], "pair": spec + "=" + sorted(cands)[-1][1]})
out = {"pilot": pilot, "rejudge": rejudge, "reuse": reuse}
(B / "v1_3-v3102-plan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8", newline="")
from collections import Counter
print("pilot", len(pilot), Counter(x["type"] for x in pilot))
print("rejudge", len(rejudge), Counter(x["type"] for x in rejudge))
print("reuse", len(reuse), [(x["paper"][9:13], x["type"], x["quality"]) for x in reuse])
