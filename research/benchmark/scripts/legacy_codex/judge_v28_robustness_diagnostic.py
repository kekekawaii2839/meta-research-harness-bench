"""Three predeclared diagnostic calls. No prompt tuning or scientific rerun."""
import argparse,copy,json,re,sys
from collections import Counter
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.io import read_json,write_json,file_hash,digest
from mrhbench.native_judge import make_prompt,run_native_judge,VERSION
from mrhbench.judging import EvidenceSession
from mrhbench.native_codex import NativeCodexRunner
from mrhbench.costs import CallLedger

BASE=Path(__file__).resolve().parents[2]
SOURCE=Path('D:/mrhbench-local-pilot/judge-v28-holdout-20260923-001/passage_alpha.fixture.json')
BASELINE=Path('D:/mrhbench-local-pilot/judge-v28-acceptance-20260923-001/passage_alpha')
POLICY=Path('D:/mrhbench-local-pilot/context-native-probe-20260923-001/context_policy.json')
PARAPHRASE='In a paired evaluation of the same 1,000 queries, mean decoding latency fell from 100 ms without caching to 70 ms with it, a 30% reduction. Baseline exact match was 80.0%, versus 79.8% for cache-assisted decoding. On the 20 rare-composition queries, baseline and cached exact match were 60% and 50%, respectively [E1]. The finite evaluation therefore shows faster decoding and a small overall accuracy difference, not demonstrated equivalence: no equivalence margin, uncertainty interval, or repeated evaluation is supplied. The rare-query comparison is descriptive and rests on only 20 examples, so the aggregate cannot establish quality preservation for every query type. These observations describe an evaluation-specific tradeoff; they do not identify a causal mechanism, guarantee broader deployment behavior, or quantify memory cost [E1].'

def prepare(destination):
 out=Path(destination).resolve();out.mkdir(parents=True,exist_ok=False)
 baseline=read_json(SOURCE);names=['exact_repeat','submission_paraphrase','evidence_order']
 cases={name:copy.deepcopy(baseline) for name in names}
 submission=next(r for r in cases['submission_paraphrase']['records'] if r['evidence_id']=='submission')
 original_submission=submission['content'];submission['content']=PARAPHRASE;submission['sha256']=digest(PARAPHRASE)
 e=next(r for r in cases['evidence_order']['records'] if r['evidence_id']=='E1');original=e['content']
 sentences=re.split(r'(?<=\.) ',original)
 assert len(sentences)==6
 order=[0,4,5,1,2,3];e['content']='\n\n'.join(sentences[i] for i in order);e['sha256']=digest(e['content'])
 assert Counter(original.split())==Counter(e['content'].split()) and original!=e['content']
 assert 0.8<len(PARAPHRASE.split())/len(original_submission.split())<1.2
 plan={'protocol':VERSION,'source_path':str(SOURCE),'baseline_call':187,'baseline_fixture_raw_sha256':file_hash(SOURCE),'baseline_prompt_raw_sha256':file_hash(BASELINE/'prompt.txt'),'baseline_result_raw_sha256':file_hash(BASELINE/'result.json'),'native_judge_raw_sha256':file_hash(BASE/'mrhbench/native_judge.py'),'policy_raw_sha256':file_hash(POLICY),'policy_canonical_sha256':digest(read_json(POLICY)),'same_task_id':'passage_alpha','max_new_model_calls':3,'no_retries':True,'no_target_exact_scores':True,'diagnostic_not_benchmark':True,'case_definitions':{}}
 for name,case in cases.items():
  changed=[a['evidence_id'] for a,b in zip(case['records'],baseline['records']) if a!=b]
  assert changed==({'exact_repeat':[],'submission_paraphrase':['submission'],'evidence_order':['E1']}[name])
  assert all(a.keys()==b.keys() for a,b in zip(case['records'],baseline['records']))
  prompt=make_prompt('passage_alpha','WRITE_CONTENT',EvidenceSession(case['records']))
  if name=='exact_repeat':assert case==baseline and prompt==(BASELINE/'prompt.txt').read_text()
  else:assert prompt!=(BASELINE/'prompt.txt').read_text()
  write_json(out/(name+'.fixture.json'),case,exclusive=True);(out/(name+'.prompt.txt')).write_bytes(prompt.encode())
  plan['case_definitions'][name]={'changed_records':changed,'fixture_raw_sha256':file_hash(out/(name+'.fixture.json')),'frozen_prompt_lf_raw_sha256':file_hash(out/(name+'.prompt.txt')),'task_type':'WRITE_CONTENT','task_id':'passage_alpha'}
 plan['transformation_audit']={'submission_word_counts':[len(original_submission.split()),len(PARAPHRASE.split())],'semantic_review':'Same paired design, all numbers/directions, speedup, finite tradeoff, no equivalence/interval/repeat, small-subgroup descriptive caution, no causal/global/memory claim. Wording only, no added inferential evidence.','evidence_order_original_blocks':sentences,'evidence_order_permutation':order,'evidence_order_token_multiset_equal':True,'evidence_order_note':'Reorders intact sentence-sized evidence blocks and renders paragraphs; no words/facts removed or added. Not mere record-order reversal; actual E1 content/hash changes.','only_hash_content_fields_changed':True,'repeat_scope':'Same task_id, records and actual judge prompt; fresh session/cwd/runtime metadata differ, not byte-identical whole native context.'}
 write_json(out/'frozen_plan.json',plan,exclusive=True);print(json.dumps({'frozen':str(out),'cases':names}))

def run(source,output):
 source=Path(source).resolve();out=Path(output).resolve();plan=read_json(source/'frozen_plan.json')
 assert VERSION==plan['protocol'] and file_hash(BASE/'mrhbench/native_judge.py')==plan['native_judge_raw_sha256']
 assert file_hash(POLICY)==plan['policy_raw_sha256'];out.mkdir(parents=True,exist_ok=False);results=[]
 for name in ['exact_repeat','submission_paraphrase','evidence_order']:
  definition=plan['case_definitions'][name]
  assert file_hash(source/(name+'.fixture.json'))==definition['fixture_raw_sha256']
  assert file_hash(BASE/'mrhbench/native_judge.py')==plan['native_judge_raw_sha256']
  case=read_json(source/(name+'.fixture.json'))
  assert make_prompt('passage_alpha','WRITE_CONTENT',EvidenceSession(case['records']))==(source/(name+'.prompt.txt')).read_text()
  runner=NativeCodexRunner(binary=Path('C:/Users/li_ha/AppData/Local/OpenAI/Codex/bin/80f78947ad880e6e/codex.exe'),model='gpt-5.6-sol',reasoning_effort='medium',ledger=CallLedger(BASE/'audit/development_call_ledger.json'),audit_root=out/'calls',permission_profile=':read-only',timeout_seconds=600,context_policy=read_json(POLICY))
  try:
   r=run_native_judge(runner=runner,task_id='passage_alpha',task_type='WRITE_CONTENT',records=case['records'],output=out/name,python_binary=Path(sys.executable));s={'case':name,'status':r.get('status'),'quality':r.get('quality')}
  except Exception as e:
   s={'case':name,'status':'failed','error_type':type(e).__name__,'message':str(e),'retry':False};write_json(out/(name+'.failure.json'),s,exclusive=True)
  results.append(s);write_json(out/'run_summary.json',{'runs':results,'manual_review_pending':True,'formal_acceptance':False});print(json.dumps(s),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run']);p.add_argument('--source');p.add_argument('--output',required=True);a=p.parse_args()
 if a.mode=='prepare':prepare(a.output)
 else:run(a.source,a.output)
