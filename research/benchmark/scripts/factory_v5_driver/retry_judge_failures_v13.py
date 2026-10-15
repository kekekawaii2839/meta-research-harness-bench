"""One judge retry for v1.3 scoring results that failed for a non-scientific reason (user 2026-10-14: "1吧，看起来是偶发现象").

Retried once (judge v3.10.2, same evidence, executor NOT re-run): status judge_attempt_failed whose message is
  * "Reference was never retrieved by this judge"  (judge miscopied a receipt/short ref; e.g. Bt1v EXP cited "R0"), or
  * "Required controller MCP server did not connect" (platform).
NOT retried: rejected_by_controller_gate (G1-G6: grading-quality rejections), awaiting_* reviews, other errors.
The failed attempt is kept as <dir>.failed-N. Re-judgments of existing runs: <run>/rejudge-v310; pilots: the pilot dir's
own evidence.json is re-judged into <pilot dir>/rejudge-v310 (the console prefers the newest current score).
Usage: python retry_judge_failures_v13.py [--dry]
"""
from pathlib import Path
import json
import subprocess
import sys

PY = r"D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe"
DRIVER = Path(__file__).resolve().parent
B = Path(r"D:/mrhbench-local-pilot")
RETRY = ("Reference was never retrieved by this judge", "Required controller MCP server did not connect")
# User 2026-10-14 ("确认追加额度并补评，v3.10.3可以做"): also retry once these listed gate rejections. Retries now run
# with judge v3.10.3 (LIT prompt adds rule 26: lit-* records are private and never feedback refs).
EXTRA_GATE_RETRY = {"iclr2025-pdF86dyoS6__EXP"}


def retryable(p):
    try:
        j = json.loads(Path(p).read_text(encoding="utf8"))
    except Exception:
        return False
    if j.get("status") == "rejected_by_controller_gate" and Path(p).parent.name in EXTRA_GATE_RETRY:
        return True
    return j.get("status") == "judge_attempt_failed" and any(m in (j.get("message") or "") for m in RETRY)


def keep(d):
    n = 1
    while d.with_name(d.name + ".failed-%d" % n).exists():
        n += 1
    d.rename(d.with_name(d.name + ".failed-%d" % n))
    (d.with_name(d.name + ".failed-%d" % n) / "FAILED_NOTE.json").write_text(json.dumps(
        {"reason": "judge attempt failed for a non-scientific reason; retried once (user 2026-10-14)"}), encoding="utf8")


def main(dry):
    plan = json.loads((B / "v1_3-v3102-plan.json").read_text(encoding="utf8"))
    pairs = []
    for r in plan["rejudge"]:
        run = Path(r["pair"].split("=", 1)[1].split("#", 1)[0])
        if retryable(run / "rejudge-v310" / "judge_run_result.json"):
            pairs.append((r["pair"], run / "rejudge-v310"))
    for t in plan["pilot"]:
        unit = Path(t["unit"].split("@", 1)[0])
        out = B / "p11-v13-v3102" / (unit.parents[1].name + "__" + unit.name)
        if retryable(out / "judge_run_result.json") and not (out / "rejudge-v310").exists():
            pairs.append((t["unit"] + "=" + str(out), None))
    print("retry", len(pairs), [p for p, _ in pairs])
    if dry or not pairs:
        return
    for _, old in pairs:
        if old is not None:
            keep(old)
    p = subprocess.run([PY, "-X", "utf8", "-u", str(DRIVER / "rejudge_v38.py"), "--judge", "v310", "--summary",
                        str(B / "v1_3-v3102-retry-summary.json")] + [p for p, _ in pairs], capture_output=True, text=True, encoding="utf8")
    print(p.stdout[-4000:], p.stderr[-1500:])


if __name__ == "__main__":
    main("--dry" in sys.argv)
