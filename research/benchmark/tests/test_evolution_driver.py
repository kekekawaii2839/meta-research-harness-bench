import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mrhbench.evolution_driver import DevelopmentEvolutionDriver, PendingEvaluationReview, tree_manifest
from mrhbench.io import ProtocolError, file_hash, read_json, write_json, digest
from mrhbench.materials import TASK_GATES
from mrhbench.scoring import TASK_TYPES, DIMENSIONS


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.events=[];self.tasks=[];self.packages={}
        self.h0=self.root/'h0';self.h0.mkdir();(self.h0/'harness.py').write_text('VERSION=0')
        for split in ('search','test'):
            for kind in TASK_TYPES:
                ident=split+'-'+kind; p=self.root/'materials'/ident;p.mkdir(parents=True)
                (p/'public.txt').write_text('public fixed start '+ident)
                (p/'private.txt').write_text('PRIVATE-GOLD-'+ident)
                task={'schema_version':'0.1','task_id':ident,'task_type':kind,'paper_id':'paper-'+split,
                      'split':'development','public':{'task_id':ident,'task_type':kind,'prompt':'Synthetic fixture only',
                        'inputs':['start'],'output_contract':{},'resources':{},'tools':[],'public_rubric':{}},
                      'private':{'secret':'PRIVATE-GOLD'},'assets':[
                         {'asset_id':'start','path':'public.txt','sha256':file_hash(p/'public.txt'),'visibility':'public'},
                         {'asset_id':'gold','path':'private.txt','sha256':file_hash(p/'private.txt'),'visibility':'private'}],
                      'gates':{g:{'status':'pending','evidence':'Synthetic fixture'} for g in TASK_GATES}}
                write_json(p/'task.json',task)
                self.tasks.append({k:task[k] for k in ('task_id','task_type','paper_id')}|{'split':split});self.packages[ident]=p

    def create(self, rounds=2):
        self.driver=DevelopmentEvolutionDriver.create(root=self.root/'controller',builder_root=self.root/'builders',
                  tasks=self.tasks,packages=self.packages,h0=self.h0,rounds=rounds)
        return self.driver

    def evaluate(self, *, request):
        t=request['identity'];self.events.append(('eval',request['version_id'],t['split'],t['task_id']))
        if t['split']=='test':self.assertIsNotNone(self.driver.run._state()['builder_selected'])
        return {'status':'accepted_development','result':dict(t,status='scored',dimension_scores={k:2 for k in DIMENSIONS[t['task_type']]}),
             'feedback':{'task_id':t['task_id'],'task_type':t['task_type'],'mode':'feedback',
                 'feedback':{'issues':[],'limitations':['Synthetic, not scientific validation']},'public_evidence_inventory_hash':'synthetic-public-hash'},
             'judge_receipt':{'invocation_id':'synthetic-'+request['version_id']+t['task_id'],'same_turn_feedback':True,
                              'trajectory_reviewed':True,'semantic_feedback_reviewed':True}}

    def builder_check(self,request):
        text=json.dumps(request)
        self.assertNotIn('PRIVATE-GOLD',text);self.assertNotIn(str(self.root/'controller'),text)
        self.assertNotIn('test-',text);self.assertNotIn('private_test',text)
        self.assertEqual(len(request['builder_view']['search_tasks']),5)
        paths=list(Path(request['search_directory']).rglob('*'))
        self.assertFalse(any(p.name=='private.txt' for p in paths))
        for p in paths:
            if p.is_file():self.assertNotIn('PRIVATE-GOLD',p.read_text())

    def evolve(self, *, request):
        self.builder_check(request);self.events.append(('evolve',request['operation']))
        p=Path(request['output_directory'])/'candidate';p.mkdir(parents=True)
        (p/'harness.py').write_text('VERSION='+request['operation'])
        return {'candidate_relative_path':'output/candidate','files':tree_manifest(p)}

    def select(self, *, request):
        self.builder_check(request);self.events.append(('select',))
        return {'version_id':'H1','reason':'Synthetic selection on search only'}

    def advance(self):return self.driver.advance(evaluate=self.evaluate,evolve=self.evolve,select=self.select)

    def test_mixed_full_rounds_selection_hidden_and_idempotent_resume(self):
        self.create();s=self.advance();self.assertEqual(len(s['curve']),3)
        self.assertEqual(sum(x[0]=='eval' for x in self.events),30)
        self.assertEqual(sum(x[0]=='evolve' for x in self.events),2)
        for version in ('H0','H1','H2'):
            self.assertEqual(sum(x[:3]==('eval',version,'search') for x in self.events),5)
        before=copy.deepcopy(self.events)
        self.driver=DevelopmentEvolutionDriver(self.root/'controller');self.assertEqual(self.advance(),s)
        self.assertEqual(self.events,before)

    def test_exception_unknown_not_zero_or_retried(self):
        self.create();count=[]
        def fail(**kw):count.append(1);raise RuntimeError('transport_unknown')
        with self.assertRaises(RuntimeError):self.driver.advance(evaluate=fail,evolve=self.evolve,select=self.select)
        with self.assertRaises(ProtocolError):self.driver.advance(evaluate=fail,evolve=self.evolve,select=self.select)
        self.assertEqual(len(count),1);self.assertFalse((self.root/'controller/search_scores').exists())
        op=read_json(next((self.root/'controller/operations').glob('*.json')))
        self.assertIsNone(op['quality_score']);self.assertFalse(op['automatic_zero'])

    def test_returned_unknown_evaluation_not_zero(self):
        self.create();count=[]
        def unknown(**kw):count.append(1);return {'status':'infrastructure_unknown'}
        for _ in range(2):
            with self.assertRaises(ProtocolError):self.driver.advance(evaluate=unknown,evolve=self.evolve,select=self.select)
        self.assertEqual(len(count),1)

    def test_input_and_snapshot_mutations_rejected(self):
        self.create();p=next(iter(self.packages.values()))/'public.txt';p.write_text('changed')
        with self.assertRaises(ProtocolError):self.advance()
        self.assertEqual(self.events,[])

    def test_snapshot_mutation_rejected(self):
        self.create();(self.root/'controller/snapshots/H0/harness.py').write_text('changed')
        with self.assertRaises(ProtocolError):self.advance()

    def test_feedback_private_fields_rejected_before_builder(self):
        self.create()
        def bad(**kw):
            r=self.evaluate(**kw);r['feedback']['private_reference']='PRIVATE-GOLD';return r
        with self.assertRaises(ProtocolError):self.driver.advance(evaluate=bad,evolve=self.evolve,select=self.select)
        self.assertFalse(any(e[0]=='evolve' for e in self.events))

    def test_same_turn_and_manual_review_required(self):
        self.create()
        def bad(**kw):
            r=self.evaluate(**kw);r['judge_receipt']['semantic_feedback_reviewed']=False;return r
        with self.assertRaises(ProtocolError):self.driver.advance(evaluate=bad,evolve=self.evolve,select=self.select)

    def test_paper_split_and_incomplete_coverage_rejected(self):
        for t in self.tasks:
            t['paper_id']='same-paper'
            p=self.packages[t['task_id']]/'task.json';v=read_json(p);v['paper_id']='same-paper';write_json(p,v)
        with self.assertRaises(ProtocolError):self.create()
        self.tasks.pop()
        with self.assertRaises(ProtocolError):self.create()

    def test_rounds_stop_without_additional_retries(self):
        self.create(rounds=1);self.advance()
        self.assertEqual(sum(x[0]=='evolve' for x in self.events),1)
        self.assertEqual(len(self.driver.run._state()['versions']),2)

    def test_builder_input_mutation_rejected(self):
        self.create()
        def bad(**kw):
            r=self.evolve(**kw);(Path(kw['request']['current_harness'])/'harness.py').write_text('mutated')
            return r
        with self.assertRaises(ProtocolError):self.driver.advance(evaluate=self.evaluate,evolve=bad,select=self.select)

    def test_configuration_hash_mutation_rejected(self):
        self.create();p=self.root/'controller/driver.json';r=read_json(p)
        r['configuration']['rounds']=999;write_json(p,r)
        with self.assertRaises(ProtocolError):self.advance()

    def test_builder_cannot_return_controller_candidate(self):
        self.create()
        def escape(**kw):return {'candidate_relative_path':'../controller','files':[]}
        with self.assertRaises(ProtocolError):self.driver.advance(evaluate=self.evaluate,evolve=escape,select=self.select)

    def test_result_cache_hash_checked(self):
        self.create();self.advance();p=next((self.root/'controller/operations').glob('*.json'));r=read_json(p)
        r['result']['tampered']=True;write_json(p,r)
        with self.assertRaises(ProtocolError):self.advance()

    def pending_evaluate(self, **kw):
        return {'status':'completed_pending_review','envelope':self.evaluate(**kw)}

    def approve(self, *, request, evaluation, binding):
        envelope=evaluation['envelope']
        return {'status':'approved','binding':binding,'envelope':envelope,
                'envelope_hash':digest(envelope),'review_receipt_hash':'a'*64}

    def test_two_phase_pending_to_approved_resume_calls_evaluate_once(self):
        self.create(rounds=1);ready=[];reviews=[]
        def review(**kw):
            reviews.append(kw['binding'])
            return self.approve(**kw) if ready else {'status':'pending_review'}
        for _ in range(2):
            with self.assertRaises(PendingEvaluationReview):
                self.driver.advance(evaluate=self.pending_evaluate,evolve=self.evolve,select=self.select,review_evaluation=review)
        self.assertEqual(len(self.events),1);self.assertEqual(len(reviews),2)
        cached=next((self.root/'controller/operations').glob('*.json'));original=cached.read_bytes()
        ready.append(True)
        self.driver=DevelopmentEvolutionDriver(self.root/'controller')
        s=self.driver.advance(evaluate=self.pending_evaluate,evolve=self.evolve,select=self.select,review_evaluation=review)
        self.assertEqual(sum(e[0]=='eval' for e in self.events),20)
        self.assertEqual(cached.read_bytes(),original)
        previous=(len(self.events),len(reviews))
        self.assertEqual(self.driver.advance(evaluate=self.pending_evaluate,evolve=self.evolve,select=self.select,review_evaluation=review),s)
        self.assertEqual((len(self.events),len(reviews)),previous)

    def test_review_input_and_score_hash_binding(self):
        self.create(rounds=1)
        for mutation in ('input','score'):
            def bad(**kw):
                r=self.approve(**kw)
                if mutation=='input':r['binding']['evaluation_hash']='bad'
                else:r['envelope_hash']='bad'
                return r
            with self.assertRaises(ProtocolError):
                self.driver.advance(evaluate=self.pending_evaluate,evolve=self.evolve,select=self.select,review_evaluation=bad)
        self.assertEqual(len(self.events),1)
        self.assertFalse(list((self.root/'controller/approved_reviews').glob('*.json')))

    def test_pending_review_cannot_be_disabled_on_resume(self):
        self.create()
        with self.assertRaises(PendingEvaluationReview):
            self.driver.advance(evaluate=self.pending_evaluate,evolve=self.evolve,select=self.select,review_evaluation=lambda **kw:{'status':'pending_review'})
        with self.assertRaises(ProtocolError):self.advance()
        self.assertEqual(len(self.events),1)

    def test_unknown_paid_failure_never_calls_resolver_or_retries(self):
        self.create();calls=[];reviews=[]
        def fail(**kw):calls.append(1);raise RuntimeError('unknown transport outcome')
        def review(**kw):reviews.append(1);return self.approve(**kw)
        with self.assertRaises(RuntimeError):self.driver.advance(evaluate=fail,evolve=self.evolve,select=self.select,review_evaluation=review)
        with self.assertRaises(ProtocolError):self.driver.advance(evaluate=fail,evolve=self.evolve,select=self.select,review_evaluation=review)
        self.assertEqual(calls,[1]);self.assertEqual(reviews,[])

    def test_public_evidence_bundle_staged_without_controller_paths(self):
        self.create(rounds=1)
        def evaluate(**kw):
            r=self.evaluate(**kw);req=kw['request'];d=self.root/'private-controller-projections'/req['version_id']/req['identity']['task_id'];d.mkdir(parents=True)
            (d/'snippet.txt').write_text('public executed evidence only')
            h=file_hash(d/'snippet.txt')
            write_json(d/'index.json',{'schema_version':'public-evidence-projection-1','records':[
                {'evidence_id':'e1','path':'snippet.txt','sha256':h,'origin':'platform_trace','visibility':'public','media_type':'text/plain','content_sha256':h}],
                'receipts':{'r1':{'evidence_id':'e1','source_sha256':h,'start_char':0,'end_char':10}}})
            files=tree_manifest(d);r['public_evidence_bundle']={'root':str(d),'files':files,'manifest_hash':digest(files),'index_path':'index.json'}
            return r
        def evolve(**kw):
            req=kw['request'];index=list(Path(req['public_evidence_directory']).rglob('index.json'))
            self.assertEqual(len(index),5)
            self.assertTrue(all(read_json(p)['receipts']['r1']['evidence_id']=='e1' for p in index))
            self.assertNotIn('private-controller-projections',json.dumps(req))
            return self.evolve(**kw)
        self.driver.advance(evaluate=evaluate,evolve=evolve,select=self.select)

    def test_bundle_tamper_is_rejected(self):
        from mrhbench.evolution_driver import verify_public_bundle
        d=self.root/'bundle';d.mkdir();write_json(d/'index.json',{'schema_version':'public-evidence-projection-1','records':[],'receipts':{}})
        files=tree_manifest(d);bundle={'root':str(d),'files':files,'manifest_hash':digest(files),'index_path':'index.json'}
        (d/'index.json').write_text('tampered')
        with self.assertRaises(ProtocolError):verify_public_bundle(bundle)

    def test_frozen_approval_mutation_rejected_without_callbacks(self):
        self.create(rounds=1)
        self.driver.advance(evaluate=self.pending_evaluate,evolve=self.evolve,select=self.select,review_evaluation=self.approve)
        p=next((self.root/'controller/approved_reviews').glob('*.json'));row=read_json(p)
        row['approval']['envelope']['result']['dimension_scores']={};write_json(p,row)
        before=len(self.events)
        with self.assertRaises(ProtocolError):
            self.driver.advance(evaluate=self.pending_evaluate,evolve=self.evolve,select=self.select,review_evaluation=self.approve)
        self.assertEqual(len(self.events),before)

    def test_private_evidence_index_rejected_even_with_matching_hash(self):
        from mrhbench.evolution_driver import verify_public_bundle
        d=self.root/'bundle';d.mkdir();(d/'secret.txt').write_text('fake private')
        write_json(d/'index.json',{'schema_version':'public-evidence-projection-1','records':[
            {'evidence_id':'x','path':'secret.txt','sha256':file_hash(d/'secret.txt'),'origin':'reference','visibility':'private'}], 'receipts':{}})
        files=tree_manifest(d)
        with self.assertRaises(ProtocolError):verify_public_bundle({'root':str(d),'files':files,'manifest_hash':digest(files),'index_path':'index.json'})


if __name__=='__main__':unittest.main()
