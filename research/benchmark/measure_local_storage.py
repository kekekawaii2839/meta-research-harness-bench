"""Write an immutable timestamped storage snapshot without modifying Docker."""
import argparse
from pathlib import Path
from mrhbench.disk_audit import snapshot, comparison
from mrhbench.io import read_json, write_json

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--phase", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--before", type=Path)
    p.add_argument("--drive", action="append", default=[])
    p.add_argument("--extra-tree", type=Path, action="append", default=[])
    a = p.parse_args()
    record = snapshot(a.workspace, phase=a.phase, drives=a.drive, extra_trees=a.extra_tree)
    if a.before:
        record["comparison"] = comparison(read_json(a.before), record)
    write_json(a.output, record, exclusive=True)
    print({k: (v["status"], v["logical_bytes"]) for k, v in record["directories"].items()})
    print("Docker:", record["docker"]["status"])
