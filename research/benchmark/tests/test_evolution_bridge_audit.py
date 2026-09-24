import tempfile,sys,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.bounded_mcp import BoundedTools
from mrhbench.evolution_native import NativeDevelopmentBuilder,released_builder_inputs
from mrhbench.io import ProtocolError,write_json
import test_evolution_native as existing


class BridgeAuditTests(unittest.TestCase):
 def setUp(self):
  self.base=existing.NativeBuilderTests('test_invalid_configuration_before_native_invocation')
  self.base.setUp();self.addCleanup(self.base.doCleanups)
 def builder_with_cleanup_error(self):
  old=self.base.args['session_factory']
  class Cleanup(old):
   def close(self):super().close();raise RuntimeError('CLEANUP_PRIMARY')
  return NativeDevelopmentBuilder(**(self.base.args|{'session_factory':Cleanup}))
 def fail_audit_write(self,path,*args,**kwargs):
  if Path(path).name in ('failure.json','cleanup_failure.json'):raise OSError('AUDIT_WRITE_FAILURE')
  return write_json(path,*args,**kwargs)
 def test_primary_survives_cleanup_and_all_failure_audit_writes(self):
  self.base.mode='raise';builder=self.builder_with_cleanup_error()
  with patch('mrhbench.evolution_native.write_json',self.fail_audit_write):
   with self.assertRaisesRegex(ProtocolError,'synthetic native failure'):builder.evolve(request=self.base.request)
  self.assertTrue(self.base.sessions[0].closed)
  with self.assertRaises(ProtocolError):builder.evolve(request=self.base.request)
  self.assertEqual(len(self.base.runners),1)
 def test_cleanup_only_error_not_masked_by_audit_write(self):
  builder=self.builder_with_cleanup_error()
  with patch('mrhbench.evolution_native.write_json',self.fail_audit_write):
   with self.assertRaisesRegex(RuntimeError,'CLEANUP_PRIMARY'):builder.evolve(request=self.base.request)
  self.assertTrue(self.base.sessions[0].closed)
 def test_invalid_server_allowlist_rejected_before_container_constructor(self):
  for allowed in [[],['host_exec'],['container_read','container_read'],'container_read',[3]]:
   with patch('mrhbench.container_runtime.ContainerSession') as create:
    with self.assertRaises(ProtocolError):BoundedTools({'container':{'unneeded':'invalid config'},'allowed_tools':allowed})
    create.assert_not_called()
 def test_output_nested_inside_any_released_input_rejected(self):
  for key in ('current_harness','search_directory','public_evidence_directory'):
   request=dict(self.base.request)
   output=Path(request[key])/'nested_output';output.mkdir()
   (output/'private_controller_output.txt').write_text('NOT_PUBLIC_INPUT')
   request['output_directory']=str(output)
   with self.assertRaises(ProtocolError):released_builder_inputs(request,self.base.root/('release-'+key))
 def test_server_initial_state_failure_closes_owned_without_masking(self):
  fake=MagicMock();fake.cid=None;fake.close.side_effect=RuntimeError('cleanup cannot replace state error')
  config={'records':[],'state_path':'unused','container':{'image_id':'fake','resources':{},'input_files':{},'audit_dir':'unused'},'allowed_tools':['container_read']}
  with patch('mrhbench.container_runtime.ContainerSession',return_value=fake),patch('mrhbench.bounded_mcp.write_json',side_effect=OSError('STATE_WRITE_FAILURE')):
   with self.assertRaisesRegex(OSError,'STATE_WRITE_FAILURE'):BoundedTools(config)
  fake.start.assert_called_once();fake.close.assert_called_once()
 def test_server_only_exposes_and_accepts_allowlisted_tools(self):
  with tempfile.TemporaryDirectory() as directory:
   fake=MagicMock();fake.cid=None;fake.read.return_value=b'readonly'
   config={'records':[],'state_path':str(Path(directory)/'state.json'),'container':{'image_id':'fake','resources':{},'input_files':{},'audit_dir':'unused'},'allowed_tools':['container_read','container_list']}
   with patch('mrhbench.container_runtime.ContainerSession',return_value=fake):
    server=BoundedTools(config)
    self.assertEqual({x['name'] for x in server.definitions},{'container_read','container_list'})
    for name,args in [('container_write',{'path':'/work/no','text':'no'}),('container_exec',{'argv':['true']}),('evidence_inventory',{})]:
     with self.assertRaises(ProtocolError):server.call(name,args)
    self.assertEqual(server.calls,0);fake.exec.assert_not_called();fake.write.assert_not_called()
    server.call('container_read',{'path':'/inputs/a'});fake.read.assert_called_once();server.close()

if __name__=='__main__':unittest.main()
