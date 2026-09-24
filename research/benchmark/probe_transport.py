"""One explicit authorized development call; no scientific task or GPU execution."""
import argparse
from pathlib import Path

from mrhbench.costs import CallLedger
from mrhbench.io import read_json, write_json
from mrhbench.providers import CodexJSONTransport


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-binary", required=True, type=Path)
    parser.add_argument("--run-authorized-probe", action="store_true", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    config = read_json(root / "config/development.json")
    ledger = CallLedger(root / "audit/development_call_ledger.json")
    client = CodexJSONTransport(binary=args.codex_binary, model=config["executor"]["model"],
                              reasoning_effort=config["executor"]["reasoning_effort"], ledger=ledger, audit_root=root/"audit/model_calls")
    schema = {"type": "object", "additionalProperties": False, "properties": {
        "protocol": {"type": "string", "enum": ["MRHB_JSON_ACTION_V1"]},
        "action": {"type": "string", "enum": ["literature.read"]},
        "document_id": {"type": "string", "enum": ["doc-2006.10726"]}}, "required": ["protocol", "action", "document_id"]}
    result = client.complete({"purpose": "connectivity and action-transport probe only", "instruction": "Return the protocol MRHB_JSON_ACTION_V1 and a literature.read action for doc-2006.10726. Do not actually read anything."}, output_schema=schema, role="probe")
    if result["response"] != {"protocol": "MRHB_JSON_ACTION_V1", "action": "literature.read", "document_id": "doc-2006.10726"}:
        raise ValueError("Unexpected probe response")
    write_json(root / "audit/json_transport_probe.json", {**result, "scope": "one_structured_action_response_not_tool_execution_or_scientific_acceptance"})
    print({"call_id": result["call_id"], "response": result["response"], "usage": result["usage"]})
