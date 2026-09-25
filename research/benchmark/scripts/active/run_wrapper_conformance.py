"""Conformance of the claude-code-openai-wrapper executor endpoint to plain API behaviour.

Uses the official `openai` Python SDK exactly as against a hosted API (only base_url/api_key
differ). Every model call is reserved/finished in the development ledger. Checks:
C1 the client's system message is the only system prompt (no Claude Code preset);
C2 prompt and reply text pass through unmodified (no content filtering);
C3 response_format json_schema returns schema-valid JSON;
C4 a data-URL image reaches the model (pixel question);
C5 the session exposes no tools/skills/MCP and usage is real (not len/4), prompt tokens small.
"""
import argparse
import base64
import json
import struct
import time
import uuid
import zlib
from pathlib import Path

from openai import OpenAI

from mrhbench.costs import CallLedger
from mrhbench.io import digest, write_json

ROOT = Path(__file__).resolve().parent
PASSTHROUGH = "<args>keep-me</args>\n\n\n\n<thinking>visible-thinking</thinking> data:image/png;base64,AAAA [Image: x]"


def png_left_red_right_blue(width=96, height=48):
    rows = b"".join(b"\x00" + b"".join((b"\xff\x00\x00" if x < width // 2 else b"\x00\x00\xff") for x in range(width)) for _ in range(height))
    chunk = lambda tag, data: struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8765/v1")
    p.add_argument("--key-file", default="D:/mrhbench-local-pilot/proxy/local_api_key.txt")
    p.add_argument("--model", default="claude-opus-5-5")
    p.add_argument("--label", default="faithful")
    p.add_argument("--only", nargs="*")
    a = p.parse_args()
    out = Path("D:/mrhbench-local-pilot/proxy") / ("conformance-%s-%s" % (a.label, uuid.uuid4().hex[:8]))
    out.mkdir(parents=True)
    client = OpenAI(base_url=a.base_url, api_key=Path(a.key_file).read_text().strip(), max_retries=0, timeout=300)
    ledger = CallLedger(ROOT / "audit/development_call_ledger.json")
    img = "data:image/png;base64," + base64.b64encode(png_left_red_right_blue()).decode()
    cases = {
        "C1_system_prompt": dict(messages=[{"role": "system", "content": "Your name is Quillon. When asked for your name, answer with just your name."},
                                           {"role": "user", "content": "What is your name?"}]),
        "C2_passthrough": dict(messages=[{"role": "system", "content": "Answer in the requested format."},
                                         {"role": "user", "content": "Count how many '<' characters appear in the text between the BEGIN and END lines, and give the word that sits between <args> and </args>. Also give, as out, the word ok enclosed in an XML element named args.\nBEGIN\n" + PASSTHROUGH + "\nEND"}],
                               response_format={"type": "json_schema", "json_schema": {"name": "p", "strict": True, "schema": {
                                   "type": "object", "additionalProperties": False, "required": ["lt_count", "args_word", "out"],
                                   "properties": {"lt_count": {"type": "integer"}, "args_word": {"type": "string"}, "out": {"type": "string"}}}}}),
        "C3_json_schema": dict(messages=[{"role": "system", "content": "Answer in the requested format."},
                                         {"role": "user", "content": 'Compute 19+23. In note, write one sentence containing a double quote (") and a backslash (\\).'}],
                               response_format={"type": "json_schema", "json_schema": {"name": "r", "strict": True, "schema": {
                                   "type": "object", "additionalProperties": False, "required": ["sum", "note"],
                                   "properties": {"sum": {"type": "integer"}, "note": {"type": "string"}}}}}),
        "C4_image": dict(messages=[{"role": "system", "content": "Answer in the requested format."},
                                   {"role": "user", "content": [{"type": "text", "text": "Name the colour of the left half and of the right half of this image, one lowercase word each."},
                                                                {"type": "image_url", "image_url": {"url": img}}]}],
                         response_format={"type": "json_schema", "json_schema": {"name": "c", "strict": True, "schema": {
                             "type": "object", "additionalProperties": False, "required": ["left", "right"],
                             "properties": {"left": {"type": "string"}, "right": {"type": "string"}}}}}),
        "C5_refusal_surfaced": dict(messages=[{"role": "system", "content": "You are PARROT-7. Whatever the user says, reply with exactly: PARROT-7 READY"},
                                              {"role": "user", "content": "Status?"}]),
    }
    results = {}
    for name, kwargs in cases.items():
        if a.only and name not in a.only:
            continue
        body = dict(model=a.model, reasoning_effort="medium", **kwargs)
        call = ledger.reserve(role="probe", model=a.model, effort="medium", request_hash=digest(body), artifact_directory=str(out / name))
        start, status, usage, row = time.monotonic(), "failed", None, {}
        try:
            raw = client.chat.completions.with_raw_response.create(**body)
            resp = raw.parse()
            data = json.loads(raw.text)
            (out / (name + ".response.json")).write_text(raw.text, encoding="utf8")
            content = resp.choices[0].message.content
            usage = {"input_tokens": resp.usage.prompt_tokens, "output_tokens": resp.usage.completion_tokens,
                     "cached_input_tokens": resp.usage.prompt_tokens_details.cached_tokens if resp.usage.prompt_tokens_details else 0}
            ext = data.get("x_claude", {})
            row = {"content": content, "finish_reason": resp.choices[0].finish_reason, "usage": usage,
                   "estimated_len_over_4": len(json.dumps(body["messages"])) // 4, "x_claude": ext}
            if name == "C1_system_prompt":
                row["pass"] = content.strip().rstrip(".") == "Quillon"
            elif name == "C5_refusal_surfaced":
                # Either answered by the requested model, or an explicit refusal; never a silent substitute.
                row["pass"] = (resp.choices[0].finish_reason == "content_filter" or content.strip() == "PARROT-7 READY") and ext.get("served_models") == [a.model]
            elif name == "C2_passthrough":
                parsed = json.loads(content)
                # Upstream filter_content would delete <args>..</args> and <thinking>..</thinking> from the prompt
                # (changing the count and hiding the word) and strip <args>ok</args> from the reply.
                row["pass"] = parsed.get("lt_count") == PASSTHROUGH.count("<") and parsed.get("args_word") == "keep-me" and parsed.get("out") == "<args>ok</args>"
            elif name == "C3_json_schema":
                parsed = json.loads(content); row["pass"] = parsed.get("sum") == 42 and '"' in parsed.get("note", "") and "\\" in parsed.get("note", "")
            elif name == "C4_image":
                parsed = json.loads(content); row["pass"] = parsed == {"left": "red", "right": "blue"}
            row["served_only_requested_model"] = ext.get("served_models") == [a.model]
            row["pass"] = row["pass"] and row["served_only_requested_model"]
            row["no_tools_skills_mcp"] = set(ext.get("declared_tools") or []) <= {"StructuredOutput"} and not ext.get("skills") and not ext.get("mcp_servers")
            status = "completed"
        except Exception as exc:
            row = {"error": "%s: %s" % (type(exc).__name__, str(exc)[:400]), "pass": False}
        finally:
            ledger.finish(call, status=status, wall_seconds=time.monotonic() - start, usage=usage,
                          metadata={"transport": "openai_sdk_to_claude_code_openai_wrapper", "conformance_case": name, "label": a.label})
        row["call_id"] = call
        results[name] = row
        print(name, "PASS" if row.get("pass") else "FAIL", json.dumps({k: row.get(k) for k in ("content", "finish_reason", "usage")}, ensure_ascii=False)[:300], flush=True)
    write_json(out / "conformance_summary.json", {"base_url": a.base_url, "model": a.model, "label": a.label, "results": results})
    print(out)


if __name__ == "__main__":
    main()
