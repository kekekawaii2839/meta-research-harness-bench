"""Deterministic lint: does a compiled task's public text describe the platform it will actually run on? (no model calls)

Found by the P11 reviews (2026-09-30): constructors were never told the platform's tool interface, so two LIT tasks
described invented library interfaces (search(query), read(library_id, locator)) and one told the solver to run a
script from the read-only public root, which the CPU tool cannot execute. This lint flags, per compiled task:
  * tool_interface  - call-like mentions (name(...)) of library/tool operations that are not granted platform tools
  * literature_tools - a LIT task whose public text never names the literature.* tools it is granted
  * public_script_run - instructions to run a script from $MRH_PUBLIC_ROOT / /inputs/public (CPU tool runs /work only)
  * contract_fields - JSON field names a contract entry lists that the task's own markdown never mentions (and vice
    versa for an explicit schema block), a weak signal of contract/task.md drift
Findings are review flags for the material pipeline, not automatic rejections.
Usage: python task_platform_lint.py <compiled task dir> ...
"""
from pathlib import Path
import json
import re
import sys

CALL = re.compile(r"`?\b(search|read|read_page|fetch|open|lookup|query|get_page|get_text)\s*\(([^)]{0,60})\)`?")
PUBLIC_RUN = re.compile(r"python[^\n`]{0,40}(\$MRH_PUBLIC_ROOT|/inputs/public)[^\s`\"']*\.py", re.I)
FIELD = re.compile(r"`([a-z][a-z0-9_]{2,40})`")


def public_texts(tdir):
    t = json.loads((tdir / "task.json").read_text(encoding="utf8"))
    texts = {"task.json:prompt": t["public"].get("prompt", "")}
    for p in sorted((tdir / "assets").rglob("*.md")):
        texts[p.relative_to(tdir).as_posix()] = p.read_text(encoding="utf8", errors="replace")
    return t, texts


def lint(tdir):
    tdir = Path(tdir)
    t, texts = public_texts(tdir)
    tools = set(t["public"].get("tools", []))
    out = []
    for name, text in texts.items():
        if name == "task.json:prompt":
            # platform notes appended by the controller legitimately name the tools; lint only the material part
            text = text.split("\nPlatform literature tools:")[0].split("\nController publication notes")[0]
        for m in CALL.finditer(text):
            op = m.group(1)
            prefix = text[max(0, m.start() - 12):m.start()]
            if "literature." in prefix and ("literature." + op) in tools:
                continue
            out.append({"kind": "tool_interface", "where": name, "text": m.group(0)[:80],
                        "note": "call-like interface that is not a granted platform tool (%s)" % ", ".join(sorted(tools))})
        for m in PUBLIC_RUN.finditer(text):
            out.append({"kind": "public_script_run", "where": name, "text": m.group(0)[:100],
                        "note": "the CPU tool executes scripts under /work only; a public-root script must be copied first"})
    if t["task_type"] == "LIT":
        material = " ".join(v for k, v in texts.items() if k != "task.json:prompt")
        if "literature.read_page" not in material and "literature.search" not in material:
            out.append({"kind": "literature_tools", "where": "assets", "text": "",
                        "note": "LIT task material never names the granted literature.* tools"})
    return {"task_id": t["task_id"], "task_type": t["task_type"], "findings": out}


if __name__ == "__main__":
    for d in sys.argv[1:]:
        r = lint(d)
        print(json.dumps({"task": d.replace("\\", "/").split("/papers/")[-1][:60], "n": len(r["findings"]),
                          "findings": [(f["kind"], f["where"], f["text"]) for f in r["findings"]][:6]}, ensure_ascii=False))
