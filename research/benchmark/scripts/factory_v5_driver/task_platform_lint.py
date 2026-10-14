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
DISCLOSURE = re.compile(r"(target(?:'s| paper| work| method)|source paper(?:'s)?|withheld target|earliest known public version|"
                        r"openreview|review platform|(?:does|do) not contain (?:the )?(?:target|source)|would pre-answer)", re.I)
META_KEY = re.compile(r"(justification|rationale|visibility|scope|note|provenance_note)", re.I)
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
    # v7: disclosure-prone public metadata fields (justification/rationale/visibility/scope/note) - review flags
    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + [k])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + [str(i)])
        elif isinstance(node, str) and any(META_KEY.search(k) for k in path):
            for m in DISCLOSURE.finditer(node):
                out.append({"kind": "public_field_disclosure", "where": "task.json:public." + ".".join(path)[:120],
                            "text": node[max(0, m.start() - 60):m.end() + 80],
                            "note": "public metadata field mentions the target/source or its provenance; must be neutral (factory v7 R1/R2)"})
                break
    pub = dict(t["public"])
    for key in ("input_contract", "output_contract"):
        v = pub.get(key)
        if isinstance(v, dict) and isinstance(v.get("description"), str):
            try:
                pub[key] = json.JSONDecoder().raw_decode(v["description"].strip())[0]
            except Exception:
                pass
    walk({k: v for k, v in pub.items() if k != "prompt"}, [])
    # the compiled prompt embeds the package's input contract as JSON text: scan its metadata-keyed blocks too
    prompt = t["public"].get("prompt", "")
    for m in re.finditer(r'"([A-Za-z_]*(?:justification|rationale|visibility|scope|note)[A-Za-z_]*)"\s*:', prompt, re.I):
        seg = prompt[m.end():m.end() + 4000]
        cut = re.search(r'\n\s{0,2}"[A-Za-z_]+"\s*:', seg)
        seg = seg[:cut.start()] if cut else seg
        d = DISCLOSURE.search(seg)
        if d:
            out.append({"kind": "public_field_disclosure", "where": "task.json:prompt[" + m.group(1) + "]",
                        "text": seg[max(0, d.start() - 60):d.end() + 80],
                        "note": "public metadata field mentions the target/source or its provenance; must be neutral (factory v7 R1/R2)"})
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
