"""Six-call regression driver offline wiring; fake native only."""
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mrhbench import factory_efficiency_regression as f
from mrhbench.io import ProtocolError,read_json,write_json

class RegressionTests(unittest.TestCase):
    def fixture(self,root):
        import test_factory_efficiency_v4 as fixtures
        b,r,l,c,t,p=fixtures.V4Tests().fixture(root)
        ledger=read_json(l);ledger['attempts'] += [{'id':i,'status':'completed'} for i in (613,614,615)]
        ledger['used_attempts']=615;write_json(l,ledger)
        cases=read_json(c);case=cases['cases'][0]
        case.update(classification='development_regression',round_no=3)
        goal=root/'goal.json';write_json(goal,{'schema_version':'goal-call-authorization-1',
            'goal_absolute_stop_at':700,'observed_baseline':615,'automatic_retry':False,'first_429_stops_batch':True,
            'first_phase':{'maximum_calls':6,'absolute_stop_at':621},'user_answer':'Synthetic budget700'})
        phase=root/'phase.json';write_json(phase,{'authorized_to_freeze':True,'ledger_baseline':615,
            'phase_stop_at':621,'phase_max_calls':6,'classification':'development_regression','goal_authorization':f.identity(goal)})
        history=root/'history';history.mkdir();(history/'614.json').write_bytes((root/'prior/j/reviewer/review.json').read_bytes())
        write_json(history/'615.json',{'round':2,'action':'drop'})
        write_json(history/'result.json',{'cost':{'call_ids':[613,614,615]}})
        selection={'protocol_version':'regression-1','ledger_baseline':615,'phase_max_calls':6,'phase_stop_at':621,
            'goal_stop_at':700,'model':'claude-opus-5-5','effort':'medium','experiment_root':str(t),'cases':[case],
            'goal_authorization':f.identity(goal),'phase_authorization':f.identity(phase),
            'failure_evidence':{'review_614':f.identity(history/'614.json'),'adjudication_615':f.identity(history/'615.json'),
                                'failed_result_615':f.identity(history/'result.json')}}
        write_json(c,selection)
        return b,r,l,c,t,p

    def native(self,prior,*,action='pass',mode=None):
        import test_factory_efficiency_v4 as fixtures
        base=fixtures.V4Tests().native_factory(prior,mode=mode)
        test=self
        class Native:
            def __init__(inner,role,ledger,arm):inner.base=base(role,ledger,arm)
            def run(inner,*,workspace,prompt,role):
                test.assertTrue((workspace/'paged_source_navigation/catalog.json').is_file())
                test.assertIn('paged_source_navigation/catalog.json',prompt)
                result=inner.base.run(workspace=workspace,prompt=prompt,role=role)
                if role=='adjudicator':
                    # Fake native authors the requested round3 terminal answer.
                    path=workspace/'review_adjudication.json';out=read_json(path)
                    out['round']=3;out['action']=action
                    if action=='drop':out['drop_reason']='Synthetic unresolved major defect'
                    write_json(path,out)
                if mode=='navigation_mutation':write_json(workspace/'paged_source_navigation/catalog.json',{})
                return result
        return lambda role,ledger,arm:Native(role,ledger,arm)

    def test_real_old_incremental_three_roles_sentinels_paging_and_immutability(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));source_before={x:x.read_bytes() for x in p.rglob('*') if x.is_file()}
            original_drop=Path(tmp)/'history/615.json';before=original_drop.read_bytes()
            f.freeze(c,b,r,l);f.verify_execution(t)
            for arm in ('old','incremental'):
                result=f.run_arm(t,'a',arm,runner_factory=self.native(p))
                self.assertEqual(result['status'],'completed',result.get('error'))
                self.assertEqual(result['cost']['calls'],3)
                self.assertEqual(result['classification'],'development_regression')
                self.assertEqual(result['adjudication']['decision']['round'],3)
                ctor=t/'arms/a'/arm/'batch/j/constructor'
                self.assertEqual(read_json(ctor/'output/package.constructor_original.json')['tasks'][0]['assets'][0]['sha256'],'CONTROLLER_FILL')
                for ws in (ctor,t/'arms/a'/arm/'batch/j/reviewer',t/'arms/a'/arm/'adjudicator'):
                    self.assertTrue((ws/'paged_navigation_receipt.json').is_file())
                    self.assertTrue((ws/'identity_controller_validation.json').is_file())
            self.assertEqual(read_json(l)['used_attempts'],621)
            self.assertEqual(original_drop.read_bytes(),before)
            self.assertEqual({x:x.read_bytes() for x in p.rglob('*') if x.is_file()},source_before)
            f.verify_execution(t)
            with self.assertRaises(ProtocolError):f.run_arm(t,'a','old',runner_factory=self.native(p))

    def test_old_drop_blocks_incremental_without_spending(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));f.freeze(c,b,r,l)
            row=f.run_arm(t,'a','old',runner_factory=self.native(p,action='drop'))
            self.assertEqual(row['status'],'completed');self.assertEqual(row['adjudication']['decision']['action'],'drop')
            with self.assertRaisesRegex(ProtocolError,'drop prior arm stops'):
                f.run_arm(t,'a','incremental',runner_factory=self.native(p))
            self.assertEqual(read_json(l)['used_attempts'],618)

    def test_new_429_and_navigation_tamper_stop(self):
        for mode in ('429','navigation_mutation'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                b,r,l,c,t,p=self.fixture(Path(tmp));f.freeze(c,b,r,l)
                row=f.run_arm(t,'a','old',runner_factory=self.native(p,mode=mode))
                self.assertEqual(row['status'],'failed_needs_attribution');self.assertEqual(row['cost']['calls'],1)
                with self.assertRaises(ProtocolError):f.run_arm(t,'a','incremental',runner_factory=self.native(p))
                self.assertEqual(read_json(l)['used_attempts'],616)

    def test_exact_phase_budget_and_failure_inputs_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,r,l,c,t,p=self.fixture(Path(tmp));cases=read_json(c)
            for change in ({'ledger_baseline':612},{'phase_max_calls':7},{'phase_stop_at':700},{'goal_stop_at':701}):
                with self.assertRaises(ProtocolError):f._validate_selection({**cases,**change},615)
            bad=dict(cases);bad['cases']=[{**cases['cases'][0],'classification':'fresh_validation'}]
            with self.assertRaises(ProtocolError):f._validate_selection(bad,615)
            original_review=Path(tmp)/'prior/j/reviewer/review.json'
            prior_bytes=original_review.read_bytes()
            write_json(original_review,{'different_review':True})
            with self.assertRaises(ProtocolError):f._validate_selection(cases,615)
            original_review.write_bytes(prior_bytes)
            f.freeze(c,b,r,l)
            write_json(Path(cases['failure_evidence']['adjudication_615']['path']),{'round':2,'action':'pass'})
            with self.assertRaises(ProtocolError):f.verify_execution(t)
            self.assertEqual(read_json(l)['used_attempts'],615)

if __name__=='__main__':unittest.main()
