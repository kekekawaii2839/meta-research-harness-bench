import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.docker_pilot import resource_args,create_args
from mrhbench.io import ProtocolError

class DockerPilotTests(unittest.TestCase):
    def setUp(self):
        self.r={"cpus":2,"memory_mb":2048,"disk_mb":1024,"pids_limit":128,"wall_seconds":1200}
    def test_different_package_values_not_global(self):
        one=resource_args(self.r);two=resource_args(dict(self.r,cpus=1,memory_mb=1024,wall_seconds=600))
        self.assertNotEqual(one,two)
        self.assertEqual(one[one.index("--memory")+1],"2048m")
    def test_budget_fail_closed(self):
        for value in (0,-1,True,float('nan')):
            with self.assertRaises(ProtocolError):resource_args(dict(self.r,wall_seconds=value))
        r=dict(self.r);del r['disk_mb']
        with self.assertRaises(ProtocolError):resource_args(r)
    def test_nonroot_offline_readonly_release(self):
        with tempfile.TemporaryDirectory() as d:
            a=create_args('sha256:'+'a'*64,Path(d),self.r,'mrh-pilot-'+'b'*32)
            self.assertIn('--read-only',a);self.assertIn('10001:10001',a);self.assertIn('none',a)
            self.assertIn('ALL',a);self.assertIn('no-new-privileges=true',a)
            self.assertEqual(a.count('--mount'),1)
            self.assertIn('dst=/package,readonly',a[a.index('--mount')+1])
            self.assertNotIn('--privileged',a)
            self.assertIn('max-file=2',a)
            with self.assertRaises(ProtocolError):create_args('python:latest',Path(d),self.r,'mrh-pilot-'+'b'*32)
    def test_disk_not_granted_twice(self):
        import re
        a=resource_args(self.r)
        sizes=[int(re.search(r'size=(\d+)',a[i+1]).group(1)) for i,x in enumerate(a) if x=='--tmpfs']
        self.assertEqual(sum(sizes),1024*1024*1024)

if __name__=='__main__':unittest.main()
