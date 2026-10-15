"""Judge v3.7 MCP evidence server: the repo bounded_mcp server with three access changes (no container tools).

* evidence_read pages up to 24000 characters (judging.EvidenceSession.read_chars patched by judge_v37);
* evidence_inventory returns the controller-listed records (manifest listed_evidence_ids; all records when null);
  unlisted records stay readable by id;
* evidence_search: case-insensitive substring locator over text records; returns positions and a short preview
  that is NOT a receipt (the judge must evidence_read the range to cite it).
Every call is counted and logged in tool_state.json exactly like the repo server.
"""
from pathlib import Path
import argparse
import json
import sys

BENCH = Path(r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_v37  # noqa: E402  (page bound patch)
import mrhbench.bounded_mcp as bm  # noqa: E402
from mrhbench.io import ProtocolError, read_json  # noqa: E402

PAGE_MAX = judge_v37.PAGE_MAX
STR = {"type": "string"}
READ = bm.tool("evidence_read", "Read at most %d characters of frozen evidence; follow next_char until needed coverage. Offsets address "
               "original text. Return exact receipt_id for citations. Images delivered as image, not base64 text. Several "
               "evidence_read calls may be issued in parallel." % PAGE_MAX,
               {"evidence_id": STR, "start_char": {"type": "integer", "minimum": 0}, "max_chars": {"type": "integer", "minimum": 1, "maximum": PAGE_MAX}},
               ["evidence_id"])
INVENTORY = bm.tool("evidence_inventory", "List the frozen evidence identifiers, roles, visibility, hashes and line counts "
                    "(unlisted library documents are in lit-library-catalog and remain readable by id).", {}, [])
SEARCH = bm.tool("evidence_search", "Locate a case-insensitive literal substring in text evidence. Returns evidence ids, start_char "
                 "positions and a short preview. It returns NO receipt and can never appear in refs: read the range with evidence_read and cite that receipt.",
                 {"query": {"type": "string", "minLength": 3, "maxLength": 200},
                  "evidence_id_prefix": STR, "max_results": {"type": "integer", "minimum": 1, "maximum": 30}}, ["query"])
bm.EVIDENCE_TOOLS[:] = [INVENTORY, READ, SEARCH]


class BoundedToolsV37(bm.BoundedTools):
    def __init__(self, manifest):
        if manifest.get("container"):
            raise ProtocolError("v3.7 judge server has no container tools")
        super().__init__(manifest)
        listed = manifest.get("listed_evidence_ids")
        if listed is not None and (not isinstance(listed, list) or not set(listed) <= set(self.session.records)):
            raise ProtocolError("listed_evidence_ids must name released records")
        self.listed = None if listed is None else set(listed)
        self._lower = None

    def call(self, name, args):
        if name not in ("evidence_inventory", "evidence_search"):
            return super().call(name, args)
        definitions = {x["name"]: x for x in self.definitions}
        if name not in definitions or not isinstance(args, dict):
            raise ProtocolError("Tool not available")
        schema = definitions[name]["inputSchema"]
        if not set(args) <= set(schema["properties"]) or not set(schema["required"]) <= set(args):
            raise ProtocolError("Unexpected tool arguments")
        if self.calls >= self.max_calls:
            raise ProtocolError("Tool call allowance exhausted")
        self.calls += 1
        if name == "evidence_inventory":
            inv = self.session.inventory()
            result = inv if self.listed is None else [x for x in inv if x["evidence_id"] in self.listed]
            event = {"name": name, "arguments": args, "receipt_id": None, "returned": len(result)}
        else:
            result = self.search(**args)
            event = {"name": name, "arguments": args, "receipt_id": None, "hits": len(result["hits"])}
        self.events.append(event)
        self.save()
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

    def search(self, query, evidence_id_prefix="", max_results=20):
        q = query.lower()
        if len(q.strip()) < 3:
            raise ProtocolError("Query too short")
        if self._lower is None:
            self._lower = {k: r["content"].lower() for k, r in self.session.records.items() if r["media_type"] == "text/plain"}
        hits, truncated = [], False
        for k in sorted(self._lower):
            if evidence_id_prefix and not k.startswith(evidence_id_prefix):
                continue
            text, i = self._lower[k], self._lower[k].find(q)
            while i >= 0:
                if len(hits) >= max_results:
                    truncated = True
                    break
                raw = self.session.records[k]["content"]
                hits.append({"evidence_id": k, "start_char": i, "preview_not_citable": raw[max(0, i - 60): i + len(q) + 80].replace("\n", " ")})
                i = text.find(q, i + len(q))
            if truncated:
                break
        return {"query": query, "hits": hits, "more_hits_exist": truncated,
                "note": "Locator only; this result has no receipt_id and must not appear in refs. Read the range with evidence_read and cite that receipt."}


def serve(manifest, instream=None, outstream=None):
    inp = instream or sys.stdin.buffer
    out = outstream or sys.stdout.buffer
    controller = BoundedToolsV37(manifest)
    try:
        while True:
            line = inp.readline(4 * 1024 * 1024 + 1)
            if not line:
                break
            if len(line) > 4 * 1024 * 1024:
                raise ProtocolError("Oversize MCP request")
            req = json.loads(line)
            rid, method = req.get("id"), req.get("method")
            if rid is None:
                continue
            try:
                if method == "initialize":
                    result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "mrhbench-bounded-v37", "version": "0.1.0"}}
                elif method == "ping":
                    result = {}
                elif method == "tools/list":
                    result = {"tools": controller.definitions}
                elif method == "tools/call":
                    result = controller.call(req["params"]["name"], req["params"].get("arguments", {}))
                else:
                    raise ProtocolError("Unsupported MCP method")
                response = {"jsonrpc": "2.0", "id": rid, "result": result}
            except Exception as e:
                if method == "tools/call":
                    response = {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": type(e).__name__ + ": " + str(e)}], "isError": True}}
                else:
                    response = {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": str(e)}}
            out.write((json.dumps(response, ensure_ascii=False) + "\n").encode())
            out.flush()
    finally:
        controller.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    a = p.parse_args()
    serve(read_json(Path(a.manifest)))
