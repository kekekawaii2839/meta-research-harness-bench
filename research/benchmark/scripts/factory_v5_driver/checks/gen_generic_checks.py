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


UNIT = r"(?:prose\s+)?(?:words|(?:whitespace[- ]separated\s+)?tokens)"
WORD_RANGE = re.compile(r"(\d[\d,]*)\s*(?:-|–|—|to)\s*(\d[\d,]*)\s*" + UNIT, re.I)
WORD_MAX = re.compile(r"(?:<=|≤|at most|up to|no more than)\s*(\d[\d,]*)\s*" + UNIT + r"|(\d[\d,]*)\s*" + UNIT + r" or (?:fewer|less)", re.I)


def _limit(text):
    """(min, max, matched text, strip_math) from one text, or None. Token counts include math; word counts do not."""
    m = WORD_RANGE.search(text)
    if m:
        return (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", "")), m.group(0), "token" not in m.group(0).lower())
    m = WORD_MAX.search(text)
    if m:
        return (0, int((m.group(1) or m.group(2)).replace(",", "")), m.group(0), "token" not in m.group(0).lower())
    return None


def word_limits(d, base, task_md=""):
    """{file: (min, max, text, strip_math)} for Markdown/text deliverables whose own contract entry (any field, e.g.
    format/requirements) or a task.md line naming the file states a word/token range or upper limit."""
    out = {}
    entries = []
    for k in ("files", "required_files", "deliverables", "deliverable_files"):
        v = d.get(k)
        if isinstance(v, dict):
            entries += [(n, json.dumps(x) if not isinstance(x, str) else x) for n, x in v.items()]
        elif isinstance(v, list):
            entries += [(x.get("path"), json.dumps(x)) for x in v if isinstance(x, dict)]
    for name, text in entries:
        if not isinstance(name, str) or not re.fullmatch(r"[\w./-]+\.(md|txt)", name):
            continue
        lim = _limit(text)
        if lim is None and task_md:  # the task text: a line (or its heading's next lines) naming the file
            lines = task_md.splitlines()
            base_name = name.rsplit("/", 1)[-1]
            for i, line in enumerate(lines):
                if base_name in line:
                    lim = _limit(" ".join(lines[i:i + 3]))
                    if lim:
                        lim = (lim[0], lim[1], "task.md: " + lim[2], lim[3])
                        break
        if lim:
            out[rel(name, base)] = lim
    return out


def entry_texts(desc):
    """{file key: its contract entry text} for files/required_files entries (dict or list form)."""
    try:
        d = json.JSONDecoder().raw_decode(desc.strip())[0]
    except Exception:
        return {}
    out = {}
    for k in ("files", "required_files", "deliverables", "deliverable_files"):
        v = d.get(k)
        if isinstance(v, dict):
            out.update({n: (x if isinstance(x, str) else json.dumps(x)) for n, x in v.items()})
        elif isinstance(v, list):
            out.update({x["path"]: json.dumps(x) for x in v if isinstance(x, dict) and isinstance(x.get("path"), str)})
    return out


def _optional(entry):
    """v6 deliverables that need not exist: optional/required:false/conditional, or described as 'Only if'/'Optional'."""
    if not isinstance(entry, dict):
        return False
    if entry.get("optional") is True or entry.get("required") is False or entry.get("conditional"):
        return True
    desc = str(entry.get("description") or "").strip().lower()
    return desc.startswith(("only if", "only when", "optional"))


def contract_files(desc, task_md=""):
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
    for k in ("files", "required_files", "deliverables", "deliverable_files"):
        v = d.get(k)
        if isinstance(v, dict):
            names += list(v)
        elif isinstance(v, list):
            names += [x.get("path") if isinstance(x, dict) else x for x in v if not _optional(x)]
    files, any_of = [], []
    for n in names:
        if not isinstance(n, str) or not n or n.endswith("/"):
            continue
        if re.fullmatch(r"[\w./-]+", n):
            files.append(rel(n, base))
            continue
        # composite keys: "+" joins independently required parts; within a part "|" / "(or ...)" are alternatives
        for part in re.split(r"\s\+\s", n):
            toks = [t for t in re.findall(r"[\w./-]+\.[A-Za-z0-9]+", part) if "{" not in t and "*" not in t]
            if not toks:
                continue
            if len(toks) == 1 and not re.search(r"\(or\b|\|", part):
                files.append(rel(toks[0], base))
            else:
                group = [rel(t, base) for t in toks]
                if re.search(r"\(or (?:any )?other", part):  # "x.py (or other named scripts)": any file of that type
                    group += sorted({str(Path(g).parent / ("*" + Path(g).suffix)).replace("\\", "/") for g in group})
                any_of.append(group)
    schema = d.get("schema") if isinstance(d.get("schema"), str) and d["schema"].endswith(".json") else None
    return files, any_of, schema, word_limits(d, base, task_md)


def main(units):
    for udir in units:
        forced = None
        if "@" in str(udir):  # explicit release: <unit dir>@<release dir name> (maintenance releases release-maintN)
            udir, forced = str(udir).split("@", 1)
        udir = Path(udir)
        pid = udir.parents[1].name
        rel_dir = forced or next(r for r in ("release-v7", "release-v6", "release-v5", "release-v4", "release-v3", "release") if (udir / r).exists())
        tdir = next((udir / rel_dir / "compiled").glob("task-*/task.json")).parent
        task = json.loads((tdir / "task.json").read_text(encoding="utf8"))
        task_md = "\n".join(p.read_text(encoding="utf8", errors="replace") for p in sorted(tdir.rglob("task.md")))
        files, any_of, schema, words = contract_files(task["public"]["output_contract"].get("description", ""), task_md)
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
        for f, (lo, hi, txt, strip) in words.items():
            spec.append({"id": "words-" + Path(f).stem, "type": "word_count", "severity": "flag", "file": f, "min": lo, "max": hi,
                         "strip_math": strip, "requirement": "task states: " + txt})
        # v6 contracts: a deliverable entry may name its own schema asset (deliverables[].schema)
        try:
            _d = json.JSONDecoder().raw_decode(task["public"]["output_contract"].get("description", "").strip())[0]
        except Exception:
            _d = {}
        _base = next((v[len("/work/"):].rstrip("/") + "/" for k, v in _d.items() if k in ("directory", "location") and isinstance(v, str) and v.startswith("/work/")), "")
        for e in (_d.get("deliverables") or []) if isinstance(_d.get("deliverables"), list) else []:
            if isinstance(e, dict) and isinstance(e.get("path"), str) and isinstance(e.get("schema"), str) and e["path"].endswith(".json"):
                fpath = rel(e["path"], _base)
                sch = e["schema"] if e["schema"] in public else ("assets/" + e["schema"] if ("assets/" + e["schema"]) in public else None)
                if sch and fpath not in {c.get("file") for c in spec if c["type"] == "json_schema"}:
                    spec.append({"id": "schema-" + Path(fpath).stem, "type": "json_schema", "severity": "hard",
                                 "requirement": "JSON deliverable validates against " + sch, "file": fpath, "schema_asset": sch})
        # a JSON deliverable with a same-stem public schema asset (e.g. manifest.json + manifest.schema.json)
        bound = {c.get("file") for c in spec if c["type"] == "json_schema"}
        for f in jsons:
            if f in bound:
                continue
            stem = Path(f).stem
            # the schema named in this file's own contract entry, else <stem>.schema.json / <stem>_schema.json
            entry = next((t for n, t in entry_texts(task["public"]["output_contract"].get("description", "")).items()
                          if Path(n.split()[0]).name == Path(f).name), "")
            match = [p for p in schema_assets if Path(p).name in entry]
            if len(match) != 1:
                match = [p for p in schema_assets if Path(p).name.split(".")[0] in (stem, stem + "_schema", stem + "-schema")]
            if len(match) == 1:
                spec.append({"id": "schema-" + Path(f).stem, "type": "json_schema", "severity": "hard",
                             "requirement": "JSON deliverable validates against " + match[0], "file": f, "schema_asset": match[0]})
        # multi-file schemas: a public schema asset whose "files" map names a JSON deliverable
        bound = {c.get("file") for c in spec if c["type"] == "json_schema"}
        tdir_assets = tdir / "assets"
        for sa in schema_assets:
            try:
                sobj = json.loads((tdir_assets / sa[len("assets/"):]).read_text(encoding="utf8")) if sa.startswith("assets/") else None
            except Exception:
                sobj = None
            fmap = sobj.get("files") if isinstance(sobj, dict) else None
            if not isinstance(fmap, dict):
                continue
            for f in jsons:
                if f not in bound and Path(f).name in fmap:
                    spec.append({"id": "schema-" + Path(f).stem, "type": "json_schema", "severity": "hard",
                                 "requirement": "JSON deliverable validates against %s (files.%s)" % (sa, Path(f).name),
                                 "file": f, "schema_asset": sa, "schema_files_key": Path(f).name})
                    bound.add(f)
        if task["task_type"] == "LIT":
            spec.append({"id": "locators", "type": "locators_resolve", "severity": "flag",
                         "requirement": "cited anchor-style locators exist in the cited library document (controller library check)"})
        spec.append({"id": "claimed-paths", "type": "claimed_paths", "severity": "flag",
                     "requirement": "paths the submission names as deliverables or evidence were actually collected",
                     "pointers": ["content.deliverables.*.path", "content.hypothesis_evidence_map.*.evidence_paths.*",
                                  "content.artifacts.*.path"]})
        out = {"schema_version": "task-checks-1", "unit": udir.name, "author": "auto-generated from the public output_contract (gen_generic_checks.py)",
               "limits": "generic only: existence (composite keys split; v6 deliverables[]), contract/same-stem schemas, identity strings, stated word/token limits (contract or task.md), claimed paths, LIT locator resolvability; no task-specific numeric/content checks",
               "release": rel_dir, "checks": spec}
        (udir / "checks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8")
        print(pid[-10:], udir.name, len(spec), "checks", files[:6])


if __name__ == "__main__":
    main(sys.argv[1:])
