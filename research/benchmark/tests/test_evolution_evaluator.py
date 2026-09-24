import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.evolution_evaluator import StageEvaluationAdapter,ReadOnlyReviewResolver,manifest,review_template
from mrhbench.io import ProtocolError,digest,file_hash,read_json,write_json
from mrhbench.judging import EvidenceSession
from mrhbench.judge_runner import evidence_record
from mrhbench.materials import TASK_GATES,export_task,load_task
from mrhbench.scoring import DIMENSIONS


class EvaluationAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.calls=[]
        p=self.root/'package';p.mkdir();(p/'public.txt').write_text('public input')
        self.task={'schema_version':'0.1','task_id':'toy','task_type':'EXP','paper_id':'paper',
            'split':'development','public':{'task_id':'toy','task_type':'EXP','prompt':'Synthetic fixture, not science.',
            'inputs':['input'],'output_contract':{},'resources':{},'tools':[],'public_rubric':{}},
            'private':{},'assets':[{'asset_id':'input','path':'public.txt','sha256':file_hash(p/'public.txt'),'visibility':'public'}],
            'gates':{g:{'status':'pending','evidence':'fixture'} for g in TASK_GATES}}
        write_json(p/'task.json',self.task)
        h=self.root/'harness';h.mkdir();(h/'harness.py').write_text('SYNTHETIC=True')
        self.request={'development':True,'identity':{'task_id':'toy','task_type':'EXP','paper_id':'paper','split':'search'},
            'version_id':'H0','harness_directory':str(h),'harness_hash':digest(manifest(h)),
            'package':str(p),'package_hash':digest(manifest(p)),'output_directory':str(self.root/'run')}
        self.reviewdir=self.root/'reviews';self.resolver=ReadOnlyReviewResolver(self.reviewdir)

    def fake_stage(self,**kw):
        self.calls.append(kw);out=Path(kw['output']);out.mkdir()
        export_task(load_task(Path(kw['package'])/'task.json'),Path(kw['package']),out/'public',audience='development_executor')
        view=read_json(out/'public/task.json')
        write_json(out/'execution/invocation.json',{'task_sha256':file_hash(out/'public/task.json'),'harness_sha256':file_hash(Path(kw['harness']))})
        write_json(out/'execution/run.json',{'formal':False,'status':'completed_structural_development_check'})
        write_json(out/'execution/submission.json',{'status':'completed','content':{'synthetic':True}})
        records=[evidence_record('task','task',json.dumps(view)),evidence_record('public-check','program_check','Public structural check'),
                 evidence_record('secret','program_check','PRIVATE_CANARY',visibility='private')]
        session=EvidenceSession(records)
        ref=session.read_chars('task')['receipt_id'];session.read_chars('secret')
        candidate={'judgment':{'status':'scored','dimensions':{d:{'score':2,'rationale':'fixture','refs':[ref]} for d in DIMENSIONS[view['task_type']]}},
                   'feedback':{'issues':[{'observation':'fixture','refs':[ref]}],'limitations':[]}}
        j=out/'judge';write_json(j/'candidate_judgment.json',candidate)
        write_json(j/'native_call.json',{'status':'completed','call_id':'synthetic-not-model','response':json.dumps(candidate)})
        write_json(j/'evidence_manifest.json',{'records':records})
        write_json(j/'tool_state.json',{'receipts':session.receipts,'image_results_returned':[]})
        (j/'prompt.txt').write_text('Synthetic prompt')
        write_json(j/'result.json',{'status':'scored','dimension_scores':{d:2 for d in DIMENSIONS[view['task_type']]},'quality':2,
             **candidate,'same_turn_feedback':True,'evidence_inventory_hash':session.inventory_hash,
             'public_evidence_inventory_hash':EvidenceSession(records,public_only=True).inventory_hash})

    def evaluate(self):
        self.evaluation=StageEvaluationAdapter(binary='fake-not-executed',stage_runner=self.fake_stage)(request=self.request)
        self.binding={'request_hash':digest(self.request),'evaluation_hash':digest(self.evaluation)}
        return self.evaluation

    def approve_file(self):
        proof=self.root/'independent-audit.json';write_json(proof,{'synthetic_test_only':True})
        gate={'status':'passed','reviewer':'synthetic-independent-fixture','note':'Not real scientific acceptance.',
              'evidence':[{'path':str(proof),'sha256':file_hash(proof)}]}
        record={'status':'approved','binding':self.binding,'scientific_binding':self.evaluation['scientific_binding'],
                'gates':{name:copy.deepcopy(gate) for name in ('trajectory','semantic_feedback','public_projection')}}
        path=self.reviewdir/(digest(self.request)+'.json');write_json(path,record)
        return path

    def resolve(self):
        return self.resolver(request=self.request,evaluation=self.evaluation,binding=self.binding)

    def test_pending_then_external_review_no_second_model_or_stage(self):
        self.evaluate();self.assertEqual(self.resolve()['status'],'pending_review')
        self.approve_file();approved=self.resolve()
        self.assertEqual(approved['status'],'approved');self.assertEqual(approved['envelope_hash'],digest(approved['envelope']))
        self.assertEqual(len(self.calls),1)
        self.assertEqual(set(self.calls[0]),{'package','harness','output','binary','skip_judge'})
        self.assertNotIn('identity',self.calls[0])
        with self.assertRaises(ProtocolError):StageEvaluationAdapter(binary='none',stage_runner=self.fake_stage)(request=self.request)
        self.assertEqual(len(self.calls),1)

    def test_projection_public_program_check_kept_private_never_published(self):
        self.evaluate();bundle=Path(self.evaluation['public_evidence_bundle']['root'])
        text=''.join(p.read_text() for p in bundle.rglob('*') if p.is_file())
        self.assertNotIn('PRIVATE_CANARY',text);self.assertNotIn('"secret"',text)
        index=read_json(bundle/'index.json');self.assertIn('public-check',{r['evidence_id'] for r in index['records']})
        self.assertEqual(len(read_json(bundle/'receipts.json')),1)

    def test_native_tool_rejection_cannot_be_waived_by_generic_approval(self):
        original=self.fake_stage
        def audited_stage(**kw):
            original(**kw)
            write_json(Path(kw['output'])/'judge/native_tool_audit.json',{'status':'rejected','private_detail':'TOOL_AUDIT_PRIVATE'})
        self.fake_stage=audited_stage
        self.evaluate();self.approve_file()
        self.assertIn('native_tool_audit_sha256',self.evaluation['scientific_binding'])
        self.assertEqual(self.resolve()['status'],'pending_review')
        bundle=Path(self.evaluation['public_evidence_bundle']['root'])
        self.assertNotIn('TOOL_AUDIT_PRIVATE',''.join(p.read_text() for p in bundle.rglob('*') if p.is_file()))

    def test_pending_code_mode_still_requires_existing_bound_trajectory_review(self):
        original=self.fake_stage
        def audited_stage(**kw):
            original(**kw)
            write_json(Path(kw['output'])/'judge/native_tool_audit.json',{'status':'pending_code_mode_review'})
        self.fake_stage=audited_stage
        self.evaluate();self.assertEqual(self.resolve()['status'],'pending_review')
        self.approve_file();self.assertEqual(self.resolve()['status'],'approved')
        path=Path(self.evaluation['attachments']['native_tool_audit']['path'])
        write_json(path,{'status':'development_admissible'})
        with self.assertRaises(ProtocolError):self.resolve()

    def test_review_binding_or_missing_semantic_gate_rejected(self):
        self.evaluate();p=self.approve_file();review=read_json(p)
        review['gates']['semantic_feedback']['status']='failed';write_json(p,review)
        self.assertEqual(self.resolve()['status'],'pending_review')
        review['binding']['evaluation_hash']='0'*64;write_json(p,review)
        with self.assertRaises(ProtocolError):self.resolve()

    def test_projection_gate_and_hash_mandatory(self):
        self.evaluate();p=self.approve_file();r=read_json(p);del r['gates']['public_projection'];write_json(p,r)
        self.assertEqual(self.resolve()['status'],'pending_review')
        (Path(self.evaluation['public_evidence_bundle']['root'])/'extra.txt').write_text('changed')
        with self.assertRaises(ProtocolError):self.resolve()

    def test_original_native_result_mutation_rejected(self):
        self.evaluate();self.approve_file()
        p=Path(self.evaluation['attachments']['validated_result']['path']);r=read_json(p);r['quality']=4;write_json(p,r)
        with self.assertRaises(ProtocolError):self.resolve()

    def test_stale_package_or_harness_rejected_before_stage(self):
        (Path(self.request['harness_directory'])/'harness.py').write_text('mutated')
        with self.assertRaises(ProtocolError):self.evaluate()
        self.assertEqual(self.calls,[])

    def test_source_request_never_formal(self):
        self.request['development']=False
        with self.assertRaises(ProtocolError):self.evaluate()
        self.assertEqual(self.calls,[])

    def test_stage_exception_not_zero(self):
        def broken(**kw):raise RuntimeError('infrastructure failure')
        with self.assertRaises(RuntimeError):StageEvaluationAdapter(binary='none',stage_runner=broken)(request=self.request)
        self.assertFalse((self.root/'run/evolution_review/evaluation_pending.json').exists())

    def test_template_never_marks_approval(self):
        self.evaluate();template=review_template(request=self.request,evaluation=self.evaluation)
        self.assertEqual(template['status'],'pending')
        self.assertTrue(all(g['status']=='pending' and g['reviewer'] is None for g in template['gates'].values()))
        write_json(self.reviewdir/(digest(self.request)+'.json'),template)
        self.assertEqual(self.resolve()['status'],'pending_review')

    def test_judge_failure_cannot_become_zero_via_review(self):
        def failed_judge(**kw):
            self.fake_stage(**kw);j=Path(kw['output'])/'judge'
            candidate=read_json(j/'candidate_judgment.json')
            candidate['judgment']={'status':'infrastructure_failure','dimensions':{}}
            write_json(j/'candidate_judgment.json',candidate)
            call=read_json(j/'native_call.json');call['response']=json.dumps(candidate);write_json(j/'native_call.json',call)
            result=read_json(j/'result.json');result.update(candidate,status='infrastructure_failure',dimension_scores={},quality=None)
            write_json(j/'result.json',result)
        self.evaluation=StageEvaluationAdapter(binary='none',stage_runner=failed_judge)(request=self.request)
        self.binding={'request_hash':digest(self.request),'evaluation_hash':digest(self.evaluation)}
        self.approve_file();reply=self.resolve()
        self.assertEqual(reply['status'],'pending_review');self.assertNotIn('envelope',reply)

    def test_absent_validated_result_stays_pending(self):
        def awaiting_revalidation(**kw):
            self.fake_stage(**kw)
            (Path(kw['output'])/'judge/result.json').unlink()
        self.evaluation=StageEvaluationAdapter(binary='none',stage_runner=awaiting_revalidation)(request=self.request)
        self.binding={'request_hash':digest(self.request),'evaluation_hash':digest(self.evaluation)}
        self.approve_file()
        self.assertEqual(self.resolve()['status'],'pending_review')


if __name__=='__main__':unittest.main()
