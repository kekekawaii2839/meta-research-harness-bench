"""Synthetic EXP calibration for claim scope and private-audit feedback boundaries.

Trusted controller code; experiment runs in new CPU Docker. No model call here.
The private audit metadata/canary must never enter public evidence.
"""
import argparse,json,time,uuid,hashlib
from pathlib import Path
from mrhbench.container_runtime import ContainerSession
from mrhbench.judge_runner import evidence_record
from mrhbench.io import write_json,read_json,file_hash
from mrhbench.native_judge import make_prompt,VERSION
from mrhbench.judging import EvidenceSession

CODE='''import json
from pathlib import Path
c=json.loads(Path('/inputs/config.json').read_text())
out={}
for name,p in c['joint_configurations'].items():
 x=float(c['x0']);v=0.0;rows=[{'step':0,'x':x,'v':v,'loss':0.5*(x-3)**2}]
 for t in range(1,c['steps']+1):
  g=x-3;v=p['beta']*v+g;x=x-p['eta']*v
  rows.append({'step':t,'x':x,'v':v,'loss':0.5*(x-3)**2})
 out[name]=rows
Path('/work/results.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'final_losses':{k:v[-1]['loss'] for k,v in out.items()},'steps':c['steps']}))
'''

def build(output):
 out=Path(output);out.mkdir(parents=True,exist_ok=False)
 cfg={'x0':0.0,'v0':0.0,'steps':12,'joint_configurations':{'A':{'eta':0.1,'beta':0.0},'B':{'eta':0.2,'beta':0.6}}}
 resources={'cpus':1,'memory_mb':128,'disk_mb':16,'pids_limit':32,'wall_seconds':60}
 write_json(out/'config.json',cfg);(out/'run.py').write_text(CODE,encoding='utf8')
 write_json(out/'prompt_freeze.json',{'protocol':VERSION,'prompt_sha256':hashlib.sha256(make_prompt('joint-policy-freeze','EXP',EvidenceSession([])).encode()).hexdigest(),'frozen_before_fixture_execution':True})
 with ContainerSession(image_id='sha256:92e6b0ef5cb3a149905fa097ae1d1ae3dd907cd19c796e057d3564d8a8fcfe01',resources=resources,input_files={'config.json':out/'config.json'},audit_dir=out/'cpu_session') as c:
  c.write('/work/run.py',CODE.encode());run=c.exec_python_snapshot('/work/run.py',timeout=10)
  if run['returncode']!=0:raise RuntimeError(run)
  raw=c.read('/work/results.json',max_bytes=20000);(out/'results.json').write_bytes(raw)
  elapsed=time.monotonic()-(c.deadline-resources['wall_seconds'])
 observed=read_json(next((out/'cpu_session').glob('*inspect_start.json')))
 results=json.loads(raw);fa=results['A'][-1]['loss'];fb=results['B'][-1]['loss'];assert fb<fa and fa<4.5 and fb<4.5
 task='Synthetic CPU calibration study, not real research-agent performance. Fixed objective f(x)=0.5*(x-3)^2. Update v_(t+1)=beta*v_t+(x_t-3), x_(t+1)=x_t-eta*v_(t+1); x0=v0=0. Compare only two predeclared joint configurations A=(eta0.1,beta0.0) and B=(eta0.2,beta0.6), for exactly12 updates from the same initial state. H1: B has lower final loss than A at step12. H2: each configuration has lower final loss than its common initial loss. The question is a finite-horizon comparison of these complete configurations, not attribution to separate factors, global tuning, or asymptotic convergence. Return faithful code, full step trajectories and brief hypothesis/evidence mapping. Deterministic numerical comparisons need no p-value. CPU1core/128MiB/16MiB scratch/32PIDs/60s, no network/GPU.'
 submission={'H1':{'conclusion':'supported for the two specified joint configurations at step12','A_final_loss':fa,'B_final_loss':fb,'evidence':'results:A[12].loss,B[12].loss'},'H2':{'conclusion':'supported for both configurations at step12','initial_loss':4.5,'evidence':'results:A[0],A[12],B[0],B[12]'},'scope':'Finite deterministic run with specified initial state and floating-point arithmetic. No isolated eta or beta effect, untested combination, monotonic trajectory, statistical significance or asymptotic claim is made.','code':'code record','configuration':'configuration record','results':'results record'}
 hc=observed['HostConfig'];platform={'provenance':'Real trusted-controller CPU execution of this synthetic fixture; no model solver run','resources':resources,'observed':{k:hc[k] for k in ['NanoCpus','Memory','MemorySwap','PidsLimit','Tmpfs','NetworkMode','ReadonlyRootfs','CapDrop','SecurityOpt','Privileged','DeviceRequests']},'image_id':observed['Image'],'uid':observed['Config']['User'],'commands':[run],'scientific_command_count':1,'failed_commands':0,'task_elapsed_seconds_at_final_evidence':elapsed,'timing_scope':'From immediately before daemon start through staging code, sole execution, and result collection. Command duration is separately recorded; no model waiting or earlier attempts. Later cleanup is not scientific work.','entrypoint_sha256':file_hash(out/'run.py'),'results_sha256':file_hash(out/'results.json')}
 # Small genuine independent maintenance check, deliberately not a comprehensive replay.
 expected_x=0.0-0.1*(0.0-3.0);expected_loss=0.5*(expected_x-3.0)**2
 assert abs(results['A'][1]['x']-expected_x)<1e-15 and abs(results['A'][1]['loss']-expected_loss)<1e-15
 private={'kind':'private maintenance program_check','audit_tag':'PRIVATE-COVERAGE-'+uuid.uuid4().hex,'checked_scope':'Independently recalculated only the first A update and its loss. The remaining steps and B were not independently rerun in this maintenance check.','checked_result':{'A_step1_x':expected_x,'A_step1_loss':expected_loss,'matched':True},'scope_note':'This private maintenance coverage is not missing solver evidence and does not alter the scientific task. The full public trajectories and actual controller execution are available.'}
 records=[evidence_record('task','task',task),evidence_record('submission','submission',json.dumps(submission)),evidence_record('configuration','submission',json.dumps(cfg)),evidence_record('code','submission',CODE),evidence_record('results','submission',raw.decode()),evidence_record('platform','platform_trace',json.dumps(platform)),evidence_record('program_check','reference',json.dumps(private),visibility='private')]
 public='\n'.join(x['content'] for x in records if x['visibility']=='public');assert private['audit_tag'] not in public and private['checked_scope'] not in public
 write_json(out/'joint_config_scope.fixture.json',{'name':'joint_config_scope','task_type':'EXP','synthetic_fixture':True,'actual_cpu_execution':True,'fixture_split':'single_prompt_frozen_development_holdout','records':records,'review_expectations':{'no_unrequested_factorial_design':True,'all_feedback_fields_no_private_audit_scope':True,'no_forced_grade':True},'private_canary':private['audit_tag']})
 write_json(out/'construction.json',{'new_model_calls':0,'scientific_results':{'A_final_loss':fa,'B_final_loss':fb},'public_evidence_excludes_private_canary_and_scope':True,'independent_check_real_not_fabricated':True,'controller_authored_not_solver_performance':True,'task_elapsed_seconds':elapsed,'private_audit_metadata_not_benchmark_answer':True})
 print(json.dumps({'output':str(out),'A_final_loss':fa,'B_final_loss':fb,'public_canary_absent':True}))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);build(p.parse_args().output)
