"""Mechanical candidate checks; not scientific coverage or judge acceptance."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mrhbench.io import read_json,file_hash,ProtocolError
from mrhbench.materials import check_task
from mrhbench.literature import LiteratureService,SharedCorpusView

class StageMigrationV3Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.workspace=ROOT.parents[1]
  cls.base=ROOT/'materials/pilot_v3/released_stage_candidates'
  cls.tasks={s:read_json(cls.base/s/'task.json') for s in ['lit','idea']}
  cls.audit=read_json(ROOT/'audit/stage_migration_v3_semantic_review.json')
 def test_originals_unchanged_and_development_not_accepted(self):
  for name,sha in self.audit['inspected_originals'].items():self.assertEqual(file_hash(self.workspace/name),sha)
  self.assertEqual(self.audit['original_files_changed'],[])
  for stage,t in self.tasks.items():
   check_task(t,self.base/stage,formal=False)
   self.assertFalse(t['private']['formal_eligible'])
   self.assertTrue(all(g['status']=='pending' for g in t['gates'].values()))
   self.assertEqual(t['split'],'development')
 def test_public_publication_no_private_assets_or_target_canaries(self):
  for stage,t in self.tasks.items():
   root=self.base/stage/'release';release=read_json(root/'task.json')
   expected={'task.json'}|{a['path'] for a in release['asset_manifest']}
   self.assertEqual({p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()},expected)
   for a in release['asset_manifest']:self.assertEqual(file_hash(root/a['path']),a['sha256'])
   text='\n'.join(p.read_text(encoding='utf8') for p in root.rglob('*.json'))
   for token in self.audit['public_target_method_canaries_checked']:
    self.assertNotIn(token,text)
   for token in ['corpus_configuration','private/evaluation','source_cache/','candidate_scope','read_evidence','private_literature_roles']:
    self.assertNotIn(token,text)
   self.assertNotIn('paper_id',release)
   self.assertNotIn('private',release)
 def test_schema_preserves_required_scientific_fields(self):
  for stage,t in self.tasks.items():
   old=read_json(ROOT/('materials/ssa_'+stage+'/task.json'))
   schema=t['public']['output_contract']
   self.assertEqual(schema['type'],'object')
   self.assertEqual(schema['required'],old['public']['output_contract']['required'])
   self.assertEqual(set(schema['properties']),set(schema['required']))
   for value in schema['properties'].values():self.assertTrue(value['type']);self.assertTrue(value['description'])
 def test_package_resource_and_controller_budgets(self):
  for stage,mc,tc in [('lit',12,120),('idea',6,60)]:
   r=self.tasks[stage]['public']['resources']
   self.assertEqual(r['container'],dict(cpus=1,memory_mb=1024,disk_mb=512,pids_limit=64,wall_seconds=600))
   self.assertEqual(r['execution_budget'],dict(model_calls=mc,tool_calls=tc,wall_seconds=600))
   self.assertEqual(r['image_id'],'sha256:399341648ce68031cef84e225a8b4985fed3125fd020ec96a8d6c5d6563036d0')
   self.assertFalse(r['gpu_allowed']);self.assertIn('development',r['budget_status'])
 def test_lit_shared_original_abstract_service(self):
  cfg=self.tasks['lit']['private']['corpus_configuration']
  self.assertTrue(cfg['shared']);self.assertEqual(cfg['required_view'],'SharedCorpusView')
  self.assertEqual(file_hash(self.workspace/cfg['corpus_manifest']),cfg['corpus_sha256'])
  rows=read_json(self.workspace/cfg['corpus_manifest'])['documents']
  svc=LiteratureService(rows,self.workspace,cfg['cutoff'],set(cfg['excluded_papers']),shared=cfg['shared'],excluded_aliases=cfg['excluded_aliases'],allowed_versions=cfg['allowed_versions'])
  self.assertIsInstance(svc.corpus,SharedCorpusView);self.assertEqual(len(svc.corpus.docs),18)
  self.assertIn('doc-1910.12358',{x['document_id'] for x in svc.search('instrumental variable',50)})
  self.assertIn('doc-2204.13263',{x['document_id'] for x in svc.search('feature alignment',50)})
  for row in rows:
   result=svc.read(row['document_id'])
   self.assertEqual(result['text_kind'],'verbatim_pinned_source_abstract')
   self.assertLessEqual(result['published_date'],cfg['cutoff'])
   self.assertNotIn(result['paper_id'],cfg['excluded_papers'])
   self.assertNotIn('tier',result)
  for doc in ['doc-2410.03263','doc-2410.01265']:
   with self.assertRaises(ProtocolError):svc.read(doc)
 def test_idea_fixed_independent_background_no_retrieval(self):
  task=self.tasks['idea'];evaluation=read_json(self.base/'idea/private/evaluation.json')
  self.assertNotIn('corpus_configuration',task['private'])
  self.assertNotIn('historical_service',evaluation)
  self.assertFalse(any(t.startswith('literature.') for t in task['public']['tools']))
  self.assertFalse(evaluation['fixed_reference_scope']['additional_executor_retrieval'])
  old=read_json(ROOT/'materials/ssa_idea/public/background_report.json')
  new=read_json(self.base/'idea/public/background_report.json')
  self.assertEqual(new['evidence_summary'],old['evidence_summary'])
  for key in old:
   if key!='kind':self.assertEqual(new[key],old[key])
  self.assertIn('not_solver_output',new['kind'])
  self.assertEqual(self.tasks['lit']['paper_id'],task['paper_id'])
  self.assertTrue(read_json(self.base/'migration_manifest.json')['no_upstream_solver_output_used'])

if __name__=='__main__':unittest.main()
