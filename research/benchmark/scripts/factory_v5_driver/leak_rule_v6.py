"""Factory v6 leak-check rule A (user decision 2026-10-02).

The runtime gate's string leak check blocks any >=40-char private sentence that also occurs in a public asset. Two
units were blocked only because the private verification plan / scoring rubric restated, word for word, a requirement
that the public task.md states ("exactly one chain per optimised network;", "a self-constructed illustrative example
stays allowed."). A string match cannot tell "private plan quotes a public requirement" from "answer leaked".

Rule A: a hit is downgraded from blocking to a review flag ONLY if
  * every private origin is a task verification plan (verification_plan:<task>) or a private asset whose file name
    marks it as a rubric / verification plan, and
  * the public file is a Markdown task text (*.md).
Hits from private-only facts, private data or any other private file, and byte-identical public/private assets,
still block. The runtime gate runs only after the independent full-public-surface review (which checks leakage
semantically) has passed the unit, so a flag is recorded as covered by that review. Applied in-process to
mrhbench.factory_runtime.leak_check; the repo file is not modified.
"""
import re

import mrhbench.factory_runtime as fr

RULE = "factory-v6 leak rule A (user decision 2026-10-02): plan/rubric restating a public task requirement -> review flag"
PLAN_ASSET = re.compile(r"(rubric|verification)", re.I)
_orig = fr.leak_check


def _restated_requirement(hit):
    if hit.get("class") != "private_string_in_public_asset" or not str(hit.get("file", "")).endswith(".md"):
        return False
    origins = hit.get("private_origins") or []
    return bool(origins) and all(o.startswith("verification_plan:") or
                                 (o.startswith("private_asset:") and PLAN_ASSET.search(o.rsplit("/", 1)[-1]))
                                 for o in origins)


def leak_check(*args, **kwargs):
    out = _orig(*args, **kwargs)
    hits = out.get("hits") or []
    flagged = [h for h in hits if _restated_requirement(h)]
    if not flagged:
        return out
    out = dict(out)
    out["hits"] = [h for h in hits if not _restated_requirement(h)]
    out["hit_count"] = len(out["hits"])
    out["flags_for_review"] = flagged
    out["flag_rule"] = RULE
    out["flag_review_basis"] = ("runtime gate follows the independent full-public-surface review, which judged leakage "
                                "semantically; these string matches are restatements of public requirements in the private plan")
    return out


if not getattr(fr.leak_check, "_v6_rule_a", False):
    leak_check._v6_rule_a = True
    fr.leak_check = leak_check
