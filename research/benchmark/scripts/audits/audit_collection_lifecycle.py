"""Synthetic end-to-end collection diagnostic, no research agent or model call."""
import hashlib
import json
from pathlib import Path
import subprocess
import uuid
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.artifact_policy import make_collection_policy
from mrhbench.container_executor import run_container_harness
from mrhbench.io import read_json, write_json, file_hash


def main():
    root=Path('D:/mrhbench-local-pilot')/('collection-lifecycle-'+uuid.uuid4().hex[:10])
    public=root/'public';public.mkdir(parents=True)
    image='sha256:92e6b0ef5cb3a149905fa097ae1d1ae3dd907cd19c796e057d3564d8a8fcfe01'
    resources={'cpus':1,'memory_mb':256,'disk_mb':64,'pids_limit':32,'wall_seconds':120}
    policy=make_collection_policy(max_total_bytes=32*1024**2,max_entries=20)
    write_json(public/'task.json',{'task_id':'synthetic-collection-no-science','task_type':'EXP',
        'resources':{'container':resources,'execution_budget':{'model_calls':1,'tool_calls':2,'wall_seconds':120},
                     'image_id':image,'artifact_collection':policy},
        'asset_manifest':[],'tools':[],'output_contract':{}})
    harness='''def run(task_view, model_client, tool_client, budget):
    import hashlib
    from pathlib import Path
    p=Path('outputs/large.bin');p.parent.mkdir()
    h=hashlib.sha256()
    with p.open('wb') as f:
        for _ in range(25):
            block=b'x'*(1024*1024);f.write(block);h.update(block)
    return {'status':'completed','content':{'synthetic':True},
            'artifacts':[{'path':str(p),'sha256':h.hexdigest()}],'omissions':[]}
'''
    (root/'harness.py').write_text(harness,encoding='utf8')
    class NoProvider:
        def complete(self,*args,**kwargs):raise AssertionError('Diagnostic must not call any model')
    submission=run_container_harness(harness=root/'harness.py',public_root=public,image_id=image,
        provider=NoProvider(),output=root/'run',max_artifact_bytes=policy['max_total_bytes'],max_artifact_files=policy['max_entries'])
    inventory=read_json(root/'run/artifact_inventory.json')
    state=read_json(root/'run/run.json');invocation=read_json(root/'run/invocation.json')
    expected=hashlib.sha256(b'x'*(25*1024**2)).hexdigest()
    cleanup=[]
    for p in (root/'run/container').glob('*-create.json'):
        cid=read_json(p).get('stdout','').strip()
        if len(cid)!=64:continue
        result=subprocess.run(['docker','inspect',cid],capture_output=True,text=True)
        cleanup.append({'container_id':cid,'absent':result.returncode!=0 and 'No such' in result.stderr})
    checks={'large_file_hash_verified':submission['artifacts'][0]['sha256']==expected,
        'captured_large_file_exact':file_hash(root/'run/artifacts/outputs/large.bin')==expected,
        'published_policy_matches_invocation':invocation['artifact_collection']==policy,
        'no_provider_calls':state['budget']['used']['model']==0,
        'completed_lifecycle':state['status']=='completed_structural_development_check',
        'owned_container_cleaned':bool(cleanup) and all(x['absent'] for x in cleanup)}
    record={'root':str(root),'scope':'Synthetic controller regression; NOT a new H0/scientific run',
        'new_model_calls':0,'checks':checks,'passed':all(checks.values()),'cleanup':cleanup,
        'inventory':inventory,'task_sha256':file_hash(public/'task.json')}
    write_json(root/'results.json',record,exclusive=True)
    print(json.dumps({'root':str(root),'passed':record['passed'],'checks':checks}))
    if not record['passed']:raise RuntimeError('Collection diagnostic failed')


if __name__=='__main__':main()
