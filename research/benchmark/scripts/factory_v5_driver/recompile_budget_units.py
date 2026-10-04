"""Zero-call recompilation of compiled factory-v5 units into release-v3 with the measured per-type executor budgets.

Budgets carry over the one measured adjustment made on the GETS pilot (WRITE_CONTENT 4->10, IDEA 6->10, LIT 12->30;
EXP 16 and WRITE_EVIDENCE 12 unchanged) as starting values for these new tasks; the next pilot measures them again.
Tool budgets, physical resources, walltime and all task content stay unchanged. Existing release dirs are kept.
Usage: python recompile_budget_units.py <paper_id>:<UNIT> ...
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recompile_v2 as r2  # noqa: E402  (tool-grant patch or confirms the committed repo fix)
from mrhbench.io import read_json, write_json, file_hash  # noqa: E402

MODEL_CALLS = {"EXP": 16, "WRITE_EVIDENCE": 12, "WRITE_CONTENT": 10, "IDEA": 10, "LIT": 30}


def main(targets):
    f = r2.factory_v5.open_factory(Path(r"D:/mrhbench-local-pilot/factory-v5"))
    from mrhbench.factory_runtime import DEFAULT_BUDGETS
    from mrhbench.artifact_policy import make_collection_policy
    from mrhbench.material_adapter import task_container
    for t in targets:
        pid, unit = t.split(":")
        state = f.unit_state(pid, unit)
        wdir, final = f.wdir(state), f.final_output(state)
        if (wdir / "release-v3").exists():
            print(pid, unit, "release-v3 exists, skipped")
            continue
        package, request = read_json(final / "package.json"), read_json(final.parent / "request.json")
        budgets, collections = {}, {}
        for task in package["tasks"]:
            d = DEFAULT_BUDGETS[task["task_type"]]
            budgets[task["task_id"]] = {"model_calls": MODEL_CALLS[task["task_type"]], "tool_calls": d["tool_calls"],
                                        "wall_seconds": task_container(task, package["environment"]["resources"])["wall_seconds"]}
            collections[task["task_id"]] = make_collection_policy(max_total_bytes=d["collection"][0], max_entries=d["collection"][1])
        r2.factory_v5.compile_identity_release(final, wdir / "release-v3", f.identity_map(state),
                                               runtime_record=read_json(wdir / "runtime/runtime_record.json"),
                                               package_slug=f.package_slug(state), source_manifest=request["sources"],
                                               execution_budgets=budgets, artifact_collections=collections, per_task_resources=True)
        write_json(wdir / "release-v3/recompile_provenance.json", {
            "reason": "per-type executor budgets carried over from the GETS pilot measurement (user decision 2026-09-28 principle)",
            "model_calls": MODEL_CALLS[unit], "default_before": DEFAULT_BUDGETS[unit]["model_calls"],
            "unchanged": ["tool_calls", "physical resources", "wall_seconds", "all task content"],
            "tool_grant_source": r2.PATCH_MODE, "material_adapter_sha256": file_hash(Path(r2.ma.__file__)),
            "previous_releases_kept": ["release"], "model_calls_made": 0}, exclusive=True)
        task = read_json(next((wdir / "release-v3/compiled").glob("task-*/task.json")))
        print(pid[-10:], unit, task["public"]["resources"]["execution_budget"], task["public"]["tools"][-1])


if __name__ == "__main__":
    main(sys.argv[1:])
