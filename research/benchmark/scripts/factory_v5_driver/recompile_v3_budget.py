"""Zero-call recompilation into release-v3 with a measured executor-budget adjustment (user decision 2026-09-28).

Principle (user-approved): executor model/tool-call budgets belong to each task, are proposed at construction,
measured once by the P11 pilot, adjusted once when clearly insufficient, then frozen for every harness.
Here the maintainer applies the one adjustment for GETS WRITE_CONTENT and IDEA from pilot p11-v5-gets-001:
both ended with 'model_calls_reserved_for_finalisation' (WC 4 calls: only one of two required files written;
IDEA 6 calls). Tool-call budgets, physical resources and all content stay unchanged. Same in-process tool-grant
patch as release-v2 (repo fix since committed as 4ae8a9c, applied identically here for byte stability).
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recompile_v2 as r2  # noqa: E402  (applies the in-process tool patch on import)
from mrhbench.io import read_json, write_json, file_hash  # noqa: E402

MODEL_CALLS = {"WRITE_CONTENT": 10, "IDEA": 10, "LIT": 30}
EVIDENCE = "D:/mrhbench-local-pilot/p11-v5-gets-001"


def main():
    f = r2.factory_v5.open_factory(Path(r"D:/mrhbench-local-pilot/factory-v5"))
    from mrhbench.factory_runtime import DEFAULT_BUDGETS
    from mrhbench.artifact_policy import make_collection_policy
    from mrhbench.material_adapter import task_container
    import sys as _s
    only = _s.argv[1:] or list(MODEL_CALLS)
    for unit, calls in MODEL_CALLS.items():
        if unit not in only:
            continue
        state = f.unit_state("iclr2025-qgsXsqahMq", unit)
        wdir, final = f.wdir(state), f.final_output(state)
        package, request = read_json(final / "package.json"), read_json(final.parent / "request.json")
        budgets, collections = {}, {}
        for t in package["tasks"]:
            d = DEFAULT_BUDGETS[t["task_type"]]
            budgets[t["task_id"]] = {"model_calls": calls, "tool_calls": d["tool_calls"],
                                     "wall_seconds": task_container(t, package["environment"]["resources"])["wall_seconds"]}
            collections[t["task_id"]] = make_collection_policy(max_total_bytes=d["collection"][0], max_entries=d["collection"][1])
        rec = r2.factory_v5.compile_identity_release(final, wdir / "release-v3", f.identity_map(state),
                                                     runtime_record=read_json(wdir / "runtime/runtime_record.json"),
                                                     package_slug=f.package_slug(state), source_manifest=request["sources"],
                                                     execution_budgets=budgets, artifact_collections=collections, per_task_resources=True)
        write_json(wdir / "release-v3/recompile_provenance.json", {
            "reason": "one measured executor-budget adjustment (user decision 2026-09-28)",
            "model_calls": {"before": DEFAULT_BUDGETS[unit]["model_calls"], "after": calls},
            "evidence": (EVIDENCE + "/" + unit) if unit != "LIT" else "D:/mrhbench-local-pilot/p11-v5-gets-001/LIT and p11-v5-gets-003/LIT (all 11 of 12 calls used; 1 document read, 0 pages)", "unchanged": ["tool_calls", "physical resources", "wall_seconds", "all task content"],
            "tool_grant_source": r2.PATCH_MODE, "material_adapter_sha256": file_hash(Path(r2.ma.__file__)), "previous_releases_kept": ["release", "release-v2"],
            "model_calls_made": 0}, exclusive=True)
        task = read_json(next((wdir / "release-v3/compiled").glob("task-*/task.json")))
        print(unit, rec["status"], task["public"]["resources"]["execution_budget"], task["public"]["tools"])


if __name__ == "__main__":
    main()
