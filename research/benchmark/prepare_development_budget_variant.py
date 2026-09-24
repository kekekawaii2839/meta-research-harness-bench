"""Explicit task-budget pilot, not harness evolution or a formal configuration."""
import argparse
import copy
import shutil
from pathlib import Path
from mrhbench.io import ProtocolError,read_json,write_json,file_hash
from mrhbench.materials import load_task,check_task


def prepare(source,output,model_calls):
    source,output=Path(source).resolve(),Path(output).resolve()
    if output.exists() or source==output or source in output.parents:
        raise ProtocolError('Independent fresh output required')
    if type(model_calls) is not int or model_calls<1:raise ProtocolError('Positive explicit call count required')
    task=load_task(source/'task.json')
    if task['split']!='development':raise ProtocolError('Cannot tune formal/search/test task budget')
    old=copy.deepcopy(task)
    task['task_id']+='-budgetpilot-002'
    task['public']['task_id']=task['task_id']
    task['public']['resources']['execution_budget']['model_calls']=model_calls
    check_task(task,source)
    shutil.copytree(source,output)
    write_json(output/'task.json',task)
    load_task(output/'task.json')
    for asset in task['assets']:
        if file_hash(output/asset['path'])!=asset['sha256']:raise ProtocolError('Source asset changed')
    record={'source_task_sha256':file_hash(source/'task.json'),'variant_task_sha256':file_hash(output/'task.json'),
        'old_task_id':old['task_id'],'new_task_id':task['task_id'],
        'old_budget':old['public']['resources']['execution_budget'],'new_budget':task['public']['resources']['execution_budget'],
        'container_resources_unchanged':old['public']['resources']['container']==task['public']['resources']['container'],
        'scientific_input_unchanged':{k:v for k,v in old['public'].items() if k not in {'resources','task_id'}}=={k:v for k,v in task['public'].items() if k not in {'resources','task_id'}}, 'assets_unchanged':old['assets']==task['assets'],
        'formal':False,'interpretation':'User-approved development budget feasibility only; not harness improvement or frozen study setting.'}
    write_json(output/'budget_variant_provenance.json',record,exclusive=True)
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--model-calls',type=int,required=True)
    a=p.parse_args();print(prepare(a.source,a.output,a.model_calls))

