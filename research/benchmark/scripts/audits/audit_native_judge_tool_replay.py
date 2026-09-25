"""Zero-call historical receipt replay; not preventative security validation."""
import sys,json,contextlib,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from inspect_judge_holdout_trajectory import inspect
from mrhbench.io import read_json,file_hash,write_json
from mrhbench.native_judge import restore_session,validate_native_result
root=Path('D:/mrhbench-local-pilot/judge-v28-robustness-runs-20260923-001')
rows=[]
for case in ['exact_repeat','submission_paraphrase','evidence_order']:
 out=root/case;buf=io.StringIO()
 with contextlib.redirect_stdout(buf):stats=inspect(root,case)
 call=read_json(out/'native_call.json');state=read_json(out/'tool_state.json');manifest=read_json(out/'evidence_manifest.json')
 invocation=read_json(Path(call['audit_directory'])/'invocation.json')
 delivered={x['receipt'] for x in stats['text_deliveries']}
 assert delivered==set(state['receipts'])
 restored=restore_session(manifest['records'],state)
 valid=validate_native_result('WRITE_CONTENT',read_json(out/'candidate_judgment.json'),restored)
 assert valid['quality']==read_json(out/'result.json')['quality']
 rollout=[json.loads(x) for x in Path(call['rollout_capture']['path']).read_text(encoding='utf8').splitlines()]
 calls=[r['payload'] for r in rollout if r.get('type')=='response_item' and r['payload'].get('type') in ('function_call','custom_tool_call')]
 outputs=[r['payload'] for r in rollout if r.get('type')=='response_item' and r['payload'].get('type') in ('function_call_output','custom_tool_call_output')]
 assert {x['call_id'] for x in calls}=={x['call_id'] for x in outputs}
 row={'case':case,'call_id':call['call_id'],'native_call_sha256':file_hash(out/'native_call.json'),'state_sha256':file_hash(out/'tool_state.json'),'manifest_sha256':file_hash(out/'evidence_manifest.json'),'rollout_sha256':stats['rollout_sha256'],'capture':call['rollout_capture'],'all_state_receipts_delivered_exactly':True,'receipt_count':len(delivered),'outer_calls_outputs_bijective':len(calls)==len(outputs),'tool_actions':stats['tool_actions'],'tool_events':state['tool_events'],'tool_call_count':state['tool_calls'],'hook_configured':'optional_hook_guard' in invocation,'image_blocks':stats['image_blocks'],'revalidated_quality':valid['quality']}
 rows.append(row)
 print(json.dumps({k:v for k,v in row.items() if k not in ('capture',)},ensure_ascii=False))
write_json(Path(__file__).resolve().parents[2]/'audit/native_judge_189_191_tool_replay_v1.json',{'zero_model_calls':True,'scope':'Posthoc observable text delivery and receipt replay, not preventative isolation or new scientific review','cases':rows},exclusive=True)
