import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.io import ProtocolError,write_json,file_hash,digest
from run_container_stage_development import model_action_records,output_inventory_for_run,run_stage,captured_artifact_records,frozen_bytes


class StageControllerEvidenceTests(unittest.TestCase):
    def test_crlf_bytes_and_record_hash_domains_are_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td);(run/'artifacts').mkdir();p=run/'artifacts/config.json'
            data=b'{\r\n  "alpha": 0.5\r\n}\r\n';p.write_bytes(data)
            write_json(run/'artifact_inventory.json',{'files':[{'path':p.name,'sha256':file_hash(p),'bytes':len(data)}]})
            records=captured_artifact_records(run);row=json.loads(records[-1]['content'])['files'][0]
            self.assertEqual(records[0]['content'],'ARTIFACT config.json\n'+data.decode('utf8'))
            self.assertEqual(row['evidence_content_sha256'],digest(records[0]['content']))
            self.assertEqual(row['sha256'],file_hash(p))
            self.assertNotEqual(row['sha256'],row['evidence_content_sha256'])
            self.assertFalse(row['content_transform']['newline_normalization'])
            self.assertEqual(frozen_bytes(p,row['sha256']),data)
            with self.assertRaises(ProtocolError):frozen_bytes(p,'0'*64)

    def test_inventory_cannot_read_outside_captured_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td);(run/'artifacts').mkdir();p=run/'outside.txt';p.write_text('synthetic nonartifact')
            write_json(run/'artifact_inventory.json',{'files':[{'path':'../outside.txt','sha256':file_hash(p),'bytes':p.stat().st_size}]})
            with self.assertRaises(ProtocolError):captured_artifact_records(run)
            write_json(run/'run.json',{'status':'completed_structural_development_check'})
            with self.assertRaises(ProtocolError):output_inventory_for_run('WRITE_EVIDENCE',run)

    def test_jsonl_is_available_and_other_formats_not_silently_lost(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td);(run/'artifacts').mkdir()
            data={'raw.jsonl':b'{"iteration":0}\n{"iteration":1}\n','binary.npy':b'BINARY','bad.txt':b'\xff\xfe'}
            rows=[]
            for name,content in data.items():
                path=run/'artifacts'/name;path.write_bytes(content)
                rows.append({'path':name,'sha256':file_hash(path),'bytes':len(content)})
            write_json(run/'artifact_inventory.json',{'files':rows})
            records=captured_artifact_records(run)
            self.assertEqual(len(records),2)
            self.assertTrue(records[0]['content'].endswith(data['raw.jsonl'].decode()))
            inventory=json.loads(records[1]['content'])['files']
            self.assertEqual(inventory[0]['evidence_id'],'artifact-0')
            self.assertIn('unsupported',inventory[1]['representation'])
            self.assertIn('encoding',inventory[2]['representation'])
            (run/'artifacts/raw.jsonl').write_text('changed')
            with self.assertRaises(ProtocolError):captured_artifact_records(run)

    def test_model_action_is_not_execution_and_local_errors_are_untrusted(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            event={'kind':'tool_denied','error':'relative .py required'}
            for seq in [1,2]:
                write_json(p/f'rpc-{seq:05d}.json',{'request':{'operation':'complete','sequence':seq,
                    'arguments':{'request':{'control':{'force_final':False},'event_history':[event]}}},
                    'response':{'ok':True,'value':{'response':{'kind':'tool','arguments':{'command':'not run'}}}}})
            records=model_action_records(p)
            self.assertEqual(len(records),3)
            self.assertIn('not executed artifacts',records[0]['content'])
            self.assertIn('not independently trusted',records[1]['content'])

    def test_empty_captured_outputs_are_not_missing_task_materials(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            write_json(p/'run.json',{'status':'completed_structural_development_check'})
            write_json(p/'artifact_inventory.json',{'files':[]})
            got=output_inventory_for_run('WRITE_EVIDENCE',p)
            self.assertEqual(got['missing_outputs'][0]['reason'],'solver_not_produced')
            self.assertTrue(got['evaluation_inputs_available'])
            self.assertIsNone(output_inventory_for_run('IDEA',p))

    def test_capture_hash_checked_not_solver_claim(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'artifacts').mkdir();(p/'artifacts/x.png').write_bytes(b'not a valid image')
            write_json(p/'run.json',{'status':'completed_structural_development_check'})
            write_json(p/'artifact_inventory.json',{'files':[{'path':'x.png','sha256':'0'*64}]})
            with self.assertRaises(ProtocolError):output_inventory_for_run('WRITE_EVIDENCE',p)
            write_json(p/'artifact_inventory.json',{'files':[{'path':'x.png','sha256':file_hash(p/'artifacts/x.png')}]})
            self.assertEqual(output_inventory_for_run('WRITE_EVIDENCE',p)['missing_outputs'],[])
            # Captured file is not claimed to be decoded pixels or scientifically valid.

    def test_dependency_failure_before_run_directory_or_model(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/'new-run'
            with patch('run_container_stage_development.load_task',return_value={'public':{'output_contract':{}},'private':{}}), \
                 patch('run_container_stage_development.validate_application_schema',side_effect=ImportError('dependency unavailable')):
                with self.assertRaises(ImportError):run_stage(td,'harness.py',output,'codex.exe')
            self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
