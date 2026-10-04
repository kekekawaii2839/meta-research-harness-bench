"""Execute an explicit evidence-bound controller tensor conversion plan (zero model calls)."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mrhbench.factory_data import convert_plan


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--paper", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--image-id", required=True)
    a = p.parse_args()
    result = convert_plan(a.paper, a.plan, a.output, image_id=a.image_id)
    print("Converted %d files; publication: %s" % (len(result["entries"]), a.output / "publication.json"))
