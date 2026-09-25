"""Revalidate unchanged native outputs against exact frozen retrieval receipts.

No model call, no score modification, no behavioral acceptance. Image transport
is verified by exact decoded-byte hashes in the captured native model input.
"""
import argparse,base64,hashlib,json
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.io import read_json,write_json,file_hash
from mrhbench.native_judge import restore_session,validate_native_result


def revalidate(run_directory,output,manual_image_audit=None):
 run=Path(run_directory);out=Path(output)
 if out.exists():raise ValueError('Revalidation output must be new')
 manifest=read_json(run/'evidence_manifest.json');records=manifest['records'];call=read_json(run/'native_call.json');state=read_json(run/'tool_state.json')
 trace=Path(call['rollout_capture']['path']);observed=[]
 def walk(v):
  if isinstance(v,dict):
   if v.get('type')=='input_image' and isinstance(v.get('image_url'),str) and v['image_url'].startswith('data:'):
    observed.append(hashlib.sha256(base64.b64decode(v['image_url'].split(',',1)[1],validate=True)).hexdigest())
   for x in v.values():walk(x)
  elif isinstance(v,list):
   for x in v:walk(x)
 for line in trace.read_text(encoding='utf8').splitlines():
  row=json.loads(line)
  if row['type']=='response_item' and row['payload'].get('type') in ['custom_tool_call_output','function_call_output']:walk(row['payload'].get('output'))
 verified=[]
 for receipt in state.get('image_results_returned',[]):
  e=state['receipts'][receipt]['evidence_id'];r=next(x for x in records if x['evidence_id']==e)
  if hashlib.sha256(base64.b64decode(r['content'],validate=True)).hexdigest() in observed:verified.append(receipt)
 if manual_image_audit:
  audit=read_json(Path(manual_image_audit))
  if not audit.get('reviewer') or audit.get('native_rollout_sha256')!=file_hash(trace):raise ValueError('Manual visual review identity mismatch')
  for item in audit['images']:
   receipt=item['receipt_id']
   if receipt not in state.get('image_results_returned',[]):raise ValueError('Image was not returned')
   record=next(x for x in records if x['evidence_id']==state['receipts'][receipt]['evidence_id'])
   source_hash=hashlib.sha256(base64.b64decode(record['content'],validate=True)).hexdigest()
   if item['source_image_sha256']!=source_hash or item['delivered_image_sha256'] not in observed or item.get('verdict')!='visually_verified_same_source_resize' or not item.get('reason'):
    raise ValueError('Manual visual review provenance mismatch')
   if receipt not in verified:verified.append(receipt)
 session=restore_session(records,state,verified_image_receipts=verified)
 prompt=(run/'prompt.txt').read_text(encoding='utf8');meta=json.loads(prompt[prompt.rfind('\n{"task_id"')+1:])
 candidate=run/'candidate_judgment.json';result=validate_native_result(meta['rubric']['task_type'],read_json(candidate),session,rubric_definition=meta['rubric'])
 result.update(revalidation_only_no_new_model_call=True,original_response_sha256=file_hash(candidate),original_call_id=call['call_id'],native_rollout_sha256=file_hash(trace),image_delivery_verified=verified,manual_image_audit=str(manual_image_audit) if manual_image_audit else None,image_verification_scope='exact input_image payload hash; source equality exact or explicit manual resized-image audit; not proof of visual reasoning')
 write_json(out,result);return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output',required=True);p.add_argument('--manual-image-audit');a=p.parse_args();r=revalidate(a.run,a.output,a.manual_image_audit);print(json.dumps({'status':r['status'],'quality':r['quality'],'image_delivery_verified':r['image_delivery_verified']}))
