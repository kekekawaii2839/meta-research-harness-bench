import io,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.bounded_mcp import BoundedTools,serve
from mrhbench.native_judge import native_rubric,validate_native_result,restore_session,make_prompt
from mrhbench.judge_runner import evidence_record
from mrhbench.judging import EvidenceSession
from mrhbench.scoring import DIMENSIONS
from mrhbench.io import ProtocolError

class NativeJudgeTests(unittest.TestCase):
 def test_all_anchors_and_unchanged_dimensions(self):
  for kind,dims in DIMENSIONS.items():
   r=native_rubric(kind)
   self.assertEqual(set(r['dimension_anchors']),set(dims))
   for levels in r['dimension_anchors'].values():self.assertEqual(set(levels),set('01234'))
 def test_mcp_scope_receipts_and_restore(self):
  with tempfile.TemporaryDirectory() as d:
   records=[evidence_record('x','task','hello\nworld')]
   b=BoundedTools({'records':records,'state_path':str(Path(d)/'state.json'),'max_tool_calls':3})
   content=b.call('evidence_read',{'evidence_id':'x','start_char':0,'max_chars':20})
   receipt=json.loads(content['content'][0]['text'])['receipt_id']
   s=restore_session(records,json.loads((Path(d)/'state.json').read_text()))
   self.assertIn(receipt,s.receipts)
   with self.assertRaises(ProtocolError):b.call('container_exec',{'argv':['whoami']})
   with self.assertRaises(ProtocolError):b.call('evidence_read',{'evidence_id':'x','path':'C:/secrets'})
 def test_protocol_does_not_offer_host_tools(self):
  with tempfile.TemporaryDirectory() as d:
   requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},{'jsonrpc':'2.0','id':2,'method':'tools/list'}]
   out=io.BytesIO();serve({'state_path':str(Path(d)/'s.json')},io.BytesIO(('\n'.join(map(json.dumps,requests))+'\n').encode()),out)
   names=[t['name'] for t in json.loads(out.getvalue().splitlines()[1])['result']['tools']]
   self.assertEqual(names,['evidence_inventory','evidence_read'])
 def test_character_pages_cover_long_single_line(self):
  text='x'*15001;s=EvidenceSession([evidence_record('long','task',text)])
  chunks=[];offset=0
  while offset is not None:
   r=s.read_chars('long',start_char=offset,max_chars=5000)
   self.assertLessEqual(len(r['content']),5000);chunks.append(r['content']);offset=r['next_char']
  self.assertEqual(''.join(chunks),text)
  with self.assertRaises(ProtocolError):s.read_chars('long',max_chars=6001)
  empty=EvidenceSession([evidence_record('empty','submission','')])
  self.assertEqual(empty.read_chars('empty')['content'],'')
 def test_same_turn_public_refs(self):
  records=[evidence_record('task','task','public task'),evidence_record('sub','submission','proposal'),evidence_record('ref','reference','private unique answer',visibility='private')]
  s=EvidenceSession(records);receipts={k:s.read(k)['receipt_id'] for k in ['task','sub','ref']}
  judgment={'status':'scored','dimensions':{d:{'score':3,'rationale':'core sound','refs':list(receipts.values())} for d in DIMENSIONS['IDEA']},'checks':[],'serious_issues':[],'uncertainty':[],'failure_reason':None}
  issue={'observation':'A localized issue','refs':[receipts['sub']],'affected_requirement':'clear hypotheses','improvement_concern':'check conditions','root_cause':{'status':'unknown','explanation':'not established'}}
  response={'judgment':judgment,'feedback':{'issues':[issue],'limitations':[]}}
  self.assertEqual(validate_native_result('IDEA',response,s)['quality'],3)
  for entry in judgment['dimensions'].values():entry['refs']=[receipts['sub']]
  # Native minimum is actual role retrieval, not gratuitous grade citations.
  self.assertEqual(validate_native_result('IDEA',response,s)['quality'],3)
  unused=s.receipts.pop(receipts['ref'])
  with self.assertRaises(ProtocolError):validate_native_result('IDEA',response,s)
  s.receipts[receipts['ref']]=unused
  issue['refs']=[receipts['ref']]
  with self.assertRaises(ProtocolError):validate_native_result('IDEA',response,s)
 def test_no_implicit_image_delivery(self):
  with tempfile.TemporaryDirectory() as d:
   # signature is sufficient for the old EvidenceSession boundary; this tests transport bookkeeping, not PNG decoding.
   import base64
   records=[evidence_record('image','rendered_artifact',base64.b64encode(b'\x89PNG\r\n\x1a\n').decode(),media_type='image/png')]
   b=BoundedTools({'records':records,'state_path':str(Path(d)/'s.json')})
   result=b.call('evidence_read',{'evidence_id':'image'})
   self.assertEqual(result['content'][1]['type'],'image')
   self.assertFalse(b.session.images_delivered)
 def test_prompt_no_separate_feedback_agent(self):
  p=make_prompt('x','IDEA',EvidenceSession([]))
  self.assertIn('SAME',p);self.assertNotIn('NEW context',p)
  self.assertIn('infrastructure_failure',p)
  self.assertIn('not by the research harness',p)
  self.assertIn('Command\nduration, complete task elapsed time',p)
 def test_lit_claim_scope_checks_use_guidance_and_original_passages(self):
  records=[evidence_record('guidance','reference','ASSET evaluation\n{"checks":["verify broad claims"]}',visibility='private')]
  prompt=make_prompt('lit','LIT',EvidenceSession(records))
  self.assertIn('"evaluation_guidance_evidence_ids": ["guidance"]',prompt)
  self.assertIn('actual supporting/counterexample passage',prompt)
  self.assertIn('No requirement to read the entire corpus',prompt)
  self.assertIn('without a forced score',prompt)
  self.assertNotIn('LIT claim verification policy',make_prompt('idea','IDEA',EvidenceSession(records)))
 def test_platform_failure_never_becomes_scientific_zero(self):
  s=EvidenceSession([evidence_record('platform','platform_trace','Controller failed to release mandatory resource attestation')])
  ref=s.read_chars('platform')['receipt_id']
  response={'judgment':{'status':'infrastructure_failure','dimensions':{},'checks':[{'check_id':'resource_evidence','state':'insufficient_evidence','rationale':'Controller evidence absent; not a solver error','refs':[ref]}],'serious_issues':[],'uncertainty':['Scientific code is assessable but required resource dimension cannot be certified.'],'failure_reason':'Required controller attestation missing'},'feedback':{'issues':[],'limitations':['Evaluation blocked by controller evidence collection.']}}
  result=validate_native_result('EXP',response,s)
  self.assertIsNone(result['quality']);self.assertIsNone(result['dimension_scores'])
 def test_visual_policy_checks_pixels_without_forcing_defects(self):
  p=make_prompt('visual','WRITE_EVIDENCE',EvidenceSession([]))
  for phrase in ['actual received pixels','label-label and label-mark overlap','legend-to-mark mapping','image region','do not invent a mandatory','clean, readable artifact','partial source read']:
   self.assertIn(phrase,p)
  self.assertNotIn('WRITE visual inspection policy',make_prompt('exp','EXP',EvidenceSession([])))
 def test_no_unrequested_factorial_design_or_private_feedback_scope(self):
  p=make_prompt('exp','EXP',EvidenceSession([]))
  for phrase in ['selected parameter pairs','separate effect','stronger unrequested','EVERY feedback field','including limitations','Private audit procedures','Keep\nthem in internal judgment uncertainty']:
   self.assertIn(phrase,p)
 def test_hash_scopes_distinguish_record_content_from_file_bytes(self):
  import hashlib
  from mrhbench.io import digest
  content='a\nb\n'
  self.assertNotEqual(digest(content),hashlib.sha256(content.encode()).hexdigest())
  self.assertNotEqual(hashlib.sha256(content.encode()).hexdigest(),hashlib.sha256(content.replace('\n','\r\n').encode()).hexdigest())
  p=make_prompt('hash','EXP',EvidenceSession([]))
  for phrase in ['CONTENT STRING','not raw file hashes','Do not directly compare','CRLF and LF','not automatically\na solver error']:
   self.assertIn(phrase,p)
 def test_confirmed_absent_solver_visual_can_be_scored_without_fake_pixels(self):
  from mrhbench.native_judge import OUTPUT_INVENTORY_ID
  inv={'version':1,'collection_status':'complete','evaluation_inputs_available':True,'expected_outputs':['figure','code'],'observed_files':[],
       'missing_outputs':[{'requirement':'figure','role':'rendered_artifact','reason':'solver_not_produced'},{'requirement':'code','role':'submission','reason':'solver_not_produced'}]}
  def setup(value,origin='platform_trace'):
   records=[evidence_record('task','task','Produce a visual and code'),evidence_record('sub','submission','No outputs'),evidence_record('reference','reference','Expected fixed evidence'),evidence_record(OUTPUT_INVENTORY_ID,origin,json.dumps(value))]
   session=EvidenceSession(records);refs=[session.read_chars(r['evidence_id'])['receipt_id'] for r in records]
   response={'judgment':{'status':'scored','dimensions':{d:{'score':0,'rationale':'Required scientific presentation absent, no visual properties inferred','refs':[refs[0],refs[1],refs[-1]]} for d in DIMENSIONS['WRITE_EVIDENCE']},'checks':[],'serious_issues':[],'uncertainty':['No pixels were produced or inspected.'],'failure_reason':None},'feedback':{'issues':[],'limitations':[]}}
   return session,response
  session,response=setup(inv)
  self.assertEqual(validate_native_result('WRITE_EVIDENCE',response,session)['quality'],0)
  self.assertFalse(session.images_delivered)
  response['judgment'].update(status='material_failure',dimensions={},failure_reason='No solver visual')
  with self.assertRaises(ProtocolError):validate_native_result('WRITE_EVIDENCE',response,session)
  for reason in ['transport_failure','collection_failure','unknown']:
   v=json.loads(json.dumps(inv));v['missing_outputs'][0]['reason']=reason
   session,response=setup(v)
   with self.assertRaises(ProtocolError):validate_native_result('WRITE_EVIDENCE',response,session)
  session,response=setup(inv,origin='submission')
  with self.assertRaises(ProtocolError):validate_native_result('WRITE_EVIDENCE',response,session)
  session,response=setup(inv)
  receipt=next(k for k,v in session.receipts.items() if v['evidence_id']==OUTPUT_INVENTORY_ID)
  session.receipts.pop(receipt)
  with self.assertRaises(ProtocolError):validate_native_result('WRITE_EVIDENCE',response,session)
 def test_partial_or_contradictory_output_collection_does_not_certify_absence(self):
  from mrhbench.native_judge import validate_output_inventory
  inv={'version':1,'collection_status':'failed','evaluation_inputs_available':True,'expected_outputs':['figure'],'observed_files':[],
       'missing_outputs':[{'requirement':'figure','role':'rendered_artifact','reason':'solver_not_produced'}]}
  with self.assertRaises(ProtocolError):validate_output_inventory(inv)
  inv['missing_outputs'][0]['reason']='collection_failure'
  self.assertEqual(validate_output_inventory(inv),inv)
 def test_export_closes_even_when_export_fails(self):
  with tempfile.TemporaryDirectory() as d:
   class Fake:
    closed=False
    def artifacts(self,*args,**kwargs):raise ProtocolError('expired')
    def close(self):self.closed=True
   b=BoundedTools({'state_path':str(Path(d)/'state.json'),'artifact_export':{'destination':str(Path(d)/'out'),'max_bytes':100,'max_files':2,'inventory_path':str(Path(d)/'inventory.json')}})
   b.container=Fake()
   b.owns_container=True
   with self.assertRaises(ProtocolError):b.close()
   self.assertTrue(b.container.closed)
if __name__=='__main__':unittest.main()
