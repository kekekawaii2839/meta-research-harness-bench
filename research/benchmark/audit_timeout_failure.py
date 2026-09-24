"""Short synthetic CPU deadline injection; fake provider, zero model calls."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid
from mrhbench.container_executor import run_container_harness
from mrhbench.io import read_json, write_json, file_hash
from mrhbench.artifact_policy import make_collection_policy


def main():
    root = Path('D:/mrhbench-local-pilot') / ('timeout-artifact-policy-' + uuid.uuid4().hex[:10])
    root.mkdir(); public = root/'public'; public.mkdir()
    image = 'sha256:399341648ce68031cef84e225a8b4985fed3125fd020ec96a8d6c5d6563036d0'
    resources = {'cpus': 1, 'memory_mb': 256, 'disk_mb': 32, 'pids_limit': 32, 'wall_seconds': 40}
    write_json(public/'task.json', {'task_id': 'synthetic-deadline-no-scientific-task', 'task_type': 'EXP',
        'resources': {'container': resources, 'execution_budget': {'model_calls': 1, 'tool_calls': 8, 'wall_seconds': 40}, 'image_id': image,
                      'artifact_collection': make_collection_policy(max_total_bytes=1024*1024,max_entries=100)},
        'asset_manifest': [], 'tools': ['artifact_read_write', 'artifact_image_view', 'cpu_python_execution'], 'output_contract': {}})
    script = "from pathlib import Path\nimport matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt\nPath('observed-marker.txt').write_text('marker-before-deadline')\nplt.plot([0,1],[0,1]);plt.savefig('observed.png');plt.close()\nprint('marker-created')\n"
    harness = '''def run(task_view, model_client, tool_client, budget):
    tool_client.call('artifact.write_text', {'path':'setup.py','text':SCRIPT})
    result = tool_client.call('cpu.run', {'script':'setup.py'})
    assert result['returncode'] == 0
    marker = tool_client.call('artifact.read_text', {'path':'observed-marker.txt'})
    image = tool_client.call('artifact.view_image', {'path':'observed.png'})
    model_client.complete({'marker':marker['text']}, output_schema={'type':'object'}, image_ids=[image['image_id']])
    tool_client.call('artifact.write_text', {'path':'sleep.py','text':'import time;time.sleep(120)'})
    tool_client.call('cpu.run', {'script':'sleep.py','timeout_seconds':120})
    raise AssertionError('deadline should prevent successful completion')
'''.replace('SCRIPT', repr(script))
    (root/'harness.py').write_text(harness, encoding='utf8')
    class FakeProvider:
        def __init__(self): self.calls = 0
        def complete(self, request, **kwargs):
            self.calls += 1
            assert kwargs['role'] == 'executor' and request['marker'] == 'marker-before-deadline'
            assert kwargs['images'][0].read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
            return {'response': {'synthetic': True}, 'call_id': 'fake-provider-no-subscription-call', 'usage': None}
    provider = FakeProvider(); started = time.monotonic(); error = None
    try:
        run_container_harness(harness=root/'harness.py', public_root=public, image_id=image, provider=provider,
                              output=root/'run', max_artifact_bytes=1024*1024, max_artifact_files=100)
    except Exception as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
    failure = read_json(root/'run/failure.json')
    rpcs = [read_json(p) for p in (root/'run/broker').glob('rpc-*.json') if 'oversize' not in p.name]
    marker_observed = any(r.get('response', {}).get('value', {}).get('text') == 'marker-before-deadline' for r in rpcs if isinstance(r.get('response', {}).get('value'), dict))
    images = list((root/'run/broker').glob('image-*.png'))
    snapshots = list((root/'run/container/executed-entrypoints').glob('*.py'))
    cids = set()
    for p in (root/'run/container').glob('*-create.json'):
        x = read_json(p); cid = x.get('stdout','').strip()
        if len(cid) == 64: cids.add(cid)
    cleanup = []
    for cid in sorted(cids):
        proc = subprocess.run(['docker','inspect',cid], capture_output=True, text=True)
        cleanup.append({'container_id':cid,'inspect_returncode':proc.returncode,'absent':proc.returncode != 0 and 'No such' in proc.stderr})
    checks = {'failed_instead_of_completed': error is not None, 'marker_observed_before_deadline':marker_observed,
              'captured_image_preserved':len(images)==1, 'executed_entrypoints_preserved':len(snapshots)==2,
              'fake_model_receipt_preserved':provider.calls==1,
              'unknown_not_empty':failure['artifact_status']=='unknown_uncollected_or_incomplete' and not failure['missing_capture_proves_no_solver_output'],
              'no_scientific_zero':failure['quality_score'] is None and not failure['automatic_zero'],
              'no_fake_complete_inventory':not (root/'run/artifact_inventory.json').exists(),
              'owned_container_removed':bool(cleanup) and all(x['absent'] for x in cleanup),
              'failure_budget_preserved':failure['budget']['used']=={'model':1,'tool':6}}
    result={'scope':'Synthetic platform deadline injection, not evaluated H0 or science; no model calls/GPU', 'root':str(root), 'resources_diagnostic_only':resources,
            'elapsed_seconds':time.monotonic()-started,'error':error,'checks':checks,'passed':all(checks.values()),
            'cleanup':cleanup,'failure_record':failure,'failure_sha256':file_hash(root/'run/failure.json'),
            'image_sha256':[file_hash(p) for p in images], 'snapshot_sha256':[file_hash(p) for p in snapshots]}
    write_json(root/'results.json',result)
    print(json.dumps({'root':str(root),'passed':result['passed'],'checks':checks}))
    if not result['passed']:raise RuntimeError('Deadline policy diagnostic failed; inspect preserved evidence')


if __name__ == '__main__': main()
