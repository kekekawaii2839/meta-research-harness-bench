import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.native_codex import NativeCodexRunner
from mrhbench.native_judge import run_native_judge
from mrhbench.judge_runner import evidence_record
from mrhbench.io import ProtocolError

class LedgerSpy:
    def __init__(self): self.reserves=0
    def reserve(self,**kwargs): self.reserves+=1; raise AssertionError('No paid transport allowed')

class StopBeforeTransport(Exception): pass

class GuardForwardingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.logs=self.root/'logs';self.logs.mkdir()
        self.config=self.root/'guard.json';self.ledger=LedgerSpy()
        self.write_config(['mcp__mrhbench__evidence_read','mcp__mrhbench__evidence_inventory'])
        self.spec={'config_path':self.config,'python_binary':Path(sys.executable)}
    def write_config(self,tools):
        self.config.write_text(json.dumps({'allowed_tools':tools,'log_directory':str(self.logs)}))
    def runner(self,guard=True):
        return NativeCodexRunner(binary=Path(sys.executable),model='gpt-5.6-sol',reasoning_effort='medium',ledger=self.ledger,audit_root=self.root/'calls',permission_profile=':read-only',tool_profile='bounded_mcp',mcp_servers={'mrhbench':{'command':'unused'}},hook_guard=self.spec if guard else None)
    def judge(self,r):
        return run_native_judge(runner=r,task_id='synthetic',task_type='WRITE_CONTENT',records=[evidence_record('task','task','Synthetic no-model wiring test',visibility='public')],output=self.root/'judge',python_binary=Path(sys.executable))
    def test_clone_forwards_frozen_spec_not_expanded_hooks(self):
        original=self.runner();seen=[]
        def stop(clone,**kwargs):
            seen.append(clone);clone.command(kwargs['workspace'],self.root/'unused');raise StopBeforeTransport()
        with patch.object(NativeCodexRunner,'run',stop),self.assertRaises(StopBeforeTransport):self.judge(original)
        self.assertEqual(len(seen),1);clone=seen[0]
        self.assertEqual(clone.hook_guard_spec,original.hook_guard_spec)
        self.assertIsNot(clone.hook_guard_spec,original.hook_guard_spec)
        self.assertEqual(clone.hook_guard_metadata,original.hook_guard_metadata)
        self.assertEqual(clone.hook_guard,original.hook_guard)
        self.assertEqual(self.ledger.reserves,0)
    def test_unguarded_legacy_default_is_not_silently_upgraded(self):
        seen=[]
        def stop(clone,**kwargs):seen.append(clone.hook_guard);raise StopBeforeTransport()
        with patch.object(NativeCodexRunner,'run',stop),self.assertRaises(StopBeforeTransport):self.judge(self.runner(False))
        self.assertEqual(seen,[None]);self.assertEqual(self.ledger.reserves,0)
    def test_mutated_config_rejected_before_clone_or_reserve(self):
        r=self.runner();self.write_config(['mcp__mrhbench__container_exec'])
        with patch.object(NativeCodexRunner,'run') as run,self.assertRaisesRegex(ValueError,'dependency changed'):self.judge(r)
        run.assert_not_called();self.assertEqual(self.ledger.reserves,0)
    def test_unreleased_allowlist_rejected_before_run_or_reserve(self):
        self.write_config(['mcp__mrhbench__container_exec']);r=self.runner()
        with patch.object(NativeCodexRunner,'run') as run,self.assertRaisesRegex(ProtocolError,'outside'):self.judge(r)
        run.assert_not_called();self.assertEqual(self.ledger.reserves,0)
    def test_legacy_expanded_guard_without_spec_fails_closed_preflight(self):
        r=self.runner();del r.hook_guard_spec
        with patch.object(NativeCodexRunner,'run') as run,self.assertRaisesRegex(ProtocolError,'transferable'):self.judge(r)
        run.assert_not_called();self.assertEqual(self.ledger.reserves,0)
    def test_changed_config_at_runner_command_is_pre_reservation(self):
        r=self.runner();self.config.write_text(self.config.read_text()+' ')
        workspace=self.root/'workspace';workspace.mkdir()
        with self.assertRaisesRegex(ValueError,'dependency changed'):r.run(workspace=workspace,prompt='No call')
        self.assertEqual(self.ledger.reserves,0)

if __name__=='__main__':unittest.main()

