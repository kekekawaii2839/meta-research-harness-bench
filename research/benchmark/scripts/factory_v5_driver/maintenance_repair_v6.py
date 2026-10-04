"""Maintenance repair of one factory-v6 unit that failed a gate (user decision 2026-10-02, +50 calls).

Same standard pipeline path as maintenance_repair.py (v5): the controller writes a repair request (author
"controller_maintenance") whose notes are the ACCEPTED findings of the unit's last independent review (observed issue +
the reviewer's repair action, verbatim) plus explicit controller notes; then one more incremental repair round:
constructor -> independent reviewer -> adjudicator (pass/drop only), all through the v6 wrappers; then the runtime gate
(v6 leak rule A applies) and a v6 compile (frozen budgets, platform lint) from the repaired output. 3 model calls.
Earlier batches are kept. Usage:
  python maintenance_repair_v6.py notes <paper_id>:<UNIT> [extra_notes.txt]   -> writes maintenance_notes_v6/<pid>__<UNIT>.json (0 calls)
  python maintenance_repair_v6.py run <paper_id>:<UNIT>                       -> runs the maintenance round (3 calls)
  python maintenance_repair_v6.py materialize <paper_id>:<UNIT>               -> controller asset copies (0 calls)
"""
from pathlib import Path
import json
import shutil
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import factory_v6  # noqa: E402  (imports platform_patches, release-v5 notes, admissibility + leak rules)
import factory_v5  # noqa: E402
from mrhbench.io import read_json, write_json, file_hash, utc_now, contained, ProtocolError  # noqa: E402
from mrhbench.factory import DONE  # noqa: E402

import os
ROOT = Path(os.environ.get("MRH_FACTORY_ROOT", r"D:/mrhbench-local-pilot/factory-v6"))  # factory-v5 units: set MRH_FACTORY_ROOT
# Sensitivity Verification EXP: the repair round failed only on the structural check because the renamed model files
# did not exist (constructors cannot copy files); its output holds the mapping, so it is the maintenance seed.
_OVERRIDE = {"iclr2025-h0vC0fm1q7:EXP": "repair"}
NOTES_DIR = DRIVER / ("maintenance_notes_v6" if ROOT.name == "factory-v6" else "maintenance_notes_" + ROOT.name)
BATCH, ADJ, REQ = "maint1", "maint1_adjudication", "maint1_request"
LAST = (("maint2", "maint2_adjudication"), ("maint1", "maint1_adjudication"), ("repair2", "repair2_adjudication"),
        ("repair", "repair_adjudication"), ("construct", "review_adjudication"))


SOURCE_OVERRIDE = dict(_OVERRIDE)  # "<pid>:<UNIT>" -> batch whose output is the maintenance seed


def _last_batch(f, state, target=None):
    if target in SOURCE_OVERRIDE:
        b = SOURCE_OVERRIDE[target]
        return b, dict(LAST)[b]
    for batch, adj in LAST:
        if state["stages"].get(batch, {}).get("status") == "completed" and (f.wdir(state) / batch).exists():
            return batch, adj
    raise ProtocolError("no completed construction batch")


def accepted_findings(f, state, target=None):
    wdir = f.wdir(state)
    batch, adj = _last_batch(f, state, target)
    rv = list((wdir / batch).glob("*/reviewer/review.json"))
    if not rv:  # the round stopped before its reviewer ran (e.g. structural check): only controller notes apply
        return batch, adj, []
    review = read_json(rv[0])
    adj_path = wdir / adj / "review_adjudication.json"
    decisions = read_json(adj_path)["finding_decisions"] if adj_path.exists() else []
    acc = {d["finding_index"] for d in decisions if d.get("decision") == "accept"} if decisions else set(range(len(review["findings"])))
    out = []
    for i, fnd in enumerate(review["findings"]):
        if i in acc:
            out.append("[reviewer finding %s, %s] %s\nRequired repair: %s" % (fnd.get("id", i), fnd.get("severity", ""),
                       fnd.get("observed_issue", "").strip(), (fnd.get("repair_action") or "").strip()))
    for d in decisions:  # findings the adjudicator raised itself (no reviewer finding index)
        if d.get("decision") == "accept" and d.get("finding_index") is None:
            out.append("[adjudicator finding, %s] %s" % (d.get("severity", ""), (d.get("rationale") or "").strip()))
    return batch, adj, out


def cmd_notes(target, extra_path=None):
    pid, unit = target.split(":")
    f = factory_v6.open_factory(ROOT)
    state = f.unit_state(pid, unit)
    batch, adj, notes = accepted_findings(f, state, target)
    extra = [n.strip() for n in Path(extra_path).read_text(encoding="utf8").split("\n\n") if n.strip()] if extra_path else []
    NOTES_DIR.mkdir(exist_ok=True)
    rec = {"target": target, "source_batch": batch, "source_adjudication": adj, "accepted_review_findings": notes,
           "controller_notes": extra, "created_at": utc_now()}
    write_json(NOTES_DIR / ("%s__%s.json" % (pid, unit)), rec)
    print(json.dumps(rec, ensure_ascii=False, indent=1)[:3000])


def cmd_materialize(target):
    """Byte-copy prepopulated controller assets to the neutral public names the constructor's
    controller_asset_materialization mapping requests (constructors have no shell and cannot copy files)."""
    pid, unit = target.split(":")
    f = factory_v6.open_factory(ROOT)
    state = f.unit_state(pid, unit)
    batch, _ = _last_batch(f, state, target)
    out = next((f.wdir(state) / batch).glob("*/constructor/output"))
    done = []
    for t in read_json(out / "package.json")["tasks"]:
        m = t.get("controller_asset_materialization") or {}
        for row in m.get("mappings", []):
            src, dst = row["prepopulated_path"], row["public_path"]
            if not (src.startswith("assets/") and dst.startswith("assets/")) or ".." in src + dst:
                raise ProtocolError("materialization path outside assets/")
            s, d = contained(out, src, must_exist=True), contained(out, dst)
            if file_hash(s) != row["sha256"]:
                raise ProtocolError("prepopulated asset hash mismatch: " + src)
            if d.exists():
                if file_hash(d) != row["sha256"]:
                    raise ProtocolError("existing public asset differs: " + dst)
            else:
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(s, d)
            done.append({"from": src, "to": dst, "sha256": row["sha256"]})
    write_json(f.wdir(state) / "controller_materialization.json", {"at": utc_now(), "output": str(out), "copies": done,
               "note": "controller byte copies for the constructor's controller_asset_materialization mapping; hash-verified; no other file changed",
               "model_calls_made": 0}, exclusive=True)
    print("materialized", len(done), "files into", out)


def _compile(f, state, final, runtime_record, batch="maint1"):
    from mrhbench.factory_runtime import DEFAULT_BUDGETS
    from mrhbench.artifact_policy import make_collection_policy
    from mrhbench.material_adapter import task_container
    import task_platform_lint
    wdir = f.wdir(state)
    frozen = read_json(factory_v6.BUDGET_FREEZE)["frozen_model_calls"]
    package, request = read_json(final / "package.json"), read_json(final.parent / "request.json")
    budgets, collections = {}, {}
    for t in package["tasks"]:
        d = DEFAULT_BUDGETS[t["task_type"]]
        budgets[t["task_id"]] = {"model_calls": frozen[t["task_type"]], "tool_calls": d["tool_calls"],
                                 "wall_seconds": task_container(t, package["environment"]["resources"])["wall_seconds"]}
        collections[t["task_id"]] = make_collection_policy(max_total_bytes=d["collection"][0], max_entries=d["collection"][1])
    rel = "release" if not (wdir / "release").exists() else "release-" + batch
    record = factory_v5.compile_identity_release(final, wdir / rel, f.identity_map(state), runtime_record=runtime_record,
                                                 package_slug=f.package_slug(state), source_manifest=request["sources"],
                                                 execution_budgets=budgets, artifact_collections=collections, per_task_resources=True)
    lint = [task_platform_lint.lint(p.parent) for p in sorted((wdir / rel / "compiled").glob("task-*/task.json"))]
    write_json(wdir / "platform_lint.json", {"tasks": lint, "release": rel})
    n = sum(len(r["findings"]) for r in lint)
    if "compile" in state["stages"]:
        state.setdefault("history", []).append({"stage": "compile", **state["stages"].pop("compile"), "set_aside": utc_now()})
    if "withdrawn" in state["stages"]:  # a withdrawn release is superseded by this repaired one
        state.setdefault("history", []).append({"stage": "withdrawn", **state["stages"].pop("withdrawn"), "set_aside": utc_now(), "superseded_by": rel})
    f._record(state, "compile", DONE, {"identity_release": rel + "/identity_release_record.json", "platform_lint": "platform_lint.json"},
              notes=["maintenance repair release %s: %d task(s), semantic gates pending; platform lint %d finding(s)" % (rel, len(record["releases"]), n)])
    print("compiled", rel, "lint findings", n)


def cmd_run(target, rebuild=False):
    pid, unit = target.split(":")
    f = factory_v6.open_factory(ROOT, max_calls=3)
    state = f.unit_state(pid, unit)
    if state["stages"].get("compile", {}).get("status") == "completed" and not rebuild:
        raise ProtocolError("unit already compiled (use rebuild for a changed source set)")
    wdir = f.wdir(state)
    n = 1
    while (wdir / ("maint%d" % n)).exists() or (wdir / ("maint%d_request" % n)).exists():
        n += 1
    BATCH, ADJ, REQ = "maint%d" % n, "maint%d_adjudication" % n, "maint%d_request" % n
    factory_v5.ROUND_OF_BATCH[BATCH] = 3  # maintenance rounds are final rounds: adjudicator may only pass or drop
    rec = read_json(NOTES_DIR / ("%s__%s.json" % (pid, unit)))
    notes = rec["accepted_review_findings"] + rec["controller_notes"]
    write_json(wdir / REQ / "review_adjudication.json", {
        "schema_version": "factory-review-adjudication-1", "project_id": state["project_id"], "round": 3,
        "finding_decisions": [], "action": "repair", "repair_notes": notes, "drop_reason": None, "excluded_task_ids": [],
        "author": "controller_maintenance", "source_batch": rec["source_batch"],
        "evidence": "accepted findings of %s/%s (independent review) + controller notes" % (rec["source_batch"], rec["source_adjudication"])},
        exclusive=True)
    f._repair(state, BATCH, rec["source_batch"], REQ, "job_%s.json" % BATCH)
    st = state["stages"][BATCH]
    print("repair batch:", st["status"], st.get("notes"))
    if st["status"] != "completed":
        return
    out = f._review_adjudication(state, ADJ, BATCH, 3)
    print("adjudication:", out["action"], (out.get("drop_reason") or "")[:300])
    if out["action"] not in ("pass", "pass_partial"):
        return
    final = wdir / BATCH / f.job_id(state) / "constructor" / "output"
    record = f.runtime.verify_runtime(final, read_json(final / "package.json"), wdir / ("runtime-" + BATCH), package_slug=f.package_slug(state))
    print("runtime:", record["status"], record.get("reasons"))
    if record["status"] != "passed":
        return
    _compile(f, state, final, record, BATCH)


if __name__ == "__main__":
    {"notes": lambda: cmd_notes(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None),
     "run": lambda: cmd_run(sys.argv[2]), "rebuild": lambda: cmd_run(sys.argv[2], rebuild=True), "materialize": lambda: cmd_materialize(sys.argv[2])}[sys.argv[1]]()
