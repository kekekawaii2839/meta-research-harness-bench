"""Judge v3.5 (in-process, repo native_judge.py unmodified) + controller platform-failure summary evidence.

P11 batch2 review (2026-09-30) found judge behaviours to correct:
  * asserted absence (of files/results/sections) without searching the evidence;
  * penalised a WRITE_CONTENT "factual error" that the source actually supports (KST WC);
  * repeated the harness's own failure label ("timeout") instead of platform records;
  * did not identify task/tool/platform mismatches as such;
  * internal rationales copied private reference details.
v3.5 appends explicit rules to the v3.4 Claude policy text (nothing is removed) and the pilot adds one public
platform_trace record, "controller-platform-failure-summary", derived only from controller files (broker RPC
responses, container audit records, run/failure records). It classifies; it does not score.
Import AFTER platform_patches and BEFORE running any judge.
"""
from pathlib import Path
import glob
import json

import mrhbench.native_judge as nj

V35_RULES = '''
Additional rules (judge v3.5):
1. Absence claims need a search. Before stating that a file, result, section, check or citation is absent or
   missing, look for it in the artifact inventory, the submission, the collected artifacts and the platform
   records, and cite what you checked. If you did not read everything relevant, write "not found in the evidence
   read" and list it under uncertainty, instead of asserting absence.
2. Error claims need both sides. Before penalising a statement as factually wrong, read the task/reference
   passage it conflicts with and cite both. If the task materials support the statement, it is not an error.
3. Failure types come from platform records. Classify tool failures, timeouts, rate limits, provider errors and
   container loss using controller-platform-failure-summary and the broker/container records. Do not repeat a
   harness's or solver's self-reported failure label (for example "timeout" or "budget exhausted") unless those
   records confirm it; if they contradict it, say so.
4. Name task/platform mismatches. When the task text, tools, paths, budgets or quotas are inconsistent with what
   the platform actually provided (for example the task names an interface the tools do not offer), state the
   mismatch explicitly as a task/platform issue, keep it separate from the solver's own errors, and do not
   charge its direct consequences to the solver's scientific dimensions.
5. controller-output-checks are deterministic facts, not scores: confirm or refute each raised flag with evidence.
6. Private references stay private. Feedback must not quote or paraphrase private reference content (expected
   values, private facts, source-paper details); describe shortfalls in terms of the public task and the
   submission. Internal rationales may cite private receipts by id but must not copy reference passages.'''

VERSION = "native-judge-claude-v3.5"
_orig_common = nj.claude_common
if not getattr(_orig_common, "_v35", False):
    def claude_common():
        return _orig_common() + V35_RULES
    claude_common._v35 = True
    nj.claude_common = claude_common
    nj.CLAUDE_VERSION = VERSION


def _read(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf8"))
    except Exception:
        return None


def platform_failure_summary(execution_dir):
    ex = Path(execution_dir)
    rpc_failures, model_calls, tool_calls = [], {"ok": 0, "failed": 0}, {"ok": 0, "failed": 0}
    for f in sorted(glob.glob(str(ex / "broker" / "rpc-*.json"))):
        r = _read(f) or {}
        req, resp = r.get("request") or {}, r.get("response") or {}
        op = req.get("operation")
        bucket = model_calls if op == "complete" else tool_calls if op == "tool" else None
        if bucket is not None:
            bucket["ok" if resp.get("ok", True) else "failed"] += 1
        if not resp.get("ok", True):
            targs = ((req.get("arguments") or {}).get("arguments") or {}) if op == "tool" else {}
            path = next((targs[k] for k in ("script", "path") if isinstance(targs.get(k), str)), None)
            row = {"sequence": req.get("sequence"), "operation": op,
                   "tool": (req.get("arguments") or {}).get("name") if op == "tool" else None,
                   "public_category": resp.get("category"), "controller_error_class": resp.get("error")}
            if path is not None:
                row["path_argument"] = path
                row["path_exists_in_collected_artifacts"] = (ex / "artifacts" / path.split("/work/", 1)[-1]).exists()
            rpc_failures.append(row)
    cpu_runs, session_events = [], []
    for f in sorted(glob.glob(str(ex / "container" / "*.json"))):
        name = Path(f).stem.split("-", 1)[-1]
        r = _read(f) or {}
        if name == "python_snapshot_completed":
            cpu_runs.append({"record": Path(f).name, "returncode": r.get("returncode"), "timed_out": r.get("timed_out"),
                             "output_limited": r.get("output_limited")})
        elif name == "exec" and (r.get("tool_timeout") or r.get("session_expired") or r.get("output_limited")):
            session_events.append({"record": Path(f).name, "tool_timeout_command_only": bool(r.get("tool_timeout")),
                                   "session_expired": bool(r.get("session_expired")), "output_limited": bool(r.get("output_limited")),
                                   "wall_seconds": round(r.get("wall_seconds") or 0, 1)})
    sub = _read(ex / "submission.json") or {}
    notes = _read(ex / "artifacts" / "h0_notes" / "harness_notes.json")
    harness_self_report = {"submission_status": sub.get("status"), "omissions": sub.get("omissions"),
                           "stop_reason": notes.get("stop_reason") if isinstance(notes, dict) else None,
                           "trust": "solver/harness-written, not platform-verified; compare with the platform records above"}
    failure = _read(ex / "failure.json")
    run = _read(ex / "run.json") or {}
    budget = (failure or run).get("budget") or {}
    notes = {"ProviderRateLimit": "provider HTTP 429 (account rate limit) - platform outcome, not a solver error",
             "PermissionError": "controller-side file write collision - platform outcome",
             "ProtocolError": ("request rejected by the controller or broker. For a tool call this usually means invalid "
                               "arguments, a missing file (see path_exists_in_collected_artifacts) or an ungranted "
                               "capability, i.e. normally a solver/harness error; for a model call it means the executor "
                               "proxy returned an error or a schema-invalid answer. Not by itself a platform fault.")}
    classes = sorted({x["controller_error_class"] for x in rpc_failures if x["controller_error_class"]})
    return {"schema_version": "platform-failure-summary-1",
            "source": "controller broker RPC responses, container audit records, run.json/failure.json (not solver-written)",
            "run_status": run.get("status"), "stage_failure_message": (failure or {}).get("message"),
            "budget_limits": budget.get("limits"), "budget_used": budget.get("used"), "wall_limit_seconds": budget.get("wall_limit"),
            "task_elapsed_seconds": run.get("task_elapsed_seconds"),
            "model_calls": model_calls, "broker_tool_calls": tool_calls, "failed_rpcs": rpc_failures,
            "controller_error_classes": {c: notes.get(c, "see broker record") for c in classes},
            "cpu_runs": cpu_runs, "container_events": session_events, "harness_self_report": harness_self_report,
            "note": ("A worker-reported label such as 'timeout' is not a platform classification. "
                     "session_expired means the container ended (task deadline or controller stop); "
                     "tool_timeout_command_only means only that command was stopped and the session continued.")}


def summary_record(sc, execution_dir):
    return sc.evidence_record("controller-platform-failure-summary", "platform_trace",
                              json.dumps(platform_failure_summary(execution_dir), ensure_ascii=False, indent=1))
