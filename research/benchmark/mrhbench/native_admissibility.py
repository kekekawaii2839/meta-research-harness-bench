"""Post-run development trace gate, NOT pre-execution prevention or OS isolation.

Outer code-mode JavaScript is deliberately not certified by a regex allowlist.
An explicit, byte-bound independent review is needed in addition to inner MCP
activity receipts. Caller-provided review/trace files must be controller-owned.
"""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from .io import ProtocolError, digest, file_hash, parse_json, read_json


def assess_native_admissibility(audit_directory, *, allowed_tools=None, guard_path=None,
                               hook_directory=None, tool_state_path=None, code_mode_review=None):
    errors, violations, notes = [], [], []
    binding, outer, mcps = {}, [], []
    result = {'version':1, 'status':'incomplete', 'formal_isolation_verified':False,
              'pre_execution_enforcement':False, 'transport_completed':False,
              'errors':errors, 'violations':violations, 'notes':notes,
              'binding':binding, 'outer_calls_requiring_review':outer}

    def finish():
        if violations: result['status']='rejected_observed_activity'
        elif errors: result['status']='incomplete'
        elif outer and not result.get('code_mode_review_verified'): result['status']='pending_code_mode_review'
        else: result['status']='development_admissible'
        result['limitations']=[
            'A completed transport is not automatically an admissible scientific evaluation.',
            'This is a post-run trace-consistency gate, not an OS boundary or prevention of earlier side effects.',
            'Matched logged MCP calls do not establish that arbitrary code-mode JavaScript had no unlogged effects.',
            'Manual review is a trusted controller input, not a cryptographic proof or a substitute for missing required trace records.',
            'No claim of model-context purity, evidence comprehension, visual delivery, or scientific/feedback correctness.'
        ]
        return result

    def load(path, key, lines=False):
        try:
            data=Path(path).read_bytes();binding[key]=hashlib.sha256(data).hexdigest()
            text=data.decode('utf8')
            return [parse_json(s) for s in text.splitlines() if s.strip()] if lines else parse_json(text)
        except (OSError, ValueError, UnicodeError, TypeError) as exc:
            errors.append(key+':unavailable_or_invalid:'+type(exc).__name__); return None

    directory=Path(audit_directory)
    invocation=load(directory/'invocation.json','invocation_sha256')
    outcome=load(directory/'result.json','result_sha256')
    cli=load(directory/'events.jsonl','events_sha256',True)
    if not isinstance(invocation,dict) or not isinstance(outcome,dict) or not isinstance(cli,list):return finish()
    if any(not isinstance(e,dict) for e in cli):errors.append('malformed_cli_events');return finish()
    if not isinstance(invocation.get('args'),list) or any(not isinstance(a,str) for a in invocation['args']):
        errors.append('invalid_invocation_args');return finish()
    result['transport_completed']=outcome.get('status')=='completed' and outcome.get('exit_code')==0
    if not result['transport_completed']: errors.append('transport_not_completed_successfully')
    if invocation.get('tool_profile')!='bounded_mcp':errors.append('unsupported_non_bounded_profile')
    if invocation.get('config_hash')!=digest(invocation.get('args')) or outcome.get('config_hash')!=invocation.get('config_hash'):
        errors.append('invocation_command_hash_mismatch')
    capture=outcome.get('rollout_capture',{})
    if not isinstance(capture,dict) or capture.get('status')!='captured':
        errors.append('complete_rollout_unavailable');return finish()
    # Only the exact local snapshot, never a path selected from arbitrary metadata.
    path=directory/'session_rollout.redacted.jsonl'
    rows=load(path,'rollout_sha256',True)
    if not isinstance(rows,list):return finish()
    if binding['rollout_sha256']!=capture.get('sha256') or len(rows)!=capture.get('row_count'):
        errors.append('rollout_hash_or_row_count_mismatch')
    if not isinstance(capture.get('path'),str) or Path(capture['path']).resolve()!=path.resolve():errors.append('rollout_path_mismatch')
    if not all(isinstance(row,dict) and isinstance(row.get('type'),str) and isinstance(row.get('payload'),dict) for row in rows):
        errors.append('malformed_rollout_rows');return finish()
    if any('ordinal' in row for row in rows) and [r.get('ordinal') for r in rows]!=list(range(len(rows))):
        errors.append('rollout_ordinal_gap_or_reorder')
    metas=[r['payload'] for r in rows if r.get('type')=='session_meta']
    session=capture.get('session_id')
    if len(metas)!=1 or metas[0].get('id')!=session:errors.append('rollout_session_identity_mismatch')
    if {e.get('thread_id') for e in cli if e.get('type')=='thread.started'}!={session}:errors.append('cli_session_identity_mismatch')
    events=[r['payload'] for r in rows if r.get('type')=='event_msg']
    if len([e for e in events if e.get('type')=='task_started'])!=1 or len([e for e in events if e.get('type')=='task_complete'])!=1:
        errors.append('missing_or_ambiguous_rollout_terminal_markers')
    terminal=[i for i,r in enumerate(rows) if r.get('type')=='event_msg' and r['payload'].get('type')=='task_complete']
    if terminal and any(r.get('type')=='response_item' or r['payload'].get('type')=='item_completed' for r in rows[terminal[0]+1:]):errors.append('response_after_terminal_marker')
    if not any(r.get('type')=='response_item' and r['payload'].get('type')=='message' and r['payload'].get('role')=='assistant' for r in rows):
        errors.append('assistant_response_missing_from_rollout')
    if len([e for e in cli if e.get('type')=='turn.completed'])!=1 or any(e.get('type') in {'turn.failed','error'} for e in cli):
        errors.append('cli_turn_not_uniquely_completed')

    guard_meta=invocation.get('optional_hook_guard')
    declared=guard_meta is not None
    result['hook_configuration']='declared' if declared else 'not_configured'
    hooks=[];guard=None
    if declared:
        if not isinstance(guard_meta,dict):errors.append('invalid_hook_metadata')
        elif guard_path is None or hook_directory is None:errors.append('declared_hook_evidence_missing')
        else:
            guard=load(guard_path,'guard_sha256')
            if not isinstance(guard,dict):errors.append('invalid_guard_config')
            else:
                if binding.get('guard_sha256')!=guard_meta.get('config_sha256'):errors.append('guard_config_hash_mismatch')
                if guard.get('allowed_tools')!=guard_meta.get('allowed_tools'):errors.append('guard_allowlist_mismatch')
                try:
                    files=sorted(Path(hook_directory).glob('*.json'))
                    hooks=[read_json(p) for p in files]
                    binding['hook_records_sha256']=digest([{'name':p.name,'sha256':file_hash(p)} for p in files])
                except (OSError,ValueError):errors.append('hook_records_unreadable')
                if allowed_tools is None:allowed_tools=guard.get('allowed_tools')
        args=invocation.get('args',[])
        if not any(a=='--enable' and i+1<len(args) and args[i+1]=='hooks' for i,a in enumerate(args)) or not any(isinstance(a,str) and a.startswith('hooks=') for a in args):
            errors.append('declared_hook_missing_command_configuration')
    else:
        notes.append('No hook declared; absence of hook records is not a lost-hook error and proves no hook enforcement.')
        if guard_path is not None or hook_directory is not None:errors.append('undeclared_hook_evidence_supplied')
    if not isinstance(allowed_tools,(list,tuple)) or not allowed_tools or any(not isinstance(n,str) or not re.fullmatch(r'mcp__mrhbench__[A-Za-z0-9_]+',n) for n in allowed_tools):
        errors.append('explicit_exact_mcp_allowlist_required');allowed=set()
    else:allowed=set(allowed_tools)
    result['allowed_tools']=sorted(allowed)
    binding['allowed_tools_sha256']=digest(sorted(allowed))

    calls,outputs={},{}
    known_outer={'session_meta','event_msg','response_item','world_state','turn_context','token_usage_record'}
    known_event={'task_started','task_complete','item_completed','token_count','agent_message','agent_reasoning'}
    for index,row in enumerate(rows):
        kind=row['type'];payload=row['payload'];typ=payload.get('type')
        if kind not in known_outer:errors.append('unreviewed_rollout_record_type:'+str(kind))
        if kind=='event_msg':
            if typ not in known_event:errors.append('unreviewed_event_type:'+str(typ))
            item=payload.get('item')
            if typ=='item_completed' and isinstance(item,dict):
                if item.get('type')=='McpToolCall':mcps.append(item)
                elif item.get('type') not in {'UserMessage','AgentMessage','Reasoning'}:
                    violations.append('nonallowed_completed_activity:'+str(item.get('type')))
        if kind!='response_item':continue
        if typ in {'function_call','custom_tool_call'}:
            cid=payload.get('call_id')
            if not isinstance(cid,str) or cid in calls:errors.append('duplicate_or_missing_outer_call_id');continue
            calls[cid]=payload
            name=payload.get('name')
            if name in {'exec','functions.exec','wait','functions.wait'}:
                outer.append({'call_id':cid,'name':name,'row_index':index,'payload_sha256':digest(payload)})
            elif name not in allowed:violations.append('nonallowed_outer_tool:'+str(name))
        elif typ in {'function_call_output','custom_tool_call_output'}:
            cid=payload.get('call_id')
            if not isinstance(cid,str) or cid in outputs:errors.append('duplicate_or_missing_outer_output_id')
            else:
                outputs[cid]=payload
                if cid not in calls:errors.append('outer_output_before_call')
        elif typ not in {'message','reasoning'}:violations.append('nonallowed_response_activity:'+str(typ))
    if set(calls)!=set(outputs):errors.append('outer_call_output_incomplete')

    def mcp_identity(item):
        value=item.get('result')
        # CLI serializes structured_content:null and drops isError; rollout uses
        # MCP structuredContent and includes isError. Compare shared content and
        # status, never pretend these two encodings have identical raw hashes.
        common=None if not isinstance(value,dict) else {
            'content':value.get('content'),
            'structured':value.get('structuredContent',value.get('structured_content'))}
        return (item.get('server'),item.get('tool'),digest(item.get('arguments')),item.get('status'),digest(common))
    cli_mcp=[]
    for event in cli:
        typ=event.get('type');item=event.get('item',{})
        if typ in {'item.started','item.completed'} and isinstance(item,dict):
            ikind=item.get('type')
            if ikind=='mcp_tool_call' and typ=='item.completed':cli_mcp.append(item)
            elif ikind=='error':
                message=item.get('message','')
                # Known informational warnings are not failed native actions.
                if not (message=='`--dangerously-bypass-hook-trust` is enabled. Enabled hooks may run without review for this invocation.' or message.startswith('Under-development features enabled:')):
                    errors.append('unreviewed_cli_error:'+str(message)[:160])
            elif ikind not in {'mcp_tool_call','agent_message','reasoning'}:
                violations.append('nonallowed_cli_activity:'+str(ikind))
        elif typ not in {'thread.started','turn.started','turn.completed'}:
            errors.append('unreviewed_cli_event:'+str(typ))
    if Counter(map(mcp_identity,mcps))!=Counter(map(mcp_identity,cli_mcp)):errors.append('cli_rollout_mcp_activity_mismatch')
    ids=set();matched_hooks=set()
    for item in mcps:
        ident=item.get('id');full='mcp__'+str(item.get('server'))+'__'+str(item.get('tool'))
        if not isinstance(ident,str) or ident in ids:
            errors.append('duplicate_or_missing_mcp_id');continue
        ids.add(ident)
        if full not in allowed:violations.append('nonallowed_mcp_tool:'+full)
        if item.get('status') not in {'completed','failed'}:errors.append('unfinished_mcp_activity')
        if declared:
            matching=[(i,h) for i,h in enumerate(hooks) if isinstance(h,dict) and h.get('tool_use_id')==ident]
            if len(matching)!=1:errors.append('missing_or_ambiguous_mcp_hook:'+str(ident));continue
            i,hook=matching[0];matched_hooks.add(i)
            expected=hashlib.sha256(json.dumps(item.get('arguments'),sort_keys=True).encode()).hexdigest()
            if hook.get('session_id')!=session or hook.get('tool_name')!=full or hook.get('tool_input_sha256')!=expected or hook.get('config_sha256')!=binding.get('guard_sha256'):
                errors.append('mcp_hook_identity_mismatch:'+str(ident))
            if hook.get('decision')!='allow':violations.append('observed_mcp_after_nonallow_hook:'+str(ident))
    for i,hook in enumerate(hooks):
        if i not in matched_hooks:
            # A deny may be a prevented attempt, not executed escape; still no silent admission.
            errors.append('unmatched_hook_attempt_requires_review:'+str(hook.get('tool_name') if isinstance(hook,dict) else 'malformed'))
    result['controller_tool_state_verified']=False
    if tool_state_path is None:
        notes.append('Controller tool_state not supplied; no controller-state cross-check claimed.')
    else:
        state=load(tool_state_path,'tool_state_sha256')
        if not isinstance(state,dict):errors.append('invalid_controller_tool_state')
        elif type(state.get('tool_calls')) is not int or state.get('tool_calls')!=len(mcps):errors.append('controller_tool_count_mismatch')
        else:
            rows_success=state.get('tool_events')
            if not isinstance(rows_success,list):errors.append('controller_tool_events_missing')
            elif any(not isinstance(e,dict) for e in rows_success) or Counter((e.get('name'),digest(e.get('arguments'))) for e in rows_success)!=Counter((e.get('tool'),digest(e.get('arguments'))) for e in mcps if e.get('status')=='completed'):
                errors.append('controller_successful_activity_mismatch')
            else:result['controller_tool_state_verified']=True
    # Direct MCP function calls must also have inner activity receipts, not merely output text.
    for call in calls.values():
        if call.get('name') in allowed:
            try:args=parse_json(call.get('arguments',''))
            except (ValueError,TypeError):errors.append('direct_mcp_arguments_unparseable');continue
            if not any('mcp__'+str(e.get('server'))+'__'+str(e.get('tool'))==call['name'] and e.get('arguments')==args for e in mcps):
                errors.append('direct_mcp_missing_inner_receipt')
    result['observed']={'rollout_rows':len(rows),'outer_calls':len(calls),'mcp_calls':len(mcps),
                        'mcp_failed':sum(e.get('status')=='failed' for e in mcps),'hook_records':len(hooks)}
    if code_mode_review is not None:
        review=code_mode_review
        expected=[{'call_id':x['call_id'],'payload_sha256':x['payload_sha256']} for x in outer]
        if not isinstance(review,dict) or review.get('status')!='passed' or review.get('binding')!=binding or review.get('reviewed_outer_calls')!=expected or not isinstance(review.get('reviewer'),str) or not review['reviewer'].strip() or not isinstance(review.get('notes'),str) or not review['notes'].strip():
            errors.append('code_mode_review_missing_exact_binding_or_scope')
        else:
            result['code_mode_review_verified']=True;result['code_mode_review_sha256']=digest(review)
    return finish()
