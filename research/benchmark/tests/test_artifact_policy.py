import copy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.artifact_policy import collection_policy,make_collection_policy
from mrhbench.container_executor import run_container_harness
from mrhbench.io import ProtocolError,write_json
from mrhbench.io import read_json,file_hash
from prepare_collection_contract import prepare


class ArtifactPolicyTests(unittest.TestCase):
    def test_versioned_migration_copies_only_manifest_assets(self):
        source=Path(__file__).resolve().parents[1]/'materials/pilot_v3/released_stage_candidates/lit'
        before=file_hash(source/'task.json')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'new'
            record=prepare(source,out,max_total_bytes=16*1024**2,max_entries=500)
            task=read_json(out/'task.json')
            self.assertTrue(record['execution_budget_unchanged'])
            self.assertTrue(record['container_resources_unchanged'])
            files={p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
            self.assertEqual(files,{'task.json','collection_contract_provenance.json'}|{x['path'] for x in task['assets']})
            self.assertFalse((out/'release').exists())
            self.assertEqual(file_hash(source/'task.json'),before)
            with self.assertRaises(ProtocolError):prepare(source,out,max_total_bytes=16*1024**2,max_entries=500)

    def test_explicit_per_package_limits_and_fail_closed(self):
        for disk,total,entries in [(32,1000,10),(1024,64*1024*1024,2000)]:
            resources={'container':{'disk_mb':disk},'artifact_collection':make_collection_policy(max_total_bytes=total,max_entries=entries)}
            self.assertEqual(collection_policy(resources)['max_total_bytes'],total)
            for key,value in [('max_total_bytes',True),('max_total_bytes',disk*1024*1024+1),('max_entries',100001),('max_entries',False),('scope','all_files')]:
                wrong=copy.deepcopy(resources);wrong['artifact_collection'][key]=value
                with self.assertRaises(ProtocolError):collection_policy(wrong)
        with self.assertRaises(ProtocolError):collection_policy({'container':{'disk_mb':32}})

    def test_controller_mismatch_rejected_before_output_or_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);public=root/'public';public.mkdir()
            write_json(public/'task.json',{'resources':{'container':{'disk_mb':32},'execution_budget':{},
                'artifact_collection':make_collection_policy(max_total_bytes=1000,max_entries=10)}})
            with self.assertRaisesRegex(ProtocolError,'differ'):
                run_container_harness(harness=root/'absent.py',public_root=public,image_id='unused',provider=None,output=root/'run',max_artifact_bytes=999,max_artifact_files=10)
            self.assertFalse((root/'run').exists())


if __name__=='__main__':unittest.main()
