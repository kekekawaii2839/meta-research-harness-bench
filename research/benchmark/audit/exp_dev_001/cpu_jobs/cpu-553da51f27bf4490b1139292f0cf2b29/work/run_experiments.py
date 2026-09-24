"""CPU experiment and analysis driver. Writes machine-readable evidence artifacts."""
from __future__ import annotations
import csv, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path('inputs').resolve()))
from baseline import generate, ordinary_least_squares
from coupled_estimator import exact_targets, run_coupled, spectral_diagnostics

def quantiles(vals):
    a=np.asarray(vals,float)
    return {'n':int(a.size),'median':float(np.median(a)),'q10':float(np.quantile(a,.1)),'q90':float(np.quantile(a,.9)),'min':float(np.min(a)),'max':float(np.max(a))}

def safe_log_slope(trace, lo, hi):
    pts=[]
    for k,v in trace.items():
        t=int(k); e=v['max_rel_error']
        if lo <= t <= hi and np.isfinite(e) and 1e-14 < e < 1e50: pts.append((t,e))
    if len(pts)<3: return {'supported':False,'reason':'fewer than 3 finite above-floor checkpoints'}
    x=np.asarray([p[0] for p in pts],float); y=np.log(np.asarray([p[1] for p in pts],float))
    slope,intercept=np.polyfit(x,y,1); pred=slope*x+intercept
    ssr=float(np.sum((y-pred)**2)); sst=float(np.sum((y-y.mean())**2))
    r2=float(1-ssr/sst) if sst>0 else None
    return {'supported':True,'points':len(pts),'start':int(x[0]),'end':int(x[-1]),'per_iteration_factor':float(math.exp(slope)),'log_slope':float(slope),'r2':r2}

def main():
    cfg=json.loads(Path('experiment_configs.json').read_text())
    records=[]
    for regime in cfg['regimes']:
      for seed in regime['seeds']:
        d=generate(seed=seed,n=regime['n'],p=regime['p'],q=regime['q'],noise=regime['noise'])
        Z,X,Y=d['Z'],d['X'],d['Y']; th,bhat,A,B=exact_targets(Z,X,Y)
        ols=ordinary_least_squares(X,Y)
        alpha_upper=2/float(np.linalg.eigvalsh(A)[-1]); eta_upper=2/float(np.linalg.eigvalsh(B)[-1])
        base={'regime':regime['id'],'seed':seed,'n':regime['n'],'p':regime['p'],'q':regime['q'],'noise':regime['noise'],
              'beta_2sls_norm':float(np.linalg.norm(bhat)),'beta_2sls_truth_error':float(np.linalg.norm(bhat-d['beta_true'])),
              'beta_ols_truth_error':float(np.linalg.norm(ols-d['beta_true']))}
        for family,key,iters in [('stable','stable_scenarios',cfg['stable_iterations']),('outside','outside_scenarios',cfg['outside_iterations'])]:
          for sc in cfg[key]:
            alpha=sc['alpha_fraction_of_upper']*alpha_upper; eta=sc['eta_fraction_of_upper']*eta_upper
            diag=spectral_diagnostics(Z,th,alpha,eta)
            run=run_coupled(Z,X,Y,alpha,eta,iters,[c for c in cfg['checkpoints'] if c<=iters])
            rate=safe_log_slope(run['trace'],*cfg['late_fit_window']) if family=='stable' else {'supported':False,'reason':'outside-region runs excluded from stable late-rate fit'}
            rec=dict(base); rec.update({'experiment_id':f"{regime['id']}__seed{seed}__{sc['id']}",'family':family,'scenario':sc['id'],
              'alpha':alpha,'eta':eta,'alpha_fraction_of_upper':sc['alpha_fraction_of_upper'],'eta_fraction_of_upper':sc['eta_fraction_of_upper'],
              'diagnostics':diag,'run':run,'late_rate_fit':rate})
            records.append(rec)
    Path('run_outputs.json').write_text(json.dumps({'task_id':'dev-exp-001','records':records},indent=2,sort_keys=True))
    rows=[]
    for r in records:
      tr=r['run']['trace']; last=tr[str(r['run']['iterations_completed'])]
      rows.append({'experiment_id':r['experiment_id'],'family':r['family'],'regime':r['regime'],'scenario':r['scenario'],
        'Lambda':r['diagnostics']['Lambda'],'gamma':r['diagnostics']['gamma'],'kappa':r['diagnostics']['kappa'],
        'cond_A':r['diagnostics']['cond_A'],'cond_B':r['diagnostics']['cond_B'],'status':r['run']['status'],
        'iterations':r['run']['iterations_completed'],'final_theta_rel_error':last['theta_rel_error'],'final_beta_rel_error':last['beta_rel_error'],
        'fit_supported':r['late_rate_fit']['supported'],'fit_factor':r['late_rate_fit'].get('per_iteration_factor'),'fit_r2':r['late_rate_fit'].get('r2')})
    with Path('diagnostics.csv').open('w',newline='') as f:
      w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    stable=[r for r in records if r['family']=='stable']; outside=[r for r in records if r['family']=='outside']
    summaries={}
    for sc in [s['id'] for s in cfg['stable_scenarios']]:
      rr=[r for r in stable if r['scenario']==sc]; finals=[r['run']['trace'][str(r['run']['iterations_completed'])]['beta_rel_error'] for r in rr]
      summaries[sc]={'beta_final':quantiles(finals),'Lambda':quantiles([r['diagnostics']['Lambda'] for r in rr]),
        'gamma_bottleneck_count':sum(r['diagnostics']['gamma']>=r['diagnostics']['kappa'] for r in rr),
        'kappa_bottleneck_count':sum(r['diagnostics']['kappa']>r['diagnostics']['gamma'] for r in rr),
        'rate_fit_supported_count':sum(r['late_rate_fit']['supported'] for r in rr),
        'fit_factor':quantiles([r['late_rate_fit']['per_iteration_factor'] for r in rr if r['late_rate_fit']['supported']]) if any(r['late_rate_fit']['supported'] for r in rr) else None}
    outside_summary={}
    for sc in [s['id'] for s in cfg['outside_scenarios']]:
      rr=[r for r in outside if r['scenario']==sc]
      outside_summary[sc]={'n':len(rr),'completed':sum(r['run']['status']=='completed' for r in rr),
        'nonfinite_or_threshold_diverged':sum(r['run']['status']!='completed' for r in rr),
        'final_beta_rel_error_for_completed':quantiles([r['run']['trace'][str(r['run']['iterations_completed'])]['beta_rel_error'] for r in rr if r['run']['status']=='completed']) if any(r['run']['status']=='completed' for r in rr) else None}
    # Within-dataset paired checkpoint comparisons provide bottleneck evidence without conflating random draws.
    paired=[]
    for regime in cfg['regimes']:
      for seed in regime['seeds']:
        sub={r['scenario']:r for r in stable if r['regime']==regime['id'] and r['seed']==seed}
        row={'regime':regime['id'],'seed':seed}
        for sc in sub:
          t='200'; row[sc+'_error_t200']=sub[sc]['run']['trace'][t]['max_rel_error']
        paired.append(row)
    aggregate={'stable_scenarios':summaries,'outside_scenarios':outside_summary,
      'all_stable_runs':len(stable),'all_outside_runs':len(outside),
      'stable_completed':sum(r['run']['status']=='completed' for r in stable),
      'stable_beta_error_below_1e-8':sum(r['run']['trace'][str(r['run']['iterations_completed'])]['beta_rel_error']<1e-8 for r in stable),
      'conditioning':{'cond_A':quantiles([r['diagnostics']['cond_A'] for r in stable[::4]]),'cond_B':quantiles([r['diagnostics']['cond_B'] for r in stable[::4]])},
      'paired_checkpoint_t200':paired}
    Path('analysis_summary.json').write_text(json.dumps(aggregate,indent=2,sort_keys=True))
    evidence={'task_id':'dev-exp-001','method_fidelity':{'implementation':'coupled_estimator.py','configs':'experiment_configs.json',
      'statement':'Zero initialization, unnormalized gradients, constant positive steps, and simultaneous old-state updates are implemented directly.'},
      'hypotheses':[
       {'hypothesis_id':'H1','experiment_ids':['all stable-family IDs in run_outputs.json'],
        'artifact_references':['coupled_estimator.py','experiment_configs.json','run_outputs.json','diagnostics.csv','analysis_summary.json'],
        'short_conclusion':'TO_BE_FILLED_FROM_EXECUTED_SUMMARY','uncertainty':'Empirical finite-seed evidence; late log-linear fits are flagged unsupported near numerical floors or with too few usable points.',
        'limitations_and_unperformed_work':['No theorem is claimed.','No population-consistency or Transformer claim is tested.','Target is sample 2SLS; truth errors are descriptive comparators only.']},
       {'hypothesis_id':'H2','experiment_ids':['all stable and outside-family IDs in run_outputs.json'],
        'artifact_references':['experiment_configs.json','run_outputs.json','diagnostics.csv','analysis_summary.json'],
        'short_conclusion':'TO_BE_FILLED_FROM_EXECUTED_SUMMARY','uncertainty':'Outside-region behavior is observed only for specified fractions, seeds, regimes, and finite horizons.',
        'limitations_and_unperformed_work':['No claim that every outside-region setting diverges.','Lambda is a local/asymptotic block diagnostic and does not model every coupled transient.']}]}
    Path('hypothesis_evidence_map.json').write_text(json.dumps(evidence,indent=2,sort_keys=True))
    print(json.dumps({'records':len(records),'aggregate':aggregate},sort_keys=True))
if __name__=='__main__': main()
