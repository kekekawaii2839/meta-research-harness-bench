"""Opt-in v4 orchestration tests; only synthetic native sessions/runtime records."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mrhbench import factory_efficiency_v4 as f
from mrhbench.io import ProtocolError,read_json,write_json,digest
from mrhbench.material_public_identity import allocate_map,scan_release

class V4Tests(unittest.TestCase):
    def fixture(self,root):
        from test_material_public_identity import IdentityTests
        source,args=IdentityTests().fixture(root)
        prior=root/'prior/j/constructor/output';shutil.copytree(source,prior)
        map_id=allocate_map(prior,root/'private/map.json')
        write_json(root/'prior/j/reviewer/review.json',{'schema_version':'material-review-1',
            'paper_id':'private-paper-Q9X','decision':'revise','findings':[]})
        (root/'paper.txt').write_text('Synthetic source',encoding='utf8')
        job={'schema_version':'material-job-1','job_id':'j','paper_id':'private-paper-Q9X',
            'requested_task_types':['EXP'],'scope_request':'Synthetic scope','first_disclosure':{},
            'environment_candidate':{'gpu':False,'network':'none','scientific_rationale':'Fixture',
                'cpus':1,'memory_mb':256,'disk_mb':32,'pids_limit':32,'wall_seconds':300},
            'sources':[{'source_id':'s','url':'https://example.invalid/p','version':'v1','local_path':'paper.txt',
                'sha256':f.file_hash(root/'paper.txt'),'role':'paper_text'}]}
        write_json(root/'job.json',job);write_json(root/'notes.json',['Retain scientific inputs'])
        write_json(root/'projection.json',{'unmodified_private_prior':True})
        benchmark=root/'benchmark';shutil.copytree(ROOT/'prompts',benchmark/'prompts')
        (benchmark/'mrhbench').mkdir();(benchmark/'mrhbench/fixture.py').write_text('# offline fixture')
        (benchmark/'scripts/active').mkdir(parents=True)
        shutil.copyfile(ROOT/'scripts/active/run_factory_efficiency_v4.py',benchmark/'scripts/active/run_factory_efficiency_v4.py')
        binary=root/'fake.exe';binary.write_bytes(b'not executed')
        roles=benchmark/'config/roles.json'
        write_json(roles,{'claude_binary_default':str(binary),'constructor':{'model':'claude-opus-5-5','effort':'medium'},
                         'judge':{'model':'claude-opus-5-5','effort':'medium'}})
        ledger=root/'ledger.json';write_json(ledger,{'authorized_maximum':1668,'used_attempts':612,
            'attempts':[{'id':i,'status':'completed'} for i in range(1,613)]})
        conditional=root/'conditional.json'
        write_json(conditional,{'baseline_observed':612,'pair_max_calls':12,'pair_stop_at':624,
            'prior_goal_stop_at':625,'conditional_extra_calls':4,'conditional_goal_stop_at':629,
            'prospective_max_calls':5,'first_429_stops_batch':True,'automatic_retry':False,
            'condition':'Both fresh pairs pass quality and frozen costs before conditional additional calls',
            'user_answer':'Synthetic conditional authorization'})
        grant=f.identity(conditional)
        approval=root/'approval.json';write_json(approval,{'protocol_version':4,'ledger_baseline':612,'ledger_stop_at':625,
            'pair_max_calls':12,'prospective_max_calls':5,'authorized_to_freeze':True,'pair_stop_at':624,
            'conditional_extra_calls':4,'conditional_goal_stop_at':629,'conditional_authorization':grant})
        case={'case_id':'a','classification':'fresh_validation','workspace':str(root),'job_path':str(root/'job.json'),
            'job_id':'j','prior_batch':str(root/'prior'),'notes_path':str(root/'notes.json'),'notes_key':None,
            'projection_record_path':str(root/'projection.json'),'round_no':2,'order':['old','incremental'],
            'frozen_inputs':[f.identity(root/'paper.txt')],'identity_map':map_id}
        trial=root/'trial';cases=root/'cases.json'
        write_json(cases,{'protocol_version':4,'ledger_baseline':612,'ledger_stop_at':625,'pair_max_calls':12,
            'prospective_max_calls':5,'pair_stop_at':624,'conditional_extra_calls':4,
            'conditional_goal_stop_at':629,'conditional_authorization':grant,'approval_record_path':str(approval),'model':'claude-opus-5-5','effort':'medium',
            'experiment_root':str(trial),'cases':[case,{**case,'case_id':'b','classification':'development_regression',
                                                    'order':['incremental','old']}]})
        return benchmark,roles,ledger,cases,trial,prior

    def native_factory(self,prior,*,mode=None):
        test=self
        class Native:
            def __init__(inner,ledger,arm):inner.ledger,inner.arm=ledger,arm
            def run(inner,*,workspace,prompt,role):
                cid=inner.ledger.reserve(role=role,model='fake',effort='medium',request_hash='0'*64,
                    artifact_directory=str(inner.arm/'native_calls'/role))
                if mode=='429':
                    inner.ledger.finish(cid,status='failed',wall_seconds=1,usage=None,
                        metadata={'failure_class':'provider_rate_limit'})
                    raise ProtocolError('Synthetic 429')
                inner.ledger.finish(cid,status='completed',wall_seconds=1,
                    usage={'input_tokens':1,'output_tokens':1,'cached_input_tokens':0,'cache_write_input_tokens':0},metadata={})
                assignment=read_json(workspace/'identity_assignment.json')
                test.assertEqual(set(assignment['tasks'][0]),{'task_id','task_type'})
                if role=='constructor':
                    shutil.copytree(prior,workspace/'output',dirs_exist_ok=True)
                    package=read_json(workspace/'output/package.json')
                    package['tasks'][0]['task_id']=assignment['tasks'][0]['task_id']
                    package['tasks'][0]['assets'][0]['sha256']='CONTROLLER_FILL'
                    package['tasks'][0]['input_contract']['files'][0]['sha256']='CONTROLLER_FILL'
                    write_json(workspace/'output/package.json',package)
                    if mode=='assignment':write_json(workspace/'identity_assignment.json',{})
                else:
                    c=read_json(workspace/'quality_contract.json');ids=list(c['public_inventory']);checks={}
                    for key in c['checks']:
                        checks[key]={'status':'clear','rationale':'Synthetic only','evidence':[{'surface_id':ids[0],
                            'locator':'fixture','observation':'Synthetic'}],**({'scope':'entire_bound_public_inventory'}
                            if key in ('identity','author_scale','target_implementation') else
                            {'scope':'selected_surfaces','inspected_surface_ids':ids})}
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
        return lambda role,ledger,arm:Native(ledger,arm)

    def test_freeze_run_both_arms_three_wrappers_sentinels(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));manifest=f.freeze(c,b,r,l)
            self.assertEqual(manifest['protocol_version'],4)
            ids=[]
            for arm in ('old','incremental'):
                result=f.run_arm(t,'a',arm,runner_factory=self.native_factory(p))
                self.assertEqual(result['status'],'completed',result.get('error'))
                self.assertEqual(result['cost']['calls'],3)
                self.assertEqual(result['classification'],'fresh_validation')
                ctor=t/'arms/a'/arm/'batch/j/constructor'
                original=read_json(ctor/'output/package.constructor_original.json')
                self.assertEqual(original['tasks'][0]['assets'][0]['sha256'],'CONTROLLER_FILL')
                filled=read_json(ctor/'output/package.json');ids.append(filled['tasks'][0]['task_id'])
                self.assertNotEqual(ids[-1],'private-task-Q9X')
                self.assertTrue((t/'arms/a'/arm/'adjudicator/identity_controller_validation.json').is_file())
                self.assertTrue((t/'arms/a'/arm/'adjudicator/quality_controller_validation.json').is_file())
            self.assertEqual(ids[0],ids[1]);self.assertEqual(read_json(l)['used_attempts'],618)
            with self.assertRaises(ProtocolError):f.run_arm(t,'a','old',runner_factory=self.native_factory(p))
            f.verify_execution(t)

    def test_map_tamper_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));f.freeze(c,b,r,l)
            write_json(Path(read_json(c)['cases'][0]['identity_map']['path']),{})
            with self.assertRaises(ProtocolError):f.run_arm(t,'a','old',runner_factory=self.native_factory(p))
            self.assertEqual(read_json(l)['used_attempts'],612)

    def test_assignment_mutation_preserved_failed_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));f.freeze(c,b,r,l)
            result=f.run_arm(t,'a','old',runner_factory=self.native_factory(p,mode='assignment'))
            self.assertEqual(result['status'],'failed_needs_attribution');self.assertEqual(result['cost']['calls'],1)
            with self.assertRaises(ProtocolError):f.run_arm(t,'a','old',runner_factory=self.native_factory(p))

    def test_new_429_stop_and_budget_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));f.freeze(c,b,r,l)
            result=f.run_arm(t,'a','old',runner_factory=self.native_factory(p,mode='429'))
            self.assertEqual(result['status'],'failed_needs_attribution');self.assertEqual(read_json(l)['used_attempts'],613)
            with self.assertRaises(ProtocolError):f.run_arm(t,'a','incremental',runner_factory=self.native_factory(p))
            case=read_json(c)
            for change in ({'ledger_baseline':613},{'ledger_stop_at':629},{'pair_max_calls':13},
                           {'prospective_max_calls':4},{'protocol_version':3}):
                with self.assertRaises(ProtocolError):f._validate_selection({**case,**change},612)

    def test_classification_required_and_map_must_bind_original_prior(self):
        for bad in ('classification','map_source'):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as tmp:
                b,r,l,c,t,p=self.fixture(Path(tmp));cases=read_json(c)
                if bad=='classification':cases['cases'][0]['classification']='new_dir_therefore_holdout'
                else:cases['cases'][0]['prior_batch']=str(Path(tmp)/'different_prior')
                write_json(c,cases)
                with self.assertRaises((ProtocolError,FileNotFoundError)):f.freeze(c,b,r,l)

    def gate_fixture(self,root):
        from mrhbench.material_adapter import compile_package
        from mrhbench.materials import export_task
        from mrhbench.artifact_policy import make_collection_policy
        b,r,l,c,t,p=self.fixture(root);f.freeze(c,b,r,l)
        for arm in ('old','incremental'):f.run_arm(t,'a',arm,runner_factory=self.native_factory(p))
        cases=read_json(c)
        write_json(t/'audits/independent.json',{'synthetic_review':True})
        gate={'case_id':'a','allow_next_case':True,'quality_passed':True,'reviewer':'synthetic',
            'findings':['Offline synthetic gate only'],'review_seconds':1,
            'result_hashes':{a:f.file_hash(t/'arms/a'/a/'result.json') for a in ('old','incremental')},
            'independent_evidence':[f.identity(t/'audits/independent.json')],
            'runtime_evidence':{},'identity_release_evidence':{},'release_review_evidence':{},
            'identity_release_review_passed':True}
        for arm in ('old','incremental'):
            package=t/'arms/a'/arm/'batch/j/constructor/output/package.json';obj=read_json(package)
            runtime={'status':'passed','synthetic':True,'arm':arm,'package_json_sha256':f.file_hash(package),
                     'package_digest':digest(obj),'output_dir':str(package.parent)}
            rp=t/'runtime'/arm/'record.json';write_json(rp,runtime);gate['runtime_evidence'][arm]=f.identity(rp)
            tid=obj['tasks'][0]['task_id'];stage=t/'releases'/arm;compiled=stage/'compiled'
            compile_package(package.parent,request={'sources':[]},destination=compiled,
                execution_budgets={tid:{'model_calls':3,'tool_calls':20,'wall_seconds':300}},
                image_id='sha256:'+'a'*64,public_rubrics={'EXP':{'version':'test'}},
                artifact_collections={tid:make_collection_policy(max_total_bytes=1024*1024,max_entries=100)})
            compiled_path=compiled/tid/'task.json';task=read_json(compiled_path)
            release=stage/'review_releases'/tid
            export_task(task,compiled/tid,release,audience='development_executor')
            scan=scan_release(release,cases['cases'][0]['identity_map'])
            row={'task_id':tid,'release_root':str(release),'task_json_sha256':f.file_hash(release/'task.json'),
                 'compiled_manifest_sha256':f.file_hash(compiled_path),'scan':scan}
            record=stage/'identity_release_record.json'
            write_json(record,{'schema_version':'identity-bound-release-staging-1','package_sha256':f.file_hash(package),
                'runtime_record_digest':digest(runtime),'releases':[row]})
            gate['identity_release_evidence'][arm]=f.identity(record)
            review=stage/'independent_release_review.json'
            write_json(review,{'schema_version':'independent-material-release-review-1','decision':'pass',
                'scope':'full_actual_published_surface','reviewer':'synthetic-independent','review_seconds':1,
                'findings':['Synthetic full view and asset inspection; not a scientific acceptance'],
                'case_id':'a','arm':arm,'independent_of_material_roles':True,'package':f.identity(package),
                'runtime':f.identity(rp),'release_record':f.identity(record),'arm_result_sha256':gate['result_hashes'][arm],
                'tasks':[{'task_id':tid,'compiled_manifest':f.identity(compiled_path),
                    'released_task':f.identity(release/'task.json'),
                    'asset_inventory_sha256':digest(read_json(release/'task.json')['asset_manifest']),
                    'binary_assets_reviewed':scan['unknown_binary_assets']}]})
            gate['release_review_evidence'][arm]=f.identity(review)
        write_json(t/'audits/a.json',gate)
        return t,cases,gate

    def test_second_pair_requires_bound_final_release(self):
        from copy import deepcopy
        with tempfile.TemporaryDirectory() as tmp:
            t,cases,gate=self.gate_fixture(Path(tmp))
            f.check_order(t,cases,'b','incremental')
            reviewpath=Path(gate['release_review_evidence']['old']['path']);original=read_json(reviewpath)
            for change in ({'decision':'pending'},{'decision':'fail'},{'scope':'candidate_only'},
                {'reviewer':''},{'findings':[]},{'review_seconds':True},{'review_seconds':float('inf')},
                {'tasks':[]},{'arm':'incremental'},{'schema_version':'unrelated-review'},
                {'tasks':[{**original['tasks'][0],'asset_inventory_sha256':'0'*64}]}):
                with self.subTest(change=change):
                    bad={**original,**change}
                    # Strict JSON writer correctly rejects infinity before publication.
                    if change.get('review_seconds')==float('inf'):
                        with self.assertRaises(ValueError):write_json(reviewpath,bad)
                        continue
                    write_json(reviewpath,bad);modified=deepcopy(gate)
                    modified['release_review_evidence']['old']=f.identity(reviewpath)
                    write_json(t/'audits/a.json',modified)
                    with self.assertRaises(ProtocolError):f.check_order(t,cases,'b','incremental')
            write_json(reviewpath,original);write_json(t/'audits/a.json',gate)
            f.check_order(t,cases,'b','incremental')

    def test_release_gate_rejects_omission_mutated_public_view_private_asset_and_wrong_runtime(self):
        from copy import deepcopy
        with tempfile.TemporaryDirectory() as tmp:
            t,cases,gate=self.gate_fixture(Path(tmp))
            first=cases['cases'][0]
            recordpath=Path(gate['identity_release_evidence']['old']['path']);record=read_json(recordpath)
            reviewpath=Path(gate['release_review_evidence']['old']['path']);review=read_json(reviewpath)
            runtimepath=Path(gate['runtime_evidence']['old']['path']);runtime=read_json(runtimepath)
            row=record['releases'][0];public=Path(row['release_root'])/'task.json'
            compiled=Path(review['tasks'][0]['compiled_manifest']['path'])
            candidate_asset=t/'arms/a/old/batch/j/constructor/output/assets/start.txt'
            files=[recordpath,reviewpath,runtimepath,public,compiled,candidate_asset]
            backup={p:p.read_bytes() for p in files}
            for mode in ('omit_asset','changed_prompt','private_asset','wrong_runtime_digest','stale_review_view','other_arm_review','other_arm_runtime','other_arm_release','candidate_asset_changed'):
                with self.subTest(mode=mode):
                    for p,data in backup.items():p.write_bytes(data)
                    rr=deepcopy(record);rv=deepcopy(review);rt=deepcopy(runtime)
                    view=read_json(public);manifest=read_json(compiled)
                    if mode=='omit_asset':view['asset_manifest']=[]
                    if mode=='changed_prompt':
                        manifest['public']['prompt']+=' New controller-added note.'
                        view['prompt']=manifest['public']['prompt']
                    if mode=='private_asset':
                        private=next(a for a in manifest['assets'] if a['visibility']=='private')
                        private['visibility']='public';manifest['public']['inputs'].append(private['asset_id'])
                    if mode=='wrong_runtime_digest':rt['package_digest']='0'*64
                    if mode=='candidate_asset_changed':candidate_asset.write_bytes(b'Changed after runtime')
                    if mode=='stale_review_view':rv['tasks'][0]['released_task']['sha256']='0'*64
                    if mode=='other_arm_review':rv['arm']='incremental'
                    if mode=='other_arm_runtime':rt['output_dir']=str(t/'arms/a/incremental/batch/j/constructor/output')
                    if mode=='other_arm_release':
                        other=read_json(Path(gate['identity_release_evidence']['incremental']['path']))
                        rr['releases'][0]['release_root']=other['releases'][0]['release_root']
                    write_json(compiled,manifest);write_json(public,view);write_json(runtimepath,rt)
                    rr['runtime_record_digest']=digest(rt)
                    rr['releases'][0]['compiled_manifest_sha256']=f.file_hash(compiled)
                    rr['releases'][0]['task_json_sha256']=f.file_hash(public)
                    # Omitted assets deliberately retain their files; strict inventory
                    # must reject instead of silently treating the release as empty.
                    if mode!='omit_asset':rr['releases'][0]['scan']=scan_release(public.parent,first['identity_map'])
                    write_json(recordpath,rr)
                    rv['runtime']=f.identity(runtimepath);rv['release_record']=f.identity(recordpath)
                    # Keep independent review's exact public/compiled identities
                    # unchanged, so controller edits cannot inherit review approval.
                    write_json(reviewpath,rv)
                    with self.assertRaises(ProtocolError):
                        f.validate_release_review(t,first,'old',f.identity(runtimepath),f.identity(recordpath),f.identity(reviewpath))

    def test_missing_prior_review_keeps_full_review_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp))
            (Path(tmp)/'prior/j/reviewer/review.json').unlink()
            f.freeze(c,b,r,l)
            for arm in ('old','incremental'):
                result=f.run_arm(t,'a',arm,runner_factory=self.native_factory(p))
                self.assertEqual(result['status'],'completed',result.get('error'))
            records=list((t/'arms/a/incremental/batch/j/reviewer/repair_context').rglob('*.json'))
            flags=[read_json(path) for path in records if isinstance(read_json(path),dict) and 'missing_prior_review' in read_json(path)]
            self.assertTrue(flags)
            self.assertTrue(flags[0]['missing_prior_review'])
            self.assertTrue(flags[0]['full_review_required'])
            self.assertIsNone(flags[0]['previous_review'])
            self.assertFalse((t/'arms/a/incremental/batch/j/reviewer/repair_context/previous_review').exists())
            self.assertFalse((Path(tmp)/'prior/j/reviewer/review.json').exists())
            validation=read_json(t/'arms/a/incremental/batch/j/reviewer/quality_controller_validation.json')
            self.assertTrue(validation['structural_contract_valid'])
            self.assertIn('not_established',validation['scientific_acceptance'])

    def test_pair_cannot_spend_conditionally_authorized_extra_calls(self):
        from mrhbench.bounded_ledger import BoundedCallLedger
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));f.freeze(c,b,r,l)
            for index in range(4):
                arm=t/'arms'/str(index)/'old'
                ledger=BoundedCallLedger(l,baseline=612,stop_at=624,experiment_root=t,arm_root=arm,arm_maximum=3)
                for _ in range(3):
                    cid=ledger.reserve(role='constructor',model='fake',effort='medium',request_hash='0'*64,
                        artifact_directory=str(arm/'native_calls'))
                    ledger.finish(cid,status='completed',wall_seconds=1,usage=None,metadata={})
            self.assertEqual(read_json(l)['used_attempts'],624)
            arm=t/'arms/extra/old'
            ledger=BoundedCallLedger(l,baseline=612,stop_at=624,experiment_root=t,arm_root=arm,arm_maximum=3)
            with self.assertRaises(ProtocolError):
                ledger.reserve(role='constructor',model='fake',effort='medium',request_hash='0'*64,
                    artifact_directory=str(arm/'native_calls'))
            self.assertEqual(read_json(l)['used_attempts'],624)

if __name__=='__main__':unittest.main()
