"""Stage source-only pilot jobs. No model invocation, Docker pull or acceptance."""
from pathlib import Path
import argparse
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.io import read_json, write_json
from mrhbench.material_pipeline import prepare_material_job

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--jobs", type=Path, default=ROOT / "materials/pilot_v2/jobs")
    args = parser.parse_args()
    results = []
    for file in sorted(args.jobs.glob("*.json")):
        job = read_json(file)
        results.append(prepare_material_job(job, ROOT.parents[1], args.destination / job["job_id"], ROOT / "prompts"))
    write_json(args.destination / "pilot_publication.json", {"jobs": results, "model_invoked": False}, exclusive=True)
    print({"prepared": len(results), "source_and_prompt_bytes": sum(r["published_bytes"] for r in results)})

if __name__ == "__main__":
    main()
