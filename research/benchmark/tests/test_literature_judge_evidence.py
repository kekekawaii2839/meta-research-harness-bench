import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mrhbench.io import read_json,ProtocolError,digest
from mrhbench.literature import LiteratureService
from mrhbench.literature_judge_evidence import build_literature_judge_evidence,literature_page_record

class LiteratureJudgeEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.workspace=ROOT.parents[1]
  cls.rows=[r for r in read_json(ROOT/'materials/pilot_v3/literature_v3/shared_background_corpus.json')['documents'] if r['document_id']=='doc-2204.13263']
 def svc(self,**kwargs):return LiteratureService(copy.deepcopy(self.rows),self.workspace,kwargs.pop('cutoff','2024-09-01'),set(),shared=True,**kwargs)
 def test_page_is_bound_private_complete_original_text(self):
  svc=self.svc();raw=svc.read_page('doc-2204.13263',2);record=literature_page_record(svc,'doc-2204.13263',2)
  self.assertEqual(record['visibility'],'private');self.assertEqual(record['origin'],'reference')
  self.assertEqual(record['content'].split('\n',1)[1],raw['text'])
  self.assertIn(raw['source_sha256'],record['content']);self.assertEqual(record['sha256'],digest(record['content']))
 def test_full_record_ranges_originals_and_no_executor_reads(self):
  class Trace:
   def append(self,*args):raise AssertionError('Judge polluted executor trace')
  svc=self.svc(trace=Trace());out=build_literature_judge_evidence(svc);idx=json.loads(out[0]['content'])
  self.assertTrue(idx['complete_text_extraction']);self.assertEqual(idx['document_count'],1)
  pages=idx['documents'][0]['pages'];self.assertEqual(len(pages),19)
  plain=self.svc();lines=out[1]['content'].splitlines()
  for pg in pages:
   text='\n'.join(lines[pg['start_line']-1:pg['end_line']])
   original=plain.read_page('doc-2204.13263',pg['pdf_page_number'])['text']
   self.assertEqual(text,'\n'.join(original.splitlines()))
   self.assertEqual(out[1]['content'][pg['start_char']:pg['end_char']],original)
   self.assertEqual(pg['end_char']-pg['start_char'],len(original))
  self.assertEqual(idx['index_schema_version'],'3')
 def test_same_time_alias_and_version_filter(self):
  for svc in [self.svc(cutoff='2021-01-01'),self.svc(excluded_aliases=['2204.13263']),self.svc(allowed_versions={})]:
   self.assertEqual(json.loads(build_literature_judge_evidence(svc)[0]['content'])['document_count'],0)
   with self.assertRaises(ProtocolError):literature_page_record(svc,'doc-2204.13263',1)
 def test_source_hash_failure_never_swallowed(self):
  svc=self.svc();svc.records['doc-2204.13263']['pdf_sha256']='0'*64
  with self.assertRaises(ProtocolError):build_literature_judge_evidence(svc,allow_incomplete=True)
  svc=self.svc();svc.records['doc-2204.13263']['abstract_sha256']='0'*64
  with self.assertRaises(ProtocolError):build_literature_judge_evidence(svc,allow_incomplete=True)
 def test_no_silent_capacity_truncation(self):
  with self.assertRaises(ProtocolError):build_literature_judge_evidence(self.svc(),max_total_chars=100)
  with self.assertRaises(ProtocolError):build_literature_judge_evidence(self.svc(),max_documents=0)
 def test_unicode_page_failure_explicit_only_on_opt_in(self):
  real=LiteratureService.read_page
  def reader(s,doc,n):
   if n==2:raise UnicodeEncodeError('utf8','\ud83d',0,1,'synthetic orphan surrogate')
   return real(s,doc,n)
  with patch.object(LiteratureService,'read_page',reader):
   with self.assertRaises(UnicodeEncodeError):build_literature_judge_evidence(self.svc())
   records=build_literature_judge_evidence(self.svc(),allow_incomplete=True)
  idx=json.loads(records[0]['content']);self.assertFalse(idx['complete_text_extraction'])
  fail=idx['unavailable_pages'];self.assertEqual(len(fail),1);self.assertEqual(fail[0]['pdf_page_number'],2)
  self.assertEqual(fail[0]['source_sha256'],self.rows[0]['pdf_sha256'])
  location=fail[0];notice=json.loads(records[1]['content'][location['start_char']:location['end_char']])
  self.assertEqual(notice['status'],'unavailable_extraction_error')
  self.assertEqual(notice['pdf_page_number'],2)
  self.assertEqual(notice['source_sha256'],self.rows[0]['pdf_sha256'])
  self.assertEqual(location['range_content'],'unavailable_page_notice_not_original_source_text')

if __name__=='__main__':unittest.main()
