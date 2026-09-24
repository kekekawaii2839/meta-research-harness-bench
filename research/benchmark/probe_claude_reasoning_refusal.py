"""Controlled 2-call probe of the executor safeguard refusal seen in calls 212/216/220/224/228.

P1: structured output whose schema has a `reasoning` property (direct application schema).
P2: same application schema only in the prompt text; the structured-output channel carries a
    fixed {payload_json: string} wire envelope (the historical Codex transport design).
Not research; one attempt each, no retry.
"""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mrhbench.claude_transport import ClaudeJSONTransport, parse_stream, provider_refusal
from mrhbench.costs import CallLedger
from mrhbench.io import canonical, write_json

BASE = Path(__file__).resolve().parent
APP_SCHEMA = {"type": "object", "required": ["action"], "properties": {
    "action": {"type": "string", "enum": ["call_tool", "finish"]}, "tool": {"type": "string"},
    "arguments": {"type": "object"}, "note": {"type": "string"}, "reasoning": {"type": "string"}}}
WIRE = {"type": "object", "additionalProperties": False, "required": ["payload_json"],
        "properties": {"payload_json": {"type": "string"}}}
REQUEST = {"instruction": "Choose the next action. Use action='call_tool' with 'tool' and 'arguments' from allowed_tools, "
                          "or action='finish' when the evidence suffices.",
           "allowed_tools": ["asset.read"], "task": "Probe only: read the asset named notes.txt."}


class Direct(ClaudeJSONTransport):
    pass


class Envelope(ClaudeJSONTransport):
    def command(self, output_schema=None):
        return super().command(WIRE)


def main():
    out = Path("D:/mrhbench-local-pilot") / ("claude-refusal-probe-" + uuid.uuid4().hex[:10])
    out.mkdir(parents=True)
    ledger = CallLedger(BASE / "audit/development_call_ledger.json")
    summary = {}
    for name, cls, schema in (("P1_direct_reasoning_schema", Direct, APP_SCHEMA), ("P2_wire_envelope", Envelope, WIRE)):
        t = cls(binary=Path("D:/programming/cluade-code/claude.exe"), model="claude-opus-5-5", reasoning_effort="medium",
                ledger=ledger, audit_root=out / name, timeout_seconds=240)
        request = REQUEST if schema is APP_SCHEMA else {"application_schema": APP_SCHEMA, "request": REQUEST,
                  "wire": "Encode the complete application JSON response as a string in payload_json."}
        try:
            r = t.complete(request, output_schema=schema, role="probe")
            row = {"status": "completed", "response": r["response"], "call_id": r["call_id"]}
        except Exception as exc:
            row = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        d = next((out / name).glob("call-*"))
        row["refusal"] = provider_refusal(parse_stream((d / "events.jsonl").read_text(encoding="utf8")))
        summary[name] = row
        print(name, json.dumps(row)[:400], flush=True)
    write_json(out / "summary.json", summary)
    print(out)


if __name__ == "__main__":
    main()
