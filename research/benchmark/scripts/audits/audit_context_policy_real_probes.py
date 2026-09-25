"""Independent read-only review of context probes183/184; no model calls."""
from pathlib import Path
import hashlib
import json
import subprocess

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.context_policy import catalog_snapshot,config_setting
from mrhbench.io import digest,file_hash,read_json,write_json


def main():
    base=Path('D:/mrhbench-local-pilot'); root=Path(__file__).resolve().parents[2]
    ledger=read_json(root/'audit/development_call_ledger.json'); audited=[]
    for stem in ['context-native-probe-20260923-001','context-json-probe-20260923-001']:
        directory=base/stem; result=read_json(directory/'results.json'); capture=result['rollout']
        original={str(p):file_hash(p) for p in directory.rglob('*') if p.is_file()}
        rollout=Path(capture['path']);assert file_hash(rollout)==capture['sha256']
        rows=[json.loads(line) for line in rollout.read_text(encoding='utf8').splitlines()]
        assert len(rows)==capture['row_count']
        invocation=read_json(next(directory.rglob('invocation.json')))
        policy=read_json(directory/'context_policy.json')
        assert invocation['opt_in_context_policy']['policy']==policy
        assert invocation['opt_in_context_policy']['sha256']==digest(policy)==result['policy_hash']
        args=invocation['args'];setting=config_setting(policy,Path(args[0]))
        assert [(args[i-1],x) for i,x in enumerate(args) if x.startswith('skills.config=')]==[('-c',setting)]
        assert file_hash(Path(args[0]))==policy['binary_sha256']==invocation['binary_sha256']
        messages=[r['payload'] for r in rows if r['type']=='response_item' and r['payload'].get('type')=='message']
        dev=[m for m in messages if m['role']=='developer'];assert len(dev)==3
        catalog=catalog_snapshot(messages);assert catalog['status']=='not_present_in_render'
        calls=[{'row':i,**r['payload']} for i,r in enumerate(rows) if r['type']=='response_item' and r['payload'].get('type') in {'custom_tool_call','function_call'}]
        outputs=[r['payload'] for r in rows if r['type']=='response_item' and r['payload'].get('type') in {'custom_tool_call_output','function_call_output'}]
        assert {c['call_id'] for c in calls}=={o['call_id'] for o in outputs}
        per_row=[{'row':i,'outer_type':r['type'],'inner_type':r.get('payload',{}).get('type'),
                  'payload_sha256':digest(r.get('payload',{})),
                  'review_scope':'Opaque encrypted reasoning accounted by hash only, not decoded.' if r.get('payload',{}).get('type')=='reasoning' else 'Visible message/action/event structure reviewed.'}
                 for i,r in enumerate(rows)]
        billed=[r for r in ledger['attempts'] if r['id']==result['call_id']]
        assert len(billed)==1 and billed[0]['status']=='completed'
        final=next(m for m in reversed(messages) if m['role']=='assistant')
        final_json=json.loads(''.join(b['text'] for b in final['content']))
        detail={'mode':result['mode'],'call_id':result['call_id'],'row_count':len(rows),
            'row_accounting':per_row,'rollout_sha256':file_hash(rollout),'binary_sha256':policy['binary_sha256'],
            'actual_command_policy_match':True,'policy_sha256':digest(policy),'command_sha256':digest(args),
            'developer_catalogue':catalog,'developer_text_blocks':len(dev),
            'base_instruction_sha256':digest(rows[0]['payload']['base_instructions']),
            'remaining_context':'Builtin Codex base instructions (including generic skill-use guidance), permission instructions, collaboration instructions and environment context persist. No bare-API equivalence.',
            'ledger_settlements':len(billed),'ledger_status':billed[0]['status'],'usage':billed[0]['usage'],
            'billed_wall_seconds':billed[0]['wall_seconds'],'dollar_cost':billed[0]['dollar_cost'],
            'tools':calls,'final_json':final_json,'formal_isolation':False}
        if result['mode']=='native':
            work=next((directory/'native').iterdir()); state=read_json(work/'tool_state.json');guard=read_json(work/'guard.json')
            events=[(i,r['payload']['item']) for i,r in enumerate(rows) if r['type']=='event_msg' and r['payload'].get('item',{}).get('type')=='McpToolCall']
            hooks=[read_json(p) for p in (work/'hook_events').glob('*.json')]
            assert len(events)==len(hooks)==state['tool_calls']==9
            received=[]
            for output in outputs:
                for block in output.get('output',[]):
                    try:obj=json.loads(block.get('text',''))
                    except ValueError:continue
                    if isinstance(obj,dict) and 'content' in obj:received.append(obj)
            verified=[]
            for i,event in events:
                matching=[h for h in hooks if h['tool_use_id']==event['id']];assert len(matching)==1
                hook=matching[0]
                assert hook['session_id']==capture['session_id'] and hook['decision']=='allow'
                assert hook['tool_name']=='mcp__mrhbench__'+event['tool'] and hook['tool_name'] in guard['allowed_tools']
                assert hook['config_sha256']==file_hash(work/'guard.json')
                assert hook['tool_input_sha256']==hashlib.sha256(json.dumps(event['arguments'],sort_keys=True).encode()).hexdigest()
                assert event['result'] in received
                assert event['arguments']['path'].startswith('/inputs/')
                check={'row':i,'tool':event['tool'],'arguments':event['arguments'],'status':event['status'],
                       'hook_match':True,'actual_outer_tool_result_delivered':True}
                if event['tool']=='container_read':
                    body=json.loads(event['result']['content'][0]['text']);path=work/'container/release'/body['path'].removeprefix('/inputs/')
                    assert body['text']==path.read_bytes().decode('utf-8')
                    check.update(released_file_sha256=file_hash(path),actual_read_text_exact=True)
                verified.append(check)
            assert len(state['tool_events'])==8
            failures=[e for _,e in events if e['status']!='completed'];assert len(failures)==1
            assert failures[0]['arguments']['path']=='/inputs/search_evidence'
            assert not (work/'container/release/search_evidence').exists()
            native=read_json(work/'native_result.json');selection=read_json(work/'selection.json')
            assert isinstance(native['response'],dict) and native['response']==selection==result['selection']==final_json
            cid=state['container_identity']['cid']; probe=subprocess.run(['docker','inspect',cid],capture_output=True,text=True)
            removal=read_json(next((work/'container').glob('*-remove_owned.json')))
            assert removal['returncode']==0 and removal['argv']==['docker','rm','-f',cid]
            assert probe.returncode!=0 and 'No such' in probe.stderr
            discovered=[]
            for block in outputs[0]['output']:
                try:obj=json.loads(block.get('text',''))
                except ValueError:continue
                if isinstance(obj,list):discovered.extend(x['name'] for x in obj if isinstance(x,dict) and 'name' in x)
            detail.update(mcp_events=verified,hook_events=hooks,tool_attempts=9,successful_tool_events=8,
                native_outer_exec_calls=len(calls),visible_discovery_tool_names=discovered,
                selector_dict_fix_actual_pass=True,selection=selection,cleanup={'container_id':cid,'owned_remove_success':True,'independent_inspect_absent':True},
                observed_failure={'path':'/inputs/search_evidence','cause':'Empty directory has no released input files and was not materialized. Prompt advertised it; this list failure was not a forbidden-path block or scientific failure.',
                    'recommendation':'Publish an explicit empty-evidence index/notice or create the promised safe directory. Do not erase the historical failed attempt.'},
                boundary='Only allowed MCP reads/lists observed, no host/network/write execution. No deny/escape attempted; guard enforcement against hostile actions is not established by this benign probe. apply_patch and resource-tool metadata remained discoverable.')
        else:
            assert not calls and not outputs and json.loads(final_json['payload_json'])=={'sum':42}==result['response']
            detail.update(json_wire_and_decoded_match=True,no_native_tools_observed=True,
                          boundary='One arithmetic JSON request succeeded without tools; not proof native tools cannot be reached for adversarial prompts or equivalence to a bare API.')
        assert original=={str(p):file_hash(p) for p in directory.rglob('*') if p.is_file()}
        detail['historical_probe_files_unchanged']=True
        audited.append(detail)
    out={'schema_version':'context-policy-real-probes-independent-review-1','new_model_calls_by_reviewer':0,
         'reviewed_existing_model_calls':[183,184],'runs':audited,
         'conclusion':'Both actual invocations used the exact binary-bound21-path denylist and omitted the visible skill catalogue. Native selector now accepts the actual dict response and uses allowed container reads/list; JSON wrapper decodes42 without native activity. One advertised empty directory was missing. These are bounded development interface/context observations, not formal OS isolation, full research evolution, or bare-model equivalence.'}
    write_json(root/'audit/context_policy_real_probes_independent_review_v1.json',out,exclusive=True)
    print(json.dumps({'audited_calls':[r['call_id'] for r in audited],'rows':[r['row_count'] for r in audited],
                      'unchanged':all(r['historical_probe_files_unchanged'] for r in audited),'new_model_calls':0}))


if __name__=='__main__':main()
