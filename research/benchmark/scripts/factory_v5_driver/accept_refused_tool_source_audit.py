"""Zero-call controller amendment (2026-10-01, user option A): accept the paid source audit of a paper whose session was
rejected only because the model emitted a tool call the CLI refused as unavailable. Re-assesses the exact saved stream
with admissibility_v6, re-validates the saved output (schema + source-id check), and records the stage with the original
ledger call id. The ledger entry itself is not modified. Usage: <factory root> <project id> <native call dir> <ledger id>"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import factory_v6, factory_v5, admissibility_v6
import mrhbench.claude_transport as ct
from mrhbench.io import read_json, write_json, file_hash, utc_now
import jsonschema

root, pid, call_dir, call_id = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), int(sys.argv[4])
parsed = ct.parse_stream((call_dir / "events.jsonl").read_text(encoding="utf8"))
allowed = read_json(call_dir / "stream_audit.json")["declared_tools"]
orig = admissibility_v6._orig(parsed, allowed_tools=allowed)
new = ct.assess_claude_admissibility(parsed, allowed_tools=allowed)
assert orig["status"] == "rejected_observed_activity" and new["status"] == "development_admissible", (orig["status"], new["status"])
# negative controls on copies of the same stream: a non-error result or a declared tool must still reject
import copy
for label, mutate in (("non_error_result", "is_error"), ("tool_declared_at_init", "declare")):
    p2 = copy.deepcopy(parsed)
    tid = new["refused_unavailable_tool_calls"][0]["id"]; name = new["refused_unavailable_tool_calls"][0]["name"]
    if mutate == "is_error":
        for e in p2["events"]:
            for b in ((e.get("message") or {}).get("content") or []) if isinstance((e.get("message") or {}).get("content"), list) else []:
                if b.get("tool_use_id") == tid: b["is_error"] = False
    else:
        p2["init"] = dict(p2["init"], tools=list(p2["init"]["tools"]) + [name])
    r = ct.assess_claude_admissibility(p2, allowed_tools=allowed)
    assert r["status"] != "development_admissible", label
f = factory_v5.open_factory(root)
state = f.state(pid)
ws = f.paper_dir(pid) / "source_audit"
out = read_json(ws / "source_audit.json")
jsonschema.validate(out, read_json(ws / "source_audit.schema.json"))
f._check_ids(out, pid, read_json(ws / "source_manifest.json"))
prev = state["stages"]["source_audit"]
assert prev["status"] == "failed_needs_attribution" and "outside its released profile" in prev["notes"][0]
rec = {"rule": admissibility_v6.RULE, "at": utc_now(), "ledger_call_id": call_id, "native_call_dir": str(call_dir),
       "events_sha256": file_hash(call_dir / "events.jsonl"), "output_sha256": file_hash(ws / "source_audit.json"),
       "original_audit_status": orig["status"], "amended_audit": new, "negative_controls": ["non_error_result", "tool_declared_at_init"],
       "ledger_entry_unchanged": True, "model_calls_made": 0}
write_json(ws / "admissibility_amendment.json", rec, exclusive=True)
state.setdefault("history", []).append({"stage": "source_audit", **state["stages"].pop("source_audit"), "set_aside": utc_now(),
                                        "set_aside_reason": "accepted under " + admissibility_v6.RULE})
blocking = [a["ambiguity_id"] for a in out["ambiguities"] if a["blocking"]]
f._record(state, "source_audit", "completed", {"source_audit": "source_audit/source_audit.json",
          "admissibility_amendment": "source_audit/admissibility_amendment.json"}, [call_id],
          ["%d ambiguities (%d blocking)" % (len(out["ambiguities"]), len(blocking)),
           "accepted under refused-unavailable-tool rule (1 CLI-refused Bash call, nothing executed)"])
print("accepted", pid, new["warnings"])
