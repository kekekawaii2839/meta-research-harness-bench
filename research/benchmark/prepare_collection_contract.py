"""Version a development task to publish explicitly chosen collection limits."""
import argparse
import copy
import shutil
from pathlib import Path
from mrhbench.artifact_policy import collection_policy, make_collection_policy, WRITABLE_STORAGE_SEMANTICS
from mrhbench.io import ProtocolError, file_hash, write_json, contained
from mrhbench.materials import load_task, check_task


def prepare(source, output, *, max_total_bytes, max_entries):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or source == output or source in output.parents:
        raise ProtocolError('Independent fresh output required')
    task = load_task(source/'task.json')
    if task['split'] != 'development':
        raise ProtocolError('Collection contract migration is development-only')
    prior = copy.deepcopy(task)
    task['task_id'] += '-collection-v2'
    task['public']['task_id'] = task['task_id']
    task['public']['resources']['artifact_collection'] = make_collection_policy(
        max_total_bytes=max_total_bytes, max_entries=max_entries)
    task['public']['resources']['disk_semantics'] = WRITABLE_STORAGE_SEMANTICS
    collection_policy(task['public']['resources'])
    check_task(task, source)
    # Copy only manifest-owned assets, never stale nested release directories,
    # prior run logs or generated answers that happen to live in a package tree.
    output.mkdir(parents=True)
    for asset in task['assets']:
        original = contained(source, asset['path'], must_exist=True)
        target = contained(output, asset['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        if file_hash(target) != asset['sha256']:
            raise ProtocolError('Asset changed during collection-contract migration')
    write_json(output/'task.json', task)
    load_task(output/'task.json')
    record = {'source_task_sha256': file_hash(source/'task.json'),
        'variant_task_sha256': file_hash(output/'task.json'),
        'old_task_id': prior['task_id'], 'new_task_id': task['task_id'],
        'published_policy': task['public']['resources']['artifact_collection'],
        'execution_budget_unchanged': prior['public']['resources']['execution_budget'] == task['public']['resources']['execution_budget'],
        'container_resources_unchanged': prior['public']['resources']['container'] == task['public']['resources']['container'],
        'formal': False, 'interpretation': 'Controller disclosure repair; not a new scientific or harness result. Prior tasks and runs remain immutable.'}
    write_json(output/'collection_contract_provenance.json', record, exclusive=True)
    return record


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    p.add_argument('--max-total-bytes',required=True,type=int);p.add_argument('--max-entries',required=True,type=int)
    a=p.parse_args();print(prepare(a.source,a.output,max_total_bytes=a.max_total_bytes,max_entries=a.max_entries))
