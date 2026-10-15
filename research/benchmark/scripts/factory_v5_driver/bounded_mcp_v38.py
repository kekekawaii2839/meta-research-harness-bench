"""Judge v3.8 MCP evidence server: the v3.7 server with 12000-character pages (see judge_v38)."""
from pathlib import Path
import argparse
import sys

BENCH = Path(r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_v37  # noqa: E402
judge_v37.PAGE_MAX = 12000  # must precede the bounded_mcp_v37 import (tool schema bound)
import bounded_mcp_v37  # noqa: E402
from mrhbench.io import read_json  # noqa: E402

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    a = p.parse_args()
    bounded_mcp_v37.serve(read_json(Path(a.manifest)))
