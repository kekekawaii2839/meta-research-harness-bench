"""v5 real controller wiring with fake native only; no scientific acceptance."""
from pathlib import Path
import tempfile
import json
import unittest
from copy import deepcopy
from mrhbench import factory_efficiency_v5 as f
from mrhbench.io import read_json, write_json, ProtocolError, digest
from mrhbench.material_public_identity import scan_release, allocate_map
from mrhbench.material_adapter import compile_package
from mrhbench.materials import export_task
from mrhbench.artifact_policy import make_collection_policy
from mrhbench.material_decision_guidance import DECISION_GUIDANCE
from mrhbench.evidence_read_batching import EVIDENCE_READ_BATCHING_GUIDANCE
import test_factory_efficiency_v4 as fixtures

class V5Tests(unittest.TestCase):
    def fixture(self, root):
        b,r,l,c,t,p=fixtures.V4Tests().fixture(root)
        ledger=read_json(l);ledger['attempts'] += [{'id':i,'status':'completed'} for i in range(613,619)]
        ledger['used_attempts']=618;write_json(l,ledger)
        case=read_json(c)['cases'][0];case['order']=['incremental','old']
        # Same minimal asset fixture, retyped before map allocation for WC-only protocol.
        package=read_json(p/'package.json')
        coverage=deepcopy(package['coverage'])
        package=json.loads(json.dumps(package).replace('"EXP"','"WRITE_CONTENT"'))
        package['coverage']=coverage
        for row in package['coverage']:
            if row['task_type']=='EXP':row['task_type']='WRITE_CONTENT'
            elif row['task_type']=='WRITE_CONTENT':row['task_type']='EXP'
        write_json(p/'package.json',package)
        case['identity_map']=allocate_map(p,root/'private/wc-map.json')
        job=read_json(root/'job.json');job['requested_task_types']=['WRITE_CONTENT'];write_json(root/'job.json',job)
        goal=root/'goal.json';write_json(goal,{'schema_version':'goal-call-authorization-1',
            'goal_absolute_stop_at':700,'automatic_retry':False,'first_429_stops_batch':True,'user_answer':'Synthetic700'})
        phase=root/'phase.json';write_json(phase,{'protocol_version':5,'authorized_to_freeze':True,
            'ledger_baseline':618,'phase_stop_at':624,'phase_max_calls':6,'classification':'fresh_validation',
            'goal_authorization':f.identity(goal),'case_id':'a','job_id':'j','order':case['order']})
        write_json(c,{'protocol_version':5,'ledger_baseline':618,'phase_max_calls':6,'phase_stop_at':624,
            'goal_stop_at':700,'model':'claude-opus-5-5','effort':'medium','experiment_root':str(t),
            'cases':[case],'goal_authorization':f.identity(goal),'phase_authorization':f.identity(phase)})
        return b,r,l,c,t,p

    def native(self, prior, mode=None):
        base=fixtures.V4Tests().native_factory(prior,mode=mode)
        test=self
        class Native:
            def __init__(inner,role,ledger,arm):inner.base=base(role,ledger,arm);inner.arm=arm
            def run(inner,*,workspace,prompt,role):
                test.assertTrue((workspace/'paged_source_navigation/catalog.json').is_file())
                test.assertEqual(DECISION_GUIDANCE in prompt,role!='constructor')
                test.assertEqual(EVIDENCE_READ_BATCHING_GUIDANCE in prompt,
                                 role!='constructor' and inner.arm.name=='incremental')
                result=inner.base.run(workspace=workspace,prompt=prompt,role=role)
                if role=='adjudicator' and mode=='drop':
                    path=workspace/'review_adjudication.json';obj=read_json(path)
                    obj.update(action='drop',drop_reason='Synthetic unresolved issue');write_json(path,obj)
                return result
        return lambda role,ledger,arm:Native(role,ledger,arm)

    def gate(self,t,cases):
        gate={'result_hashes':{'incremental':f.file_hash(t/'arms/a/incremental/result.json')},
              'runtime_evidence':{},'identity_release_evidence':{},'release_review_evidence':{}}
        for arm in ('incremental',):
            package=t/'arms/a'/arm/'batch/j/constructor/output/package.json';obj=read_json(package)
            runtime={'status':'passed','synthetic':True,'arm':arm,'package_json_sha256':f.file_hash(package),
                     'package_digest':digest(obj),'output_dir':str(package.parent)}
            rp=t/'runtime'/arm/'record.json';write_json(rp,runtime);gate['runtime_evidence'][arm]=f.identity(rp)
            tid=obj['tasks'][0]['task_id'];stage=t/'releases'/arm;compiled=stage/'compiled'
            compile_package(package.parent,request={'sources':[]},destination=compiled,
                execution_budgets={tid:{'model_calls':3,'tool_calls':20,'wall_seconds':300}},
                image_id='sha256:'+'a'*64,public_rubrics={'WRITE_CONTENT':{'version':'test'}},
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
        result=t/'arms/a/incremental/result.json'
        science=t/'audits/science.json'
        case=cases['cases'][0]
        write_json(science,{'schema_version':'independent-material-science-review-1','decision':'pass',
            'case_id':'a','arm':'incremental','scope':'full_candidate_and_necessary_original_sources',
            'package':f.identity(package),'arm_result':f.identity(result),'release_record':f.identity(record),
            'independent_of_material_roles':True,'reviewer':'synthetic','findings':['Fixture only'],
            'blocking_findings':[],'evidence_bindings':[f.identity(package),f.identity(Path(case['workspace'])/'paper.txt')]})
        gate={'schema_version':'factory-efficiency-v5-arm-gate-1','case_id':'a','arm':'incremental',
            'allow_next_arm':True,'quality_passed':True,'result':f.identity(result),'reviewer':'synthetic',
            'findings':['Synthetic gate only'],'review_seconds':1,'science_review':f.identity(science),
            'runtime_record':gate['runtime_evidence']['incremental'],
            'release_record':gate['identity_release_evidence']['incremental'],
            'release_review':gate['release_review_evidence']['incremental']}
        write_json(t/'audits/a.incremental_gate.json',gate)
        return gate

    def test_full_native_chain_sentinels_gate_and_two_arms(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));before={x:x.read_bytes() for x in p.rglob('*') if x.is_file()}
            f.freeze(c,b,r,l)
            row=f.run_arm(t,'a','incremental',runner_factory=self.native(p))
            self.assertEqual(row['status'],'completed',row.get('error'));self.assertEqual(row['cost']['calls'],3)
            with self.assertRaises(FileNotFoundError):f.run_arm(t,'a','old',runner_factory=self.native(p))
            self.assertEqual(read_json(l)['used_attempts'],621)
            self.gate(t,read_json(c))
            row=f.run_arm(t,'a','old',runner_factory=self.native(p))
            self.assertEqual(row['status'],'completed',row.get('error'));self.assertEqual(row['cost']['calls'],3)
            self.assertEqual(read_json(l)['used_attempts'],624)
            for arm in ('incremental','old'):
                ctor=t/'arms/a'/arm/'batch/j/constructor'
                self.assertEqual(read_json(ctor/'output/package.constructor_original.json')['tasks'][0]['assets'][0]['sha256'],'CONTROLLER_FILL')
                for ws in (ctor,t/'arms/a'/arm/'batch/j/reviewer',t/'arms/a'/arm/'adjudicator'):
                    self.assertTrue((ws/'identity_controller_validation.json').is_file())
                    self.assertTrue((ws/'paged_navigation_receipt.json').is_file())
            self.assertEqual({x:x.read_bytes() for x in p.rglob('*') if x.is_file()},before)
            with self.assertRaises(ProtocolError):f.run_arm(t,'a','incremental',runner_factory=self.native(p))
            f.verify_execution(t)

    def test_gate_rejects_pending_or_unbound_science_and_actual_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));f.freeze(c,b,r,l)
            f.run_arm(t,'a','incremental',runner_factory=self.native(p));cases=read_json(c);gate=self.gate(t,cases)
            f.check_order(t,cases,'a','old')
            for key,change in [('science_review',{'decision':'pending'}),('science_review',{'evidence_bindings':[]}),
                ('science_review',{'release_record':{}}),('science_review',{'arm_result':{}}),
                ('release_review',{'tasks':[]}),('release_review',{'scope':'candidate_only'}),
                ('runtime_record',{'package_digest':'0'*64}),('release_record',{'releases':[]})]:
                path=Path(gate[key]['path']);original=path.read_bytes()
                write_json(path,{**read_json(path),**change});bad=deepcopy(gate);bad[key]=f.identity(path)
                write_json(t/'audits/a.incremental_gate.json',bad)
                with self.assertRaises(ProtocolError):f.check_order(t,cases,'a','old')
                path.write_bytes(original)
            write_json(t/'audits/a.incremental_gate.json',gate)
            f.check_order(t,cases,'a','old');self.assertEqual(read_json(l)['used_attempts'],621)

    def test_drop_429_and_assignment_tamper_stop(self):
        for mode in ('drop','429','assignment'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                b,r,l,c,t,p=self.fixture(Path(tmp));f.freeze(c,b,r,l)
                row=f.run_arm(t,'a','incremental',runner_factory=self.native(p,mode))
                self.assertEqual(row['cost']['calls'],3 if mode=='drop' else 1)
                with self.assertRaises(ProtocolError):f.run_arm(t,'a','old',runner_factory=self.native(p))

    def test_non_wc_selection_or_incorrect_declared_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));cases=read_json(c)
            job=Path(tmp)/'job.json';original=read_json(job)
            for change in ({'requested_task_types':['EXP']},
                           {'sources':[{**original['sources'][0],'sha256':'0'*64}]}):
                write_json(job,{**original,**change})
                with self.assertRaises(ProtocolError):f._validate_selection(cases,618)
            write_json(job,original);f._validate_selection(cases,618)

    def test_exact_budget_authority_source_and_snapshot_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));cases=read_json(c)
            for change in ({'ledger_baseline':619},{'phase_max_calls':7},{'phase_stop_at':700},{'goal_stop_at':701}):
                with self.assertRaises(ProtocolError):f._validate_selection({**cases,**change},618)
            f.freeze(c,b,r,l)
            for path in (Path(tmp)/'paper.txt',Path(cases['phase_authorization']['path']),t/'execution/snapshot/mrhbench/fixture.py'):
                before=path.read_bytes();path.write_bytes(before+b'changed')
                with self.assertRaises(ProtocolError):f.verify_execution(t)
                path.write_bytes(before)
            f.verify_execution(t);self.assertEqual(read_json(l)['used_attempts'],618)

if __name__=='__main__':unittest.main()
