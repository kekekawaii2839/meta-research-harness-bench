"""Retain invalid paid review; one separately authorized diagnostic fake call."""
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mrhbench import material_adjudication_continuation as m
from mrhbench import factory_efficiency_regression as engine
from mrhbench.io import read_json,write_json,ProtocolError,digest

class ContinuationTests(unittest.TestCase):
    def fixture(self,root):
        from test_factory_efficiency_regression import RegressionTests
        helper=RegressionTests();b,r,l,c,t,p=helper.fixture(root);engine.freeze(c,b,r,l)
        base=helper.native(p)
        class Conflict:
            def __init__(self,inner):self.inner=inner
            def run(self,*,workspace,prompt,role):
                result=self.inner.run(workspace=workspace,prompt=prompt,role=role)
                if role=='material_reviewer':
                    path=workspace/'quality_coverage.json';coverage=read_json(path)
                    coverage['checks']['core_science']['status']='issue';write_json(path,coverage)
                return result
        row=engine.run_arm(t,'a','old',runner_factory=lambda role,led,arm:Conflict(base(role,led,arm)))
        self.assertEqual(row['cost']['call_ids'],[616,617]);self.assertEqual(row['status'],'failed_needs_attribution')
        old=t/'arms/a/old';reviewer=old/'batch/j/reviewer';ctor=old/'batch/j/constructor/output/package.json'
        audit=t/'audits/conflict.json'
        write_json(audit,{'schema_version':'review-conflict-independent-audit-1','decision':'eligible_for_explicit_adjudication_only',
            'original_failed_result':m.identity(old/'result.json'),'original_review':m.identity(reviewer/'review.json'),
            'original_coverage':m.identity(reviewer/'quality_coverage.json'),'quality_contract':m.identity(reviewer/'quality_contract.json'),
            'blocking_findings':[],'scientific_acceptance':False,
            'evidence_bindings':[m.identity(p) for p in old.rglob('*') if p.is_file()]})
        science=t/'audits/science.json';write_json(science,{'synthetic_independent_science':True})
        runtime=t/'audits/runtime.json';write_json(runtime,{'status':'passed','package_json_sha256':m.file_hash(ctor),
            'package_digest':digest(read_json(ctor)),'output_dir':str(ctor.parent)})
        release=t/'audits/release.json';write_json(release,{'package_sha256':m.file_hash(ctor),
            'runtime_record_digest':digest(read_json(runtime))})
        auth=t/'audits/authorization.json';write_json(auth,{'schema_version':'material-adjudication-continuation-authorization-1',
            'decision':'allow_adjudication_only','case_id':'a','arm':'old','ledger_baseline':615,'ledger_current':617,
            'phase_stop_at':621,'max_new_calls':1,'original_failed_result':m.identity(old/'result.json'),
            'independent_conflict_audit':m.identity(audit),'science_review':m.identity(science),'runtime_record':m.identity(runtime),
            'release_record':m.identity(release),'goal_authorization':read_json(c)['goal_authorization']})
        return t,t/'continuations/diagnostic',auth,old,reviewer,base,l

    def test_paid_issue_retained_one_fresh_adjudication_three_wrappers(self):
        with tempfile.TemporaryDirectory() as tmp:
            t,d,a,old,reviewer,base,l=self.fixture(Path(tmp));before=m._tree(old)
            m.prepare(t,d,a)
            testcase=self
            class Adjud:
                def __init__(self,inner):self.inner=inner
                def run(self,*,workspace,prompt,role):
                    testcase.assertEqual(role,'adjudicator')
                    testcase.assertEqual(read_json(workspace/'original_reviewer_quality_coverage.json')['checks']['core_science']['status'],'issue')
                    testcase.assertFalse(read_json(workspace/'original_review_conflict.json')['raw_review_is_valid_acceptance'])
                    testcase.assertEqual(read_json(workspace/'review.json')['decision'],'pass_with_pending_runtime')
                    return self.inner.run(workspace=workspace,prompt=prompt,role=role)
            out=m.run(d,runner_factory=lambda ledger,dest:Adjud(base('adjudicator',ledger,dest)))
            self.assertEqual(out['status'],'completed_diagnostic_adjudication_pending_independent_audit',out.get('error'))
            self.assertEqual(out['new_call_cost']['call_ids'],[618]);self.assertEqual(out['paid_evidence_total_cost']['call_ids'],[616,617,618])
            self.assertEqual(m._tree(old),before)
            self.assertEqual(read_json(old/'result.json')['status'],'failed_needs_attribution')
            self.assertEqual(read_json(reviewer/'quality_coverage.json')['checks']['core_science']['status'],'issue')
            for name in ('identity_controller_validation.json','quality_controller_validation.json','paged_navigation_receipt.json'):
                self.assertTrue((d/'adjudicator'/name).exists())
            with self.assertRaises(ProtocolError):m.run(d,runner_factory=lambda *a:self.fail('No retry'))

    def test_adjudicator_unresolved_issue_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            t,d,a,old,reviewer,base,l=self.fixture(Path(tmp));m.prepare(t,d,a)
            class Bad:
                def __init__(self,inner):self.inner=inner
                def run(self,*,workspace,prompt,role):
                    result=self.inner.run(workspace=workspace,prompt=prompt,role=role)
                    path=workspace/'quality_coverage.json';coverage=read_json(path)
                    coverage['checks']['core_science']['status']='issue';write_json(path,coverage)
                    return result
            out=m.run(d,runner_factory=lambda led,dest:Bad(base('adjudicator',led,dest)))
            self.assertEqual(out['status'],'failed_needs_attribution');self.assertIn(m.ERROR,out['error']['message'])
            self.assertEqual(out['new_call_cost']['call_ids'],[618])

    def test_tampered_original_evidence_and_nonmatching_conflict_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            t,d,a,old,reviewer,base,l=self.fixture(Path(tmp))
            original=(reviewer/'quality_coverage.json').read_bytes()
            coverage=read_json(reviewer/'quality_coverage.json');coverage['checks']['core_science']['status']='unknown'
            write_json(reviewer/'quality_coverage.json',coverage)
            with self.assertRaises(ProtocolError):m.prepare(t,d,a)
            (reviewer/'quality_coverage.json').write_bytes(original);m.prepare(t,d,a)
            (reviewer/'sources/000-paper.txt').write_text('Changed evidence')
            with self.assertRaises(ProtocolError):m.run(d,runner_factory=lambda *a:self.fail('No call'))
            self.assertEqual(read_json(l)['used_attempts'],617)

    def test_new429_terminal_and_exact_one_call_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            t,d,a,old,reviewer,base,l=self.fixture(Path(tmp));m.prepare(t,d,a)
            class RateLimit:
                def __init__(self,ledger,dest):self.ledger,self.dest=ledger,dest
                def run(self,**kwargs):
                    cid=self.ledger.reserve(role='adjudicator',model='fake',effort='medium',request_hash='0'*64,
                        artifact_directory=str(self.dest/'native_calls'))
                    self.ledger.finish(cid,status='failed',wall_seconds=1,usage=None,metadata={'failure_class':'provider_rate_limit'})
                    with ContinuationTests().assertRaises(ProtocolError):
                        self.ledger.reserve(role='adjudicator',model='fake',effort='medium',request_hash='0'*64,
                            artifact_directory=str(self.dest/'native_calls'))
                    raise ProtocolError('Synthetic429')
            out=m.run(d,runner_factory=lambda led,dest:RateLimit(led,dest))
            self.assertEqual(out['status'],'failed_needs_attribution');self.assertEqual(read_json(l)['used_attempts'],618)
            with self.assertRaises(ProtocolError):m.run(d,runner_factory=lambda *a:self.fail('No retry'))

    def test_conflict_integrity_checked_on_exception_without_masking_primary(self):
        with tempfile.TemporaryDirectory() as tmp:
            t,d,a,old,reviewer,base,l=self.fixture(Path(tmp));m.prepare(t,d,a)
            class Broken:
                def __init__(self,inner):self.inner=inner
                def run(self,*,workspace,prompt,role):
                    self.inner.run(workspace=workspace,prompt=prompt,role=role)
                    write_json(workspace/'original_reviewer_quality_coverage.json',{})
                    raise ProtocolError('Original diagnostic quality failure')
            result=m.run(d,runner_factory=lambda led,dest:Broken(base('adjudicator',led,dest)))
            self.assertEqual(result['error']['message'],'Original diagnostic quality failure')
            self.assertEqual(result['original_conflict_input_integrity']['status'],'failed')
            self.assertEqual(result['new_call_cost']['call_ids'],[618])
            self.assertTrue(result['original_arm_unchanged'])

    def test_unreadable_original_tree_keeps_terminal_receipt_and_primary_error(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            t,d,a,old,reviewer,base,l=self.fixture(Path(tmp));m.prepare(t,d,a)
            real_tree=m._tree
            def fail_after_call(path):
                if Path(path)==old and (d/'adjudicator').exists():raise ProtocolError('Synthetic unreadable old tree')
                return real_tree(path)
            class Failing:
                def __init__(self,inner):self.inner=inner
                def run(self,**kwargs):
                    self.inner.run(**kwargs)
                    raise ProtocolError('Primary native diagnostic failure')
            with patch.object(m,'_tree',side_effect=fail_after_call):
                result=m.run(d,runner_factory=lambda led,dest:Failing(base('adjudicator',led,dest)))
            self.assertEqual(result['error']['message'],'Primary native diagnostic failure')
            self.assertIsNone(result['original_arm_unchanged'])
            self.assertEqual(result['status'],'failed_needs_attribution')
            self.assertEqual(read_json(d/'continuation_result.json')['original_arm_integrity_error']['message'],'Synthetic unreadable old tree')

if __name__=='__main__':unittest.main()
