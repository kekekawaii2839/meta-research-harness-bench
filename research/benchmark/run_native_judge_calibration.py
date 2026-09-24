"""Explicitly bounded native judge calibration, never formal benchmark scoring."""
import argparse,concurrent.futures,copy,json,sys
from pathlib import Path
from mrhbench.io import read_json,write_json
from mrhbench.costs import CallLedger
from mrhbench.native_codex import NativeCodexRunner
from mrhbench.native_judge import run_native_judge
from mrhbench.judge_calibration import fixtures

p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--names',nargs='+',required=True);p.add_argument('--workers',type=int,default=1);p.add_argument('--fixture-files',nargs='*',default=[]);args=p.parse_args()
BASE=Path(__file__).resolve().parent;OUT=Path(args.output).resolve();OUT.mkdir(exist_ok=False,parents=True)
cases={x['name']:x for x in fixtures()}
for path in args.fixture_files:
 case=read_json(Path(path));cases[case['name']]=case
# Historical real artifacts are regression evidence, not a held-out formal task.
old=read_json(BASE/'audit/write_evidence_dev_001/evidence.json')
cases['write_real_obscured_header']={'name':'write_real_obscured_header','task_type':'WRITE_EVIDENCE','fixture_split':'development','records':old,'synthetic_fixture':False,'review_expectations':{'notice_header_overlap':True,'resource_mismatch_not_agent_fault':True}}
repeat=copy.deepcopy(cases['idea_sound_analysis']);repeat['name']='idea_sound_analysis_repeat';repeat['fixture_split']='repeat_check';cases[repeat['name']]=repeat
if not 1<=args.workers<=2 or len(args.names)>7 or len(set(args.names))!=len(args.names):raise ValueError('Bounded distinct calibration required')
def run(name):
 case=cases[name];write_json(OUT/(name+'.fixture.json'),case)
 runner=NativeCodexRunner(binary=Path('C:/Users/li_ha/AppData/Local/OpenAI/Codex/bin/80f78947ad880e6e/codex.exe'),model='gpt-5.6-sol',reasoning_effort='medium',ledger=CallLedger(BASE/'audit/development_call_ledger.json'),audit_root=OUT/'calls',permission_profile=':read-only',timeout_seconds=600)
 try:
  result=run_native_judge(runner=runner,task_id=name,task_type=case['task_type'],records=case['records'],output=OUT/name,python_binary=Path(sys.executable))
  return {'name':name,'status':result.get('status'),'quality':result.get('quality')}
 except Exception as e:
  failure={'name':name,'status':'judge_failure','error_type':type(e).__name__,'reason':str(e)};write_json(OUT/(name+'.failure.json'),failure);return failure
with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
 results=list(pool.map(run,args.names))
write_json(OUT/'run_summary.json',{'runs':results,'manual_trajectory_review_complete':False,'formal_acceptance':False});print(json.dumps(results))
