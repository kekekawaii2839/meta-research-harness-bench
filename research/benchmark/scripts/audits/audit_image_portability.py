"""Same-host image byte delivery rehearsal, NOT cross-host reproducibility."""
from __future__ import annotations
import argparse,json,shutil,subprocess,tarfile,traceback
from pathlib import Path
from types import SimpleNamespace
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.container_runtime import ContainerSession
from mrhbench.executor_broker import ExecutorBroker
from mrhbench.io import file_hash,utc_now,write_json,ProtocolError

IMAGES={'iv':'sha256:92e6b0ef5cb3a149905fa097ae1d1ae3dd907cd19c796e057d3564d8a8fcfe01',
        'ssa':'sha256:399341648ce68031cef84e225a8b4985fed3125fd020ec96a8d6c5d6563036d0'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--destination',type=Path,required=True)
 ap.add_argument('--reuse-export',type=Path);ap.add_argument('--expected-export-sha');args=ap.parse_args()
 root=args.destination.resolve();root.mkdir(parents=True,exist_ok=False)
 result={'started':utc_now(),'scope':'Same-host docker save/load by exact image ID; existing daemon layers remain present, NOT a clean-host import or cross-host numerical/kernel equivalence test.',
         'new_model_calls':0,'pulls':0,'image_removals':0,'gpu_used':False,'cases':{},'container_ids':[]}
 def command(argv,timeout=60):
  p=subprocess.run(argv,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=timeout)
  row={'argv':argv,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
  result.setdefault('commands',[]).append(row);write_json(root/'results.json',result)
  if p.returncode:raise RuntimeError(row)
  return p.stdout
 def disk():
  d=shutil.disk_usage(root);return {'total':d.total,'used':d.used,'free':d.free}
 result['disk_before']=disk()
 if result['disk_before']['free']<2*1024**3:raise RuntimeError('Require at least 2 GiB available for bounded export')
 try:
  before=json.loads(command(['docker','image','inspect',*IMAGES.values()]))
  result['images_before']=before
  result['host']=json.loads(command(['docker','info','--format','{{json .}}']))
  archive=args.reuse_export or root/'iv-ssa-frozen-images.tar'
  if args.reuse_export:
   if not args.expected_export_sha or file_hash(archive)!=args.expected_export_sha:raise RuntimeError('Reused export hash mismatch')
  else:command(['docker','image','save','--output',str(archive),*IMAGES.values()],600)
  result['export']={'path':str(archive),'sha256':file_hash(archive),'logical_bytes':archive.stat().st_size}
  with tarfile.open(archive,'r:') as tf:
   manifest_member=tf.getmember('manifest.json')
   if manifest_member.size>1024*1024:raise RuntimeError('Unexpected oversized export manifest')
   manifest=json.load(tf.extractfile(manifest_member))
   result['tar_manifest']=manifest
   layers=[x for entry in manifest for x in entry['Layers']]
   unique=set(layers)
   result['export_layers']={'references':len(layers),'unique_paths':len(unique),
      'unique_member_bytes':sum(tf.getmember(p).size for p in unique),
      'note':'Both images saved together. Shared layer paths counted once. Tar bytes include metadata; image reported sizes and host VHDX allocated bytes are different quantities.'}
  command(['docker','image','load','--input',str(archive)],600)
  after=json.loads(command(['docker','image','inspect',*IMAGES.values()]))
  for b,a in zip(before,after):
   for key in ['Id','RootFS','Architecture','Os']:assert a[key]==b[key],key
  result['images_after']=after;result['identity_and_layers_preserved']=True
  for name,image in IMAGES.items():
   resources=dict(cpus=1,memory_mb=512,disk_mb=32,pids_limit=32,wall_seconds=90)
   code='''import json,sys,numpy as np
x=np.arange(1.,6.);y=2*x+1
b=np.linalg.lstsq(np.column_stack([np.ones(5),x]),y,rcond=None)[0]
assert np.allclose(b,[1,2],rtol=0,atol=1e-12)
result={'python':sys.version,'numpy':np.__version__,'ols_coefficients':b.tolist()}
'''
   if name=='ssa':code+='''import csv,io,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
rows=list(csv.DictReader(io.StringIO('x,y\\n1,3\\n2,5\\n')));assert len(rows)==2
plt.plot(x,y);plt.savefig('/work/smoke.png');plt.close()
result.update(csv_rows=len(rows),matplotlib=matplotlib.__version__)
'''
   code+='print(json.dumps(result))'
   with ContainerSession(image_id=image,resources=resources,input_files={},audit_dir=root/(name+'-session')) as session:
    result['container_ids'].append(session.cid)
    observed=session.exec(['python','-I','-c',code]);assert observed['returncode']==0,observed
    session.write('/work/claimed.txt',b'actual immutable captured bytes\n')
    fake='0'*64
    session.write('/work/solver-claimed-inventory.json',json.dumps({'path':'claimed.txt','sha256':fake}).encode())
    inventory=session.artifacts(root/(name+'-artifacts'),max_bytes=1024*1024,max_files=20,exclude_internal=True)
    row=next(r for r in inventory['files'] if r['path']=='claimed.txt')
    recomputed=file_hash(root/(name+'-artifacts')/'claimed.txt')
    assert row['sha256']==recomputed and recomputed!=fake
    try:ExecutorBroker.verify_artifacts(SimpleNamespace(session=session),[{'path':'claimed.txt','sha256':fake}])
    except ProtocolError as e:assert 'hash mismatch' in str(e)
    else:raise AssertionError('Broker accepted forged artifact hash')
    ExecutorBroker.verify_artifacts(SimpleNamespace(session=session),[{'path':'claimed.txt','sha256':recomputed}])
    result['cases'][name]={'passed':True,'image_id':image,'diagnostic_resources_not_scientific_budget':resources,'smoke':json.loads(observed['stdout']),
      'artifact_inventory':inventory,'forged_hash_probe':{'solver_claim':fake,'controller_captured_hash':row['sha256'],'independent_host_rehash':recomputed,'mismatch_detected':True,
         'broker_verifier_rejects_fake_accepts_true':True,'scope':'Actual ContainerSession collection hashes captured bytes; actual ExecutorBroker.verify_artifacts rejects false and accepts true hash against a live session. No full run_container_harness submission trajectory.'}}
   write_json(root/'results.json',result)
  still=command(['docker','ps','-a','--no-trunc','--format','{{.ID}}']).splitlines()
  result['owned_containers_remaining']=[cid for cid in result['container_ids'] if cid in still]
  assert not result['owned_containers_remaining']
  result['passed']=True
 except Exception as exc:
  result['passed']=False;result['error']=str(exc);result['traceback']=traceback.format_exc()
 finally:
  result['finished']=utc_now();result['disk_after']=disk()
  result['output_directory_logical_bytes']=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
  result['disk_measurement_limits']='Free-space difference is a host interval observation including concurrent work, not isolated project allocation. No VHDX allocation attribution is made.'
  write_json(root/'results.json',result)
 print(json.dumps({'passed':result['passed'],'result':str(root/'results.json'),'export':result.get('export'),'disk_after':result['disk_after']}))
 if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
