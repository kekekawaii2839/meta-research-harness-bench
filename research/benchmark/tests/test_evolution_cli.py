"""Concrete CLI + real evaluator/resolver/driver, fake science/native workers only."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts/active"))
import run_evolution_development as cli
import test_evolution_driver as driver_fixtures
import test_evolution_evaluator as evaluator_fixtures
from mrhbench.evolution_driver import DevelopmentEvolutionDriver
from mrhbench.evolution_evaluator import StageEvaluationAdapter
from mrhbench.io import ProtocolError,digest,file_hash,read_json,write_json


class EvolutionCLITests(unittest.TestCase):
    def setUp(self):
        self.f=driver_fixtures.DriverTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=evaluator_fixtures.EvaluationAdapterTests();self.s.setUp();self.addCleanup(self.s.doCleanups)
        self.root=self.f.root;self.remaining=1000
        fake_binary=self.root/'fake-codex.bin';fake_binary.write_bytes(b'SYNTHETIC-NOT-EXECUTABLE')
        for package in self.f.packages.values():
            p=package/'task.json';t=read_json(p);t['public']['resources']={'execution_budget':{'model_calls':2}};write_json(p,t)
        self.config={'development':True,'root':str(self.root/'controller'),'builder_root':str(self.root/'builders'),
            'h0':str(self.f.h0),'tasks':self.f.tasks,'packages':{k:str(v) for k,v in self.f.packages.items()},
            'rounds':1,'codex_binary':str(fake_binary),'review_directory':str(self.root/'reviews'),
            'native_builder':{'image_id':'sha256:'+'a'*64,'resources':{'cpus':1,'memory_mb':512,'disk_mb':64,'pids_limit':32,'wall_seconds':60},
                'native_timeout_seconds':30,'max_tool_calls':20,'max_artifact_bytes':1024**2,'max_artifact_entries':100,'use_hook_guard':False}}
        self.assertEqual(cli.initialize(self.config)['status'],'initialized_no_model_calls')
        self.driver=DevelopmentEvolutionDriver(self.config['root'])
        outer=self
        class Ledger:
            def summary(self):return {'authorized_maximum':outer.remaining,'used_runs_including_failures':0}
        class Builder:
            def __init__(self,**kw):pass
            def evolve(self,**kw):return outer.f.evolve(**kw)
            def select(self,**kw):return outer.f.select(**kw)
        def fake_stage(**kw):
            Path(kw['output']).parent.mkdir(parents=True,exist_ok=True)
            return outer.s.fake_stage(**kw)
        self.patches=[patch.object(cli,'CallLedger',lambda *a,**k:Ledger()),
            patch.object(cli,'NativeDevelopmentBuilder',Builder),
            patch.object(cli,'StageEvaluationAdapter',lambda **kw:StageEvaluationAdapter(stage_runner=fake_stage,**kw))]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def approve_pending_synthetic(self):
        # Test fixture approvals ONLY; never write approvals for historical actual runs.
        reviewdir=Path(self.config['review_directory']);proof=self.root/'synthetic-proof.json'
        if not proof.exists():write_json(proof,{'synthetic_test_only':True})
        for p in reviewdir.glob('*.pending-template.json'):
            target=p.with_name(p.name.replace('.pending-template.json','.json'))
            if target.exists():continue
            r=read_json(p);r['status']='approved'
            for gate in r['gates'].values():gate.update(status='passed',reviewer='synthetic-only',note='Test fixture, not scientific acceptance.',evidence=[{'path':str(proof),'sha256':file_hash(proof)}])
            write_json(target,r)

    def test_initialize_zero_worker_calls_and_ceiling_operation_names(self):
        self.assertEqual(self.s.calls,[]);self.assertEqual(cli.remaining_call_ceiling(self.driver,self.config),62)
        task=self.config['tasks'][0];op='evaluate-'+digest(['H0',task['task_id']])
        for name,decrement in [(op,3),('evolve-H0',1),('select',1)]:
            before=cli.remaining_call_ceiling(self.driver,self.config)
            write_json(self.driver.root/'operations'/(name+'.json'),{'status':'complete'})
            self.assertEqual(cli.remaining_call_ceiling(self.driver,self.config),before-decrement)

    def test_pending_review_resume_never_repeats_paid_stage(self):
        r=cli.advance(self.config);self.assertEqual(r['status'],'awaiting_external_trajectory_and_semantic_review')
        self.assertEqual(len(self.s.calls),1);self.assertEqual(self.f.events,[])
        r=cli.advance(self.config);self.assertEqual(len(self.s.calls),1)
        self.approve_pending_synthetic();r=cli.advance(self.config)
        self.assertEqual(len(self.s.calls),2)
        self.assertEqual(r['status'],'awaiting_external_trajectory_and_semantic_review')
        self.assertEqual(self.f.events,[])

    def test_full_fake_workers_real_adapter_review_cli_protocol(self):
        for _ in range(25):
            r=cli.advance(self.config)
            if r['status']=='completed_development_only':break
            self.approve_pending_synthetic()
        self.assertEqual(r['status'],'completed_development_only')
        self.assertEqual(len(self.s.calls),20)
        self.assertEqual(sum(e[0]=='evolve' for e in self.f.events),1)
        self.assertEqual(sum(e[0]=='select' for e in self.f.events),1)
        self.assertEqual(cli.remaining_call_ceiling(self.driver,self.config),0)
        before=len(self.s.calls);self.assertEqual(cli.advance(self.config),r);self.assertEqual(len(self.s.calls),before)

    def test_template_error_occurs_after_paid_cache_and_recovers(self):
        with patch.object(cli,'review_template',side_effect=OSError('synthetic template write/preparation failure')):
            r=cli.advance(self.config)
        self.assertEqual(len(r['template_errors']),1)
        operations=list((self.driver.root/'operations').glob('*.json'));self.assertEqual(len(operations),1)
        self.assertEqual(read_json(operations[0])['status'],'complete');self.assertEqual(len(self.s.calls),1)
        r=cli.advance(self.config);self.assertEqual(r['template_errors'],[]);self.assertEqual(len(self.s.calls),1)

    def test_insufficient_budget_stops_before_stage(self):
        self.remaining=61
        with self.assertRaises(ProtocolError):cli.advance(self.config)
        self.assertEqual(self.s.calls,[])

    def test_bound_configuration_and_implementation_changes_rejected(self):
        config=copy.deepcopy(self.config);config['native_builder']['max_tool_calls']=21
        with self.assertRaises(ProtocolError):cli.advance(config)
        with patch.object(cli,'implementation_manifest',return_value=[]):
            with self.assertRaises(ProtocolError):cli.advance(self.config)
        self.assertEqual(self.s.calls,[])

    def test_unknown_paid_operation_is_not_retried(self):
        p=self.driver.root/'operations'/('evaluate-'+digest(['H0',self.config['tasks'][0]['task_id']])+'.json')
        write_json(p,{'status':'in_flight'})
        with self.assertRaises(ProtocolError):cli.advance(self.config)
        self.assertEqual(self.s.calls,[])

    def test_review_store_cannot_overlap_builder_workspace(self):
        config=copy.deepcopy(self.config);config['review_directory']=str(Path(config['builder_root'])/'private')
        with self.assertRaises(ProtocolError):cli.check_configuration(config)

    def test_claude_roles_gate_and_factory(self):
        roles=read_json(Path(cli.ROOT)/'config/role_transport_claude_v1.json')
        config=copy.deepcopy(self.config);config['roles']=roles
        cli.check_configuration(config)
        factory=cli.builder_factory(config)
        from mrhbench.claude_transport import ClaudeNativeRunner
        self.assertIs(factory.keywords['runner_factory'],ClaudeNativeRunner)
        self.assertEqual(factory.keywords['model'],roles['builder']['model'])
        guarded=copy.deepcopy(config);guarded['native_builder']['use_hook_guard']=True
        with self.assertRaises(ProtocolError):cli.check_configuration(guarded)
        mixed=copy.deepcopy(config);mixed['context_policy']={'x':1}
        with self.assertRaises(ProtocolError):cli.check_configuration(mixed)
        bad=copy.deepcopy(config);bad['roles']['judge'].pop('effort')
        with self.assertRaises(ProtocolError):cli.check_configuration(bad)

    def test_binary_hash_change_stops_before_any_worker(self):
        Path(self.config['codex_binary']).write_bytes(b'CHANGED-SYNTHETIC-NOT-EXECUTABLE')
        with self.assertRaises(ProtocolError):cli.advance(self.config)
        self.assertEqual(self.s.calls,[])


if __name__=='__main__':unittest.main()
