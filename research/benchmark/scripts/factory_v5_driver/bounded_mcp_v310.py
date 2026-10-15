"""Judge v3.10.1 MCP evidence server: the v3.8 server (12000-char pages) + short receipt references.

Every evidence_read result additionally carries "ref": "R<n>", n = 1-based index of the receipt's FIRST appearance
in this session (re-reading the same range returns the same ref). The controller (judge_v310.translate_refs)
rebuilds the same map from tool_state.json events and replaces R<n> by the exact receipt_id before the unchanged
repo validators run. Motivation: three judgments were rejected for miscopied 64-hex receipt ids (a dropped/added
character), none for a scientific reason.
"""
from pathlib import Path
import argparse
import json
import sys

BENCH = Path(r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_v37  # noqa: E402
judge_v37.PAGE_MAX = 12000  # before the bounded_mcp_v37 import (tool schema bound)
import bounded_mcp_v37  # noqa: E402
from mrhbench.io import read_json  # noqa: E402

_Base = bounded_mcp_v37.BoundedToolsV37


class BoundedToolsV310(_Base):
    def __init__(self, manifest):
        super().__init__(manifest)
        self.refs = {}

    def call(self, name, args):
        result = super().call(name, args)
        if name != "evidence_read":
            return result
        first = result["content"][0]
        payload = json.loads(first["text"])
        rid = payload.get("receipt_id")
        if rid:
            if rid not in self.refs:
                self.refs[rid] = "R%d" % (len(self.refs) + 1)
            payload = {"ref": self.refs[rid], **payload}
            first = {**first, "text": json.dumps(payload, ensure_ascii=False)}
        return {**result, "content": [first] + result["content"][1:]}


bounded_mcp_v37.BoundedToolsV37 = BoundedToolsV310  # serve() instantiates this name

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    a = p.parse_args()
    bounded_mcp_v37.serve(read_json(Path(a.manifest)))
