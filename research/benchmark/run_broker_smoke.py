"""CPU-only synthetic RPC test, fake provider: no subscription model calls."""
import json
import uuid
from pathlib import Path
from mrhbench.container_executor import run_container_harness
from mrhbench.io import write_json

if __name__ == '__main__':
    root=Path('D:/mrhbench-local-pilot')/('broker-smoke-'+uuid.uuid4().hex[:10]);root.mkdir()
    public=root/'public';public.mkdir()
    resources={'cpus':1,'memory_mb':256,'disk_mb':32,'pids_limit':32,'wall_seconds':180}
    write_json(public/'task.json',{'task_id':'synthetic-broker-smoke','task_type':'EXP','resources':{'image_id':'sha256:92e6b0ef5cb3a149905fa097ae1d1ae3dd907cd19c796e057d3564d8a8fcfe01','container':resources,'execution_budget':{'model_calls':1,'tool_calls':4,'wall_seconds':180}},'asset_manifest':[],'tools':['artifact_read_write','cpu_python_execution'],'output_contract':{}})
    (root/'harness.py').write_text('''def run(task_view, model_client, tool_client, budget):
    remaining=budget.remaining()
    tool_client.call("artifact.write_text",{"path":"smoke.py","text":"from pathlib import Path;Path('observed.txt').write_text('cpu-ok')"})
    result=tool_client.call("cpu.run",{"script":"smoke.py"})
    if result["returncode"]: raise RuntimeError("CPU smoke failed")
    artifact=tool_client.call("artifact.read_text",{"path":"observed.txt"})
    answer=model_client.complete({"value":artifact["text"]},output_schema={"type":"object"})
    return {"status":"completed","content":answer["response"],"artifacts":[{"path":"observed.txt","sha256":artifact["sha256"]}],"omissions":[]}
''',encoding='utf8')
    class FakeProvider:
        def complete(self,request,**kwargs):
            assert kwargs['role']=='executor'
            return {'response':{'synthetic':True,'observed':request['value']},'call_id':'fake-no-model-call','usage':None}
    try:
        result=run_container_harness(harness=root/'harness.py',public_root=public,image_id='sha256:92e6b0ef5cb3a149905fa097ae1d1ae3dd907cd19c796e057d3564d8a8fcfe01',provider=FakeProvider(),output=root/'run',max_artifact_bytes=4000000,max_artifact_files=200)
        print(json.dumps({'root':str(root),'status':'passed_synthetic_no_model','result':result}))
    except Exception as exc:
        print(json.dumps({'root':str(root),'error':str(exc)}));raise
