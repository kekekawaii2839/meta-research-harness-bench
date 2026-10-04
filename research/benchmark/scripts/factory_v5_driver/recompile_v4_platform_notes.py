"""Zero-call recompilation of compiled factory-v5 units into release-v4: adds platform notes to the task prompt.

Why (P11 batch2 review, 2026-09-30): task texts/contracts name deliverables as /work/<path>, but tool paths are
relative to the working directory and the frozen H0 rejects absolute paths, so executors lost calls on
"invalid path"; LIT task texts describe read(library_id, locator) while the platform tools are literature.search/
read/read_page. The notes state the platform conventions only; task content, assets, budgets and resources are
unchanged (same package bytes, same identity map, same runtime record, same release-v3 budgets).
The repo material_adapter.py is NOT modified: the prompt tail is extended in-process. Previous releases are kept.
Usage: python recompile_v4_platform_notes.py <paper_id>:<UNIT> ...
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recompile_v2 as r2  # noqa: E402  (tool-grant patch or confirms the committed repo fix)
ma = r2.ma
from mrhbench.io import read_json, write_json, file_hash  # noqa: E402

OLD_ITEM1 = ("1. Released paths: a document path written in the task files, such as assets/<...>, refers to the material "
             "package; its released copy is listed in asset_manifest with the extra prefix \"assets/\" (for example "
             "assets/assets/<...>) under the read-only public input root. Relative paths for your deliverables "
             "(for example submission/..., results/...) are inside your writable work directory.\n")
NEW_ITEM1 = ("1. Released paths: a document path written in the task files, such as assets/<...>, is also its path in "
             "asset_manifest; the file is mounted read-only at /inputs/public/<that path> (environment variable "
             "MRH_PUBLIC_ROOT=/inputs/public) for code you run, and is read through tools by asset id. Your working "
             "directory is /work and every artifact/CPU tool path is relative to it: wherever the task names "
             "/work/<path>, pass <path> to tools (for example results/x.json, not /work/results/x.json).\n")
LIT_NOTE = ("\nPlatform literature tools: literature.search(query, limit) returns document_id values (doc-<arXiv id>v<version>), "
            "titles, version dates and snippets; literature.read(document_id) returns the item record and abstract; "
            "literature.read_page(document_id, page_number) returns full-text pages whose text carries arXiv section/"
            "paragraph anchor markers such as [\u00a7S2.p3]. If the task text describes a different interface (e.g. "
            "read(library_id, locator)), it maps onto these tools: match each manifest item to its document by arXiv id, "
            "and cite the anchor markers as locators.")
ANCHOR = '"Experiment design choices remain yours within fixed method/assumptions and published resources.")'
NEW = (ANCHOR[:-1] + ' + (PLATFORM_LIT_NOTE if task["task_type"] == "LIT" else ""))')
src = Path(ma.__file__).read_text(encoding="utf8")
if src.count(ANCHOR) != 1:
    raise SystemExit("material_adapter prompt tail changed unexpectedly; review")
if r2.PATCH_MODE == "in_process_patch_applied":
    src = src.replace(r2.OLD, r2.NEW)
ma.PLATFORM_LIT_NOTE = LIT_NOTE
exec(compile(src.replace(ANCHOR, NEW), ma.__file__, "exec"), ma.__dict__)
import mrhbench.factory_runtime as fr  # noqa: E402
_orig_notes = fr.controller_notes


def controller_notes(*a, **k):
    text = _orig_notes(*a, **k)
    if text.count(OLD_ITEM1) != 1:
        raise SystemExit("controller_notes item 1 changed unexpectedly; review")
    return text.replace(OLD_ITEM1, NEW_ITEM1)


fr.controller_notes = controller_notes


def expected_prompt(prev_prompt, task_type):
    head, sep, tail = prev_prompt.partition("\nController publication notes")
    assert sep and tail.count(OLD_ITEM1) == 1
    return head + (LIT_NOTE if task_type == "LIT" else "") + sep + tail.replace(OLD_ITEM1, NEW_ITEM1)


def main(targets):
    f = r2.factory_v5.open_factory(Path(r"D:/mrhbench-local-pilot/factory-v5"))
    for t in targets:
        pid, unit = t.split(":")
        state = f.unit_state(pid, unit)
        wdir, final = f.wdir(state), f.final_output(state)
        if (wdir / "release-v4").exists():
            print(pid, unit, "release-v4 exists, skipped")
            continue
        prev = read_json(next((wdir / "release-v3/compiled").glob("task-*/task.json")))
        package, request = read_json(final / "package.json"), read_json(final.parent / "request.json")
        res = prev["public"]["resources"]
        budgets = {task["task_id"]: dict(res["execution_budget"]) for task in package["tasks"]}
        from mrhbench.artifact_policy import make_collection_policy
        ac = res["artifact_collection"]
        collections = {task["task_id"]: make_collection_policy(max_total_bytes=ac["max_total_bytes"], max_entries=ac["max_entries"])
                       for task in package["tasks"]}
        r2.factory_v5.compile_identity_release(final, wdir / "release-v4", f.identity_map(state),
                                               runtime_record=read_json(wdir / "runtime/runtime_record.json"),
                                               package_slug=f.package_slug(state), source_manifest=request["sources"],
                                               execution_budgets=budgets, artifact_collections=collections, per_task_resources=True)
        task = read_json(next((wdir / "release-v4/compiled").glob("task-*/task.json")))
        assert task["task_id"] == prev["task_id"], "opaque id must be stable"
        assert task["public"]["resources"] == prev["public"]["resources"], "resources must be unchanged"
        assert task["public"]["prompt"] == expected_prompt(prev["public"]["prompt"], unit), "only the platform notes may change"
        assert [a["sha256"] for a in task["assets"]] == [a["sha256"] for a in prev["assets"]], "assets must be unchanged"
        added = {"controller_note_1_before": OLD_ITEM1, "controller_note_1_after": NEW_ITEM1,
                 "lit_note_inserted": LIT_NOTE if unit == "LIT" else None}
        write_json(wdir / "release-v4/recompile_provenance.json", {
            "reason": "controller note 1 corrected (it described a double assets/ prefix the patched export no longer uses) and states the "
                      "/work/<p> -> <p> tool path convention; for LIT, the literature tool mapping is inserted "
                      "(P11 batch2 review 2026-09-30)", "prompt_changes": added,
            "unchanged": ["assets", "resources", "execution budgets", "task_id", "all task content before the note"],
            "based_on": "release-v3", "repo_material_adapter_sha256_unmodified": file_hash(Path(ma.__file__)),
            "model_calls_made": 0}, exclusive=True)
        print(pid[-10:], unit, "release-v4 ok")


if __name__ == "__main__":
    main(sys.argv[1:])
