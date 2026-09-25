"""Real bounded CPU container diagnostics; never evaluates scientific quality."""
from __future__ import annotations
import argparse,json,subprocess,time,traceback
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.container_runtime import ContainerSession
from mrhbench.io import ProtocolError,write_json,file_hash,utc_now

CGROUP = r'''import pathlib,json
p=pathlib.Path('/sys/fs/cgroup')
keys=['memory/memory.limit_in_bytes','memory/memory.memsw.limit_in_bytes','memory/memory.failcnt','memory/memory.memsw.failcnt','memory/memory.oom_control','memory/memory.max_usage_in_bytes','pids/pids.max','pids/pids.current','pids/pids.events','cpu/cpu.cfs_quota_us','cpu/cpu.cfs_period_us','cpu/cpu.stat','memory.max','pids.max','cpu.max']
print(json.dumps({k:(p/k).read_text().strip() for k in keys if (p/k).is_file()}))'''


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--destination',type=Path,required=True)
    ap.add_argument('--image',default='sha256:92e6b0ef5cb3a149905fa097ae1d1ae3dd907cd19c796e057d3564d8a8fcfe01')
    args=ap.parse_args();root=args.destination.absolute();root.mkdir(parents=True,exist_ok=False)
    r=dict(cpus=.5,memory_mb=64,disk_mb=4,pids_limit=16,wall_seconds=90)
    public=root/'public.txt';public.write_text('only this public input is released')
    canary=root/'private-host-canary.txt';canary.write_text('private-'+str(time.time_ns()))
    results={'started':utc_now(),'scope':'synthetic CPU runtime diagnostics, not scientific task performance',
             'image':args.image,'diagnostic_resources':r,'cases':{},'formal_full_isolation_accepted':False}
    ids=[]
    def session(name,**changes):
        obj=ContainerSession(image_id=args.image,resources=dict(r,**changes),input_files={'public.txt':public},
                             input_hashes={'public.txt':file_hash(public)},audit_dir=root/name)
        return obj
    def check(name,fn):
        try:results['cases'][name]={'passed':True,'observations':fn()}
        except Exception as e:results['cases'][name]={'passed':False,'error':str(e),'traceback':traceback.format_exc()}
        write_json(root/'results.json',results)
    def basic():
        with session('basic') as s:
            ids.append(s.cid)
            assert s.read('/inputs/public.txt')==public.read_bytes()
            s.write('/work/nested/state.txt',b'hello');assert s.read('/work/nested/state.txt')==b'hello'
            assert s.list('/work/nested')[0]['name']=='state.txt'
            out=s.exec(['python','-I','-S','-c',r'''import pathlib,os,json,socket
assert os.getuid()==10001
assert sorted(p.name for p in pathlib.Path('/sys/class/net').iterdir())==['lo']
for path in ['/inputs/forbidden','/etc/forbidden']:
 try:pathlib.Path(path).write_text('unexpected')
 except OSError:pass
 else:raise AssertionError(path)
for path in ['/var/run/docker.sock','/run/docker.sock','/run/secrets','/host_mnt','/mnt/host','/run/desktop/mnt/host']:
 assert not pathlib.Path(path).exists(),path
assert not pathlib.Path('/inputs/private-host-canary.txt').exists()
assert not any(k.startswith(('OPENAI','CODEX','CHATGPT')) or k.endswith(('API_KEY','ACCESS_TOKEN','AUTH_TOKEN')) for k in os.environ)
sock=socket.socket();sock.settimeout(1)
try:sock.connect(('1.1.1.1',443))
except OSError:pass
else:raise AssertionError('external connection')
status=pathlib.Path('/proc/self/status').read_text()
assert 'NoNewPrivs:\t1' in status
assert next(x for x in status.splitlines() if x.startswith('CapEff:')).split()[1]=='0000000000000000'
print(json.dumps({'uid':os.getuid(),'read_only':True,'network_none':True,'selected_host_probes_denied':True}))'''])
            assert out['returncode']==0,out
            c=s.exec(['python','-I','-S','-c',CGROUP]);cg=json.loads(c['stdout'])
            assert int(cg['memory/memory.limit_in_bytes'])==64*1024*1024,cg
            assert int(cg['memory/memory.memsw.limit_in_bytes'])==64*1024*1024,cg
            assert int(cg['pids/pids.max'])==16,cg
            assert int(cg['cpu/cpu.cfs_quota_us'])/int(cg['cpu/cpu.cfs_period_us'])==.5,cg
            artifacts=s.artifacts(root/'basic-collected',max_bytes=4096,max_files=50)
            assert (root/'basic-collected/nested/state.txt').read_bytes()==b'hello'
            assert artifacts['bytes']==5,artifacts
            h=s.start_process(['python','-c','import time; print("background");time.sleep(.5)'])
            until=time.monotonic()+5
            while time.monotonic()<until:
                poll=s.poll_process(h)
                if poll['status']=='reported_complete':break
                time.sleep(.1)
            assert poll['reported']['returncode']==0,poll
            assert s.exec(['python','-c','print("independent tool call")'])['returncode']==0
            return {'cgroup_direct_read':cg,'security':json.loads(out['stdout']),'artifacts':artifacts,'background':poll}
    def binary_and_atomic():
        import hashlib
        with session('binary-atomic',memory_mb=128,disk_mb=32) as s:
            ids.append(s.cid)
            out=s.exec(['python','-I','-S','-c','with open("/work/image-bytes.bin","wb") as f:\n for i in range(20):f.write(bytes(range(256))*4096)'])
            assert out['returncode']==0,out
            data=s.read('/work/image-bytes.bin',max_bytes=20*1024*1024)
            expected=hashlib.sha256(bytes(range(256))*4096*20).hexdigest()
            assert len(data)==20*1024*1024 and hashlib.sha256(data).hexdigest()==expected
            result=s.write('/work/response.json',b'{"iteration":0}')
            assert result['atomic_replace'] is True
            handle=s.start_process(['python','-I','-S','-c',r'''import time,json
until=time.monotonic()+3;n=0
while time.monotonic()<until:
 with open('/work/response.json') as f:x=json.load(f)
 assert isinstance(x['iteration'],int);n+=1
print(json.dumps({'successful_concurrent_reads':n}))'''])
            for i in range(8):s.write('/work/response.json',json.dumps({'iteration':i}).encode())
            time.sleep(3)
            status=s.poll_process(handle);assert status['reported']['returncode']==0,status
            receipt_files=list((root/'binary-atomic').glob('*read_binary_receipt.json'))
            receipt=json.loads(receipt_files[0].read_text())
            assert receipt['stdout']=='' and receipt['bytes']==20*1024*1024
            return {'binary_bytes':len(data),'sha256':expected,'binary_not_in_audit_stdout':True,'atomic_writes':True,'concurrent_reader':status}
    def fresh():
        with session('fresh') as s:
            ids.append(s.cid);assert s.list()==[]
            return {'work_entries':[],'new_container':s.cid}
    def oom():
        with session('memory') as s:
            ids.append(s.cid)
            out=s.exec(['python','-I','-S','-c','print("allocating bounded diagnostic",flush=True); a=bytearray(256*1024*1024);print(len(a))'])
            after=s.exec(['python','-I','-S','-c',CGROUP]);cg=json.loads(after['stdout'])
            assert out['returncode']==137,out
            assert int(cg.get('memory/memory.memsw.failcnt','0'))>0 or 'oom_kill 1' in cg.get('memory/memory.oom_control',''),cg
            return {'allocation_returncode':out['returncode'],'cgroup_after':cg}
    def pids():
        with session('pids') as s:
            ids.append(s.cid)
            out=s.exec(['python','-I','-S','-c',r'''import subprocess,json,errno,pathlib
children=[];error=None
try:
 for i in range(40):
  try:children.append(subprocess.Popen(['python','-I','-S','-c','import time;time.sleep(10)']))
  except OSError as e:error=e.errno;break
 print(json.dumps({'children_started':len(children),'errno':error,'pids_current':pathlib.Path('/sys/fs/cgroup/pids/pids.current').read_text().strip(),'events':pathlib.Path('/sys/fs/cgroup/pids/pids.events').read_text().strip()}))
finally:
 for child in children:child.kill()
 for child in children:child.wait()
assert error==errno.EAGAIN'''])
            assert out['returncode']==0,out
            x=json.loads(out['stdout']);assert int(x['pids_current'])==16,x
            return x
    def storage():
        with session('storage',memory_mb=128) as s:
            ids.append(s.cid)
            out=s.exec(['python','-I','-S','-c',r'''import os,errno,json
n=0;error=None
try:
 with open('/work/fill','wb',buffering=0) as f:
  for i in range(16):n+=f.write(b'x'*(1024*1024))
except OSError as e:error=e.errno
v=os.statvfs('/work');print(json.dumps({'written':n,'errno':error,'filesystem_bytes':v.f_blocks*v.f_frsize,'available':v.f_bavail*v.f_frsize}))
assert error==errno.ENOSPC'''])
            assert out['returncode']==0,out
            return json.loads(out['stdout'])
    def artifacts_reject():
        with session('artifact-reject') as s:
            ids.append(s.cid)
            assert s.exec(['python','-I','-S','-c','import os;os.symlink("/inputs/public.txt","/work/link")'])['returncode']==0
            rejected=False
            try:s.artifacts(root/'must-not-exist-link',max_bytes=4096)
            except ProtocolError:rejected=True
            assert rejected and not (root/'must-not-exist-link').exists()
            assert s.exec(['python','-I','-S','-c','import os;os.unlink("/work/link");open("/work/big","wb").write(b"x"*2000)'])['returncode']==0
            rejected=False
            try:s.artifacts(root/'must-not-exist-quota',max_bytes=1024)
            except ProtocolError:rejected=True
            assert rejected and not (root/'must-not-exist-quota').exists()
            return {'linked_file_rejected':True,'artifact_byte_quota_rejected':True}
    def timeout():
        with session('timeout') as s:
            ids.append(s.cid)
            out=s.exec(['python','-I','-S','-c','import time;time.sleep(30)'],timeout=1)
            assert out['timed_out'],out
            state=json.loads(subprocess.check_output(['docker','inspect','--format','{{json .State}}',s.cid],text=True))
            assert not state['Running'],state
            return {'command_timeout':True,'daemon_state':state}
    def idle_deadline():
        with session('idle-deadline',wall_seconds=3) as s:
            ids.append(s.cid);time.sleep(4)
            until=time.monotonic()+15
            while time.monotonic()<until:
                state=json.loads(subprocess.check_output(['docker','inspect','--format','{{json .State}}',s.cid],text=True))
                if not state['Running']:break
                time.sleep(.1)
            assert s.expired.is_set() and not state['Running'],state
            return {'model_idle_counts_toward_deadline':True,'daemon_state':state}
    def output_cap():
        with session('output-cap') as s:
            ids.append(s.cid)
            out=s.exec(['python','-I','-S','-c','import sys;sys.stdout.write("x"*(4*1024*1024))'])
            assert out['output_limited'] and len(out['stdout'].encode())<=s.max_log_bytes,out
            return {'captured_bytes':len(out['stdout']),'observed_bytes':out['stdout_bytes'],'session_expired':s.expired.is_set()}
    for name,fn in [('lifecycle_and_isolation',basic),('binary_and_atomic_write',binary_and_atomic),('cross_task_fresh_state',fresh),('memory_limit',oom),('pid_limit',pids),('writable_storage_limit',storage),('artifact_rejection',artifacts_reject),('timeout_kills_daemon_work',timeout),('idle_deadline',idle_deadline),('bounded_output',output_cap)]:check(name,fn)
    remaining=[]
    for cid in ids:
        p=subprocess.run(['docker','inspect',cid],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if p.returncode==0:remaining.append(cid)
    results['owned_containers_remaining']=remaining
    results['passed']=all(x['passed'] for x in results['cases'].values()) and not remaining
    results['finished']=utc_now()
    results['limitations']=['No kernel escape proof','No model authentication broker audited here','Artifact capture is not an atomic filesystem snapshot','Detached process status remains solver-writable/untrusted','Only selected host probes; not a complete adversarial isolation audit']
    write_json(root/'results.json',results)
    print(json.dumps({'destination':str(root),'passed':results['passed'],'cases':{k:v['passed'] for k,v in results['cases'].items()},'owned_containers_remaining':remaining}))
    return 0 if results['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
