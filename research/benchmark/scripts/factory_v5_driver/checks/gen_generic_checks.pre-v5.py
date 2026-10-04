"""Auto-generate conservative, generic controller checks for compiled factory-v5 units (zero model calls).

Derived only from each task's public output_contract and its paper identity:
  * exists       - required files named in the contract (files / required_files; directory / location prefix)
  * json_schema  - a JSON deliverable validated against the schema asset the contract names (or the single
                   public *schema*.json asset when there is exactly one JSON deliverable)
  * regex_none   - flag if the paper's arXiv id, OpenReview id or exact title appears in a text deliverable
  * word_count   - flag when a Markdown/text deliverable's own contract entry states a word range or upper limit
                   ("about 1500-4000 words", "2500 words or fewer", "at most 200 words"); math stripped, approximate
  * claimed_paths- flag deliverable / evidence paths the submission manifest names but that were not collected
Task-specific checks (numeric table matching, required equations, ...) are NOT generated here.
"""
from pathlib import Path
import json
import re
import sys

PAPERS = Path("D:/mrhbench-local-pilot/factory-v5/papers")
TEXT_EXT = {".md", ".txt", ".json", ".py", ".csv", ".tex"}


def rel(p, base):
    p = p.strip()
    if p.startswith("/work/"):
        return p[len("/work/"):]
    if base and not p.startswith(base):
        return base + p
    return p


WORD_RANGE = re.compile(r"(\d[\d,]*)\s*(?:-|–|to)\s*(\d[\d,]*)\s*(?:prose\s+)?words", re.I)
WORD_MAX = re.compile(r"(?:<=|≤|at most|up to|no more than)\s*(\d[\d,]*)\s*(?:prose\s+)?words|(\d[\d,]*)\s*(?:prose\s+)?words or (?:fewer|less)", re.I)


def word_limits(d, base):
    """{file: (min, max, text)} for file entries whose own format text states a word range/upper limit."""
    out = {}
    entries = []
    for k in ("files", "required_files"):
        v = d.get(k)
        if isinstance(v, dict):
            entries += [(n, json.dumps(x) if not isinstance(x, str) else x) for n, x in v.items()]
        elif isinstance(v, list):
            entries += [(x.get("path"), json.dumps(x)) for x in v if isinstance(x, dict)]
    for name, text in entries:
        if not isinstance(name, str) or not re.fullmatch(r"[\w./-]+\.(md|txt)", name):
            continue
        m = WORD_RANGE.search(text)
        if m:
            out[rel(name, base)] = (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", "")), m.group(0))
            continue
        m = WORD_MAX.search(text)
        if m:
            out[rel(name, base)] = (0, int((m.group(1) or m.group(2)).replace(",", "")), m.group(0))
    return out


def contract_files(desc):
    try:
        d = json.JSONDecoder().raw_decode(desc.strip())[0]  # tolerate trailing prose after the JSON object
    except Exception:
        return [], [], None, {}
    base = ""
    for k in ("directory", "location"):
        v = d.get(k)
        if isinstance(v, str) and v.startswith("/work/"):
            base = v[len("/work/"):].rstrip("/") + "/"
    names = []
    for k in ("files", "required_files"):
        v = d.get(k)
        if isinstance(v, dict):
            names += list(v)
        elif isinstance(v, list):
            names += [x.get("path") if isinstance(x, dict) else x for x in v]
    files, any_of = [], []
    for n in names:
        if not isinstance(n, str) or not n or n.endswith("/"):
            continue
        if re.fullmatch(r"[\w./-]+", n):
            files.append(rel(n, base))
        else:  # alternatives or prose ("a | b (or ...)", "x.py (or other scripts) + config.json"): any one suffices
            toks = [t for t in re.findall(r"[\w./-]+\.[A-Za-z0-9]+", n) if "{" not in t and "*" not in t]
            if toks:
                any_of.append([rel(t, base) for t in toks])
    schema = d.get("schema") if isinstance(d.get("schema"), str) and d["schema"].endswith(".json") else None
    return files, any_of, schema, word_limits(d, base)


def main(units):
    for udir in units:
        udir = Path(udir)
        pid = udir.parents[1].name
        rel_dir = next(r for r in ("release-v4", "release-v3", "release") if (udir / r).exists())
        task = json.loads(next((udir / rel_dir / "compiled").glob("task-*/task.json")).read_text(encoding="utf8"))
        files, any_of, schema, words = contract_files(task["public"]["output_contract"].get("description", ""))
        public = [a["path"] for a in task["assets"] if a["visibility"] == "public"]
        src = json.loads((udir.parents[1] / "sources" / "manifest.json").read_text(encoding="utf8"))
        arxiv = (src.get("arxiv") or {}).get("id")
        title = json.loads((udir / "state.json").read_text(encoding="utf8")).get("title") or ""
        ident = {"openreview_id": re.escape(pid.split("-", 1)[1])}
        if arxiv:
            ident["arxiv_id"] = re.escape(arxiv)
        if len(title) > 12:
            ident["title"] = re.escape(title.split(":")[0].strip()) if len(title.split(":")[0].strip()) > 12 else re.escape(title)
        spec = []
        if files or any_of:
            spec.append({"id": "files", "type": "exists", "severity": "hard", "requirement": "required deliverables named in the output contract",
                         "files": files, "any_of": any_of})
        jsons = [f for f in files if f.endswith(".json")]
        schema_assets = [p for p in public if "schema" in Path(p).name and p.endswith(".json")]
        if schema and jsons and schema in public:
            target = next((f for f in jsons if Path(f).stem in ("verdicts", "results", "hypotheses", "claims", "proposal")), jsons[0]) if len(jsons) > 1 else jsons[0]
            if len(jsons) == 1:
                spec.append({"id": "schema", "type": "json_schema", "severity": "hard", "requirement": "JSON deliverable validates against " + schema,
                             "file": target, "schema_asset": schema})
        elif len(jsons) == 1 and len(schema_assets) == 1:
            spec.append({"id": "schema", "type": "json_schema", "severity": "hard", "requirement": "JSON deliverable validates against " + schema_assets[0],
                         "file": jsons[0], "schema_asset": schema_assets[0]})
        for i, f in enumerate(f for f in files if Path(f).suffix in TEXT_EXT):
            spec.append({"id": "identity-%d" % i, "type": "regex_none", "severity": "flag", "requirement": "do not identify the source paper", "file": f, "patterns": ident})
        for f, (lo, hi, txt) in words.items():
            spec.append({"id": "words-" + Path(f).stem, "type": "word_count", "severity": "flag", "file": f, "min": lo, "max": hi,
                         "strip_math": True, "requirement": "contract states: " + txt})
        spec.append({"id": "claimed-paths", "type": "claimed_paths", "severity": "flag",
                     "requirement": "paths the submission names as deliverables or evidence were actually collected",
                     "pointers": ["content.deliverables.*.path", "content.hypothesis_evidence_map.*.evidence_paths.*",
                                  "content.artifacts.*.path"]})
        out = {"schema_version": "task-checks-1", "unit": udir.name, "author": "auto-generated from the public output_contract (gen_generic_checks.py)",
               "limits": "generic only: existence, contract schema, identity strings, stated word limits, claimed paths; no task-specific numeric/content checks",
               "release": rel_dir, "checks": spec}
        (udir / "checks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8")
        print(pid[-10:], udir.name, len(spec), "checks", files[:6])


if __name__ == "__main__":
    main(sys.argv[1:])
