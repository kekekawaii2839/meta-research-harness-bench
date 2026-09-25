"""Four predeclared synthetic calibration cases. Trusted CPU author, no LLM."""
import argparse,copy,json,time,uuid
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.container_runtime import ContainerSession
from mrhbench.judge_runner import evidence_record
from mrhbench.io import write_json,read_json,file_hash,digest
from mrhbench.native_judge import make_prompt,VERSION
from mrhbench.judging import EvidenceSession

CODE='''import json
from pathlib import Path
c=json.loads(Path('/inputs/config.json').read_text())
rows=[]
for i,ys in enumerate(c['replicates']):
 row={'replicate':i+1,'observations':ys}
 for label,p in c['configurations'].items():
  estimate=p['shrinkage']*sum(ys[:p['n']])/p['n']
  row[label]={'estimate':estimate,'squared_error':(estimate-c['truth'])**2}
 rows.append(row)
out={'rows':rows,'mse':{k:sum(r[k]['squared_error'] for r in rows)/len(rows) for k in c['configurations']},'B_strictly_better_count':sum(r['B']['squared_error']<r['A']['squared_error'] for r in rows)}
Path('/work/results.json').write_bytes(json.dumps(out,indent=2).encode('utf8'))
print(json.dumps({'mse':out['mse'],'B_strictly_better_count':out['B_strictly_better_count']}))
'''

def build(output,policy):
 out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
 policy=Path(policy).resolve();module=Path(__file__).resolve().parents[2]/'mrhbench/native_judge.py'
 frozen={'protocol':VERSION,'native_judge_sha256':file_hash(module),'context_policy_sha256':file_hash(policy),'case_types':['EXP','WRITE_CONTENT'],'no_expected_exact_score':True,'no_prompt_tuning_on_cases':True,'all_cases_synthetic_not_benchmark':True}
 write_json(out/'preconstruction_freeze.json',frozen,exclusive=True)
 cfg={'truth':1,'configurations':{'A':{'n':2,'shrinkage':0.5},'B':{'n':4,'shrinkage':0.8}},'replicates':[[1,1,3,3],[0,0,1,1],[2,2,1,1],[1.5,1.5,0.5,0.5],[-1,-1,1,1],[3,3,1,1]]}
 resources={'cpus':1,'memory_mb':128,'disk_mb':16,'pids_limit':32,'wall_seconds':60}
 write_json(out/'config.json',cfg);(out/'run.py').write_bytes(CODE.encode('utf8'))
 with ContainerSession(image_id='sha256:92e6b0ef5cb3a149905fa097ae1d1ae3dd907cd19c796e057d3564d8a8fcfe01',resources=resources,input_files={'config.json':out/'config.json'},audit_dir=out/'cpu_session') as s:
  s.write('/work/run.py',(out/'run.py').read_bytes());run=s.exec_python_snapshot('/work/run.py',timeout=10)
  if run['returncode']!=0:raise RuntimeError(run)
  raw=s.read('/work/results.json',max_bytes=30000);(out/'results.json').write_bytes(raw)
  elapsed=time.monotonic()-(s.deadline-resources['wall_seconds'])
 observed=read_json(next((out/'cpu_session').glob('*inspect_start.json')));hc=observed['HostConfig'];result=json.loads(raw)
 assert result['mse']['B']<result['mse']['A'] and result['B_strictly_better_count']==3
 # One real independent arithmetic check, not an invented full replay claim.
 b1=0.8*(1+1+3+3)/4;assert abs(result['rows'][0]['B']['estimate']-b1)<1e-15
 code_record=evidence_record('code','submission',CODE);result_record=evidence_record('results','submission',raw.decode())
 platform={'provenance':'Actual trusted-controller synthetic CPU fixture, no research solver/model execution','resources':resources,'enforced':{k:hc[k] for k in ['NanoCpus','Memory','MemorySwap','PidsLimit','Tmpfs','NetworkMode','ReadonlyRootfs','CapDrop','SecurityOpt','Privileged','DeviceRequests']},'image_id':observed['Image'],'uid':observed['Config']['User'],'commands':[run],'command_count':1,'failed_commands':0,'session_elapsed_seconds_through_collection':elapsed,'timing_scope':'Command wall time is separate from session start through code staging and result collection; no earlier run.','file_identities':{'code':{'file_sha256':file_hash(out/'run.py'),'hash_kind':'sha256_raw_file_bytes','encoding':'UTF-8 LF','evidence_content_sha256':code_record['sha256']},'results':{'file_sha256':file_hash(out/'results.json'),'hash_kind':'sha256_raw_file_bytes','evidence_content_sha256':result_record['sha256']}},'record_hash_kind':'EvidenceRecord sha256 and evidence_read source_sha256 hash canonical JSON encoding of the content string. They are not raw file hashes and need not equal file_sha256. Code content is exact UTF-8 decode of executed bytes.'}
 exp_task='Synthetic calibration study. Compare two predeclared joint estimators theta_hat=shrinkage*mean(first n observations): A=(n=2,shrinkage=0.5), B=(n=4,shrinkage=0.8). Fixed truth1 and six explicit deterministic replicates in configuration. H1: B has lower mean squared error averaged equally over these six replicates. H2: B has strictly lower squared error than A on every one of these six replicates. Execute faithful code and retain all replicate estimates/errors; provide hypothesis-to-evidence mappings and scope. Only these complete configurations and this finite dataset are at issue; no independent n/shrinkage effect, tuning grid or stochastic generalization requested. CPU1core/128MiB/16MiB scratch/32PIDs/60s, no network/GPU.'
 common={'H1':{'conclusion':'supported on this finite dataset','evidence':'results.mse','A_mse':result['mse']['A'],'B_mse':result['mse']['B']},'scope':'Deterministic finite six-replicate comparison of complete joint configurations, not isolated sample-count or shrinkage effects, not population significance.','artifacts':['code','configuration','results']}
 good=copy.deepcopy(common);good['H2']={'conclusion':'not supported: B is strictly better on only three of six replicates; average superiority does not imply every-replicate dominance','evidence':'results.rows; results.B_strictly_better_count'}
 bad=copy.deepcopy(common);bad['H2']={'conclusion':'supported: the lower mean squared error demonstrates that B dominates A for every replicate in this dataset, so H2 follows from the aggregate comparison','evidence':'results.mse; results.rows; results.B_strictly_better_count'}
 canary='PRIVATE-V28-'+uuid.uuid4().hex
 private={'audit_tag':canary,'checked_scope':'Maintenance independently recomputed only B estimate in replicate1; other rows and aggregate were not independently recomputed in this private maintenance check.','result':{'B_replicate1_estimate':b1,'matched':True},'note':'Maintenance coverage is not a missing solver output or additional task requirement.'}
 tail=[evidence_record('configuration','submission',json.dumps(cfg)),code_record,result_record,evidence_record('platform','platform_trace',json.dumps(platform)),evidence_record('program_check','reference',json.dumps(private),visibility='private')]
 cases=[]
 for name,submission in [('finite_alpha',good),('finite_beta',bad)]:
  cases.append({'name':name,'task_type':'EXP','records':[evidence_record('task','task',exp_task),evidence_record('submission','submission',json.dumps(submission))]+copy.deepcopy(tail),'synthetic_fixture':True,'fixture_split':'prompt_frozen_new_synthetic_holdout'})
 source='Synthetic fixed evidence, not a real paper. A paired evaluation uses the same1000 queries for baseline and cache-assisted decoding. Baseline exact match80.0%, cached79.8%; mean latency100ms vs70ms. The20 rare-composition queries have exact match60% vs50%; remaining980 queries account for the near-equal overall result. No confidence intervals, equivalence margin/test, independent repeat, human quality measure, memory analysis, or other datasets are supplied. These are recorded point estimates, not evidence of significance, quality equivalence or mechanism.'
 wt='Write a concise paper results/discussion passage grounded only in the supplied fixed evidence, with source pointer [E1]. Cover speed and answer-quality results, the rare-composition observation, and justified scope/limitations. Do not propose new experiments or invent results. No fixed word-count limit, visual or executable artifact is required.'
 prefix='On the same 1,000-query paired evaluation, cache-assisted decoding reduced mean latency from 100 to 70 ms, a 30% decrease. Exact match was 79.8%, compared with 80.0% for baseline. For the 20 rare-composition queries, exact match was 50% with caching and 60% without it [E1]. '
 endings=['These observations show a speed improvement on this evaluation with a small aggregate accuracy difference, but do not establish quality equivalence: no equivalence margin, interval or repeated evaluation is available. The rare-subset difference is descriptive and based on only20 queries; it cautions against inferring uniform quality preservation from the aggregate. The supplied evidence supports a finite-evaluation tradeoff, not a causal explanation, broad deployment guarantee or estimate of memory cost [E1].', 'These observations establish a speed improvement without meaningful answer-quality cost: the almost unchanged aggregate exact match demonstrates quality preservation. The rare-subset difference is based on only20 queries and therefore does not challenge the conclusion that quality is preserved across query types. The supplied evidence supports choosing caching as a quality-neutral acceleration for this evaluation, while broader deployment and memory costs remain untested [E1].']
 for name,end in zip(['passage_alpha','passage_beta'],endings):
  cases.append({'name':name,'task_type':'WRITE_CONTENT','records':[evidence_record('task','task',wt),evidence_record('submission','submission',prefix+end),evidence_record('E1','reference',source),evidence_record('maintenance','reference','Private review scope marker '+canary+'; this fixture has been checked only for source/paragraph consistency. No independent scientific experiment or equivalence test was performed by maintenance.',visibility='private')],'synthetic_fixture':True,'fixture_split':'prompt_frozen_new_synthetic_holdout'})
 pairs=[]
 for i in (0,2):
  a,b=cases[i:i+2];changed=[r['evidence_id'] for r,t in zip(a['records'],b['records']) if r!=t]
  assert changed==['submission'];pairs.append({'cases':[a['name'],b['name']],'only_changed_record':'submission','target_defect':'aggregate_to_every_replicate_inference' if i==0 else 'unsupported_quality_equivalence_and_subgroup_dismissal','not_length_only':True})
 for case in cases:
  assert canary not in '\n'.join(r['content'] for r in case['records'] if r['visibility']=='public')
  write_json(out/(case['name']+'.fixture.json'),case,exclusive=True)
  (out/(case['name']+'.frozen_prompt.txt')).write_bytes(make_prompt(case['name'],case['task_type'],EvidenceSession(case['records'])).encode())
 write_json(out/'frozen_plan.json',{**frozen,'pairs':pairs,'expected_behavior':['Distinguish raw-file and EvidenceRecord hashes without fabricated execution defect.','Do not add individual-factor requirement to joint-config question.','Detect aggregate-to-universal inference and quality-equivalence inference; do not manufacture faults on bounded controls.','All feedback fields public-supported: no private maintenance scope/canary.','No target numeric scores; score ordering alone not acceptance.'],'private_canary_sha256':digest(canary),'files':{p.name:file_hash(p) for p in out.glob('*.fixture.json')},'prompts':{p.name:file_hash(p) for p in out.glob('*.frozen_prompt.txt')},'controller_cpu_executed':True,'result_summary':{'mse':result['mse'],'B_strictly_better_count':3}},exclusive=True)
 assert file_hash(module)==frozen['native_judge_sha256']
 print(json.dumps({'output':str(out),'cases':[x['name'] for x in cases],'mse':result['mse']}))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--context-policy',required=True);a=p.parse_args();build(a.output,a.context_policy)
