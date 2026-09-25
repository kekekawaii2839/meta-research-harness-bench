"""Real 25-MiB artifact hashing and safety diagnostic; no model calls."""
import hashlib,json,subprocess
from pathlib import Path
from types import SimpleNamespace
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.container_runtime import ContainerSession,ArtifactHashError
from mrhbench.executor_broker import ExecutorBroker
from mrhbench.artifact_policy import make_collection_policy
from mrhbench.io import write_json,utc_now,file_hash

def main():
 root=Path('D:/mrhbench-local-pilot/stream-artifact-hash-20260923-001');root.mkdir(exist_ok=False)
 resources=dict(cpus=1,memory_mb=128,disk_mb=64,pids_limit=32,wall_seconds=90)
 expected=hashlib.sha256()
 for _ in range(25):expected.update(b'x'*1024*1024)
 report={'started':utc_now(),'new_model_calls':0,'diagnostic_resources':resources,'cases':{}}
 with ContainerSession(image_id='sha256:399341648ce68031cef84e225a8b4985fed3125fd020ec96a8d6c5d6563036d0',resources=resources,input_files={},audit_dir=root/'container') as session:
  cid=session.cid
  result=session.exec(['python','-I','-S','-c',"with open('/work/large.bin','wb') as f:\n for _ in range(25):f.write(b'x'*1048576)\nopen('/work/empty','wb').close()"])
  assert result['returncode']==0,result
  receipt=session.hash_file('/work/large.bin',max_bytes=25*1024*1024)
  assert receipt['bytes']==25*1024*1024 and receipt['sha256']==expected.hexdigest()
  report['cases']['25mib_stream_hash']=receipt
  view={'resources':{'container':resources,'artifact_collection':make_collection_policy(max_total_bytes=32*1024*1024,max_entries=1000)}}
  broker=SimpleNamespace(session=session,view=view)
  verified=ExecutorBroker.verify_artifacts(broker,[{'path':'large.bin','sha256':expected.hexdigest()}])
  report['cases']['broker_25mib_accepted']=verified
  def rejected(name,fn,code):
   try:fn()
   except ArtifactHashError as exc:
    assert exc.code==code,(name,exc.code);report['cases'][name]={'rejected':True,'code':exc.code}
   else:raise AssertionError(name+' unexpectedly passed')
  rejected('explicit_smaller_byte_quota',lambda:session.hash_file('/work/large.bin',max_bytes=24*1024*1024),'byte_limit_exceeded')
  rejected('outside_root',lambda:session.hash_file('/etc/passwd',max_bytes=1024),'unsafe_path')
  rejected('parent_traversal',lambda:session.hash_file('/work/../etc/passwd',max_bytes=1024),'unsafe_path')
  rejected('missing',lambda:session.hash_file('/work/missing',max_bytes=1024),'not_found')
  rejected('declared_false_hash',lambda:ExecutorBroker.verify_artifacts(broker,[{'path':'large.bin','sha256':'0'*64}]),'hash_mismatch')
  report['cases']['zero_byte_cap_empty']=session.hash_file('/work/empty',max_bytes=0)
  result=session.exec(['python','-I','-S','-c',"import os\nos.symlink('/etc/passwd','/work/link')\nos.symlink('/etc','/work/parent-link')\nos.mkfifo('/work/fifo')\nopen('/work/small','wb').write(b'x')\nos.link('/work/small','/work/hard')"])
  assert result['returncode']==0,result
  rejected('symlink',lambda:session.hash_file('/work/link',max_bytes=4096),'unsafe_path')
  rejected('intermediate_symlink',lambda:session.hash_file('/work/parent-link/passwd',max_bytes=4096),'unsafe_path')
  rejected('fifo_nonblocking',lambda:session.hash_file('/work/fifo',max_bytes=4096),'unsafe_file_type_or_link')
  rejected('hardlink',lambda:session.hash_file('/work/hard',max_bytes=4096),'unsafe_file_type_or_link')
 ps=subprocess.run(['docker','ps','-a','--no-trunc','--format','{{.ID}}'],capture_output=True,text=True,check=True);assert cid not in ps.stdout.splitlines()
 logs=list((root/'container').glob('*exec.json'));report['exec_stdout_max_bytes']=max((json.loads(p.read_text(encoding='utf8')).get('stdout_bytes',0) for p in logs),default=0)
 assert report['exec_stdout_max_bytes']<1024
 report.update(finished=utc_now(),owned_container_id=cid,owned_container_removed=True,passed=True,
   scope='Live file bytes streamed inside container in 64KiB chunks; host receives only receipt. No byte-content or base64 hashing response. Metadata checks reject common races but do not create atomic collection snapshots.',
   untested=['Adversarial timed in-place mutation stress','New runner end-to-end 25MiB artifact finalization after public policy migration'],
   old_materials_and_runs_modified=False)
 write_json(root/'results.json',report,exclusive=True)
 write_json(Path(__file__).resolve().parents[2]/'audit/stream_artifact_hash_acceptance_v1.json',report,exclusive=True)
 print(json.dumps({'passed':True,'cases':len(report['cases']),'max_stdout_bytes':report['exec_stdout_max_bytes'],'output':str(root/'results.json')}))

if __name__=='__main__':main()
