import io,json,sys,tarfile,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.container_runtime import ContainerSession,safe_artifact_extract,ArtifactHashError,FILE_HELPER
from mrhbench.io import ProtocolError


def archive(entries):
    data=io.BytesIO()
    with tarfile.open(fileobj=data,mode='w') as tf:
        for name,content,kind in entries:
            m=tarfile.TarInfo(name);m.type=kind
            if kind==tarfile.REGTYPE:m.size=len(content)
            if kind in (tarfile.SYMTYPE,tarfile.LNKTYPE):m.linkname=content.decode()
            tf.addfile(m,io.BytesIO(content) if kind==tarfile.REGTYPE else None)
    data.seek(0);return data

class ContainerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_collect_regular_preserves_hash(self):
        a=archive([('./x/a.json',b'{"a":1}',tarfile.REGTYPE)])
        r=safe_artifact_extract(a,self.root/'out',max_bytes=100,max_files=2)
        self.assertEqual(r['bytes'],7);self.assertEqual((self.root/'out/x/a.json').read_bytes(),b'{"a":1}')
    def test_link_traversal_special_and_alias_rejected(self):
        for i,(name,content,kind) in enumerate([('../evil',b'x',tarfile.REGTYPE),('/evil',b'x',tarfile.REGTYPE),
            ('x',b'/etc/passwd',tarfile.SYMTYPE),('x',b'a',tarfile.LNKTYPE),('x',b'',tarfile.FIFOTYPE),
            ('C:x',b'x',tarfile.REGTYPE),('CON',b'x',tarfile.REGTYPE),('a/../x',b'x',tarfile.REGTYPE)]):
            with self.assertRaises(ProtocolError):safe_artifact_extract(archive([(name,content,kind)]),self.root/str(i),max_bytes=100,max_files=10)
            self.assertFalse((self.root/str(i)).exists())
    def test_entire_manifest_validated_before_writes(self):
        a=archive([('good',b'ok',tarfile.REGTYPE),('bad',b'good',tarfile.SYMTYPE)])
        with self.assertRaises(ProtocolError):safe_artifact_extract(a,self.root/'out',max_bytes=100,max_files=10)
        self.assertFalse((self.root/'out').exists())
    def test_quota_and_case_collision_rejected(self):
        cases=[([('a',b'123',tarfile.REGTYPE)],2,10),
               ([('a',b'1',tarfile.REGTYPE),('b',b'2',tarfile.REGTYPE)],100,1),
               ([('a',b'1',tarfile.REGTYPE),('A',b'2',tarfile.REGTYPE)],100,10),
               ([('a',b'1',tarfile.REGTYPE),('a/b',b'2',tarfile.REGTYPE)],100,10)]
        for i,(entries,n,m) in enumerate(cases):
            with self.assertRaises(ProtocolError):safe_artifact_extract(archive(entries),self.root/str(i),max_bytes=n,max_files=m)
    def test_existing_destination_refused(self):
        with self.assertRaises(ProtocolError):safe_artifact_extract(archive([]),self.root,max_bytes=10,max_files=10)
    def test_resource_and_image_fail_closed(self):
        r=dict(cpus=1,memory_mb=64,disk_mb=8,pids_limit=16,wall_seconds=30)
        kwargs=dict(resources=r,input_files={},audit_dir=self.root/'audit')
        with self.assertRaises(ProtocolError):ContainerSession(image_id='python:latest',**kwargs)
        for key in r:
            x=dict(r);del x[key]
            with self.assertRaises(ProtocolError):ContainerSession(image_id='sha256:'+'a'*64,**dict(kwargs,resources=x))
    def test_no_reopen_or_calls_before_start(self):
        s=ContainerSession(image_id='sha256:'+'a'*64,resources=dict(cpus=1,memory_mb=64,disk_mb=8,pids_limit=16,wall_seconds=30),input_files={},audit_dir=self.root/'audit')
        with self.assertRaises(ProtocolError):s.exec(['true'])
        s.close()
        with self.assertRaises(ProtocolError):s.start()
    def test_absolute_deadline_validation_and_no_reset(self):
        import time
        resources=dict(cpus=1,memory_mb=64,disk_mb=8,pids_limit=16,wall_seconds=30)
        kwargs=dict(image_id='sha256:'+'a'*64,resources=resources,input_files={},audit_dir=self.root/'audit')
        deadline=time.monotonic()+20
        session=ContainerSession(**kwargs,deadline_monotonic=deadline)
        self.assertEqual(session.deadline,deadline)
        for bad in (True,float('nan'),float('inf'),time.monotonic()+40):
            with self.assertRaises(ProtocolError):ContainerSession(**kwargs,deadline_monotonic=bad)
        session=ContainerSession(**kwargs,deadline_monotonic=time.monotonic()-1)
        with self.assertRaises(ProtocolError):session.start()
        self.assertFalse((self.root/'audit').exists())

    def test_mismatched_input_hash_rejected_before_docker(self):
        p=self.root/'input';p.write_text('not expected')
        s=ContainerSession(image_id='sha256:'+'a'*64,resources=dict(cpus=1,memory_mb=64,disk_mb=8,pids_limit=16,wall_seconds=30),input_files={'input':p},input_hashes={'input':'a'*64},audit_dir=self.root/'audit')
        with self.assertRaises(ProtocolError):s.start()
        self.assertIsNone(s.cid)

    def test_hash_path_and_published_limit_fail_before_exec(self):
        s=ContainerSession(image_id='sha256:'+'a'*64,resources=dict(cpus=1,memory_mb=64,disk_mb=8,pids_limit=16,wall_seconds=30),input_files={},audit_dir=self.root/'audit')
        for path in ['/etc/passwd','/work/../inputs/a','/work/a//b','/work/a\\b','/work/','relative']:
            with self.assertRaises(ArtifactHashError) as e:s.hash_file(path,max_bytes=10)
            self.assertEqual(e.exception.code,'unsafe_path')
        for limit in [-1,True,8*1024*1024+1,1.5]:
            with self.assertRaises(ArtifactHashError) as e:s.hash_file('/work/x',max_bytes=limit)
            self.assertEqual(e.exception.code,'invalid_or_unpublished_limit')
        compile(FILE_HELPER,'file_helper','exec')

if __name__=='__main__':unittest.main()
