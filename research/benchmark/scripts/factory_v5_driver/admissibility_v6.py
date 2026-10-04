"""Factory v6 admissibility rule for CLI-refused unavailable tools (user decision 2026-10-01, option A).

The post-run stream audit rejects a whole native session if any tool_use names a tool outside the released profile.
A model can still *emit* such a call (e.g. "Bash") although the tool was removed at launch; the CLI then answers
with an error result and nothing runs. Rule: a disallowed tool_use is downgraded from rejection to a warning ONLY if
  * the tool name was not declared in the session's init tool list (it was not available at all), and
  * its matching tool_result is an error whose text starts with "<tool_use_error>Error: No such tool available".
Any other out-of-profile activity (a declared-but-unreleased tool, a non-error result, a missing result, a different
error) still rejects the session. Applied in-process to mrhbench.claude_transport.assess_claude_admissibility;
the repo file is not modified. Not OS isolation; still a post-run audit.
"""
import json

import mrhbench.claude_transport as ct

RULE = "factory-v6 refused-unavailable-tool rule (user decision 2026-10-01, option A)"
REFUSAL_PREFIX = "<tool_use_error>Error: No such tool available"
_orig = ct.assess_claude_admissibility


def _result_text(events, tool_use_id):
    for e in events:
        if e.get("type") != "user":
            continue
        content = (e.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_result" and block.get("tool_use_id") == tool_use_id:
                c = block.get("content")
                text = c if isinstance(c, str) else " ".join(i.get("text", "") for i in c or [] if isinstance(i, dict))
                return bool(block.get("is_error")), text
    return None, None


def refused_unavailable(parsed, tool_use):
    declared = set((parsed.get("init") or {}).get("tools") or [])
    is_error, text = _result_text(parsed["events"], tool_use["id"])
    return tool_use["name"] not in declared and is_error is True and isinstance(text, str) and text.startswith(REFUSAL_PREFIX)


def assess(parsed, *, allowed_tools, tool_state=None):
    audit = _orig(parsed, allowed_tools=allowed_tools, tool_state=tool_state)
    observed = audit.get("disallowed_tool_calls") or []
    if audit["status"] != "rejected_observed_activity" or not observed:
        return audit
    if not all(refused_unavailable(parsed, t) for t in observed):
        return audit
    audit = dict(audit)
    audit["status"] = "incomplete" if audit["errors"] else "development_admissible"
    audit["warnings"] = list(audit["warnings"]) + ["refused_unavailable_tool_calls:%d" % len(observed)]
    audit["refused_unavailable_tool_calls"] = observed
    audit["disallowed_tool_calls"] = []
    audit["amendment_rule"] = RULE
    return audit


if not getattr(ct.assess_claude_admissibility, "_v6_rule", False):
    assess._v6_rule = True
    ct.assess_claude_admissibility = assess
