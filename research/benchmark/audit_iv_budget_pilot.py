"""Independent mechanical IV checks; submitted code executes only in Docker."""
import ast,collections,json,math,statistics,subprocess
from pathlib import Path
from mrhbench.io import read_json,write_json,file_hash,utc_now
from mrhbench.container_runtime import ContainerSession
from mrhbench.judge_runner import evidence_record

def strict(text):
 def pairs(items):
  result={}
  for k,v in items:
   if k in result:raise ValueError('Duplicate JSON key: '+k)
   result[k]=v
  return result
 def invalid(x):raise ValueError('Nonstandard numeric token '+x)
 def decimal_number(x):
  value=float(x)
  if not math.isfinite(value):raise ValueError('Numeric token overflows finite float64: '+x)
  return value
 return json.loads(text,object_pairs_hook=pairs,parse_constant=invalid,parse_float=decimal_number)

REPLAY=r'''import runpy,json,math,numpy as np
from pathlib import Path
m=runpy.run_path('/inputs/experiment.py',run_name='not_main');g=runpy.run_path('/inputs/base_resources.py',run_name='not_main')
original=[json.loads(x) for x in Path('/inputs/raw.jsonl').read_text().splitlines()]
summaries=[];count=0;max_relative=0.0
for seed,n in [(51001,50),(151001,150)]:
 a=m['generate_data'](np.random.default_rng(seed),n,10,5,1.0)
 b=g['generate_data'](np.random.default_rng(seed),n,10,5,1.0)
 assert all(np.array_equal(x,y) for x,y in zip(a,b))
 y,x,z,true,_=b;theta_hat=np.linalg.lstsq(z,x,rcond=None)[0];projected=z@theta_hat
 sls=np.linalg.lstsq(projected,y,rcond=None)[0];ols=np.linalg.lstsq(x,y,rcond=None)[0]
 aa=2/np.linalg.svd(projected,compute_uv=False)[0]**2;ae=2/np.linalg.svd(z,compute_uv=False)[0]**2
 for setting in m['RATES']:
  raw=next(r for r in original if r['seed']==seed and r['setting_id']==setting['setting_id'])
  alpha=setting['alpha'];eta=setting['eta'];theta=np.zeros((10,5));beta=np.zeros(5);steps=min(64,len(raw['iterations'])-1)
  assert np.isclose(raw['rate_diagnostics']['A_alpha'],aa,rtol=1e-12,atol=1e-12)
  assert np.isclose(raw['rate_diagnostics']['A_eta'],ae,rtol=1e-12,atol=1e-12)
  for t in range(steps+1):
   with np.errstate(over='ignore',invalid='ignore'):
    metrics={'beta_2sls_l2':np.linalg.norm(beta-sls),'beta_true_l2':np.linalg.norm(beta-true),'beta_ols_l2':np.linalg.norm(ols-true),'beta_2sls_true_l2':np.linalg.norm(sls-true),'theta_frobenius':np.linalg.norm(theta)}
    for key,value in metrics.items():
     expected=raw['iterations'][t][key]
     if expected is None:assert not np.isfinite(value)
     else:
      assert np.isclose(value,expected,rtol=1e-10,atol=1e-12),(seed,setting['setting_id'],t,key,value,expected)
      max_relative=max(max_relative,abs(float(value)-expected)/max(1.0,abs(expected)))
     count+=1
    assert bool(np.all(np.isfinite(beta)))==raw['iterations'][t]['beta_finite']
    assert bool(np.all(np.isfinite(theta)))==raw['iterations'][t]['theta_finite']
    if t<steps:
     oldtheta=theta.copy();oldbeta=beta.copy()
     theta=oldtheta-eta*(z.T@(z@oldtheta-x))
     beta=oldbeta-alpha*(oldtheta.T@z.T@(z@oldtheta@oldbeta-y))
  summaries.append({'seed':seed,'n':n,'setting_id':setting['setting_id'],'iterations_checked_including_zero':steps+1,'last_iteration_checked':steps})
result={'generator_exact_array_equality':True,'samples':summaries,'metric_comparisons':count,'max_relative_error_scaled_by_max_1':max_relative,'rtol':1e-10,'atol':1e-12,'scope':'Eight trajectory prefixes across two seeds, max iteration 64; NOT all 48 trajectories or every full run recomputed. Independent old-state equations and released starter used.'}
Path('/work/replay.json').write_text(json.dumps(result,allow_nan=False));print(json.dumps(result))
'''

def main():
 run=Path('D:/mrhbench-local-pilot/h0-budget-pilot-20260923-001/iv-exp');art=run/'execution/artifacts'
 dest=Path('D:/mrhbench-local-pilot/iv-independent-20260923-001');dest.mkdir(exist_ok=False)
 originals={str(p):file_hash(p) for p in run.rglob('*') if p.is_file()}
 config=strict((art/'config.json').read_text(encoding='utf8'));report=strict((art/'report.json').read_text(encoding='utf8'))
 raw=[strict(x) for x in (art/'replicate_results.jsonl').read_text(encoding='utf8').splitlines()]
 ids={r['experiment_id'] for r in raw};pairs={(r['replicate_id'],r['setting_id']) for r in raw}
 assert len(ids)==len(pairs)==len(raw)==48
 reps={x['replicate_id']:x for x in config['replicates']};settings={x['setting_id']:x for x in config['rate_settings']}
 summaries=[];metrics=['beta_2sls_l2','beta_true_l2','beta_ols_l2','beta_2sls_true_l2'];tol=config['tolerance']['value']
 for r in raw:
  assert r['config_id']==config['config_id'] and r['seed']==reps[r['replicate_id']]['seed'] and r['n']==reps[r['replicate_id']]['n']
  rd=r['rate_diagnostics'];setting=settings[r['setting_id']]
  assert rd['alpha']==setting['alpha'] and rd['eta']==setting['eta']
  assert rd['within_alpha_bound']==(0<rd['alpha']<rd['A_alpha']) and rd['within_eta_bound']==(0<rd['eta']<rd['A_eta'])
  assert [x['t'] for x in r['iterations']]==list(range(len(r['iterations'])))
  hits=[x['t'] for x in r['iterations'] if x['beta_2sls_l2'] is not None and x['beta_2sls_l2']<=tol]
  first=min(hits) if hits else None;assert first==r['stopping']['first_tolerance_iteration']
  nulls={k:[x['t'] for x in r['iterations'] if x.get(k) is None] for k in [*metrics,'theta_frobenius']}
  nonfinite=[x['t'] for x in r['iterations'] if not x.get('beta_finite',True) or not x.get('theta_finite',True)]
  for key in ['beta_ols_l2','beta_2sls_true_l2']:assert len({x[key] for x in r['iterations']})==1
  summaries.append({k:r[k] for k in ['experiment_id','replicate_id','setting_id','seed','n','status','rate_diagnostics','rank_diagnostics']}|
     {'iteration_count':len(r['iterations']),'first_record':r['iterations'][0],'last_record':r['iterations'][-1],'first_tolerance_iteration_recomputed':first,'null_metric_iterations':nulls,'nonfinite_state_iterations':nonfinite,'stopping':r['stopping'],'execution_failure_reason':r['execution']['failure_reason']})
 assert {r['experiment_id'] for r in report['experiments']}==ids
 assert all(set(h['experiment_ids'])<=ids for h in report['hypotheses'])
 aggregate_errors=[];max_abs=0.;max_relative=0.
 seen=set()
 for a in report['aggregates']:
  key=(a['setting_id'],a['n'],a['metric'],a['iteration']);assert key not in seen;seen.add(key)
  candidates=[r for r in raw if r['setting_id']==a['setting_id'] and r['n']==a['n']]
  available=[r for r in candidates if a['iteration']<len(r['iterations']) and r['iterations'][a['iteration']][a['metric']] is not None]
  vals=[r['iterations'][a['iteration']][a['metric']] for r in available]
  assert a['independent_replicate_count']==len(vals) and a['included_replicate_ids']==[r['replicate_id'] for r in available]
  for metric,expected in [('mean',statistics.mean(vals) if vals else None),('median',statistics.median(vals) if vals else None)]:
   actual=a[metric]
   if expected is None:assert actual is None
   else:
    error=abs(actual-expected);max_abs=max(max_abs,error);max_relative=max(max_relative,error/max(1,abs(expected)))
    if not math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-12):aggregate_errors.append({'key':key,'metric':metric,'actual':actual,'expected':expected})
 assert not aggregate_errors
 completed=[r for r in raw if r['status']=='completed'];failed=[r for r in raw if r['status']=='numerical_failure']
 beyond=[r for r in raw if not(r['rate_diagnostics']['within_alpha_bound'] and r['rate_diagnostics']['within_eta_bound'])]
 sourcefiles={p.name:{'path':str(p),'sha256':file_hash(p),'bytes':p.stat().st_size} for p in art.iterdir() if p.is_file()}
 inputs={'experiment.py':art/'experiment.py','base_resources.py':run/'public/assets/assets/base_resources.py','raw.jsonl':art/'replicate_results.jsonl'}
 resources=dict(cpus=2,memory_mb=512,disk_mb=16,pids_limit=64,wall_seconds=90)
 with ContainerSession(image_id=read_json(run/'execution/invocation.json')['image_id'],resources=resources,input_files=inputs,input_hashes={k:file_hash(v) for k,v in inputs.items()},audit_dir=dest/'container') as session:
  cid=session.cid;session.write('/work/independent_replay.py',REPLAY.encode())
  execution=session.exec_python_snapshot('/work/independent_replay.py',timeout=60);assert execution['returncode']==0,execution
  replay=json.loads(session.read('/work/replay.json'));session.artifacts(dest/'replay-artifacts',max_bytes=1024*1024,max_files=10)
 ps=subprocess.run(['docker','ps','-a','--no-trunc','--format','{{.ID}}'],capture_output=True,text=True,check=True);assert cid not in ps.stdout.splitlines()
 mechanical={'schema_version':'iv-independent-program-check-1','sources':sourcefiles,'strict_json':{'standard_numeric_tokens_only':True,'duplicate_keys_rejected':True,'jsonl_rows':48},
  'linkage':{'unique_experiment_ids':48,'unique_replicate_setting_pairs':48,'config_seed_n_rate_links_match':True,'report_experiments_exactly_raw_ids':True,'hypothesis_references_non_dangling':True},
  'trajectory_summaries':summaries,'iteration_records_checked':sum(len(r['iterations']) for r in raw),
  'aggregate_check':{'rows_recomputed':len(report['aggregates']),'all_included_ID_sets_and_counts_match':True,'mean_median_errors':aggregate_errors,'max_absolute_difference':max_abs,'max_relative_difference_scaled_by_max_1':max_relative,'rtol':1e-12,'atol':1e-12,'method':'Independent Python statistics.mean/median over listed finite raw per-replicate values, not submitted build_report code.'},
  'status_counts':dict(collections.Counter(r['status'] for r in raw)),
  'bound_and_outcome_counts':{'inside_both':len(raw)-len(beyond),'beyond_at_least_one':len(beyond),'beyond_numerical_failure':sum(r['status']=='numerical_failure' for r in beyond),'beyond_completed':sum(r['status']=='completed' for r in beyond),'completed_tol_hits':sum(r['stopping']['first_tolerance_iteration'] is not None for r in completed),'completed_final_true_error_below_2sls':sum(r['iterations'][-1]['beta_true_l2']<r['iterations'][-1]['beta_2sls_true_l2'] for r in completed)},
  'report_selection_facts':{'report_conclusions':report['conclusions'],'report_hypotheses':[{k:v for k,v in h.items() if k!='experiment_ids'} for h in report['hypotheses']],
     'report_h2_count_expression_filters_completed_first':True,'numerical_failure_ids_not_counted_in_h2_completed_denominator':[r['experiment_id'] for r in failed],
     'failure_ids_present_in_report_experiments':all(r['experiment_id'] in {e['experiment_id'] for e in report['experiments']} for r in failed),'failure_ids_present_in_H2_evidence_links':all(r['experiment_id'] in next(h['experiment_ids'] for h in report['hypotheses'] if h['hypothesis_id']=='H2') for r in failed)},
  'partial_numeric_reexecution':replay,'new_model_calls':0,'scientific_quality_score':None,
  'limits':'Full raw file remains available. All 48 rows/108781 recorded iterations and 432 aggregates mechanically checked; independent numerical trajectory computation only two seeds/eight prefixes through at most t=64. No claim that every raw iterate was regenerated.'}
 write_json(dest/'program_check.json',mechanical,exclusive=True)
 write_json(dest/'program_check_evidence.json',evidence_record('iv-independent-program-check','program_check',json.dumps(mechanical,ensure_ascii=False,indent=2),visibility='private'),exclusive=True)
 rpcfiles=[];actions=[];execution_receipts=[]
 for path in sorted((run/'execution/broker').glob('rpc-*.json')):
  row=read_json(path);rpcfiles.append({'path':str(path),'sha256':file_hash(path)})
  if row['request']['operation']=='complete':actions.append({'rpc':path.name,'call_id':row['response']['value']['call_id'],'action':row['response']['value']['response']})
  if row['request']['operation']=='tool' and row['request']['arguments']['name']=='cpu.run' and row['response']['ok']:
   receipt=row['response']['value']['execution_receipt'];assert file_hash(run/'execution/container'/receipt['snapshot_path'])==receipt['entrypoint_sha256']
   execution_receipts.append({'rpc':path.name,'receipt':receipt,'returncode':row['response']['value']['returncode']})
 audit={'audited_at':utc_now(),'run':str(run),'rpc_files':rpcfiles,'model_actions':actions,'model_action_count':len(actions),'execution_receipts_checked':execution_receipts,'budget':read_json(run/'execution/run.json'),
  'program_check':str(dest/'program_check.json'),'program_check_sha256':file_hash(dest/'program_check.json'),'judge_ready_evidence':str(dest/'program_check_evidence.json'),
  'scientific_maintenance_observations':['Final code uses old_theta and old_beta for both updates and no gradient division by n. Both arrays are replaced, not updated in place; old_theta remains the prior state.',
    'Embedded generator draw order and equations match released starter; fresh container exact-array check for two seeds confirms. Code does not import supplied starter despite claiming embedded exact copy; provenance hash is checked below.',
    'H1 has 35 inside-bound trajectories and 30 tolerance hits; all thirteen failures are beyond at least one bound, so no inside-bound failures were silently excluded from H1 here.',
    'H2 report completed-only denominator 0/0 excludes all thirteen informative beyond-bound numerical failures. Raw/report experiment IDs retain them and final submission explicitly acknowledges the reporting defect. Scientific summary still needs failure-aware treatment, not deletion as missing noise.',
    'H3 compares paired finite-iteration/2SLS errors, with 20 of35 smaller and15 not smaller; rates reuse12samples, not48independent replicates. No significance or population-general claim established.',
    'Raw JSONL captured by controller is24993124bytes but omitted from final hashed artifact list after20MiB reader/verification cap. Do not confuse final list omission with absent scientific data. Driver32MiB/1000collection cap is not explicit in public TaskView; total capture here below cap does not close the admission gap.'],
  'generator_provenance_hash_matches':config['generator_sha256']==file_hash(inputs['base_resources.py']),
  'replay_execution':execution,'owned_container_removed':True,'original_run_files_unchanged':all(file_hash(Path(p))==h for p,h in originals.items()),'new_model_calls':0,'scientific_judge_score':None}
 assert audit['generator_provenance_hash_matches'] and audit['original_run_files_unchanged']
 write_json(dest/'review.json',audit,exclusive=True);write_json(Path(__file__).parent/'audit/iv_budget_independent_review_v1.json',audit,exclusive=True)
 print(json.dumps({'judge_evidence':audit['judge_ready_evidence'],'program_check_bytes':(dest/'program_check_evidence.json').stat().st_size,'aggregates':len(report['aggregates']),'replay':replay}))

if __name__=='__main__':main()
