"""Real CPU Docker + fake NativeRunner integration audit; ZERO LLM calls.

Only controller-authored synthetic interface material is released. This is not
research execution, actual model evolution, or a proof of native-tool isolation.
"""
import argparse,json,subprocess
from pathlib import Path
from unittest.mock import patch
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.bounded_mcp import BoundedTools
from mrhbench.container_runtime import ContainerSession
from mrhbench.evolution_native import NativeDevelopmentBuilder
from mrhbench.evolution_driver import tree_manifest
from mrhbench.io import ProtocolError,write_json,read_json,file_hash

HARNESS='''def run(task_view, model_client, tool_client, budget):
    if budget.remaining()['model_calls'] < 1:
        return {'status':'partial','content':{},'artifacts':[],'omissions':['No model budget']}
    result=model_client.complete({'task_id':task_view['task_id']},output_schema={'type':'object'})
    return {'status':'completed','content':result['response'],'artifacts':[],'omissions':[]}
'''
TEST='''import json,inspect
from pathlib import Path
import harness
abi=json.loads(Path('/inputs/interface.json').read_text())
assert abi['entry_point'].startswith('run(task_view, model_client, tool_client, budget)')
assert list(inspect.signature(harness.run).parameters)==['task_view','model_client','tool_client','budget']
class Budget:
 def __init__(self,n):self.n=n
 def remaining(self):return {'model_calls':self.n,'tool_calls':0,'wall_seconds':20,'cancelled':False}
class Fake:
 def complete(self,request,**kwargs):return {'response':{'synthetic_echo':request['task_id']}}
assert harness.run({'task_id':'interface-only'},Fake(),None,Budget(1))['content']=={'synthetic_echo':'interface-only'}
assert harness.run({'task_id':'interface-only'},Fake(),None,Budget(0))['status']=='partial'
r={'synthetic_controller_interface_test':True,'tests_passed':3,'new_model_calls':0,'scientific_task_run':False}
Path('/work/candidate/test_report.json').write_text(json.dumps(r));print(json.dumps(r))
'''

def audit(output):
 output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
 source_paths=[Path(__file__),Path(__file__).resolve().parents[2]/'mrhbench/evolution_native.py',Path(__file__).resolve().parents[2]/'mrhbench/bounded_mcp.py']
 source_hashes={str(p):file_hash(p) for p in source_paths}
 stages=output/'synthetic_stages';stages.mkdir();records=[]
 for mode in ['evolve','select','primary_and_cleanup','primary_and_audit_failure','primary_cleanup_and_audit_failure','cleanup_and_audit_failure']:
  stage=stages/mode;stage.mkdir()
  for folder in ['harness','search','search_evidence','output']:(stage/folder).mkdir()
  (stage/'harness/harness.py').write_bytes(b'CONTROLLER_SYNTHETIC_INITIAL=True\n')
  write_json(stage/'search/interface_task.json',{'synthetic_interface_only':True,'scientific_content':False})
  write_json(stage/'search_evidence/public.json',{'synthetic_public_feedback':True})
  (stage/'PRIVATE-controller.json').write_text('PRIVATE_CONTROLLER_CANARY')
  (stage/'output/preexisting.txt').write_text('OUTPUT_CANARY_NOT_INPUT')
  request={'development':True,'operation':'select' if mode=='select' else 'evolve-H0','workspace':str(stage),
    'current_harness':str(stage/'harness'),'search_directory':str(stage/'search'),
    'public_evidence_directory':str(stage/'search_evidence'),'output_directory':str(stage/'output'),
    'builder_view':{'phase':'search','search_tasks':['synthetic-interface'],
      'versions':[{'version_id':'H0','hash':file_hash(stage/'harness/harness.py')}],'search_scores':{},'search_feedback':{}}}
  trace={'mode':mode,'runner_calls':0,'tools':[]};sessions=[]
  class Session(ContainerSession):
   def __init__(self,**kw):super().__init__(**kw);sessions.append(self)
   def close(self):
    super().close()
    if mode in ('primary_and_cleanup','primary_cleanup_and_audit_failure','cleanup_and_audit_failure'):raise RuntimeError('synthetic cleanup failure AFTER real container removal')
  class Runner:
   def __init__(self,**kw):self.kw=kw
   def run(self,**kw):
    trace['runner_calls']+=1;trace['native_cwd_empty']=not list(kw['workspace'].iterdir())
    trace['native_model_and_effort']=[self.kw['model'],self.kw['reasoning_effort']]
    trace['native_tool_profile']=self.kw['tool_profile'];trace['native_permission_profile']=self.kw['permission_profile']
    trace['stage_host_path_not_in_prompt']=str(stage) not in kw['prompt']
    mcp=self.kw['mcp_servers']['mrhbench'];trace['cli_enabled_tools']=mcp['enabled_tools']
    manifest=read_json(Path(mcp['args'][-1]));bridge=BoundedTools(manifest)
    trace['server_tools']=[x['name'] for x in bridge.definitions]
    def call(name,args):
     result=bridge.call(name,args);value=json.loads(result['content'][0]['text'])
     trace['tools'].append({'name':name,'arguments':args,'result':value});return value
    try:
     listing=call('container_list',{'path':'/inputs'});trace['input_top_level']=[x['name'] for x in listing]
     for n in ['EVOLVER_PROMPT.txt','interface.json','builder_view.json','previous/harness.py','search/interface_task.json','search_evidence/public.json']:
      value=call('container_read',{'path':'/inputs/'+n});assert 'PRIVATE_CONTROLLER_CANARY' not in value['text'] and 'OUTPUT_CANARY_NOT_INPUT' not in value['text']
     for forbidden in ['/inputs/PRIVATE-controller.json','/inputs/output/preexisting.txt','/inputs/controller','/var/run/docker.sock']:
      try:call('container_read',{'path':forbidden});trace.setdefault('unexpected_readable_paths',[]).append(forbidden)
      except Exception as e:trace.setdefault('denied_paths',[]).append({'path':forbidden,'error_type':type(e).__name__})
     if mode=='select':
      # Server-side enforcement is tested independently of the CLI filter/hook.
      for name,args in [('container_write',{'path':'/work/selection_probe.txt','text':'harmless synthetic probe'}),('container_exec',{'argv':['python','-I','-S','-c','print("synthetic selection exec probe")'],'timeout':5})]:
       try:call(name,args);trace.setdefault('server_disallowed_calls_succeeded',[]).append(name)
       except ProtocolError:trace.setdefault('server_disallowed_calls_rejected',[]).append(name)
      return {'call_id':'synthetic-no-llm-selection','response':json.dumps({'version_id':'H0','reason':'Synthetic public view has only H0; no research ranking inferred.'})}
     if mode.startswith('primary_'):raise ProtocolError('synthetic PRIMARY_NATIVE_FAILURE')
     call('container_write',{'path':'/work/candidate/harness.py','text':HARNESS})
     call('container_write',{'path':'/work/candidate/test_interface.py','text':TEST})
     call('container_write',{'path':'/work/candidate/change_manifest.json','text':json.dumps({'synthetic_interface_smoke':True,'research_harness_validated':False})})
     run=call('container_exec',{'argv':['python','/work/candidate/test_interface.py'],'timeout':10});assert run['returncode']==0
     trace['actual_interface_test']=json.loads(run['stdout'])
     return {'call_id':'synthetic-no-llm-evolve','response':'Synthetic candidate and three interface assertions executed in real Docker.'}
    finally:bridge.close();trace['attached_bridge_did_not_own_lifecycle']=not bridge.owns_container
  kwargs={'binary':Path('C:/synthetic/not-executed.exe'),'ledger':None,'audit_root':output/'adapter_audit'/mode,
    'image_id':'sha256:92e6b0ef5cb3a149905fa097ae1d1ae3dd907cd19c796e057d3564d8a8fcfe01',
    'resources':{'cpus':1,'memory_mb':128,'disk_mb':16,'pids_limit':32,'wall_seconds':120},
    'native_timeout_seconds':90,'max_tool_calls':40,'max_artifact_bytes':1048576,'max_artifact_entries':100,
    'session_factory':Session,'runner_factory':Runner}
  builder=NativeDevelopmentBuilder(**kwargs);original_write=write_json
  def failure_write(path,*args,**kw):
   if Path(path).name in ('failure.json','cleanup_failure.json'):raise OSError('synthetic audit disk failure')
   return original_write(path,*args,**kw)
  try:
   with patch('mrhbench.evolution_native.write_json',failure_write if 'audit_failure' in mode else original_write):
    result=builder.select(request=request) if mode=='select' else builder.evolve(request=request)
   trace['result']=result
  except Exception as e:trace['observed_exception']={'type':type(e).__name__,'message':str(e)}
  assert len(sessions)==1
  inspect=subprocess.run(['docker','inspect',sessions[0].cid],capture_output=True,text=True,timeout=15)
  trace['actual_container_removed']=inspect.returncode!=0
  observed=read_json(next(sessions[0].audit_dir.glob('*inspect_start.json')))
  trace['actual_mounts']=[{'destination':x['Destination'],'readonly':not x['RW']} for x in observed['Mounts']]
  trace['root_readonly']=observed['HostConfig']['ReadonlyRootfs'];trace['network']=observed['HostConfig']['NetworkMode']
  trace['uid']=observed['Config']['User'];trace['actual_container_env_names']=[x.split('=',1)[0] for x in observed['Config']['Env']]
  trace['same_request_retry_rejected']=False
  try:builder.select(request=request) if mode=='select' else builder.evolve(request=request)
  except ProtocolError:trace['same_request_retry_rejected']=True
  assert trace['runner_calls']==1 and trace['actual_container_removed'] and trace['same_request_retry_rejected']
  assert trace['native_cwd_empty'] and trace['stage_host_path_not_in_prompt']
  assert not trace.get('unexpected_readable_paths')
  assert trace['actual_mounts']==[{'destination':'/inputs','readonly':True}]
  assert trace['network']=='none' and trace['root_readonly'] and trace['uid']=='10001:10001'
  if mode.startswith('primary_'):assert trace['observed_exception']=={'type':'ProtocolError','message':'synthetic PRIMARY_NATIVE_FAILURE'}
  if mode=='cleanup_and_audit_failure':assert trace['observed_exception']['type']=='RuntimeError' and 'synthetic cleanup failure' in trace['observed_exception']['message']
  if mode=='evolve':
   candidate=stage/'output/candidate';trace['published_manifest']=tree_manifest(candidate)
   assert trace['published_manifest']==trace['result']['files'] and (candidate/'harness.py').read_bytes()==HARNESS.encode()
   assert read_json(candidate/'test_report.json')['tests_passed']==3
  if mode=='select':
   trace['no_candidate_publication']=not (stage/'output/candidate').exists()
   assert trace['no_candidate_publication'] and not trace.get('server_disallowed_calls_succeeded')
   assert set(trace['server_disallowed_calls_rejected'])=={'container_write','container_exec'}
  records.append(trace)
 end_hashes={str(p):file_hash(p) for p in source_paths}
 assert source_hashes==end_hashes,'Source changed during audit; retain attempt but do not certify snapshot'
 write_json(output/'audit.json',{'new_model_calls':0,'fake_native_runner':True,'real_cpu_docker_sessions':len(records),'not_actual_model_evolution':True,'formal_isolation_verified':False,'cases':records,'source_hashes':source_hashes,'source_hashes_unchanged_at_end':True})
 print(json.dumps({'audit':str(output/'audit.json'),'cases':[{'mode':x['mode'],'error':x.get('observed_exception'),'readonly_bypass':x.get('server_disallowed_calls_succeeded',[]),'removed':x['actual_container_removed']} for x in records]}))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);audit(p.parse_args().output)
