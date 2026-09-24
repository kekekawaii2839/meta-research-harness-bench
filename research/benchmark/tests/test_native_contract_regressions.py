"""Independent real adapter contract paths; subprocess/Docker are synthetic."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_evolution_native as fixtures
from mrhbench.costs import CallLedger
from mrhbench.evolution_native import NativeDevelopmentBuilder
from mrhbench.native_codex import NativeCodexRunner
from mrhbench.providers import CodexJSONTransport
from mrhbench.io import ProtocolError,read_json,write_json


class NativeContractRegressions(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.NativeBuilderTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root
        self.binary=self.root/'fake-native.bin';self.binary.write_bytes(b'SYNTHETIC-NOT-EXECUTABLE')
        self.ledger_path=self.root/'independent-ledger.json'
        write_json(self.ledger_path,{'authorized_maximum':10,'used_attempts':0,'attempts':[]})
        self.ledger=CallLedger(self.ledger_path)

    def fake_native_process(self,response):
        def process(command,**kw):
            output=Path(command[command.index('-o')+1]);write_json(output,response)
            kw['stdout'].write((json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}})+'\n').encode())
            kw['stdout'].flush()
            return SimpleNamespace(returncode=0)
        return process

    def test_actual_native_schema_decoder_connects_to_selector(self):
        request=copy.deepcopy(self.f.request);request['operation']='select'
        args=self.f.args|{'binary':self.binary,'ledger':self.ledger,'runner_factory':NativeCodexRunner,'use_hook_guard':False}
        response={'version_id':'H0','reason':'Synthetic public evidence'}
        with patch('mrhbench.native_codex.run_process_tree',side_effect=self.fake_native_process(response)) as process, \
             patch('mrhbench.native_codex.capture_session_rollout',return_value={'status':'captured','observed_tools':[]}):
            result=NativeDevelopmentBuilder(**args).select(request=request)
        self.assertEqual(result,response);self.assertIsInstance(result,dict);self.assertEqual(process.call_count,1)
        native=read_json(next((self.root/'audit').glob('*/native_result.json')))
        self.assertIsInstance(native['response'],dict)
        self.assertEqual(read_json(self.ledger_path)['attempts'][0]['status'],'completed')
        self.assertTrue(self.f.sessions[0].closed)

    def test_actual_schema_decoded_nonobject_or_blank_reason_rejected(self):
        for i,response in enumerate([[],None,{'version_id':'H0','reason':'   '} ]):
            request=copy.deepcopy(self.f.request);request['operation']='select'
            args=self.f.args|{'binary':self.binary,'ledger':self.ledger,'runner_factory':NativeCodexRunner,'use_hook_guard':False,'audit_root':self.root/('bad'+str(i))}
            with patch('mrhbench.native_codex.run_process_tree',side_effect=self.fake_native_process(response)), \
                 patch('mrhbench.native_codex.capture_session_rollout',return_value={'status':'captured','observed_tools':[]}):
                with self.assertRaises(ProtocolError):NativeDevelopmentBuilder(**args).select(request=request)
        # Native transport completed; invalid selector output is an application failure, not a reserved call.
        self.assertEqual([r['status'] for r in read_json(self.ledger_path)['attempts']],['completed']*3)
        self.assertTrue(all(s.closed for s in self.f.sessions))

    def test_plaintext_native_mode_remains_string(self):
        workspace=self.root/'empty';workspace.mkdir()
        runner=NativeCodexRunner(binary=self.binary,ledger=self.ledger,audit_root=self.root/'plain',model='gpt-5.6-sol',reasoning_effort='medium',permission_profile=':read-only')
        with patch('mrhbench.native_codex.run_process_tree',side_effect=self.fake_native_process({'x':1})), \
             patch('mrhbench.native_codex.capture_session_rollout',return_value={'status':'captured','observed_tools':[]}):
            result=runner.run(workspace=workspace,prompt='Synthetic',role='probe')
        self.assertIsInstance(result['response'],str)

    def test_provider_rejection_statuses_and_original_exceptions_preserved(self):
        cases=[({'status':'unavailable'},[], 'failed','Full executor rollout missing','incomplete_executor_rollout'),
               ({'status':'captured','observed_tools':[{'name':'fake'}]},[], 'rejected_native_tool_activity','Full executor rollout contains native tool activity','native_activity_in_executor_rollout'),
               ({'status':'captured','observed_tools':[]},[{'type':'item.started','item':{'type':'command_execution','command':'synthetic-not-executed'}}], 'rejected_native_tool_activity','Unexpected native tool activity',None)]
        for i,(capture,extra,status,message,failure_class) in enumerate(cases):
            transport=CodexJSONTransport(binary=self.binary,ledger=self.ledger,audit_root=self.root/('transport'+str(i)),model='gpt-5.6-sol',reasoning_effort='medium')
            events=extra+[{'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}}]
            fake=SimpleNamespace(returncode=0,stdout='\n'.join(json.dumps(x) for x in events),stderr='')
            with patch('mrhbench.providers.run_process_tree',return_value=fake) as process,patch('mrhbench.native_codex.capture_session_rollout',return_value=capture):
                with self.assertRaisesRegex(ProtocolError,message):
                    transport.complete({},output_schema={'type':'object','properties':{},'additionalProperties':False},role='probe')
            attempt=read_json(self.ledger_path)['attempts'][-1]
            self.assertEqual(attempt['status'],status);self.assertIn('finished_at',attempt)
            self.assertFalse(attempt['metadata']['automatic_outer_retry']);self.assertEqual(process.call_count,1)
            if failure_class:self.assertEqual(attempt['metadata']['failure_class'],failure_class)
        self.assertFalse(any(r['status']=='reserved' for r in read_json(self.ledger_path)['attempts']))


if __name__=='__main__':unittest.main()
