import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.evolution_native import NativeDevelopmentBuilder,released_builder_inputs
from mrhbench.io import ProtocolError,write_json,read_json


class NativeBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.stage=self.root/'stage';self.stage.mkdir()
        for folder in ['harness','search','search_evidence']:(self.stage/folder).mkdir()
        (self.stage/'harness/harness.py').write_text('INITIAL=True')
        (self.stage/'search/task.json').write_text('{"public":true}')
        (self.stage/'search_evidence/receipt.json').write_text('{"public_receipt":"abc"}')
        (self.stage/'PRIVATE-controller.json').write_text('CANARY_SHOULD_NOT_ENTER_CONTAINER')
        self.request={'development':True,'operation':'evolve-H0','workspace':str(self.stage),
            'current_harness':str(self.stage/'harness'),'search_directory':str(self.stage/'search'),
            'public_evidence_directory':str(self.stage/'search_evidence'),'output_directory':str(self.stage/'output'),
            'builder_view':{'phase':'search','search_tasks':['a'],'versions':[{'version_id':'H0','hash':'a'*64}],
                            'search_scores':{},'search_feedback':{}}}
        self.sessions=[];self.runners=[];self.mode='normal'
        owner=self
        class Session:
            def __init__(self,**kwargs):
                self.kwargs=kwargs;self.resources=kwargs['resources'];self.closed=False;self.cid='fake-container';self.owner='fake-owner';self.deadline=99999999;self.remaining_seconds=100
                owner.sessions.append(self)
            def start(self):return self
            def close(self):self.closed=True
            def artifacts(self,destination,**kwargs):
                p=Path(destination)/'candidate';p.mkdir(parents=True)
                (p/'harness.py').write_text('IMPROVED=True')
                if owner.mode!='missing':write_json(p/'change_manifest.json',{'synthetic':True})
                return {'files':[],'synthetic':True}
        class Runner:
            def __init__(self,**kwargs):self.kwargs=kwargs;owner.runners.append(self)
            def run(self,**kwargs):
                self.request=kwargs
                if owner.mode=='raise':raise ProtocolError('synthetic native failure')
                response={'version_id':'H99' if owner.mode=='bad_choice' else 'H0','reason':'Visible search evidence only'}
                return {'call_id':'synthetic-no-model','response':response if kwargs.get('output_schema') else json.dumps(response)}
        self.args={'binary':self.root/'not-executed.exe','ledger':None,'audit_root':self.root/'audit',
            'image_id':'sha256:'+'a'*64,'resources':{'cpus':1,'memory_mb':256,'disk_mb':32,'pids_limit':32,'wall_seconds':120},
            'native_timeout_seconds':100,'max_tool_calls':30,'max_artifact_bytes':1024**2,'max_artifact_entries':100,
            'session_factory':Session,'runner_factory':Runner}

    def test_releases_only_explicit_staged_public_inputs(self):
        inputs=released_builder_inputs(self.request,self.root/'release')
        self.assertEqual(set(inputs),{'previous/harness.py','search/task.json','search_evidence/receipt.json','builder_view.json'})
        self.assertNotIn('CANARY_SHOULD_NOT_ENTER_CONTAINER',''.join(p.read_text() for p in inputs.values()))
        wrong=copy.deepcopy(self.request);wrong['private_test']=str(self.root/'secret')
        with self.assertRaises(ProtocolError):released_builder_inputs(wrong,self.root/'other')
        wrong=copy.deepcopy(self.request);wrong['search_directory']=str(self.root)
        with self.assertRaises(ProtocolError):released_builder_inputs(wrong,self.root/'other2')
        wrong=copy.deepcopy(self.request);wrong['output_directory']=str(self.stage/'search/output')
        with self.assertRaises(ProtocolError):released_builder_inputs(wrong,self.root/'other3')

    def test_native_edit_publishes_exact_candidate_and_no_retries(self):
        builder=NativeDevelopmentBuilder(**self.args);r=builder.evolve(request=self.request)
        self.assertEqual(r['candidate_relative_path'],'output/candidate')
        self.assertEqual({x['path'] for x in r['files']},{'harness.py','change_manifest.json'})
        self.assertTrue(self.sessions[0].closed)
        self.assertEqual(self.runners[0].kwargs['model'],'gpt-5.6-sol')
        self.assertEqual(self.runners[0].kwargs['reasoning_effort'],'medium')
        self.assertEqual(self.runners[0].kwargs['tool_profile'],'bounded_mcp')
        self.assertIsNotNone(self.runners[0].kwargs['hook_guard'])
        self.assertNotIn(str(self.stage),self.runners[0].request['prompt'])
        self.assertEqual(list(self.runners[0].request['workspace'].iterdir()),[])
        with self.assertRaises(ProtocolError):builder.evolve(request=self.request)
        self.assertEqual(len(self.runners),1)

    def test_selection_has_read_only_tools_and_version_schema(self):
        r=copy.deepcopy(self.request);r['operation']='select'
        choice=NativeDevelopmentBuilder(**self.args).select(request=r)
        self.assertEqual(choice['version_id'],'H0')
        tools=self.runners[0].kwargs['mcp_servers']['mrhbench']['enabled_tools']
        self.assertEqual(tools,['container_read','container_list'])
        self.assertEqual(self.runners[0].request['output_schema']['properties']['version_id']['enum'],['H0'])
        self.assertFalse((self.stage/'output').exists());self.assertTrue(self.sessions[0].closed)

    def test_empty_evidence_directory_has_truthful_controller_inventory(self):
        (self.stage/'search_evidence/receipt.json').unlink()
        request=copy.deepcopy(self.request);request['operation']='select'
        NativeDevelopmentBuilder(**self.args).select(request=request)
        inventory=self.sessions[0].kwargs['input_files']['search_evidence/_controller_availability.json']
        self.assertEqual(read_json(inventory)['released_evidence_file_count'],0)
        self.assertEqual(list((self.stage/'search_evidence').iterdir()),[])

    def test_native_failure_closes_without_retry_or_zero(self):
        self.mode='raise';builder=NativeDevelopmentBuilder(**self.args)
        with self.assertRaisesRegex(ProtocolError,'synthetic native'):builder.evolve(request=self.request)
        self.assertTrue(self.sessions[0].closed)
        failure=read_json(next((self.root/'audit').glob('*/failure.json')))
        self.assertFalse(failure['automatic_scientific_zero']);self.assertFalse(failure['automatic_retry'])
        with self.assertRaises(ProtocolError):builder.evolve(request=self.request)
        self.assertEqual(len(self.runners),1)

    def test_missing_candidate_is_not_published(self):
        self.mode='missing'
        with self.assertRaises((ProtocolError,FileNotFoundError)):NativeDevelopmentBuilder(**self.args).evolve(request=self.request)
        self.assertFalse((self.stage/'output/candidate').exists());self.assertTrue(self.sessions[0].closed)

    def test_unknown_selection_rejected(self):
        self.mode='bad_choice';r=copy.deepcopy(self.request);r['operation']='select'
        with self.assertRaises(ProtocolError):NativeDevelopmentBuilder(**self.args).select(request=r)

    def test_invalid_configuration_before_native_invocation(self):
        for changed in [{'image_id':'python:latest'},{'native_timeout_seconds':120},{'max_tool_calls':True},{'max_artifact_bytes':100*1024**2}]:
            with self.assertRaises(ProtocolError):NativeDevelopmentBuilder(**(self.args|changed))
        for field,value in [('cpus',0),('memory_mb',-1),('pids_limit',0),('wall_seconds',float('inf'))]:
            with self.assertRaises(ProtocolError):
                NativeDevelopmentBuilder(**(self.args|{'resources':self.args['resources']|{field:value}}))
        self.assertEqual(self.runners,[])


if __name__=='__main__':unittest.main()
