"""Explicit bounded developer probe: one native selection OR one JSON call.

Synthetic inputs only. No global settings/credentials changed. Not formal
bare-model equivalence, scientific evolution, or host isolation acceptance.
"""
import argparse
import functools
import json
from pathlib import Path
import re
import sys
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.context_policy import build_policy,catalog_snapshot
from mrhbench.costs import CallLedger
from mrhbench.evolution_driver import tree_manifest
from mrhbench.evolution_native import NativeDevelopmentBuilder
from mrhbench.io import digest,read_json,write_json,file_hash
from mrhbench.native_codex import NativeCodexRunner
from mrhbench.providers import CodexJSONTransport

ROOT=Path(__file__).resolve().parents[2]


def observe_rollout(capture):
    if capture.get('status')!='captured':return {'verified':False,'reason':'No exact rollout'}
    p=Path(capture['path'])
    if file_hash(p)!=capture['sha256']:raise ValueError('Exact rollout changed')
    rows=[json.loads(line) for line in p.read_text(encoding='utf8').splitlines()]
    messages=[r['payload'] for r in rows if r.get('type')=='response_item' and r.get('payload',{}).get('type')=='message']
    developers=[c.get('text','') for m in messages if m.get('role')=='developer' for c in m.get('content',[])]
    paths=[p for text in developers for p in re.findall(r'\(file: ([^)]+SKILL\.md)\)',text)]
    parsed=catalog_snapshot([{'type':'message','role':'developer','content':[{'type':'input_text','text':t} for t in developers]}])
    unexplained=parsed['status']=='not_present_in_render' and any('### Available skills' in t or '(file:' in t for t in developers)
    return {'verified':bool(developers) and not unexplained,'catalogue_status':parsed['status'],
            'developer_text_blocks':len(developers),'visible_skill_catalog_paths':paths,
            'observed_tools':capture.get('observed_tools'),'scope':'Observed exact invocation only, not future catalogs or all implicit knowledge.'}


def probe(*,binary,baseline,output,mode,image_id=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    policy=build_policy(read_json(baseline),Path(binary));write_json(output/'context_policy.json',policy,exclusive=True)
    ledger=CallLedger(ROOT/'audit/development_call_ledger.json')
    before=ledger.summary()['used_runs_including_failures']
    summary={'mode':mode,'new_call_limit':1,'policy_hash':digest(policy),'formal':False,'scientific_input':False}
    try:
        if mode=='native':
            stage=output/'stage';stage.mkdir()
            for name in ['harness','search','search_evidence']:(stage/name).mkdir()
            (stage/'harness/harness.py').write_text('# Synthetic context/selection probe only\n',encoding='utf8')
            write_json(stage/'search/task.json',{'task_id':'synthetic','test_fixture':True,'scientific_task':False})
            request={'development':True,'operation':'select','workspace':str(stage),'current_harness':str(stage/'harness'),
                'search_directory':str(stage/'search'),'public_evidence_directory':str(stage/'search_evidence'),
                'output_directory':str(stage/'output'),'builder_view':{'phase':'search','search_tasks':['synthetic'],
                'versions':[{'version_id':'H0','hash':digest(tree_manifest(stage/'harness'))}],
                'search_scores':{'H0':{'synthetic_note':'No scientific score, interface probe only.'}},'search_feedback':{}}}
            adapter=NativeDevelopmentBuilder(binary=Path(binary),ledger=ledger,audit_root=output/'native',image_id=image_id,
                resources={'cpus':1,'memory_mb':512,'disk_mb':64,'pids_limit':64,'wall_seconds':180},
                native_timeout_seconds=150,max_tool_calls=30,max_artifact_bytes=1024**2,max_artifact_entries=100,
                runner_factory=functools.partial(NativeCodexRunner,context_policy=policy))
            summary['selection']=adapter.select(request=request)
            native=read_json(output/'native'/digest(request)/'native_result.json')
            summary['native_response_type']=type(native['response']).__name__
            summary['call_id']=native['call_id'];summary['rollout']=native['rollout_capture']
        else:
            transport=CodexJSONTransport(binary=Path(binary),model='gpt-5.6-sol',reasoning_effort='medium',ledger=ledger,
                audit_root=output/'json',timeout_seconds=120,context_policy=policy)
            result=transport.complete({'instruction':'Return the integer sum of 19 and 23. Do not use any tools.'},
                output_schema={'type':'object','properties':{'sum':{'type':'integer'}},'required':['sum'],'additionalProperties':False},role='probe')
            summary.update(call_id=result['call_id'],response=result['response'])
            summary['rollout']=read_json(Path(result['audit_directory'])/'rollout_capture.json')
        summary['context_observation']=observe_rollout(summary['rollout'])
    except Exception as exc:
        summary['error']={'type':type(exc).__name__,'message':str(exc)}
    finally:
        summary['new_calls']=ledger.summary()['used_runs_including_failures']-before
        summary['automatic_retry']=False
        write_json(output/'results.json',summary,exclusive=True)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True,type=Path);p.add_argument('--baseline',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--mode',required=True,choices=['native','json']);p.add_argument('--image-id')
    a=p.parse_args()
    if a.mode=='native' and not a.image_id:p.error('native mode requires an explicit frozen image ID')
    probe(binary=a.binary,baseline=a.baseline,output=a.output,mode=a.mode,image_id=a.image_id)
