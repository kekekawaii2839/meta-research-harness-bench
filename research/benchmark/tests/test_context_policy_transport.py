import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.context_policy import build_policy,config_setting
from mrhbench.native_codex import NativeCodexRunner
from mrhbench.providers import CodexJSONTransport
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError,read_json,write_json
import test_evolution_evaluator as evaluator_fixtures


class ContextTransportTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.binary=self.root/'fake.exe';self.binary.write_bytes(b'not executable')
        render=[{'type':'message','role':'developer','content':[{'type':'input_text','text':
            '<skills_instructions>\n### Skill roots\n- `r0` = `C:/synthetic/skills`\n### Available skills\n- test: Synthetic. (file: r0/example/SKILL.md)\n</skills_instructions>'}]}]
        self.policy=build_policy(render,self.binary)
        self.ledgerpath=self.root/'ledger.json';write_json(self.ledgerpath,{'authorized_maximum':1,'used_attempts':0,'attempts':[]})
        self.args={'binary':self.binary,'model':'gpt-5.6-sol','reasoning_effort':'medium','ledger':CallLedger(self.ledgerpath),'audit_root':self.root/'audit'}

    def test_native_profile_opt_in_not_mutable_default_unchanged(self):
        ordinary=NativeCodexRunner(**self.args).command(self.root,self.root/'output')
        self.assertFalse(any(s.startswith('skills.config=') for s in ordinary))
        runner=NativeCodexRunner(**self.args,context_policy=self.policy)
        expected=config_setting(self.policy,self.binary)
        self.policy['disabled_skills'][0]['enabled']=True
        command=runner.command(self.root,self.root/'output')
        self.assertIn(expected,command)
        self.binary.write_bytes(b'changed')
        with self.assertRaises(ProtocolError):runner.command(self.root,self.root/'output')
        self.assertEqual(read_json(self.ledgerpath)['used_attempts'],0)

    def test_json_context_before_payment_and_in_observed_invocation(self):
        transport=CodexJSONTransport(**self.args,context_policy=self.policy)
        expected=config_setting(self.policy,self.binary)
        proc=SimpleNamespace(returncode=0,stdout=json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}}),stderr='')
        with patch('mrhbench.providers.run_process_tree',return_value=proc) as worker,patch('mrhbench.native_codex.capture_session_rollout',return_value={'status':'unavailable'}):
            with self.assertRaisesRegex(ProtocolError,'rollout missing'):
                transport.complete({},output_schema={'type':'object','properties':{},'additionalProperties':False},role='probe')
            self.assertIn(expected,worker.call_args.args[0])
        invocation=read_json(next((self.root/'audit').glob('*/invocation.json')))
        self.assertEqual(invocation['opt_in_context_policy']['policy'],self.policy)
        self.assertEqual(read_json(self.ledgerpath)['attempts'][0]['status'],'failed')

    def test_json_changed_binary_rejected_before_payment(self):
        transport=CodexJSONTransport(**self.args,context_policy=self.policy)
        self.binary.write_bytes(b'changed')
        with self.assertRaisesRegex(ProtocolError,'binary hash mismatch'):
            transport.complete({},output_schema={'type':'object'},role='probe')
        self.assertEqual(read_json(self.ledgerpath)['used_attempts'],0)

    def test_stage_adapter_forwards_policy_without_changing_public_task(self):
        from mrhbench.evolution_evaluator import StageEvaluationAdapter
        fixture=evaluator_fixtures.EvaluationAdapterTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        evaluation=StageEvaluationAdapter(binary=self.binary,stage_runner=fixture.fake_stage,context_policy=self.policy)(request=fixture.request)
        self.assertEqual(fixture.calls[0]['context_policy'],self.policy)
        self.assertEqual(evaluation['status'],'pending_review')
        self.assertNotIn('context_policy',read_json(Path(fixture.request['output_directory'])/'public/task.json'))

    def test_judge_bounded_runner_clone_preserves_explicit_policy(self):
        from mrhbench.native_judge import run_native_judge
        runner=NativeCodexRunner(**self.args,context_policy=self.policy)
        with patch('mrhbench.native_codex.NativeCodexRunner') as factory:
            factory.return_value.run.side_effect=RuntimeError('STOP_BEFORE_MODEL')
            with self.assertRaisesRegex(RuntimeError,'STOP_BEFORE_MODEL'):
                run_native_judge(runner=runner,task_id='synthetic',task_type='IDEA',records=[],output=self.root/'judge',python_binary=Path(sys.executable))
            self.assertEqual(factory.call_args.kwargs['context_policy'],self.policy)
        self.assertEqual(read_json(self.ledgerpath)['used_attempts'],0)


if __name__=='__main__':unittest.main()
