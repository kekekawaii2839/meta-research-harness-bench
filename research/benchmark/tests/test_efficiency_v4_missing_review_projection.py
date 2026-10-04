import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
import test_material_adapter as fixture
from mrhbench.io import write_json,read_json,file_hash,ProtocolError

p=Path(__file__).resolve().parents[1]/'scripts/active/prepare_efficiency_v4_missing_review_case.py'
spec=importlib.util.spec_from_file_location('missing_projection',p)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)


class MissingReviewProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.ws=self.root/'workspace';self.ws.mkdir()
        original,_=fixture.MaterialAdapterTests().fixture(self.root/'fixture')
        self.prior=self.ws/'construct/job/constructor/output'
        self.prior.parent.mkdir(parents=True);shutil.copytree(original,self.prior)
        package=read_json(self.prior/'package.json');package['coverage'].append(package['coverage'][2])
        write_json(self.prior/'package.json',package)
        source=self.ws/'original.txt';source.write_text('unaltered original source')
        self.job={'schema_version':'material-job-1','job_id':'job','paper_id':'p',
            'requested_task_types':['EXP'],'scope_request':'original order',
            'sources':[{'source_id':'s','local_path':'original.txt','sha256':file_hash(source),'url':'https://example.invalid/p','version':'1'}],
            'environment_candidate':{'gpu':False,'network':'none','scientific_rationale':'fixture',**package['environment']['resources']}}
        write_json(self.ws/'job.json',self.job)
        write_json(self.ws/'construct/job/receipt.json',{'job_id':'job','status':'failed_needs_attribution','error':{'message':'Explicit five-type coverage matrix required'}})
        self.audit=self.root/'entry.json';write_json(self.audit,{'fixture':True})
        self.dest=self.root/'new'

    def run_projection(self):
        return mod.prepare(self.ws,self.dest,task_id='t',notes=['Repair real coverage failure'],entry_audit=self.audit)

    def test_preserves_real_defect_bytes_and_missing_review(self):
        before=read_json(self.prior/'package.json');r=self.run_projection()
        candidate=self.dest/'prior/job/constructor/output'
        self.assertEqual(read_json(candidate/'package.json')['coverage'],before['coverage'])
        self.assertFalse((self.dest/'prior/job/reviewer').exists())
        for rel in ['assets/start.txt','environment/smoke.py','environment/image/Dockerfile']:
            self.assertEqual((candidate/rel).read_bytes(),(self.prior/rel).read_bytes())
        self.assertTrue(r['missing_prior_review']);self.assertFalse(r['prior_review_fabricated'])
        self.assertEqual((self.dest/'prior/job/receipt.json').read_bytes(),(self.ws/'construct/job/receipt.json').read_bytes())
        with self.assertRaises(ProtocolError):self.run_projection()

    def test_existing_review_rejected(self):
        review=self.ws/'construct/job/reviewer/review.json';write_json(review,{})
        with self.assertRaises(ProtocolError):self.run_projection()
        self.assertFalse(self.dest.exists())

    def test_unknown_failure_rejected(self):
        write_json(self.ws/'construct/job/receipt.json',{'job_id':'job','status':'failed_needs_attribution','error':{'message':'unknown'}})
        with self.assertRaises(ProtocolError):self.run_projection()
        self.assertFalse(self.dest.exists())

    def test_source_tamper_rejected_before_projection(self):
        (self.ws/'original.txt').write_text('changed')
        with self.assertRaises(ProtocolError):self.run_projection()
        self.assertFalse(self.dest.exists())


if __name__=='__main__':unittest.main()
