"""Read saved observable trajectory; no models. Static duplicates hash, data exact."""
import argparse,json
from pathlib import Path
from mrhbench.io import file_hash,digest

def inspect(output,case):
 out=Path(output);call=json.loads((out/case/'native_call.json').read_text())
 p=Path(call['rollout_capture']['path'])
 assert file_hash(p)==call['rollout_capture']['sha256']
 rows=[json.loads(x) for x in p.read_text().splitlines()]
 print('ROLLOUT',str(p),'SHA256',file_hash(p))
 records={r['evidence_id']:r for r in json.loads((out/case/'evidence_manifest.json').read_text())['records']}
 stats={'tool_actions':[],'text_deliveries':[],'static_messages':[],'unexpected_outputs':[],'image_blocks':0,'rollout_sha256':file_hash(p)}
 def show(v):
  if isinstance(v,str):
   try:show(json.loads(v));return
   except (ValueError,TypeError):print(v);return
  if isinstance(v,list):
   for x in v:show(x)
  elif isinstance(v,dict):
   if 'receipt_id' in v and 'evidence_id' in v and 'content' in v:
    r=records[v['evidence_id']];text=v['content'];a=v.get('start_char',0);b=v.get('end_char',len(r['content']))
    assert text==r['content'][a:b] and v['source_sha256']==r['sha256']
    stats['text_deliveries'].append({'receipt':v['receipt_id'],'evidence_id':v['evidence_id'],'start':a,'end':b,'exact':True})
    print('DELIVERED',v['evidence_id'],a,b,'receipt',v['receipt_id']);print(text)
   elif 'content' in v:show(v['content'])
   elif 'text' in v:show(v['text'])
   elif v.get('type')=='input_image':stats['image_blocks']+=1;print('IMAGE',v.get('detail'))
   elif 'inventory_hash' in v:print('INVENTORY',json.dumps(v))
   elif any(isinstance(x,dict) and 'content' in x for x in v.values()):
    for key,x in v.items():print('GROUP',key);show(x)
   else:print(json.dumps(v,ensure_ascii=False))
  else:print(v)
 for i,r in enumerate(rows):
  v=r.get('payload',{});kind=v.get('type')
  if r.get('type')!='response_item':continue
  if kind=='message':
   if v.get('role') in ('developer','system','user'):
    entry={'row':i,'role':v.get('role'),'digest':digest(v['content']),'characters':len(str(v['content']))}
    stats['static_messages'].append(entry);print('STATIC',entry)
   else:print('MESSAGE',i,v.get('role'),v.get('phase'));show(v.get('content'))
  elif kind in ('custom_tool_call','function_call'):
   a={'row':i,'name':v.get('name'),'input':v.get('input',v.get('arguments'))};stats['tool_actions'].append(a);print('TOOL',a)
  elif kind in ('custom_tool_call_output','function_call_output'):print('RETURN',i);show(v.get('output'))
  elif kind=='reasoning':
   if v.get('summary'):print('OBSERVABLE_REASONING_SUMMARY',v['summary'])
 print('STATS',json.dumps(stats,ensure_ascii=False))
 return stats

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--case',required=True);a=p.parse_args();inspect(a.output,a.case)
