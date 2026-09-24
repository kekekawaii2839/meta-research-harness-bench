import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from mrhbench.execution_identity import public_input_identities
from mrhbench.io import ProtocolError, digest, write_json


class InputIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'assets').mkdir()
        self.data = b'alpha,beta\r\n1,2\r\n'
        (self.root/'assets/any-research-settings.csv').write_bytes(self.data)
        self.raw = hashlib.sha256(self.data).hexdigest()
        self.view = {'task_id':'x','asset_manifest':[{'asset_id':'a','path':'assets/any-research-settings.csv','sha256':self.raw}]}
        write_json(self.root/'task.json',self.view)
        self.manifest = {'owner':'private-controller-id','inputs':[{'path':'worker.py','bytes':10,'sha256':'0'*64}]}
        for name in ['task.json','assets/any-research-settings.csv']:
            data=(self.root/name).read_bytes()
            self.manifest['inputs'].append({'path':'public/'+name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})

    def run_check(self):
        return public_input_identities(self.view,self.manifest,self.root)

    def test_crlf_raw_hash_is_not_content_digest(self):
        result=self.run_check()
        self.assertEqual(result['identities'][1]['raw_sha256'],self.raw)
        self.assertNotEqual(self.raw,digest(self.data.decode()))
        self.assertNotEqual(self.raw,hashlib.sha256(self.data.replace(b'\r\n',b'\n')).hexdigest())
        self.assertNotIn('private-controller-id',str(result))
        self.assertNotIn('worker.py',str(result))

    def test_missing_duplicate_extra_private_rejected(self):
        base=copy.deepcopy(self.manifest)
        for change in ('missing','duplicate','extra','private'):
            self.manifest=copy.deepcopy(base)
            if change=='missing': self.manifest['inputs'].pop()
            elif change=='duplicate': self.manifest['inputs'].append(copy.deepcopy(base['inputs'][-1]))
            elif change=='extra': self.manifest['inputs'].append({'path':'public/private/answer.json','sha256':'0'*64,'bytes':1})
            else: self.manifest['inputs'][-1]['visibility']='private'
            with self.subTest(change=change),self.assertRaises(ProtocolError): self.run_check()

    def test_changed_released_bytes(self):
        (self.root/'assets/any-research-settings.csv').write_bytes(b'changed')
        with self.assertRaises(ProtocolError):self.run_check()

    def test_changed_view_and_raw_manifest(self):
        self.view['task_id']='different'
        with self.assertRaises(ProtocolError):self.run_check()

    def test_asset_hash_and_private_misclassification(self):
        self.view['asset_manifest'][0]['visibility']='private'
        with self.assertRaises(ProtocolError):self.run_check()
        del self.view['asset_manifest'][0]['visibility']
        self.view['asset_manifest'][0]['sha256']='1'*64
        with self.assertRaises(ProtocolError):self.run_check()

    def test_paths_and_byte_count_strict(self):
        for path in ('public/../secret','public//task.json','public/TASK.JSON'):
            old=self.manifest['inputs'][1]['path'];self.manifest['inputs'][1]['path']=path
            with self.assertRaises(ProtocolError):self.run_check()
            self.manifest['inputs'][1]['path']=old
        self.manifest['inputs'][1]['bytes']=True
        with self.assertRaises(ProtocolError):self.run_check()

    def test_zero_asset_task_works(self):
        self.view['asset_manifest']=[]
        write_json(self.root/'task.json',self.view)
        data=(self.root/'task.json').read_bytes()
        self.manifest['inputs']=[{'path':'public/task.json','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]
        self.assertEqual(len(self.run_check()['identities']),1)


if __name__=='__main__': unittest.main()
