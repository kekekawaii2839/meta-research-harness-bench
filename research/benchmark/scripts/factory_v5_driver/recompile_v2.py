"""Zero-call recompilation of factory-v5 units into release-v2 with the tool-grant fix applied in-process.

The repo file research/benchmark/mrhbench/material_adapter.py is NOT modified: its source is read, the single
hard-coded tools line is replaced (same change as repo_merge/material_adapter_tools.patch), and the module is
re-executed in this process before anything imports compile_package. The applied patch and the original file
hash are recorded next to each new release. The previous release/ directory is kept untouched.
"""
from pathlib import Path
import sys

BENCH = Path(r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mrhbench.material_adapter as ma  # noqa: E402

OLD = '"tools": ["model_client", "artifact_read_write", "cpu_python_execution", "artifact_image_view"],'
NEW = ('"tools": ["artifact_read_write", "cpu_python_execution", "artifact_image_view"]'
       ' + (["literature.search", "literature.read", "literature.read_page"] if task["task_type"] == "LIT" else []),')
src = Path(ma.__file__).read_text(encoding="utf8")
if src.count(OLD) == 1:
    exec(compile(src.replace(OLD, NEW), ma.__file__, "exec"), ma.__dict__)
    PATCH_MODE = "in_process_patch_applied"
elif '"literature.search", "literature.read", "literature.read_page"' in src and '"model_client", "artifact_read_write"' not in src:
    PATCH_MODE = "repo_fix_already_committed_4ae8a9c_no_patch"
else:
    raise SystemExit("material_adapter source changed unexpectedly; review")

from mrhbench.io import read_json, write_json, file_hash  # noqa: E402
import factory_v5  # noqa: E402  (imports factory_runtime -> patched compile_package)


def recompile(root, pid, units):
    f = factory_v5.open_factory(root)
    out = []
    for unit in units:
        state = f.unit_state(pid, unit)
        wdir = f.wdir(state)
        final = f.final_output(state)
        package = read_json(final / "package.json")
        request = read_json(final.parent / "request.json")
        from mrhbench.factory_runtime import DEFAULT_BUDGETS
        from mrhbench.artifact_policy import make_collection_policy
        from mrhbench.material_adapter import task_container
        budgets, collections = {}, {}
        for t in package["tasks"]:
            d = DEFAULT_BUDGETS[t["task_type"]]
            budgets[t["task_id"]] = {"model_calls": d["model_calls"], "tool_calls": d["tool_calls"],
                                     "wall_seconds": task_container(t, package["environment"]["resources"])["wall_seconds"]}
            collections[t["task_id"]] = make_collection_policy(max_total_bytes=d["collection"][0], max_entries=d["collection"][1])
        rec = factory_v5.compile_identity_release(final, wdir / "release-v2", f.identity_map(state),
                                                  runtime_record=read_json(wdir / "runtime/runtime_record.json"),
                                                  package_slug=f.package_slug(state), source_manifest=request["sources"],
                                                  execution_budgets=budgets, artifact_collections=collections, per_task_resources=True)
        write_json(wdir / "release-v2" / "recompile_provenance.json", {
            "reason": "factory compile hard-coded one tool list for every task type: LIT lacked literature capability groups; "
                      "model_client is not a capability group (interface v4)",
            "in_process_patch": {"old": OLD, "new": NEW},
            "repo_material_adapter_sha256_unmodified": file_hash(Path(ma.__file__)),
            "repo_fix_pending_merge": "D:/mrhbench-local-pilot/factory-v5-driver/repo_merge/material_adapter_tools.patch",
            "previous_release_kept": str(wdir / "release"), "model_calls": 0}, exclusive=True)
        task = read_json(next((wdir / "release-v2/compiled").glob("task-*/task.json")))
        out.append((unit, rec["status"], [r["scan"]["status"] for r in rec["releases"]], task["public"]["tools"]))
    return out


if __name__ == "__main__":
    for row in recompile(Path(r"D:/mrhbench-local-pilot/factory-v5"), "iclr2025-qgsXsqahMq",
                         ["WRITE_EVIDENCE", "WRITE_CONTENT", "LIT", "IDEA"]):
        print(row)
