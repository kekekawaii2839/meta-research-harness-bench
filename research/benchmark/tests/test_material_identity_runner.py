"""Identity assignment + actual batch/quality/adjudication, fake native only."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mrhbench.io import ProtocolError,read_json,write_json,file_hash
from mrhbench.material_identity_runner import IdentityBoundRunner
from mrhbench.material_quality_runner import QualityBoundRunner
from mrhbench.material_public_identity import allocate_map,project_candidate,validate_map
from mrhbench.material_batch import run_batch
from mrhbench.factory_efficiency import adjudicate
from mrhbench.material_policy_schema import bind_policy_rules
from mrhbench.bounded_ledger import BoundedCallLedger

class IdentityRunnerTests(unittest.TestCase):
    def exercise(self,root,*,incremental=False,mode=None):
        from test_material_public_identity import IdentityTests
        source,_=IdentityTests().fixture(root)
        map_id=allocate_map(source,root/'private/map.json')
        project_candidate(source,root/'prior/j/constructor/output',map_id,receipt_path=root/'private/projection.json')
        write_json(root/'prior/j/reviewer/review.json',{'schema_version':'material-review-1',
            'paper_id':'private-paper-Q9X','decision':'revise','findings':[]})
        (root/'paper.txt').write_text('Synthetic source only',encoding='utf8')
        job={'schema_version':'material-job-1','job_id':'j','paper_id':'private-paper-Q9X',
             'requested_task_types':['EXP'],'scope_request':'Synthetic neutral scope','first_disclosure':{},
             'environment_candidate':{'gpu':False,'network':'none','scientific_rationale':'Fixture',
                'cpus':1,'memory_mb':256,'disk_mb':32,'pids_limit':32,'wall_seconds':300},
             'sources':[{'source_id':'s','url':'https://example.invalid/source','version':'v1',
                'local_path':'paper.txt','sha256':file_hash(root/'paper.txt'),'role':'paper_text'}]}
        templates=root/'templates';shutil.copytree(ROOT/'prompts',templates)
        for name in ('policy.md','adjudicator_review.txt'):
            shutil.copyfile(templates/'material_efficiency_v3'/name,templates/'factory_v4'/name)
        bound,_=bind_policy_rules(read_json(templates/'factory_v4/review_adjudication.schema.json'),
                                (templates/'factory_v4/policy.md').read_bytes())
        write_json(templates/'factory_v4/review_adjudication.schema.json',bound)
        write_json(root/'ledger.json',{'authorized_maximum':3,'used_attempts':0,'attempts':[]})
        arm=root/'arms/one'
        ledger=BoundedCallLedger(root/'ledger.json',baseline=0,stop_at=3,experiment_root=root,arm_root=arm)
        called=[];assignments=[]
        testcase=self
        class Native:
            def run(inner,*,workspace,prompt,role):
                cid=ledger.reserve(role=role,model='fake',effort='medium',request_hash='0'*64,
                    artifact_directory=str(arm/'native_calls'/role))
                ledger.finish(cid,status='completed',wall_seconds=1,
                    usage={'input_tokens':1,'cached_input_tokens':0,'cache_write_input_tokens':0,'output_tokens':1},metadata={})
                called.append(role)
                assignment=read_json(workspace/'identity_assignment.json');assignments.append(assignment)
                testcase.assertEqual(set(assignment),{'schema_version','tasks'})
                testcase.assertNotIn('private-paper-Q9X',(workspace/'identity_assignment.json').read_text())
                testcase.assertIn('identity_assignment.json',prompt)
                testcase.assertFalse((workspace/'map.json').exists())
                if role=='constructor':
                    shutil.copytree(root/'prior/j/constructor/output',workspace/'output',dirs_exist_ok=True)
                    p=read_json(workspace/'output/package.json')
                    if mode=='old_id':p['tasks'][0]['task_id']='private-task-Q9X'
                    if mode=='wrong_type':p['tasks'][0]['task_type']='IDEA'
                    if mode=='public_leak':p['tasks'][0]['input_contract']['extra']='private-paper-Q9X'
                    if mode=='binary_unknown':
                        asset=workspace/'output/assets/start.txt';asset.write_bytes(b'\x89PNG\x00\xff')
                        p['tasks'][0]['assets'][0]['sha256']=file_hash(asset)
                        p['tasks'][0]['input_contract']['files'][0]['sha256']=file_hash(asset)
                    # Native file-only constructor writes sentinel hashes;
                    # only the real run_batch controller may fill these later.
                    p['tasks'][0]['assets'][0]['sha256']='CONTROLLER_FILL'
                    p['tasks'][0]['input_contract']['files'][0]['sha256']='CONTROLLER_FILL'
                    write_json(workspace/'output/package.json',p)
                    if mode=='mutate_assignment':write_json(workspace/'identity_assignment.json',{})
                else:
                    c=read_json(workspace/'quality_contract.json');ids=list(c['public_inventory']);checks={}
                    for key in c['checks']:
                        checks[key]={'status':'unknown' if mode=='quality_unknown' else 'clear',
                            'rationale':'Synthetic coverage only','evidence':[{'surface_id':ids[0],'locator':'fixture','observation':'Synthetic'}],
                            **({'scope':'entire_bound_public_inventory'} if key in ('identity','author_scale','target_implementation')
                               else {'scope':'selected_surfaces','inspected_surface_ids':ids})}
                    write_json(workspace/'quality_coverage.json',{'contract_sha256':c['contract_sha256'],
                        'policy_sha256':c['policy_sha256'],'checks':checks})
                    if role=='material_reviewer':
                        write_json(workspace/'review.json',{'schema_version':'material-review-1','paper_id':'private-paper-Q9X',
                            'decision':'pass_with_pending_runtime','findings':[]})
                    else:
                        write_json(workspace/'review_adjudication.json',{'schema_version':'factory-review-adjudication-1',
                            'project_id':'private-paper-Q9X','round':2,'action':'pass','finding_decisions':[],
                            'repair_notes':[],'drop_reason':None,'excluded_task_ids':[]})
                return {'call_id':cid}
        def runner():
            quality=QualityBoundRunner(Native(),policy_path=templates/'factory_v4/policy.md',
                                      project_id='private-paper-Q9X',round_no=2)
            return IdentityBoundRunner(quality,map_identity=map_id)
        batch=run_batch([job],workspace=root,batch_root=arm/'batch',templates=templates,
            constructor=runner(),reviewer=runner(),repair_from=root/'prior',repair_notes={'j':['Preserve neutral scientific scope']},
            incremental_repair=incremental,controller_hash_fill=True,max_jobs=1,max_workers=1)
        decision=None
        if batch['jobs'][0]['status']=='pass_with_pending_runtime':
            decision=adjudicate(arm/'batch/j/reviewer',arm/'adjudicator',templates/'factory_v4',runner(),
                'private-paper-Q9X',2,['pass','pass_partial','drop'])
        return batch,decision,called,assignments,arm,map_id

    def test_real_old_and_incremental_batch_three_roles_keep_quality_gates(self):
        for incremental in (False,True):
            with self.subTest(incremental=incremental),tempfile.TemporaryDirectory() as tmp:
                batch,decision,called,assignments,arm,map_id=self.exercise(Path(tmp),incremental=incremental)
                self.assertEqual(batch['jobs'][0]['status'],'pass_with_pending_runtime',batch)
                self.assertEqual(called,['constructor','material_reviewer','adjudicator'])
                self.assertEqual(decision['decision']['action'],'pass')
                self.assertTrue(all(x==assignments[0] for x in assignments))
                self.assertTrue((arm/'adjudicator/quality_controller_validation.json').is_file())
                receipt=read_json(arm/'adjudicator/identity_controller_validation.json')
                self.assertFalse(receipt['post_generation_renaming'])
                self.assertFalse(receipt['scientific_acceptance'])
                self.assertEqual(read_json(Path(tmp)/'ledger.json')['used_attempts'],3)
                ctor=arm/'batch/j/constructor'
                original=read_json(ctor/'output/package.constructor_original.json')
                filled=read_json(ctor/'output/package.json')
                self.assertEqual(original['tasks'][0]['assets'][0]['sha256'],'CONTROLLER_FILL')
                self.assertEqual(filled['tasks'][0]['assets'][0]['sha256'],file_hash(ctor/'output/assets/start.txt'))
                ctor_receipt=read_json(ctor/'identity_controller_validation.json')
                self.assertEqual(ctor_receipt['scan_after']['status'],'pending_controller_hash_fill_then_pre_review_scan')
                self.assertTrue(batch['jobs'][0]['controller_hash_fill']['controller_hash_fill'])
                self.assertEqual(set(assignments[0]['tasks'][0]),{'task_id','task_type'})

    def test_bad_identity_or_public_leak_stops_before_paid_review(self):
        for mode in ('old_id','wrong_type','public_leak','mutate_assignment'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                batch,decision,called,_,arm,_=self.exercise(Path(tmp),mode=mode)
                self.assertEqual(batch['jobs'][0]['status'],'failed_needs_attribution',batch)
                self.assertEqual(called,['constructor'])
                self.assertIsNone(decision)
                if mode=='public_leak':
                    self.assertTrue(batch['jobs'][0]['controller_hash_fill']['controller_hash_fill'])
                    self.assertIn('Known private identity remains',batch['jobs'][0]['error']['message'])
                    receipt=read_json(arm/'batch/j/constructor/identity_controller_validation.json')
                    self.assertEqual(receipt['scan_after']['status'],'pending_controller_hash_fill_then_pre_review_scan')
                if mode=='old_id':
                    self.assertEqual(read_json(arm/'batch/j/constructor/output/package.json')['tasks'][0]['task_id'],'private-task-Q9X')

    def test_original_unknown_quality_cannot_become_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch,decision,called,_,_,_=self.exercise(Path(tmp),mode='quality_unknown')
            self.assertEqual(batch['jobs'][0]['status'],'failed_needs_attribution')
            self.assertEqual(called,['constructor','material_reviewer'])
            self.assertIsNone(decision)

    def test_refuses_unwrapped_inner(self):
        with self.assertRaises(ProtocolError):IdentityBoundRunner(object(),map_identity={})

    def test_binary_unknown_preserved_not_claimed_mechanically_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch,decision,called,_,arm,_=self.exercise(Path(tmp),mode='binary_unknown')
            self.assertEqual(called,['constructor','material_reviewer','adjudicator'])
            receipt=read_json(arm/'adjudicator/identity_controller_validation.json')
            self.assertEqual(receipt['scan_after']['status'],'unknown_binary_requires_independent_review')
            self.assertFalse(receipt['scientific_acceptance'])
            self.assertFalse(receipt['scan_after']['semantic_anonymity_verified'])

    def test_review_invalid_assignment_rejected_before_native_call(self):
        from test_material_public_identity import IdentityTests
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,_=IdentityTests().fixture(root)
            map_id=allocate_map(source,root/'private/map.json')
            role=root/'reviewer';role.mkdir()
            shutil.copytree(source,role/'output')
            write_json(role/'request.json',{'paper_id':'private-paper-Q9X'})
            class NoCall:
                def run(inner,**kwargs):self.fail('Invalid review input must not invoke native')
            quality=QualityBoundRunner(NoCall(),policy_path=ROOT/'prompts/material_efficiency_v3/policy.md',
                project_id='private-paper-Q9X',round_no=2)
            with self.assertRaises(ProtocolError):
                IdentityBoundRunner(quality,map_identity=map_id).run(workspace=role,prompt='fixture',role='material_reviewer')

if __name__=='__main__':unittest.main()
