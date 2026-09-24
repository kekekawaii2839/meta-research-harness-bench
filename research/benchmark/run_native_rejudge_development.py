"""Explicit new native judgment of immutable development evidence; no solver rerun."""
import argparse
import sys
from pathlib import Path
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError,read_json,write_json,file_hash
from mrhbench.materials import load_task
from mrhbench.native_codex import NativeCodexRunner
from mrhbench.native_judge import run_native_judge
from run_container_stage_development import output_inventory_for_run


def run(package,run_root,records_path,output,binary):
    package,run_root,records_path,output=map(Path,[package,run_root,records_path,output])
    if output.exists():raise ProtocolError('New rejudge directory required; historical evaluations are immutable')
    task=load_task(package/'task.json')
    if task['split']!='development':raise ProtocolError('This rejudge entrypoint is development-only')
    public=read_json(run_root/'public/task.json')
    if public['task_id']!=task['task_id']:raise ProtocolError('Task/run identity mismatch')
    root=Path(__file__).resolve().parent
    runner=NativeCodexRunner(binary=Path(binary),model='gpt-5.6-sol',reasoning_effort='medium',
        ledger=CallLedger(root/'audit/development_call_ledger.json'),audit_root=output.parent/(output.name+'-calls'),
        permission_profile=':read-only',timeout_seconds=600)
    result=run_native_judge(runner=runner,task_id=task['task_id'],task_type=task['task_type'],
        records=read_json(records_path),output=output,python_binary=Path(sys.executable),
        controller_output_inventory=output_inventory_for_run(task['task_type'],run_root/'execution'))
    write_json(output/'rejudge_provenance.json',{'records_path':str(records_path.resolve()),
        'records_sha256':file_hash(records_path),'task_sha256':file_hash(package/'task.json'),
        'new_executor_calls':0,'explicit_new_judge':True,'formal':False},exclusive=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('package','run-root','records','output','binary'):p.add_argument('--'+key,required=True)
    a=p.parse_args();r=run(a.package,a.run_root,a.records,a.output,a.binary)
    print({k:r.get(k) for k in ('status','quality','acceptance_status')})
