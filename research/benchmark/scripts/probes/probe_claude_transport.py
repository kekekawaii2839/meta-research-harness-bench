"""Two bounded real probes of the Claude transports (AGENTS §0.2.13). Not research.

1. executor ClaudeJSONTransport: arithmetic + pixel question on an explicit image.
2. judge ClaudeNativeRunner(bounded_mcp): inventory + canary text + image via MCP.
Each call is reserved in the development ledger; no automatic retry.
"""
import argparse
import json
import base64
import struct
import sys
import uuid
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.claude_transport import ClaudeJSONTransport, ClaudeNativeRunner, parse_stream, assess_claude_admissibility
from mrhbench.costs import CallLedger
from mrhbench.io import read_json, write_json
from mrhbench.judge_runner import evidence_record

BASE = Path(__file__).resolve().parents[2]
CANARY = "cobalt-heron-417"


def two_colour_png(width=96, height=48):
    """Left half pure red, right half pure blue; no third-party imaging library."""
    rows = b"".join(b"\x00" + b"".join((b"\xff\x00\x00" if x < width // 2 else b"\x00\x00\xff") for x in range(width))
                    for _ in range(height))
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--claude-binary", default="D:/programming/cluade-code/claude.exe")
    p.add_argument("--model", default="claude-opus-5-5")
    p.add_argument("--effort", default="medium")
    p.add_argument("--which", choices=["executor", "judge", "both", "structured"], default="both")
    a = p.parse_args()
    out = Path("D:/mrhbench-local-pilot") / ("claude-transport-probe-" + uuid.uuid4().hex[:10])
    out.mkdir(parents=True)
    png = two_colour_png()
    (out / "left_red_right_blue.png").write_bytes(png)
    ledger = CallLedger(BASE / "audit/development_call_ledger.json")
    summary = {"output": str(out), "model": a.model, "effort": a.effort, "calls": {}}
    if a.which in {"executor", "both"}:
        t = ClaudeJSONTransport(binary=Path(a.claude_binary), model=a.model, reasoning_effort=a.effort, ledger=ledger,
                                audit_root=out / "executor_calls", timeout_seconds=240)
        schema = {"type": "object", "additionalProperties": False, "required": ["sum", "left_half_colour", "right_half_colour", "tools_available"],
                  "properties": {"sum": {"type": "integer"}, "left_half_colour": {"type": "string"},
                                 "right_half_colour": {"type": "string"}, "tools_available": {"type": "array", "items": {"type": "string"}}}}
        request = {"probe": "Transport probe, not research. Compute 19+23. Name the colour of the left half and right half of the attached image "
                            "in one lowercase word each. List any tools you can call (empty list if none)."}
        try:
            r = t.complete(request, output_schema=schema, role="probe", images=[out / "left_red_right_blue.png"])
            summary["calls"]["executor"] = {"status": "completed", "response": r["response"], "call_id": r["call_id"], "audit_directory": r["audit_directory"]}
        except Exception as exc:
            summary["calls"]["executor"] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    if a.which in {"judge", "both"}:
        jdir = out / "judge"; jdir.mkdir(); ws = jdir / "empty_workspace"; ws.mkdir()
        records = [evidence_record("E1", "task", "Probe task: this bundle has a text record and an image record."),
                   evidence_record("E2", "submission", "The verification phrase is " + CANARY + ".\nSecond line."),
                   evidence_record("E3", "rendered_artifact", base64.b64encode(png).decode("ascii"), media_type="image/png")]
        manifest = {"records": records, "state_path": str((jdir / "tool_state.json").resolve()), "max_tool_calls": 12,
                    "max_text_chars": 20000, "container": None, "allowed_tools": ["evidence_inventory", "evidence_read"]}
        write_json(jdir / "evidence_manifest.json", manifest)
        from mrhbench.bounded_mcp import BoundedTools
        BoundedTools(manifest)  # zero-cost preflight: invalid manifests never reach a paid call
        servers = {"mrhbench": {"command": sys.executable, "args": [str(BASE / "mrhbench/bounded_mcp.py"), "--manifest",
                                                                  str((jdir / "evidence_manifest.json").resolve())],
                                "enabled_tools": ["evidence_inventory", "evidence_read"]}}
        r = ClaudeNativeRunner(binary=Path(a.claude_binary), model=a.model, reasoning_effort=a.effort, ledger=ledger,
                               audit_root=jdir / "calls", timeout_seconds=300, tool_profile="bounded_mcp", mcp_servers=servers)
        prompt = ("Bounded tool probe, not research. Call evidence_inventory, then evidence_read on E2 and on E3. "
                  "Report the verification phrase in E2, and the colour of the left and right halves of the E3 image as you actually see it "
                  "(say 'not_visible' if you received no image). List every tool you can call. "
                  'Return JSON {"phrase":string,"left":string,"right":string,"tools":[string],"image_seen":boolean}.')
        schema = {"type": "object", "required": ["phrase", "left", "right", "tools", "image_seen"],
                  "properties": {"phrase": {"type": "string"}, "left": {"type": "string"}, "right": {"type": "string"},
                                 "tools": {"type": "array", "items": {"type": "string"}}, "image_seen": {"type": "boolean"}}}
        try:
            res = r.run(workspace=ws, prompt=prompt, output_schema=schema, role="probe")
            parsed = parse_stream(Path(res["audit_directory"], "events.jsonl").read_text(encoding="utf8"))
            audit = assess_claude_admissibility(parsed, allowed_tools=r.allowed_tools(), tool_state=read_json(jdir / "tool_state.json"))
            write_json(jdir / "admissibility_with_server_state.json", audit)
            summary["calls"]["judge"] = {"status": "completed", "response": res["response"], "call_id": res["call_id"],
                                         "audit_directory": res["audit_directory"], "admissibility": audit["status"],
                                         "server_state_images_returned": read_json(jdir / "tool_state.json")["image_results_returned"]}
        except Exception as exc:
            summary["calls"]["judge"] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    if a.which == "structured":
        # Does --json-schema add a tool to an otherwise tool-free session? Observe, do not assume.
        schema = {"type": "object", "additionalProperties": False, "required": ["sum", "note"],
                  "properties": {"sum": {"type": "integer"}, "note": {"type": "string"}}}
        class Structured(ClaudeJSONTransport):
            def command(self):
                return super().command() + ["--json-schema", json.dumps(schema)]
        t = Structured(binary=Path(a.claude_binary), model=a.model, reasoning_effort=a.effort, ledger=ledger,
                       audit_root=out / "structured_calls", timeout_seconds=240)
        request = {"probe": 'Transport probe, not research. Compute 19+23; in note write a sentence containing a double quote character (") and a backslash (\).'}
        try:
            r = t.complete(request, output_schema=schema, role="probe")
            summary["calls"]["structured"] = {"status": "completed", "response": r["response"], "call_id": r["call_id"]}
        except Exception as exc:
            summary["calls"]["structured"] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        call_dir = next((out / "structured_calls").glob("call-*"))
        parsed = parse_stream((call_dir / "events.jsonl").read_text(encoding="utf8"))
        summary["structured_observation"] = {"init_tools": (parsed["init"] or {}).get("tools"),
            "tool_uses": parsed["tool_uses"], "result_keys": sorted((parsed["result"] or {}).keys()),
            "structured_output": (parsed["result"] or {}).get("structured_output"),
            "result_text": (parsed["result"] or {}).get("result")}
    write_json(out / "summary.json", summary)
    print(out)


if __name__ == "__main__":
    main()
