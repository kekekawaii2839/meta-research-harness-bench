"""Factory v6 leak-check rule A (user decision 2026-10-02).

The runtime gate's string leak check blocks any >=40-char private sentence that also occurs in a public asset. Two
units were blocked only because the private verification plan / scoring rubric restated, word for word, a requirement
that the public task.md states ("exactly one chain per optimised network;", "a self-constructed illustrative example
stays allowed."). A string match cannot tell "private plan quotes a public requirement" from "answer leaked".

Rule A: a hit is downgraded from blocking to a review flag ONLY if
  * every private origin is a task verification plan (verification_plan:<task>) or a private asset whose file name
    marks it as a rubric / verification plan, and
  * the public file is a Markdown task text (*.md), or - extension approved by the user 2026-10-06 - a public
    checker/validator script (*.py whose file name contains check / validat / verif). Cause: an IDEA unit's public
    check_proposal.py restated the public output-contract constraint "every background key exists in
    assets/background_index.json" that the private verification plan also lists.
Hits from private-only facts, private data or any other private file, and byte-identical public/private assets,
still block. The runtime gate runs only after the independent full-public-surface review (which checks leakage
semantically) has passed the unit, so a flag is recorded as covered by that review. Applied in-process to
mrhbench.factory_runtime.leak_check; the repo file is not modified.
"""
import re

import mrhbench.factory_runtime as fr

RULE = ("factory-v6 leak rule A (user decision 2026-10-02; public checker scripts added 2026-10-06): "
        "plan/rubric restating a public task requirement -> review flag")
PLAN_ASSET = re.compile(r"(rubric|verification)", re.I)
CHECKER = re.compile(r"(check|validat|verif)[^/]*\.py$", re.I)


def _public_file_ok(f):
    f = str(f)
    return f.endswith(".md") or bool(CHECKER.search(f.rsplit("/", 1)[-1]))
_orig = fr.leak_check


def _restated_requirement(hit):
    if hit.get("class") != "private_string_in_public_asset" or not _public_file_ok(hit.get("file", "")):
        return False
    origins = hit.get("private_origins") or []
    return bool(origins) and all(o.startswith("verification_plan:") or
                                 (o.startswith("private_asset:") and PLAN_ASSET.search(o.rsplit("/", 1)[-1]))
                                 for o in origins)


# Rule B (user decision 2026-10-12): a hit whose whole needle is one line of generic Python boilerplate shared by a
# private .py asset and a public .py file (e.g. `with open(path, encoding="utf-8") as fh:` in iclr2025-kbjJ9ZOakb EXP)
# carries no task content. Only three line shapes qualify, and any string literal must be an encoding/mode/__main__ word.
RULE_B = ("factory leak rule B (user decisions 2026-10-12, extended 2026-10-13): a single generic Python boilerplate line "
          "(open/import/__main__, or the standard-library file-hash idiom hashlib.<algo>() + chunked read) shared by a "
          "private and a public .py file -> review flag")
# 2026-10-13 extension (user: "同意把泄漏规则B扩展到hashlib.sha256()分块读文件这种样板代码"; iclr2025-QFO1asgas2 WE):
# `h = hashlib.sha256() with open(path, "rb") as f:` and `for chunk in iter(lambda: f.read(1 << 16), b""):`.
_BOILER = [re.compile(r"^(with\s+)?open\([\w\s.,=\"'-]*\)(\s+as\s+\w+)?\s*:?$"),
           re.compile(r"^(from\s+[\w.]+\s+)?import\s+[\w.,\s*]+(\s+as\s+\w+)?$"),
           re.compile(r"^if\s+__name__\s*==\s*[\"']__main__[\"']\s*:$"),
           re.compile(r"^(\w+\s*=\s*hashlib\.(sha256|sha1|sha512|md5|blake2b)\(\)\s*)?(with\s+)?open\([\w\s.,=\"'-]*\)(\s+as\s+\w+)?\s*:?$"),
           re.compile(r"^for\s+\w+\s+in\s+iter\(\s*lambda\s*:\s*\w+\.read\([\w\s<*+]*\)\s*,\s*b?[\"']{2}\s*\)\s*:$")]
_OK_LITERALS = {"utf-8", "utf8", "r", "w", "rb", "wb", "a", "ab", "rt", "wt", "__main__", "ascii", "latin-1", ""}


def _boilerplate(hit):
    if hit.get("class") != "private_string_in_public_asset" or not str(hit.get("file", "")).endswith(".py"):
        return False
    origins = hit.get("private_origins") or []
    if not origins or not all(o.startswith("private_asset:") and o.endswith(".py") for o in origins):
        return False
    needle = (hit.get("needle_excerpt") or "").strip()
    if not needle or len(needle) != hit.get("needle_chars"):  # excerpt must be the whole needle
        return False
    if any(lit.lower() not in _OK_LITERALS for lit in re.findall(r"[\"']([^\"']*)[\"']", needle)):
        return False
    return any(p.match(needle) for p in _BOILER)


def leak_check(*args, **kwargs):
    out = _orig(*args, **kwargs)
    hits = out.get("hits") or []
    flagged = [h for h in hits if _restated_requirement(h)]
    boiler = [h for h in hits if not _restated_requirement(h) and _boilerplate(h)]
    if not flagged and not boiler:
        return out
    out = dict(out)
    out["hits"] = [h for h in hits if not _restated_requirement(h) and not _boilerplate(h)]
    out["hit_count"] = len(out["hits"])
    if boiler:
        out["boilerplate_flags"] = boiler
        out["boilerplate_rule"] = RULE_B
    if not flagged:
        return out
    out["flags_for_review"] = flagged
    out["flag_rule"] = RULE
    out["flag_review_basis"] = ("runtime gate follows the independent full-public-surface review, which judged leakage "
                                "semantically; these string matches are restatements of public requirements in the private plan")
    return out


if not getattr(fr.leak_check, "_v6_rule_a", False):
    leak_check._v6_rule_a = True
    fr.leak_check = leak_check
