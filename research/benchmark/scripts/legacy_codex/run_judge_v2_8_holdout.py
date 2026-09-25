"""Exactly four authorized native judge attempts on frozen synthetic fixtures."""
import argparse,json,sys
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.io import read_json,write_json,file_hash
from mrhbench.costs import CallLedger
from mrhbench.native_codex import NativeCodexRunner
from mrhbench.native_judge import run_native_judge,make_prompt,VERSION
from mrhbench.judging import EvidenceSession

def run(source,output,policy):
 source=Path(source).resolve();out=Path(output).resolve();policy=Path(policy).resolve()
 plan=read_json(source/'frozen_plan.json');base=Path(__file__).resolve().parents[2]
 assert VERSION==plan['protocol'] and file_hash(base/'mrhbench/native_judge.py')==plan['native_judge_sha256']
 assert file_hash(policy)==plan['context_policy_sha256']
 names=['finite_alpha','finite_beta','passage_alpha','passage_beta']
 for n in names:
  assert file_hash(source/(n+'.fixture.json'))==plan['files'][n+'.fixture.json']
  assert file_hash(source/(n+'.frozen_prompt.txt'))==plan['prompts'][n+'.frozen_prompt.txt']
 out.mkdir(parents=True,exist_ok=False);results=[]
 write_json(out/'authorization_scope.json',{'max_attempts':4,'retry':False,'source':str(source),'plan_sha256':file_hash(source/'frozen_plan.json'),'context_policy_sha256':file_hash(policy),'model':'gpt-5.6-sol','effort':'medium','synthetic_only':True,'full_manual_review_pending':True},exclusive=True)
 for n in names:
  fixture=read_json(source/(n+'.fixture.json'))
  assert file_hash(base/'mrhbench/native_judge.py')==plan['native_judge_sha256']
  assert make_prompt(n,fixture['task_type'],EvidenceSession(fixture['records']))==(source/(n+'.frozen_prompt.txt')).read_text()
  runner=NativeCodexRunner(binary=Path('C:/Users/li_ha/AppData/Local/OpenAI/Codex/bin/80f78947ad880e6e/codex.exe'),model='gpt-5.6-sol',reasoning_effort='medium',ledger=CallLedger(base/'audit/development_call_ledger.json'),audit_root=out/'calls',permission_profile=':read-only',timeout_seconds=600,context_policy=read_json(policy))
  try:
   r=run_native_judge(runner=runner,task_id=n,task_type=fixture['task_type'],records=fixture['records'],output=out/n,python_binary=Path(sys.executable))
   summary={'case':n,'status':r.get('status'),'quality':r.get('quality')}
  except Exception as e:
   summary={'case':n,'status':'judge_attempt_failed','error_type':type(e).__name__,'message':str(e),'retry':False}
   write_json(out/(n+'.failure.json'),summary,exclusive=True)
  results.append(summary);write_json(out/'run_summary.json',{'runs':results,'manual_review_complete':False,'formal_acceptance':False})
  print(json.dumps(summary),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--context-policy',required=True);a=p.parse_args();run(a.source,a.output,a.context_policy)
