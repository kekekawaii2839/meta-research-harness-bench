"""Zero-call controller amendment (2026-10-01, user option A): accept a paid source adjudication rejected only because a
citation named the controller-published source_manifest.json. Re-runs every post-call check of stage_adjudication with
the v6 _check_ids (manifest citation allowed, all other unknown ids still fail) and records the stage with its call id.
Usage: <factory root> <project id> <native call dir>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import factory_v6, factory_v5
from mrhbench.io import read_json, write_json, file_hash, utc_now
from mrhbench.factory import TASK_TYPES
import jsonschema

root, pid, call_dir = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
f = factory_v5.open_factory(root)
state = f.state(pid)
prev = state["stages"]["adjudication"]
assert prev["status"] == "failed_needs_attribution" and prev["notes"] == ["ProtocolError: Unknown source_id cited: source_manifest.json"], prev
res = read_json(call_dir / "result.json"); audit_s = read_json(call_dir / "stream_audit.json")
assert res["status"] == "completed" and audit_s["status"] == "development_admissible"
pdir = f.paper_dir(pid); ws = pdir / "adjudication"
out = read_json(ws / "adjudication.json")
jsonschema.validate(out, read_json(ws / "adjudication.schema.json"))
manifest = read_json(ws / "source_manifest.json")
try:
    factory_v5.FactoryV5._check_ids(out, pid, manifest); raise AssertionError("v5 check unexpectedly passes")
except Exception as e:
    assert "source_manifest.json" in str(e)
f._check_ids(out, pid, manifest)  # v6 rule
audit = read_json(pdir / "source_audit" / "source_audit.json")
assert not ({a["ambiguity_id"] for a in audit["ambiguities"]} - {d["ambiguity_id"] for d in out["ambiguity_decisions"]})
assert out["decision"] != "construct" or (out["requested_task_types"] and out["scope_request"].strip())
assert not ((set(TASK_TYPES) - set(out["requested_task_types"])) - set(out["unrequested_reasons"]))
assert out["decision"] != "construct" or set(out.get("task_scopes") or {}) == set(out["requested_task_types"])
write_json(ws / "admissibility_amendment.json", {"rule": "factory-v6 metadata-citation rule (user decision 2026-10-01, option A; source_manifest.json, candidate.json, source_audit.json)",
           "at": utc_now(), "ledger_call_id": res["call_id"], "native_call_dir": str(call_dir), "output_sha256": file_hash(ws / "adjudication.json"),
           "v5_check_error": prev["notes"][0], "all_other_post_call_checks": "passed", "model_calls_made": 0}, exclusive=True)
state.setdefault("history", []).append({"stage": "adjudication", **state["stages"].pop("adjudication"), "set_aside": utc_now(),
                                        "set_aside_reason": "accepted under factory-v6 metadata-citation rule"})
status = "completed" if out["decision"] == "construct" else "dropped"
f._record(state, "adjudication", status, {"adjudication": "adjudication/adjudication.json",
          "admissibility_amendment": "adjudication/admissibility_amendment.json"}, [res["call_id"]],
          ([out["drop_reason"]] if status == "dropped" else ["requested " + ",".join(out["requested_task_types"])]) +
          ["accepted under metadata-citation rule (cited source_manifest.json version dates and candidate.json abstract)"])
print(pid, status, out.get("requested_task_types"))
