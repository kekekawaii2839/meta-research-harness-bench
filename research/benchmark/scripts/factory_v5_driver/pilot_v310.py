"""P11 pilot of ONE compiled task with judge v3.10.2 (search set v1.3, option B; user 2026-10-13).

Same flow as pilot_v5.run_task (frozen H0 v3 + Sonnet 4.6/low executor via the faithful wrapper, controller checks,
platform failure summary); only the judge differs: judge_v310.run_native_judge (v3.10.2) instead of the v3.6 path.
LIT tasks use their lit_corpus_configuration.json (frozen shared-library-v8 since T17).
Usage: python pilot_v310.py <unit_dir>@<release> <out_root> [--dry-run]
"""
from pathlib import Path
import json
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import platform_patches  # noqa: F401  (must precede mrhbench imports)
import pilot_v5  # noqa: E402
import judge_v310  # noqa: E402
from mrhbench.io import read_json  # noqa: E402

HARNESS = r"D:/mrhbench-local-pilot/h0-claude-frozen-v3/harness.py"
HARNESS_SHA = "619dc7240d7d0437e6f449319adcf710e2c13ffa2220bb45e5f06e343309b181"
ROLES = r"D:/mrhbench-local-pilot/factory-v5-driver/config/role_transport_sonnet46low_executor.json"


def _judge(**kw):
    return judge_v310.run_native_judge(**kw, run_dir=Path(kw["output"]).parent / "execution")


pilot_v5.sc.run_native_judge = _judge  # run_task calls sc.run_native_judge


def main():
    spec, out_root = sys.argv[1], Path(sys.argv[2])
    dry = "--dry-run" in sys.argv
    unit, rel = spec.split("@", 1)
    unit = Path(unit)
    if pilot_v5.file_hash(Path(HARNESS)) != HARNESS_SHA:
        raise SystemExit("frozen H0 hash mismatch")
    judge_v310.CHECKS_SPEC = read_json(unit / "checks.json")["checks"]
    out = out_root / (unit.parents[1].name + "__" + unit.name)
    try:
        row = pilot_v5.run_task(unit, HARNESS, out, ROLES, dry_run=dry, release=rel)
        row["judge_version"] = judge_v310.VERSION
    except Exception as exc:
        row = {"unit": str(unit), "status": "stage_failed", "error": "%s: %s" % (type(exc).__name__, str(exc)[:500])}
    row.update(unit_spec=spec, output=str(out))
    print("RESULT " + json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
