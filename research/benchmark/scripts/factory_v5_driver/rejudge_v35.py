"""Re-judge finished P11 task runs with judge v3.5 (one judge call each; originals kept).

Usage: python rejudge_v35.py [--dry-run] --roles <roles.json> <run_dir/paper__UNIT> ...
Each task dir must hold execution/submission.json and evidence.json. The unit dir and release are derived from
the dir name and the run's task id (the release whose compiled task id equals public/task.json task_id, v3 first).
--dry-run builds evidence/checks/summary and the v3.5 policy text only (zero model calls). Stops at the first 429.
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_v5  # noqa: E402  (platform_patches + judge_v35 applied)
from mrhbench.io import read_json, write_json  # noqa: E402
import mrhbench.native_judge as nj  # noqa: E402

PAPER_ROOTS = [Path("D:/mrhbench-local-pilot/%s/papers" % r) for r in ("factory-v5", "factory-v6", "factory-v7")]


def locate(task_dir):
    """The unit + release whose compiled task id matches the run (searches factory-v5/v6/v7, any release-*)."""
    pid, unit = task_dir.name.split("__")
    tid = read_json(task_dir / "public/task.json")["task_id"]
    for papers in PAPER_ROOTS:
        udir = papers / pid / "units" / unit
        if not udir.is_dir():
            continue
        # prefer the release the unit state records as current (maintenance repairs keep the opaque task id)
        cur = (((read_json(udir / "state.json")["stages"].get("compile") or {}).get("artifacts") or {}).get("identity_release") or "").split("/")[0]
        cands = ([udir / cur] if cur else []) + sorted(udir.glob("release*"), key=lambda r: r.stat().st_mtime, reverse=True)
        for rdir in cands:
            if (rdir / "compiled" / tid).is_dir():
                return udir, rdir.name
    raise SystemExit("no release with task id %s for %s" % (tid, task_dir))


def main(argv):
    dry = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]
    roles = argv[argv.index("--roles") + 1]
    dirs = [Path(a) for i, a in enumerate(argv) if a != "--roles" and (i == 0 or argv[i - 1] != "--roles")]
    for d in dirs:
        udir, rel = locate(d)
        if dry:
            summary = pilot_v5.judge_v35.platform_failure_summary(d / "execution")
            print(d.parent.name, d.name, rel, "failed_rpcs", len(summary["failed_rpcs"]), summary["controller_error_classes"],
                  "container_events", len(summary["container_events"]), "v3.5 rules in policy:", "judge v3.5" in nj.claude_common(), nj.CLAUDE_VERSION)
            continue
        led = read_json(pilot_v5.LEDGER)["attempts"]
        r = pilot_v5.rejudge(udir, d, roles, rel)
        print(json.dumps({"dir": str(d), **{k: r[k] for k in ("judge_status", "quality")}}), flush=True)
        new = read_json(pilot_v5.LEDGER)["attempts"][len(led):]
        if any("provider_rate_limit" in json.dumps(x) or "HTTP 429" in json.dumps(x) for x in new):
            print("STOP: rate limited"); return


if __name__ == "__main__":
    main(sys.argv[1:])
