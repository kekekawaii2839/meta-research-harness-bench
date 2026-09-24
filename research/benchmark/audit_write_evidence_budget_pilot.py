"""Independent numeric/trace replay; submission Python executes ONLY in Docker."""
import ast,base64,csv,hashlib,io,json,subprocess
from decimal import Decimal
from pathlib import Path
from PIL import Image
from mrhbench.container_runtime import ContainerSession
from mrhbench.io import read_json,write_json,file_hash,utc_now

def main():
 run=Path('D:/mrhbench-local-pilot/h0-budget-pilot-20260923-001/ssa-write-evidence')
 dest=Path('D:/mrhbench-local-pilot/write-evidence-independent-20260923-001');dest.mkdir(exist_ok=False)
 outputs=run/'execution/artifacts/outputs';original_hashes={str(p):file_hash(p) for p in run.rglob('*') if p.is_file()}
 csvpath=run/'public/assets/assets/table4_utkface.csv';source=read_json(run/'public/assets/assets/table4_manifest.json')
 rows=list(csv.DictReader(io.StringIO(csvpath.read_text(encoding='utf-8-sig'))))
 submitted=read_json(outputs/'numeric_provenance.json');tree=ast.parse((outputs/'generate_figure.py').read_text(encoding='utf8'))
 node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CSV' for t in n.targets))
 assert isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)
 copied=list(csv.DictReader(io.StringIO(node.value.value)));assert copied==rows
 cols=list(rows[0])[1:];checks=[]
 for row in rows:
  for col in cols:
   key=row['Method']+'|'+col
   assert submitted['cells'][key]==source['cells'][key]
   assert source['cells'][key]['value']==row[col]
   checks.append({'cell':key,'source_string':row[col],'locator':source['cells'][key]['locator'],'matched':True})
 assert len(checks)==140 and len(submitted['cells'])==140
 bymethod={r['Method']:r for r in rows}
 differences=sorted([{'corruption':c,'ssa_minus_fr':str(Decimal(bymethod['SSA (ours)'][c])-Decimal(bymethod['FR'][c]))} for c in cols if c!='Mean'],key=lambda x:Decimal(x['ssa_minus_fr']),reverse=True)
 rpcs=[];actions=[];executions=[];image_requests=[]
 for path in sorted((run/'execution/broker').glob('rpc-*.json')):
  row=read_json(path);rpcs.append({'path':str(path),'sha256':file_hash(path)})
  request=row['request'];response=row['response']
  if request['operation']=='complete':
   actions.append({'rpc':path.name,'call_id':response['value']['call_id'],'action':response['value']['response'],'control':request['arguments']['request']['control']})
   if request['arguments'].get('image_ids'):image_requests.append({'rpc':path.name,'ids':request['arguments']['image_ids'],'call_id':response['value']['call_id']})
  if request['operation']=='tool' and request['arguments']['name']=='cpu.run':
   result=response['value'];receipt=result['execution_receipt'];snapshot=run/'execution/container'/receipt['snapshot_path']
   assert file_hash(snapshot)==receipt['entrypoint_sha256']
   executions.append({'rpc':path.name,'entrypoint_receipt':receipt,'returncode':result['returncode'],'stdout':result['stdout'],'stderr':result['stderr']})
 image_result=next(read_json(p) for p in (run/'executor_calls').glob('*/result.json') if read_json(p)['call_id']==165)
 rollout=Path(image_result['rollout_capture']['path']);assert file_hash(rollout)==image_result['rollout_capture']['sha256']
 transported=[]
 for line in rollout.read_text(encoding='utf8').splitlines():
  row=json.loads(line)
  for part in row.get('payload',{}).get('content',[]):
   if part.get('type')=='input_image':
    raw=base64.b64decode(part['image_url'].split(',',1)[1],validate=True);path=dest/'actual-transport-input.png';path.write_bytes(raw)
    with Image.open(io.BytesIO(raw)) as im:
     transported.append({'rollout_ordinal':row['ordinal'],'role':row['payload']['role'],'detail':part.get('detail'),'bytes_sha256':hashlib.sha256(raw).hexdigest(),
        'dimensions':im.size,'pixel_mode':im.mode,'rgba_pixel_sha256':hashlib.sha256(im.convert('RGBA').tobytes()).hexdigest(),'saved_exact_payload':str(path)})
 assert len(transported)==1
 with Image.open(outputs/'utkface_table4_heatmap.png') as im:
  original_image={'bytes_sha256':file_hash(outputs/'utkface_table4_heatmap.png'),'dimensions':im.size,'rgba_pixel_sha256':hashlib.sha256(im.convert('RGBA').tobytes()).hexdigest()}
 cfg=read_json(run/'public/task.json')['resources'];inputs={'generator.py':outputs/'generate_figure.py','released.csv':csvpath,'released-manifest.json':run/'public/assets/assets/table4_manifest.json'}
 with ContainerSession(image_id=cfg['image_id'],resources=cfg['container'],input_files=inputs,input_hashes={k:file_hash(v) for k,v in inputs.items()},audit_dir=dest/'container') as session:
  cid=session.cid;session.write('/work/outputs/generate_figure.py',(outputs/'generate_figure.py').read_bytes())
  rerun=session.exec_python_snapshot('/work/outputs/generate_figure.py',timeout=120);assert rerun['returncode']==0,rerun
  inventory=session.artifacts(dest/'reproduced',max_bytes=3*1024*1024,max_files=20)
 reproduced=[]
 for filename in ['generate_figure.py','utkface_table4_heatmap.png','caption.md','interpretation.md','numeric_provenance.json']:
  a=file_hash(dest/'reproduced/outputs'/filename);b=file_hash(outputs/filename);assert a==b,filename
  reproduced.append({'file':filename,'sha256':a,'exact_original_bytes_reproduced':True})
 ps=subprocess.run(['docker','ps','-a','--no-trunc','--format','{{.ID}}'],capture_output=True,text=True,check=True);assert cid not in ps.stdout.splitlines()
 old=read_json(Path('D:/mrhbench-local-pilot/h0-integration-20260923-001/ssa-write-evidence/execution/invocation.json'));current=read_json(run/'execution/invocation.json');assert old['harness_sha256']==current['harness_sha256']
 report={'audited_at':utc_now(),'scope':'Maintenance independent review, not a numeric judge score; full executor actions/tool records plus static code and actual image inspection; submission code only rerun in fresh frozen CPU Docker.',
  'run':str(run),'new_model_calls':0,'rpc_files':rpcs,'model_actions':actions,'model_action_count':len(actions),'run_budget':read_json(run/'execution/run.json'),
  'entrypoint_snapshots_verified':executions,'cell_checks':checks,'cell_count':140,'embedded_csv_equals_released_csv':True,'ssa_minus_fr_sorted':differences,
  'image_delivery':{'request':image_requests,'provider_result':image_result,'actual_payload':transported,'original_file':original_image,
     'interpretation':'The observed native rollout contains an actual user input_image after provider CLI --image. It is resized to 2048x1092 from 4204x2241. Original file hash is not delivered-pixel hash; receipt does not prove attentive model inspection or unobserved server transforms.'},
  'rerun':{'directory':str(dest),'result':rerun,'inventory':inventory,'exact_matches':reproduced,'owned_container_id':cid,'owned_container_removed':True},
  'findings':[{'type':'visual_defect','detail':'Actual PNG: rotated corruption headers descend into the Source row; Defocus blur approaches/overlaps Source label and long Elastic transform/Gaussian/Impulse headers crowd the first-row cells. Header padding/orientation is wrong despite substantial blank space above. Most numeric cells remain legible; not total chart failure.'},
     {'type':'comparative_statement_error','detail':'Interpretation says largest SSA-over-FR advantages occur for the three noise corruptions, but Snow difference .089 is second largest after Shot .102, ahead of Gaussian .071 and Impulse .070. Local overgeneralization, not incorrect source cell values.'},
     {'type':'input_loading_requirement','detail':'Final generator embeds a copied CSV and reconstructs locators arithmetically instead of loading supplied CSV/provenance files as requested. All 140 copied values and locators match today, but automatic linkage is weakened. Earlier FileNotFoundError came from guessed /work-relative paths, while inputs were staged readonly under /inputs/public/assets/assets; not evidence that assets were absent.'},
     {'type':'interface_and_status','detail':'First cpu.run action used inline code and was harness-denied before broker dispatch. Final model says completed with omissions=null; H0 converts to partial with malformed-omissions and prior-denial notices. Raw model status must not be mistaken for final executor submission status.'},
     {'type':'strengths','detail':'All 140 source strings and locators match. PNG and all required text/manifest artifacts exactly reproduce in fresh frozen container. Negative values remain visible; Mean and Oracle are separated; caption specifies units/severity/aggregation and does not extend TTA seed protocol to other comparators. 203-word interpretation avoids fabricated uncertainty/significance.'}],
  'visual_review_scope':'Direct view_image requested original, tool actually displayed resized 2048x1092; overlap directly visible there. File dimensions and transported bitmap determined mechanically, not inferred from display.',
  'budget_comparison':{'harness_sha256':current['harness_sha256'],'identical_old_h0':True,'old_model_budget':4,'new_model_budget':12,'conclusion':'Development budget feasibility only. No harness edit or controlled evolution benefit; task/budget and stochastic execution differ. Do not report as self-improvement.'},
  'original_run_files_unchanged':all(file_hash(Path(p))==h for p,h in original_hashes.items()),'scientific_judge_score':None}
 assert report['original_run_files_unchanged']
 write_json(dest/'review.json',report,exclusive=True)
 write_json(Path(__file__).parent/'audit/write_evidence_budget_independent_review_v1.json',report,exclusive=True)
 print(json.dumps({'reproduced':len(reproduced),'cells':len(checks),'transport_dimensions':transported[0]['dimensions'],'audit':str(dest/'review.json')}))

if __name__=='__main__':main()
