"""Mechanical source/visibility checks, not a domain-coverage or LLM acceptance."""
import copy,hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mrhbench.io import ProtocolError,read_json,file_hash
from mrhbench.literature import LiteratureService,SharedCorpusView,original_abstract

class SharedBackgroundV3Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.workspace=ROOT.parents[1]
  cls.base=ROOT/'materials/pilot_v3/literature_v3'
  cls.corpus=read_json(cls.base/'shared_background_corpus.json')
  cls.rows=cls.corpus['documents']
  cls.times=read_json(cls.base/'source_time_audit.json')
 def service(self,cutoff='2024-09-01',excluded=()):
  return LiteratureService(self.rows,self.workspace,cutoff,set(excluded),shared=True)
 def test_source_identity_version_hash_and_seed_immutability(self):
  self.assertGreaterEqual(self.corpus['new_document_count'],8)
  self.assertFalse(self.corpus['formal_material_accepted'])
  old=read_json(ROOT/'materials/pilot_v2/shared_background_corpus.json')['documents']
  self.assertEqual(self.rows[:len(old)],old)
  self.assertEqual(len({r['paper_id'] for r in self.rows}),len(self.rows))
  for row in self.rows:
   self.assertEqual(row['version'],'arxiv-v1')
   self.assertEqual(original_abstract(row,self.workspace)['text'],row['text'])
   self.assertEqual(file_hash(self.workspace/row['pdf_source_path']),row['pdf_sha256'])
 def test_failed_or_incomplete_pdf_not_indexed(self):
  docs={r['document_id'] for r in self.rows}
  audit=read_json(ROOT/'audit/shared_background_v3_construction.json')
  for error in audit['errors']:self.assertNotIn('doc-'+error['id'],docs)
  self.assertIn('doc-1910.12358',docs)
 def test_cross_package_queries_and_original_abstracts(self):
  svc=self.service()
  iv={r['document_id'] for r in svc.search('instrumental variable',50)}
  ssa={r['document_id'] for r in svc.search('test time adaptation',50)}
  self.assertIn('doc-1910.12358',iv)
  self.assertIn('doc-2204.13263',ssa)
  self.assertIn('doc-2006.10726',ssa)
  self.assertEqual(svc.read('doc-2405.19463')['text_kind'],'verbatim_pinned_source_abstract')
 def test_private_labels_not_exposed(self):
  private=read_json(self.base/'private_literature_roles_candidates.json')
  self.assertEqual(private['visibility'],'maintainer_private_never_solver_index')
  svc=self.service()
  for row in self.rows:
   public=svc.read(row['document_id'])
   for key in ['candidate_scope','tier','rationale','reference_source','reference_text','abstract_source_path','pdf_source_path','index_approved']:
    self.assertNotIn(key,public)
  for row in self.rows:
   self.assertNotIn('tier',row);self.assertNotIn('rationale',row)
 def test_date_and_alias_filter_before_title_body_page(self):
  svc=LiteratureService(self.rows,self.workspace,'2023-01-01',set(),shared=True,excluded_aliases={'2212.07677'})
  for key in ['doc-2405.19463','doc-2212.07677']:
   self.assertNotIn(key,{r['document_id'] for r in svc.search('transformer gradient instrumental',50)})
   with self.assertRaises(ProtocolError):svc.read(key)
   with self.assertRaises(ProtocolError):svc.read_page(key,1)
 def test_future_revision_cannot_enter_historical_view(self):
  base=next(x for x in self.rows if x['document_id']=='doc-2402.05639')
  future=copy.deepcopy(base);future.update(document_id='future-v3',version='arxiv-v3',version_number=3,published_date='2024-12-23',text='FUTURE_VERSION_CANARY')
  view=SharedCorpusView(self.rows+[future],'2024-09-01',set())
  self.assertNotIn('future-v3',view.docs)
  self.assertEqual(view.read(base['document_id'])['version'],'arxiv-v1')
 def test_page_derivatives_preserve_source_binding(self):
  for row in self.times['background_versions']:
   path=self.workspace/row['page_text_path'];self.assertEqual(file_hash(path),row['page_text_sha256'])
   data=read_json(path);self.assertEqual(data['source_pdf_sha256'],row['raw_pdf_sha256'])
   self.assertEqual(len(data['pages']),row['pdf_pages']);self.assertTrue(row['pdf_v1_stamp_verified'])
   for page in data['pages']:
    self.assertEqual(hashlib.sha256(page['text'].encode()).hexdigest(),page['sha256'])
 def test_target_disclosure_bounds_not_overclaimed(self):
  ids={r['paper_id'] for r in self.rows};aliases={a for r in self.rows for a in r['paper_aliases']}
  for row in self.times['target_audits']:
   self.assertNotIn(row['paper_id'],ids);self.assertNotIn(row['arxiv_id'],aliases)
   self.assertFalse(row['target_content_in_background_index'])
   self.assertIn('not_global_first_disclosure',row['earliest_verified_in_this_audit'])
   self.assertGreaterEqual(len(row['unresolved']),3)
   self.assertLess(row['recommended_candidate_cutoff'],row['arxiv_v1_submitted_at'][:10])
 def test_source_storage_and_unchanged_originals(self):
  report=read_json(ROOT/'audit/shared_background_v3_construction.json')
  self.assertEqual(report['original_files_changed'],[])
  self.assertGreaterEqual(report['original_files_checked'],116)
  self.assertLessEqual(report['new_raw_bytes']+report['new_material_bytes'],100*1024*1024)

if __name__=='__main__':unittest.main()
