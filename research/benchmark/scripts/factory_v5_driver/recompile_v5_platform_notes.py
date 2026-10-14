"""Zero-call recompilation of factory-v5 units into release-v5 (release-v4 platform notes, LIT note corrected).

release-v5 vs release-v4 (P11 review, 2026-09-30):
  * the LIT literature-tool note no longer prints a concrete example anchor: executors copied the example
    "[\u00a7S2.p3]" into citations although no cited paper had that anchor. It now says to copy the nearest
    preceding marker exactly and never construct an anchor;
  * a unit whose material was maintenance-repaired (maintenance_repair.py) compiles from that repaired output
    (--final <constructor output dir>); its assets/prompt then legitimately differ from release-v3.
Everything else as release-v4: controller note 1 corrected (single assets/ prefix, /work/<p> -> <p> tool paths),
release-v3 budgets/collection limits, same identity map and task ids. The repo material_adapter.py is NOT
modified (prompt tail extended in-process). Previous releases are kept.
Usage: python recompile_v5_platform_notes.py [--final <dir>] <paper_id>:<UNIT> ...
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
            "literature.read_page(document_id, page_number) returns full-text pages whose text carries bracketed arXiv "
            "section/paragraph anchor markers beginning with \u00a7. If the task text describes a different interface, it "
            "maps onto these tools: match each manifest item to its document by arXiv id. To cite a passage, copy the "
            "nearest anchor marker that precedes it on the page you read, exactly as printed; never construct an anchor "
            "that does not appear in the text.")
ANCHOR = '"Experiment design choices remain yours within fixed method/assumptions and published resources.")'
NEW = (ANCHOR[:-1] + ' + (PLATFORM_LIT_NOTE if task["task_type"] == "LIT" else ""))')
src = Path(ma.__file__).read_text(encoding="utf8")
if getattr(ma, "PLATFORM_LIT_NOTE", None) == LIT_NOTE and src.count(NEW) == 1:
    LIT_NOTE_MODE = "repo_fixed_e43ca03_no_patch"  # core PATCH 7 committed the same LIT note
else:
    if src.count(ANCHOR) != 1:
        raise SystemExit("material_adapter prompt tail changed unexpectedly; review")
    if r2.PATCH_MODE == "in_process_patch_applied":
        src = src.replace(r2.OLD, r2.NEW)
    ma.PLATFORM_LIT_NOTE = LIT_NOTE
    exec(compile(src.replace(ANCHOR, NEW), ma.__file__, "exec"), ma.__dict__)
    LIT_NOTE_MODE = "in_process_patch_applied"
import mrhbench.factory_runtime as fr  # noqa: E402
_orig_notes = fr.controller_notes


def controller_notes(*a, **k):
    text = _orig_notes(*a, **k)
    if text.count(NEW_ITEM1) == 1 and OLD_ITEM1 not in text:
        return text  # core PATCH 7 (e43ca03) already emits the corrected item 1
    if text.count(OLD_ITEM1) != 1:
        raise SystemExit("controller_notes item 1 changed unexpectedly; review")
    return text.replace(OLD_ITEM1, NEW_ITEM1)


fr.controller_notes = controller_notes


def expected_prompt(prev_prompt, task_type):
    head, sep, tail = prev_prompt.partition("\nController publication notes")
    assert sep and tail.count(OLD_ITEM1) == 1
    return head + (LIT_NOTE if task_type == "LIT" else "") + sep + tail.replace(OLD_ITEM1, NEW_ITEM1)


def main(targets, final_override=None, runtime_record=None, release="release-v5"):
    f = r2.factory_v5.open_factory(Path(r"D:/mrhbench-local-pilot/factory-v5"))
    for t in targets:
        pid, unit = t.split(":")
        state = f.unit_state(pid, unit)
        wdir = f.wdir(state)
        final = Path(final_override) if final_override else f.final_output(state)
        if (wdir / release).exists():
            print(pid, unit, release, "exists, skipped")
            continue
        prev = read_json(next((wdir / "release-v3/compiled").glob("task-*/task.json")))
        package, request = read_json(final / "package.json"), read_json(final.parent / "request.json")
        res = prev["public"]["resources"]
        budgets = {task["task_id"]: dict(res["execution_budget"]) for task in package["tasks"]}
        from mrhbench.artifact_policy import make_collection_policy
        ac = res["artifact_collection"]
        collections = {task["task_id"]: make_collection_policy(max_total_bytes=ac["max_total_bytes"], max_entries=ac["max_entries"])
                       for task in package["tasks"]}
        rt = Path(runtime_record) if runtime_record else wdir / "runtime/runtime_record.json"
        r2.factory_v5.compile_identity_release(final, wdir / release, f.identity_map(state),
                                               runtime_record=read_json(rt),
                                               package_slug=f.package_slug(state), source_manifest=request["sources"],
                                               execution_budgets=budgets, artifact_collections=collections, per_task_resources=True)
        task = read_json(next((wdir / release / "compiled").glob("task-*/task.json")))
        assert task["task_id"] == prev["task_id"], "opaque id must be stable"
        assert task["public"]["resources"]["execution_budget"] == res["execution_budget"], "budget must be unchanged"
        if not final_override:
            assert task["public"]["resources"] == res, "resources must be unchanged"
            assert task["public"]["prompt"] == expected_prompt(prev["public"]["prompt"], unit), "only the platform notes may change"
            assert [a["sha256"] for a in task["assets"]] == [a["sha256"] for a in prev["assets"]], "assets must be unchanged"
        write_json(wdir / release / "recompile_provenance.json", {
            "reason": "release-v4 platform notes with the LIT note corrected (no example anchor; copy the nearest preceding "
                      "marker exactly). P11 review 2026-09-30",
            "controller_note_1_before": OLD_ITEM1, "controller_note_1_after": NEW_ITEM1,
            "lit_note_inserted": LIT_NOTE if unit == "LIT" else None,
            "compiled_from": str(final), "runtime_record": str(rt),
            "material_maintenance_repaired": bool(final_override),
            "unchanged": ["execution budgets", "task_id"] + ([] if final_override else ["assets", "resources", "task content"]),
            "based_on": "release-v3 budgets", "repo_material_adapter_sha256_unmodified": file_hash(Path(ma.__file__)),
            "model_calls_made": 0}, exclusive=True)
        print(pid[-10:], unit, release, "ok", final)


if __name__ == "__main__":
    args = sys.argv[1:]
    kw = {}
    for flag, key in (("--final", "final_override"), ("--runtime-record", "runtime_record")):
        if flag in args:
            i = args.index(flag)
            kw[key] = args[i + 1]
            del args[i:i + 2]
    main(args, **kw)
