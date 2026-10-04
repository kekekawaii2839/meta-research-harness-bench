"""Offline resume amendment tests; no model sessions, no historical edits."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('resume_v3',ROOT/'scripts/active/resume_efficiency_v3_after_rate_limit.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from mrhbench.io import read_json,write_json,ProtocolError
from mrhbench.bounded_ledger import BoundedCallLedger

class ResumeTests(unittest.TestCase):
    def fixture(self,root):
        original=root/'original'; fresh=root/'fresh'; auth=root/'authorization.json'; ledger=root/'ledger.json'
        arm=original/'arms/exp_autonomy_repair/old'
        call={'id':609,'status':'failed','role':'constructor','metadata':{'failure_class':'provider_rate_limit'},
              'artifact_directory':str(arm/'native_calls/constructor/session')}
        attempts=[{'id':i,'status':'completed'} for i in range(1,609)]+[call]
        write_json(ledger,{'authorized_maximum':1668,'used_attempts':609,'attempts':attempts})
        write_json(arm/'result.json',{'status':'failed_needs_attribution','cost':{'call_ids':[609]},
                                    'batch':{'jobs':[{'job_id':'j'}]}})
        write_json(original/'audits/failure.json',{'independent_failure':True})
        write_json(original/'execution/snapshot/code.json',{'frozen':True})
        cases={'experiment_root':str(original),'ledger_baseline':608,'ledger_stop_at':625,'pair_max_calls':12,
               'prospective_max_calls':5,'cases':[{'case_id':'exp_autonomy_repair','job_id':'j','order':['old','incremental']}]}
        write_json(original/'execution/cases.json',cases)
        manifest={'ledger_path':str(ledger),'cases':f.engine.identity(original/'execution/cases.json')}
        write_json(original/'execution/manifest.json',manifest)
        write_json(auth,{**f.EXPECTED,'user_message':'额度应该恢复了，是每五小时有一个限额，到时间自动重置',
                        'new_experiment_root':str(fresh),'original_manifest':f.engine.identity(original/'execution/manifest.json'),
                        'failed_result':f.engine.identity(arm/'result.json'),
                        'independent_failure_audit':f.engine.identity(original/'audits/failure.json')})
        return original,fresh,auth,ledger,manifest,cases

    def test_prepare_zero_calls_original_unchanged_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            original,fresh,auth,ledger,manifest,cases=self.fixture(Path(tmp))
            before=f.tree(original); ledger_before=ledger.read_bytes()
            with patch.object(f,'VERIFY_ORIGINAL',return_value=(manifest,cases)):
                result=f.prepare(original,fresh,auth)
                m,c=f.verify_resume(fresh)
                self.assertEqual(c['ledger_baseline'],609)
                self.assertEqual(c['prospective_max_calls'],4)
                self.assertEqual(result['pair_stop_at'],621)
                with self.assertRaises(ProtocolError):f.prepare(original,fresh,auth)
            self.assertEqual(f.tree(original),before)
            self.assertEqual(ledger.read_bytes(),ledger_before)

    def test_unknown_failure_and_output_rejected(self):
        for alteration in ('unknown','reserved','output','otherarm','laterledger'):
            with self.subTest(alteration=alteration),tempfile.TemporaryDirectory() as tmp:
                original,fresh,auth,ledger,manifest,cases=self.fixture(Path(tmp))
                state=read_json(ledger)
                if alteration=='unknown':state['attempts'][-1]['metadata']['failure_class']='unknown'
                if alteration=='reserved':state['attempts'][-1]['status']='reserved'
                if alteration=='laterledger':
                    state['used_attempts']=610;state['attempts'].append({'id':610,'status':'completed'})
                if alteration=='output':write_json(original/'arms/exp_autonomy_repair/old/batch/j/constructor/output/package.json',{})
                if alteration=='otherarm':(original/'arms/exp_autonomy_repair/incremental').mkdir()
                write_json(ledger,state)
                with patch.object(f,'VERIFY_ORIGINAL',return_value=(manifest,cases)),self.assertRaises(ProtocolError):
                    f.prepare(original,fresh,auth)
                self.assertFalse(fresh.exists())

    def test_tamper_new_snapshot_cases_and_authorization(self):
        for alteration in ('snapshot','cases','auth','originaltrace','history'):
            with self.subTest(alteration=alteration),tempfile.TemporaryDirectory() as tmp:
                original,fresh,auth,ledger,manifest,cases=self.fixture(Path(tmp))
                with patch.object(f,'VERIFY_ORIGINAL',return_value=(manifest,cases)):
                    f.prepare(original,fresh,auth)
                    if alteration=='snapshot':write_json(fresh/'execution/snapshot/added.json',{})
                    if alteration=='cases':write_json(fresh/'execution/cases.json',{})
                    if alteration=='auth':write_json(auth,{})
                    if alteration=='originaltrace':write_json(original/'arms/exp_autonomy_repair/old/newtrace.json',{})
                    if alteration=='history':
                        state=read_json(ledger);state['attempts'][0]['changed']=True;write_json(ledger,state)
                    with self.assertRaises(ProtocolError):f.verify_resume(fresh)

    def test_new_429_stops_and_previous_609_not_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            original,fresh,auth,ledger,manifest,cases=self.fixture(Path(tmp))
            with patch.object(f,'VERIFY_ORIGINAL',return_value=(manifest,cases)):
                f.prepare(original,fresh,auth)
                state=read_json(ledger)
                state['attempts'].append({'id':610,'status':'failed','metadata':{'failure_class':'provider_rate_limit'}})
                state['used_attempts']=610;write_json(ledger,state)
                with self.assertRaisesRegex(ProtocolError,'New provider rate limit'):f.verify_resume(fresh)
                self.assertEqual(read_json(ledger)['attempts'][608]['status'],'failed')

    def test_paired_budget_stops_at_621(self):
        with tempfile.TemporaryDirectory() as tmp:
            original,fresh,auth,ledger,manifest,cases=self.fixture(Path(tmp))
            with patch.object(f,'VERIFY_ORIGINAL',return_value=(manifest,cases)):
                f.prepare(original,fresh,auth)
                _, adapted=f.verify_resume(fresh)
            bounded=BoundedCallLedger(ledger,baseline=adapted['ledger_baseline'],stop_at=621,
                experiment_root=fresh,arm_root=fresh/'arms/a/old')
            state=read_json(ledger)
            state['used_attempts']=621
            with self.assertRaises(ProtocolError):bounded._check_reservation(state,str(fresh/'arms/a/old/native_calls'))
            state['used_attempts']=620
            bounded._check_reservation(state,str(fresh/'arms/a/old/native_calls'))

    def test_run_restores_original_verifier_after_failure(self):
        old=f.engine.verify_execution
        with patch.object(f.engine,'run_arm',side_effect=ProtocolError('injected')):
            with self.assertRaises(ProtocolError):f.run(Path('unused'),'x','old')
        self.assertIs(f.engine.verify_execution,old)

    def test_real_prepare_resume_engine_quality_fake_three_calls(self):
        import shutil
        from test_factory_efficiency_v3 import DriverTests
        from test_material_pipeline_v2 import MaterialPipelineTests
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            benchmark,rolepath,ledger,casespath,original,ws=DriverTests().fixture(root)
            shutil.copytree(ROOT/'prompts',benchmark/'prompts',dirs_exist_ok=True)
            selection=read_json(casespath)
            selection['cases'][0]['case_id']='exp_autonomy_repair'
            selection['cases'][0]['notes_key']=None
            write_json(ws/'notes.json',['Synthetic repair notes'])
            resources=dict(cpus=1,memory_mb=128,disk_mb=128,pids_limit=32,wall_seconds=60)
            job=dict(schema_version='material-job-1',job_id='j',paper_id='p',requested_task_types=['EXP'],
                scope_request='Synthetic fixture',first_disclosure={},
                environment_candidate=dict(gpu=False,network='none',scientific_rationale='Fixture',**resources),
                sources=[dict(source_id='s',url='https://example.invalid/p',version='v1',local_path='source.txt',
                    sha256=f.engine.file_hash(ws/'source.txt'),role='paper_text')])
            write_json(ws/'job.json',job);write_json(casespath,selection)
            f.engine.freeze(casespath,benchmark,rolepath,ledger)
            original_arm=original/'arms/exp_autonomy_repair/old'
            write_json(original_arm/'result.json',{'status':'failed_needs_attribution','cost':{'call_ids':[609]},
                'batch':{'jobs':[{'job_id':'j'}]}})
            write_json(original/'audits/failure.json',{'fixture_only':True})
            state=read_json(ledger)
            failed={'id':609,'status':'failed','role':'constructor',
                'artifact_directory':str(original_arm/'native_calls/constructor/session'),
                'metadata':{'failure_class':'provider_rate_limit'}}
            state['attempts'].append(failed);state['used_attempts']=609;write_json(ledger,state)
            fresh=root/'resumed';auth=root/'resume_authorization.json'
            write_json(auth,{**f.EXPECTED,'user_message':'Synthetic explicit resume authorization for test only',
                'new_experiment_root':str(fresh),
                'original_manifest':f.engine.identity(original/'execution/manifest.json'),
                'failed_result':f.engine.identity(original_arm/'result.json'),
                'independent_failure_audit':f.engine.identity(original/'audits/failure.json')})
            before=f.tree(original)
            f.prepare(original,fresh,auth)
            def relative_bytes(path):
                return {p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()}
            self.assertEqual(relative_bytes(original/'execution/snapshot'),relative_bytes(fresh/'execution/snapshot'))
            observed=[];policy_paths=[];template_paths=[]
            quality_cls=f.engine.QualityBoundRunner
            batch_impl=f.engine.run_batch
            def quality_factory(inner,**kwargs):
                policy_paths.append(kwargs['policy_path'])
                return quality_cls(inner,**kwargs)
            def batch_spy(*args,**kwargs):
                template_paths.append(kwargs['templates'])
                return batch_impl(*args,**kwargs)
            class NativeFake:
                def __init__(inner,led,arm):inner.ledger,inner.arm=led,arm
                def run(inner,*,workspace,prompt,role):
                    self.assertTrue(Path(workspace).resolve().is_relative_to(fresh))
                    cid=inner.ledger.reserve(role=role,model='fake',effort='medium',request_hash='0'*64,
                        artifact_directory=str(inner.arm/'native_calls'/role))
                    inner.ledger.finish(cid,status='completed',wall_seconds=1,
                        usage={'input_tokens':1,'cached_input_tokens':0,'cache_write_input_tokens':0,'output_tokens':1},metadata={})
                    observed.append((role,cid))
                    if role=='constructor':
                        out=workspace/'output'
                        package=MaterialPipelineTests()._valid_private_package(out)
                        package['facts'][0]['evidence'][0]['source_sha256']=f.engine.file_hash(ws/'source.txt')
                        write_json(out/'package.json',package)
                    else:
                        contract=read_json(workspace/'quality_contract.json');ids=list(contract['public_inventory'])
                        checks={}
                        for key in contract['checks']:
                            checks[key]={'status':'clear','rationale':'Synthetic; runtime remains pending',
                                'evidence':[{'surface_id':ids[0],'locator':'fixture','observation':'Synthetic only'}],
                                **({'scope':'entire_bound_public_inventory'} if key in ('identity','author_scale','target_implementation')
                                   else {'scope':'selected_surfaces','inspected_surface_ids':ids})}
                        write_json(workspace/'quality_coverage.json',{'contract_sha256':contract['contract_sha256'],
                            'policy_sha256':contract['policy_sha256'],'checks':checks})
                        if role=='material_reviewer':
                            write_json(workspace/'review.json',{'schema_version':'material-review-1','paper_id':'p',
                                'decision':'pass_with_pending_runtime','findings':[]})
                        else:
                            self.assertEqual((workspace/'policy.md').read_bytes(),(workspace/'quality_policy.md').read_bytes())
                            write_json(workspace/'review_adjudication.json',{'schema_version':'factory-review-adjudication-1',
                                'project_id':'p','round':2,'action':'pass','finding_decisions':[{'finding_index':None,
                                'decision':'accept','severity':'minor','repair_note':None,'rationale':'Synthetic J2/F4',
                                'policy_rules':['J2','F4']}],'repair_notes':[],'drop_reason':None,'excluded_task_ids':[]})
                    return {'call_id':cid}
            with patch.object(f.engine,'QualityBoundRunner',side_effect=quality_factory),patch.object(f.engine,'run_batch',side_effect=batch_spy):
                result=f.run(fresh,'exp_autonomy_repair','old',runner_factory=lambda role,led,arm:NativeFake(led,arm))
            self.assertEqual(result['status'],'completed',result.get('error'))
            self.assertEqual(observed,[('constructor',610),('material_reviewer',611),('adjudicator',612)])
            self.assertEqual(result['cost']['calls'],3)
            self.assertEqual(template_paths,[fresh/'execution/snapshot/prompts'])
            self.assertEqual(policy_paths,[fresh/'execution/snapshot/prompts/factory_v4/policy.md']*3)
            self.assertEqual(read_json(ledger)['attempts'][608],failed)
            self.assertEqual(f.tree(original),before)
            f.verify_resume(fresh)
            with self.assertRaises(ProtocolError):
                f.run(fresh,'exp_autonomy_repair','old',runner_factory=lambda *args:self.fail('No repeat'))

if __name__=='__main__':unittest.main()
