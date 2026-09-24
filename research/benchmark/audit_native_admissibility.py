"""Replay historical call183 and bind an independently inspected wrapper review.

No model/container calls; this does not rewrite historical qualification or grades.
"""
from pathlib import Path
from mrhbench.io import read_json, write_json, file_hash
from mrhbench.native_admissibility import assess_native_admissibility


def main():
    base=Path('D:/mrhbench-local-pilot/context-native-probe-20260923-001')
    work=next((base/'native').iterdir()); call=next((work/'calls').iterdir())
    before={str(p):file_hash(p) for p in base.rglob('*') if p.is_file()}
    args=dict(guard_path=work/'guard.json',hook_directory=work/'hook_events',tool_state_path=work/'tool_state.json')
    pending=assess_native_admissibility(call,**args)
    assert pending['status']=='pending_code_mode_review' and not pending['errors'] and not pending['violations']
    assert pending['observed']==dict(rollout_rows=42,outer_calls=3,mcp_calls=9,mcp_failed=1,hook_records=9)
    # The reviewer inspected every visible outer JavaScript payload, not a regex
    # approval generated from a superficially matching MCP function name.
    review={'status':'passed','binding':pending['binding'],
        'reviewer':'independent container_runtime_v2 maintenance review',
        'reviewed_outer_calls':[{k:c[k] for k in ('call_id','payload_sha256')} for c in pending['outer_calls_requiring_review']],
        'notes':'Read all three complete outer exec payloads. First filters/describes ALL_TOOLS metadata only; second runs seven explicit container read/list operations on listed /inputs paths and forwards all results via text; third reads the two explicit previous/search files and forwards results. No dynamic external dispatch, host/network/patch/collaboration invocation in these visible payloads. Actual nine inner MCP events and hook/controller evidence match; one allowed list fails because the advertised empty directory was absent. This is bounded retrospective review of visible activity, not a proof against hidden effects or an OS boundary.'}
    admitted=assess_native_admissibility(call,code_mode_review=review,**args)
    assert admitted['status']=='development_admissible' and admitted['controller_tool_state_verified']
    assert before=={str(p):file_hash(p) for p in base.rglob('*') if p.is_file()}
    root=Path(__file__).resolve().parent
    source=root/'audit/context_policy_real_probes_independent_review_v1.json'
    output={'version':1,'new_model_calls':0,'new_container_runs':0,'historical_call':183,
        'before_explicit_review':pending,'explicit_wrapper_review':review,'after_explicit_review':admitted,
        'prior_full_visible_trajectory_audit':{'path':str(source),'sha256':file_hash(source)},
        'historical_files_unchanged':True,
        'official_documentation':{'url':'https://learn.chatgpt.com/docs/hooks','opened_by_reviewer':True,
            'relevant_scope':'Tool coverage excludes some paths and hosted tools; hooks are guardrails rather than a complete enforcement boundary. Unsupported PreToolUse output can fail and allow continuation.'},
        'acceptance':'12 offline synthetic regression tests passed. Real call183 mechanical replay stays pending until the separately explicit byte-bound review. No new scientific score or historical qualification rewritten.',
        'limitations':['Code-mode exec and inner MCP activity are separate layers; complete visible review is not regex matching.',
            'CLI drops the raw isError field and adds structured_content:null; shared content/structured/status are matched, not raw result hashes.',
            'The module does not read encrypted reasoning or authenticate controller files with a digital signature.',
            'No negative live boundary probe was authorized or run. This closes silent post-run admission paths only, not all hook fail-open execution risks.']}
    dest=root/'audit/native_admissibility_independent_review_v1.json';write_json(dest,output,exclusive=True)
    print(dest)


if __name__=='__main__':main()
