import json
import tempfile
import unittest
from pathlib import Path

from mrhbench.claude_transport import (ClaudeJSONTransport, ClaudeNativeRunner, assess_claude_admissibility,
                                       child_environment, decode_json_text, parse_stream, usage_of)
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, write_json


def stream(*events):
    return "\n".join(json.dumps(e) for e in events) + "\n"


INIT = {"type": "system", "subtype": "init", "session_id": "s1", "tools": [], "mcp_servers": [], "model": "m"}
RESULT = {"type": "result", "subtype": "success", "is_error": False, "result": "{\"a\":1}", "num_turns": 1,
          "usage": {"input_tokens": 10, "output_tokens": 3, "cache_read_input_tokens": 2}, "session_id": "s1"}


class ClaudeStreamTests(unittest.TestCase):
    def test_clean_no_tool_stream_is_admissible(self):
        parsed = parse_stream(stream(INIT, {"type": "assistant", "message": {"content": [{"type": "text", "text": "{\"a\":1}"}]}}, RESULT))
        audit = assess_claude_admissibility(parsed, allowed_tools=[])
        self.assertEqual(audit["status"], "development_admissible")
        self.assertEqual(usage_of(parsed["result"]), {"input_tokens": 10, "output_tokens": 3, "cached_input_tokens": 2})

    def test_disallowed_tool_use_is_rejected(self):
        parsed = parse_stream(stream(INIT,
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1"}]}}, RESULT))
        self.assertEqual(assess_claude_admissibility(parsed, allowed_tools=["mcp__x__y"])["status"], "rejected_observed_activity")

    def test_declared_tools_beyond_release_are_incomplete(self):
        init = dict(INIT, tools=["Read"])
        parsed = parse_stream(stream(init, RESULT))
        audit = assess_claude_admissibility(parsed, allowed_tools=[])
        self.assertEqual(audit["status"], "incomplete")
        self.assertTrue(any(e.startswith("declared_tools_exceed_release") for e in audit["errors"]))

    def test_unanswered_tool_use_and_missing_result_are_incomplete(self):
        parsed = parse_stream(stream(dict(INIT, tools=["mcp__s__r"], mcp_servers=[{"name": "s", "status": "connected"}]),
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "mcp__s__r", "input": {}}]}}))
        audit = assess_claude_admissibility(parsed, allowed_tools=["mcp__s__r"])
        self.assertIn("tool_use_result_mismatch", audit["errors"])
        self.assertIn("missing_or_ambiguous_result", audit["errors"])

    def test_disconnected_mcp_and_server_overcount(self):
        parsed = parse_stream(stream(dict(INIT, mcp_servers=[{"name": "s", "status": "failed"}]), RESULT))
        audit = assess_claude_admissibility(parsed, allowed_tools=[], tool_state={"tool_calls": 2})
        self.assertIn("mcp_server_not_connected:s", audit["errors"])
        self.assertIn("mcp_server_recorded_calls_exceed_stream", audit["errors"])

    def test_unknown_event_fails_closed(self):
        parsed = parse_stream(stream(INIT, {"type": "mystery"}, RESULT))
        self.assertIn("unrecognized_stream_shape", assess_claude_admissibility(parsed, allowed_tools=[])["errors"])

    def test_non_json_stdout_rejected(self):
        with self.assertRaises(ProtocolError):
            parse_stream("not json\n")

    def test_fence_tolerance_is_recorded(self):
        self.assertEqual(decode_json_text("```json\n{\"a\": 2}\n```"), ({"a": 2}, True))
        self.assertEqual(decode_json_text(" {\"a\": 2} "), ({"a": 2}, False))

    def test_child_environment_drops_parent_session_and_api_keys(self):
        import os
        saved = dict(os.environ)
        try:
            os.environ.update(CLAUDE_EFFORT="max", CLAUDECODE="1", ANTHROPIC_API_KEY="sk-x", CLAUDE_CONFIG_DIR="C:/cfg")
            env, removed = child_environment()
            self.assertNotIn("CLAUDE_EFFORT", env)
            self.assertNotIn("ANTHROPIC_API_KEY", env)
            self.assertEqual(env["CLAUDE_CONFIG_DIR"], "C:/cfg")
            self.assertIn("CLAUDECODE", removed)
        finally:
            os.environ.clear(); os.environ.update(saved)


class ClaudeConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.binary = root / "claude.exe"; self.binary.write_bytes(b"x")
        self.ledger = CallLedger(root / "ledger.json")
        write_json(root / "ledger.json", {"attempts": [], "used_attempts": 0, "authorized_maximum": 5})
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()

    def test_executor_command_removes_every_tool_and_system_prompt(self):
        t = ClaudeJSONTransport(binary=self.binary, model="claude-opus-5-5", reasoning_effort="medium", ledger=self.ledger, audit_root=self.root)
        args = t.command()
        self.assertEqual(args[args.index("--tools") + 1], "")
        self.assertNotIn("--json-schema", args)
        schema_args = t.command({"type": "object"})
        self.assertEqual(json.loads(schema_args[schema_args.index("--json-schema") + 1]), {"type": "object"})
        for flag in ("--safe-mode", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence", "--system-prompt"):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("--setting-sources") + 1], "")

    def test_executor_rejects_codex_context_policy(self):
        with self.assertRaises(ProtocolError):
            ClaudeJSONTransport(binary=self.binary, model="m", reasoning_effort="medium", ledger=self.ledger, audit_root=self.root, context_policy={})

    def test_bounded_judge_exposes_only_mcp_tools(self):
        r = ClaudeNativeRunner(binary=self.binary, model="m", reasoning_effort="medium", ledger=self.ledger, audit_root=self.root,
                               tool_profile="bounded_mcp", mcp_servers={"mrhbench": {"command": "py", "args": [], "enabled_tools": ["evidence_read"]}})
        args = r.command(self.root / "m.json")
        self.assertEqual(args[args.index("--tools") + 1], "")
        self.assertEqual(r.allowed_tools(), ["mcp__mrhbench__evidence_read"])
        self.assertEqual(args[args.index("--allowedTools") + 1], "mcp__mrhbench__evidence_read")

    def test_material_profile_is_restricted_file_tools_only(self):
        r = ClaudeNativeRunner(binary=self.binary, model="m", reasoning_effort="medium", ledger=self.ledger, audit_root=self.root,
                               tool_profile="material_workspace")
        args = r.command()
        self.assertIn("--restricted", args)
        self.assertNotIn("Bash", args[args.index("--tools") + 1])
        self.assertEqual(set(r.allowed_tools()), {"Read", "Write", "Edit", "Glob", "Grep"})

    def test_workspace_under_project_context_file_is_refused_before_any_call(self):
        nested = self.root / "a" / "b"; nested.mkdir(parents=True)
        (self.root / "a" / "AGENTS.md").write_text("maintainer memory", encoding="utf8")
        r = ClaudeNativeRunner(binary=self.binary, model="m", reasoning_effort="medium", ledger=self.ledger, audit_root=self.root / "audit",
                               tool_profile="material_workspace")
        with self.assertRaises(ProtocolError):
            r.run(workspace=nested, prompt="x", role="constructor")
        self.assertEqual(json.loads((self.root / "ledger.json").read_text())["used_attempts"], 0)

    def test_native_runner_refuses_executor_role_and_bad_profiles(self):
        with self.assertRaises(ProtocolError):
            ClaudeNativeRunner(binary=self.binary, model="m", reasoning_effort="medium", ledger=self.ledger, audit_root=self.root,
                               tool_profile="bounded_mcp")
        r = ClaudeNativeRunner(binary=self.binary, model="m", reasoning_effort="medium", ledger=self.ledger, audit_root=self.root)
        with self.assertRaises(ProtocolError):
            r.run(workspace=self.root, prompt="x", role="executor")


class StructuredOutputTests(unittest.TestCase):
    def _parsed(self, tool_input, structured):
        return parse_stream(stream(dict(INIT, tools=["StructuredOutput"]),
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "StructuredOutput", "input": tool_input}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}},
            dict(RESULT, structured_output=structured)))

    def test_structured_output_must_match_observed_output_call(self):
        from mrhbench.claude_transport import structured_response
        self.assertEqual(structured_response(self._parsed({"a": 1}, {"a": 1})), {"a": 1})
        with self.assertRaises(ProtocolError):
            structured_response(self._parsed({"a": 1}, {"a": 2}))
        with self.assertRaises(ProtocolError):
            structured_response(parse_stream(stream(INIT, RESULT)))

    def test_output_tool_is_admissible_only_when_released(self):
        parsed = self._parsed({"a": 1}, {"a": 1})
        self.assertEqual(assess_claude_admissibility(parsed, allowed_tools=["StructuredOutput"])["status"], "development_admissible")
        self.assertEqual(assess_claude_admissibility(parsed, allowed_tools=[])["status"], "rejected_observed_activity")


class SchemaChannelTests(unittest.TestCase):
    def test_provider_key_pattern_selects_channel(self):
        from mrhbench.claude_transport import provider_schema_compatible
        self.assertTrue(provider_schema_compatible({"type": "object", "properties": {"a_b.c-1": {"type": "string"}}}))
        long_key = "k" * 65
        self.assertFalse(provider_schema_compatible({"type": "object", "properties": {long_key: {"type": "string"}}}))
        nested = {"type": "object", "properties": {"x": {"type": "object", "properties": {"has space": {}}}}}
        self.assertFalse(provider_schema_compatible(nested))


class RefusalTests(unittest.TestCase):
    def test_safeguard_refusal_is_classified_not_parsed_as_answer(self):
        from mrhbench.claude_transport import provider_refusal
        parsed = parse_stream(stream(INIT,
            {"type": "system", "subtype": "model_refusal_no_fallback", "api_refusal_category": "reasoning_extraction", "request_id": "req_1"},
            {"type": "assistant", "message": {"stop_reason": "refusal", "stop_details": {"category": "reasoning_extraction"},
                                              "content": [{"type": "text", "text": "API Error"}]}},
            dict(RESULT, is_error=True, subtype="success")))
        self.assertEqual(provider_refusal(parsed), {"category": "reasoning_extraction", "request_id": "req_1"})
        self.assertIsNone(provider_refusal(parse_stream(stream(INIT, RESULT))))


class ClaudeJudgeWiringTests(unittest.TestCase):
    def test_claude_prompt_replaces_only_codex_tool_mechanics(self):
        from mrhbench.native_judge import COMMON, claude_common
        text = claude_common()
        self.assertNotIn("code-mode", text)
        self.assertNotIn("Codex", text)
        self.assertIn("Hash identity semantics", text)
        # v3.3 adds exactly the two-line image downscale/tile disclosure.
        self.assertEqual(len(text.splitlines()) - len(COMMON.splitlines()), 2)
        self.assertIn("full_resolution_tiles", text)

    def test_stream_image_delivery_matches_record_hash_domain(self):
        import base64
        from mrhbench.judge_runner import evidence_record
        from mrhbench.native_judge import verify_stream_image_delivery
        png = bytes([137, 80, 78, 71, 13, 10, 26, 10]) + b"0" * 20
        data = base64.b64encode(png).decode()
        records = [evidence_record("E3", "rendered_artifact", data, media_type="image/png")]
        parsed = parse_stream(stream(INIT,
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "mcp__m__evidence_read", "input": {"evidence_id": "E3"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": [
                {"type": "text", "text": "{}"}, {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}]}]}},
            RESULT))
        state = {"tool_events": [{"name": "evidence_read", "arguments": {"evidence_id": "E3"}, "receipt_id": "r1", "image_returned_as_mcp_content": True}]}
        self.assertEqual(verify_stream_image_delivery(parsed, records, state), (["r1"], []))
        other = [evidence_record("E3", "rendered_artifact", base64.b64encode(png + b"x").decode(), media_type="image/png")]
        self.assertEqual(verify_stream_image_delivery(parsed, other, state), ([], ["r1"]))


class JudgeSchemaTests(unittest.TestCase):
    def test_v32_schema_is_provider_compatible_and_task_specific(self):
        from jsonschema import Draft202012Validator
        from mrhbench.native_judge import claude_output_schema
        from mrhbench.claude_transport import provider_schema_compatible
        from mrhbench.scoring import DIMENSIONS
        for task_type, dims in DIMENSIONS.items():
            schema = claude_output_schema(task_type)
            self.assertTrue(provider_schema_compatible(schema))
            ok = {"judgment": {"status": "scored", "dimensions": {d: {"score": 3, "rationale": "r", "refs": ["x"]} for d in dims},
                               "checks": [], "serious_issues": [{"issue": "i", "affected_dimensions": [dims[0]], "refs": ["x"]}],
                               "uncertainty": [], "failure_reason": None},
                  "feedback": {"issues": [], "limitations": []}}
            self.assertEqual(list(Draft202012Validator(schema).iter_errors(ok)), [])
            bad = json.loads(json.dumps(ok)); bad["judgment"]["serious_issues"][0]["affected_dimensions"] = ["not_a_dimension"]
            self.assertTrue(list(Draft202012Validator(schema).iter_errors(bad)))
            missing = json.loads(json.dumps(ok)); del missing["judgment"]["failure_reason"]
            self.assertTrue(list(Draft202012Validator(schema).iter_errors(missing)))


class KeyAliasTests(unittest.TestCase):
    def test_long_keys_alias_losslessly(self):
        from mrhbench.claude_transport import provider_safe_schema, restore_aliases, provider_schema_compatible
        from mrhbench.providers import validate_application_schema
        long_key = "x" * 70
        schema = {"type": "object", "required": [long_key, "ok"], "additionalProperties": False,
                  "properties": {long_key: {"type": "object", "properties": {"has space": {"type": "string"}}}, "ok": {"type": "string"}}}
        safe, aliases = provider_safe_schema(schema)
        self.assertTrue(provider_schema_compatible(safe))
        self.assertEqual(set(aliases.values()), {long_key, "has space"})
        response = {k: v for k, v in {a: {"has space" if False else next(x for x, y in aliases.items() if y == "has space"): "v"} for a in safe["required"] if aliases.get(a) == long_key}.items()}
        response["ok"] = "y"
        restored = restore_aliases(response, aliases)
        validate_application_schema(schema, restored, check_response=True)
        self.assertEqual(restored, {long_key: {"has space": "v"}, "ok": "y"})


class TilePromptTests(unittest.TestCase):
    def test_claude_write_evidence_prompt_names_tiles_codex_unchanged(self):
        import base64
        from mrhbench.judge_runner import evidence_record
        from mrhbench.judging import EvidenceSession
        from mrhbench.native_judge import make_prompt
        png = base64.b64encode(bytes([137, 80, 78, 71, 13, 10, 26, 10]) + b"0" * 20).decode()
        records = [evidence_record("task", "task", "t"), evidence_record("artifact-1", "rendered_artifact", png, media_type="image/png"),
                   evidence_record("artifact-1-tile-r0c0", "rendered_artifact", png, media_type="image/png")]
        claude = make_prompt("x", "WRITE_EVIDENCE", EvidenceSession(records), transport="claude")
        codex = make_prompt("x", "WRITE_EVIDENCE", EvidenceSession(records), transport="codex")
        self.assertIn("artifact-1-tile-r0c0. Read the tiles", claude)
        self.assertNotIn("Full-resolution tiles (exact crops", codex)


if __name__ == "__main__":
    unittest.main()
