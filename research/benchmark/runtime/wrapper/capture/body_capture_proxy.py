"""Local pass-through proxy that records Messages API request BODIES only.

The Claude CLI is pointed at http://127.0.0.1:<port> via ANTHROPIC_BASE_URL. Each request is
forwarded unchanged to https://api.anthropic.com and the response is streamed back. Only the
JSON body is written to disk; request headers (which carry the OAuth credential) are never
logged or stored.
"""
import http.server
import json
import sys
import time
from pathlib import Path

import httpx

OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
UPSTREAM = "https://api.anthropic.com"
HOP = {"host", "content-length", "connection", "accept-encoding", "transfer-encoding"}
client = httpx.Client(timeout=300)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        stamp = "%d-%s" % (time.time_ns(), self.path.split("?")[0].strip("/").replace("/", "_"))
        try:
            parsed = json.loads(body) if body else None
        except ValueError:
            parsed = {"_non_json_body_bytes": len(body)}
        (OUT / (stamp + ".body.json")).write_text(json.dumps({"method": self.command, "path": self.path, "body": parsed},
                                                            ensure_ascii=False, indent=1), encoding="utf8")
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        with client.stream(self.command, UPSTREAM + self.path, headers=headers, content=body) as r:
            self.send_response(r.status_code)
            for k, v in r.headers.items():
                if k.lower() not in HOP | {"content-encoding"}:
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for chunk in r.iter_bytes():  # decoded; Content-Encoding is not forwarded
                if chunk:
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.write(b"0\r\n\r\n")

    do_POST = _proxy
    do_GET = _proxy

    def log_message(self, *a):
        pass


http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
