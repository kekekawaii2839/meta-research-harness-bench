import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, ProviderRefusal, write_json
from mrhbench.openai_compat_transport import OpenAICompatTransport

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["a"], "properties": {"a": {"type": "integer"}}}


class Stub(BaseHTTPRequestHandler):
    reply = None
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Stub.seen.append({"body": body, "auth": self.headers.get("Authorization")})
        code, payload = Stub.reply
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def ok(content, *, finish="stop", ext=None):
    return 200, {"id": "x", "object": "chat.completion", "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 2, "prompt_tokens_details": {"cached_tokens": 1}},
                 "x_claude": ext if ext is not None else {"declared_tools": [], "tool_uses": [], "skills": [], "mcp_servers": []}}


class OpenAICompatTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "key.txt").write_text("local-key")
        write_json(root / "ledger.json", {"attempts": [], "used_attempts": 0, "authorized_maximum": 20})
        self.ledger = CallLedger(root / "ledger.json")
        self.t = OpenAICompatTransport(base_url="http://127.0.0.1:%d" % self.server.server_port, api_key_file=root / "key.txt",
                                       model="claude-opus-5-5", reasoning_effort="medium", ledger=self.ledger, audit_root=root / "calls")
        Stub.seen = []

    def tearDown(self):
        self.tmp.cleanup()

    def test_sends_plain_openai_body_and_parses_schema_response(self):
        Stub.reply = ok('{"a": 3}')
        r = self.t.complete({"q": 1}, output_schema=SCHEMA, role="executor")
        self.assertEqual(r["response"], {"a": 3})
        sent = Stub.seen[0]
        self.assertEqual(sent["auth"], "Bearer local-key")
        body = sent["body"]
        self.assertEqual(set(body), {"model", "reasoning_effort", "messages", "response_format"})
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])
        self.assertEqual(body["response_format"]["json_schema"]["schema"], SCHEMA)
        self.assertEqual(r["usage"], {"input_tokens": 10, "output_tokens": 2, "cached_input_tokens": 1})
        self.assertEqual(json.loads(self.ledger.path.read_text())["attempts"][0]["status"], "completed")

    def test_images_travel_as_data_urls(self):
        png = Path(self.tmp.name) / "a.png"
        png.write_bytes(bytes([137, 80, 78, 71, 13, 10, 26, 10]) + b"0" * 10)
        Stub.reply = ok('{"a": 1}')
        self.t.complete({"q": 1}, output_schema=SCHEMA, role="executor", images=[png])
        parts = Stub.seen[0]["body"]["messages"][1]["content"]
        self.assertEqual(parts[0]["type"], "text")
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_long_keys_are_aliased_and_restored(self):
        long_key = "k" * 70
        schema = {"type": "object", "additionalProperties": False, "required": [long_key], "properties": {long_key: {"type": "string"}}}
        body, aliases = self.t.body({"q": 1}, schema, [])
        alias = next(iter(aliases))
        Stub.reply = ok(json.dumps({alias: "v"}))
        self.assertEqual(self.t.complete({"q": 1}, output_schema=schema, role="executor")["response"], {long_key: "v"})

    def test_refusal_is_typed_and_ledgered(self):
        Stub.reply = ok("", finish="content_filter")
        with self.assertRaises(ProviderRefusal):
            self.t.complete({"q": 1}, output_schema=SCHEMA, role="executor")
        self.assertEqual(json.loads(self.ledger.path.read_text())["attempts"][0]["metadata"]["failure_class"], "provider_safety_refusal")

    def test_tool_or_skill_exposure_rejects(self):
        Stub.reply = ok('{"a": 1}', ext={"declared_tools": ["Bash"], "tool_uses": [], "skills": [], "mcp_servers": []})
        with self.assertRaises(ProtocolError):
            self.t.complete({"q": 1}, output_schema=SCHEMA, role="executor")
        self.assertEqual(json.loads(self.ledger.path.read_text())["attempts"][0]["status"], "rejected_native_tool_activity")

    def test_substituted_model_rejects(self):
        Stub.reply = ok('{"a": 1}', ext={"declared_tools": [], "tool_uses": [], "skills": [], "mcp_servers": [], "served_models": ["claude-opus-4-8"]})
        with self.assertRaises(ProtocolError):
            self.t.complete({"q": 1}, output_schema=SCHEMA, role="executor")

    def test_http_error_and_schema_violation_fail(self):
        Stub.reply = (502, {"error": {"message": "x", "code": "model_substituted"}})
        with self.assertRaises(ProtocolError):
            self.t.complete({"q": 1}, output_schema=SCHEMA, role="executor")
        Stub.reply = ok('{"a": "not-int"}')
        with self.assertRaises(Exception):
            self.t.complete({"q": 1}, output_schema=SCHEMA, role="executor")

    def test_non_loopback_endpoint_refused(self):
        with self.assertRaises(ProtocolError):
            OpenAICompatTransport(base_url="http://example.com:8765", api_key_file="k", model="m", reasoning_effort="medium",
                                  ledger=self.ledger, audit_root=self.tmp.name)


if __name__ == "__main__":
    unittest.main()
