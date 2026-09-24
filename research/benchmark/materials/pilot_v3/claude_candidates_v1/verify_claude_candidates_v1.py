"""Zero-model-call verification of claude_candidates_v1 TaskView packages.

Checks: load_task; development export contains only public files; string leak check of each export
against its private files, private-only facts and sibling-task-only inputs; stage-runner preflight
(schema validation, collection policy, budget/resources, frozen image present). Never calls run_stage.
"""
from __future__ import annotations

import importlib.metadata
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parents[2]
sys.path.insert(0, str(BENCH))

from mrhbench.io import ProtocolError, file_hash, read_json, digest  # noqa: E402
from mrhbench.materials import load_task, export_task  # noqa: E402
from mrhbench.providers import validate_application_schema  # noqa: E402
from mrhbench.artifact_policy import collection_policy  # noqa: E402
from mrhbench.sdk import Budget  # noqa: E402
from mrhbench.docker_pilot import resource_args  # noqa: E402

EXPORTS = Path('D:/mrhbench-local-pilot/claude-candidates-compile-v1/exports')
BATCH = Path('D:/mrhbench-local-pilot/material-claude-20260924-004-repair')
PACKAGES = {'ftct-write-content': 'ftct-write-v2', 'ftct-write-evidence': 'ftct-write-v2', 'diffusion-exp': 'diffusion-exp-2d-v1'}
CANARIES = {
    'diffusion-exp': ['80 x 80', '80x80', '80 × 80', '12800', 'top-64', 'top 64', '100 repetitions', '1000 steps',
                      'population 512', '25 iterations', 'OpenES run for', 'Tufts', 'CC BY-NC'],
    'ftct-write-content': ['FTCT-P01', 'FTCT-P02', 'FTCT-S04', 'FTCT-U06', 'ltx_font_bold'],
    'ftct-write-evidence': ['FTCT-P01', 'FTCT-P02', 'FTCT-S04', 'FTCT-U06', 'FTCT-R02', 'FTCT-R03', 'FTCT-R04',
                            'FTCT-R05', 'FTCT-R06', 'ltx_font_bold'],
}
# Sibling-task-only inputs that must not reach this task's export.
SIBLING_ONLY = {'ftct-write-evidence': ['ftct-write-content/assets/write_content/facts_author_findings.json',
                                        'ftct-write-content/assets/write_content/task.md'],
                'ftct-write-content': ['ftct-write-evidence/assets/write_evidence/task.md']}


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def needles_from_text(text, minimum=40):
    out = set()
    for line in text.splitlines():
        s = line.strip().strip('|').strip()
        if len(s) >= minimum:
            out.add(s)
    for sentence in re.split(r'(?<=[.;:])\s+', text):
        s = sentence.strip()
        if len(s) >= minimum:
            out.add(s)
    return out


def needles_from_file(path):
    text = path.read_text(encoding='utf-8')
    if path.suffix == '.json':
        found = set()
        for s in strings(json.loads(text)):
            found |= needles_from_text(s)
        return found
    return needles_from_text(text)


def private_needles(name, root, task):
    needles = {}
    for asset in task['assets']:
        if asset['visibility'] != 'private':
            continue
        p = root / asset['path']
        if asset['path'] == 'private/reference.json':
            ref = read_json(p)
            for key in ('private_facts', 'verification_plan'):
                for s in strings(ref[key]):
                    for n in needles_from_text(s):
                        needles.setdefault(n, set()).add('private/reference.json:' + key)
        else:
            for n in needles_from_file(p):
                needles.setdefault(n, set()).add(asset['path'])
    for sib in SIBLING_ONLY.get(name, []):
        for n in needles_from_file(HERE / sib):
            needles.setdefault(n, set()).add('sibling-only:' + sib)
    return needles


def docker_image(image_id):
    out = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}|{{.Architecture}}|{{.Os}}|{{.Config.User}}', image_id],
                         capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        return {'present': False, 'error': out.stderr.strip()[:300]}
    iid, arch, os_, user = out.stdout.strip().split('|')
    return {'present': True, 'id': iid, 'architecture': arch, 'os': os_, 'image_user': user, 'id_matches': iid == image_id}


def verify(name):
    root = HERE / name
    task = load_task(root / 'task.json')
    report = {'package_dir': 'research/benchmark/materials/pilot_v3/claude_candidates_v1/' + name,
              'task_id': task['task_id'], 'task_type': task['task_type'], 'paper_id': task['paper_id'],
              'split': task['split'], 'task_sha256': file_hash(root / 'task.json'), 'load_task': 'passed',
              'gates': {k: v['status'] for k, v in task['gates'].items()},
              'asset_hashes': {a['path']: {'sha256': a['sha256'], 'visibility': a['visibility']} for a in task['assets']}}
    # Preflight as in run_container_stage_development.run_stage before any worker/billed call.
    validate_application_schema(task['public']['output_contract'])
    policy = collection_policy(task['public']['resources'])
    Budget.from_task(task['public'])
    res = task['public']['resources']
    resource_args(res['container'])
    if res['execution_budget']['wall_seconds'] != res['container']['wall_seconds']:
        raise ProtocolError('wall mismatch')
    if task['private'].get('corpus_configuration'):
        raise ProtocolError('unexpected corpus configuration')
    quota_stated = (str(policy['max_total_bytes']) in task['public']['prompt']
                    and str(policy['max_entries']) in task['public']['prompt'])
    if not quota_stated:
        raise ProtocolError('collection quota not stated in public prompt')
    report['preflight'] = {'application_schema_valid': True, 'collection_policy': policy,
                           'budget_parsed': res['execution_budget'], 'container_resource_args_valid': True,
                           'quota_stated_in_prompt': quota_stated,
                           'jsonschema_version': importlib.metadata.version('jsonschema'),
                           'image': docker_image(res['image_id']), 'run_stage_called': False, 'model_calls': 0}
    # Export and public-only file check.
    dest = EXPORTS / name
    receipt = export_task(task, root, dest, audience='development_executor')
    exported = sorted(str(p.relative_to(dest)).replace('\\', '/') for p in dest.rglob('*') if p.is_file())
    expected = sorted(['task.json'] + ['assets/' + a['path'] for a in task['assets'] if a['visibility'] == 'public'])
    if exported != expected:
        raise ProtocolError('Export file set differs from public assets: %s' % exported)
    private_paths = [a['path'] for a in task['assets'] if a['visibility'] == 'private']
    view = read_json(dest / 'task.json')
    view_hashes = {r['path']: r['sha256'] for r in view['asset_manifest']}
    for rel in exported:
        if rel != 'task.json' and file_hash(dest / rel) != view_hashes[rel]:
            raise ProtocolError('Exported bytes differ from manifest')
    if any('private' in rel.split('/') for rel in exported):
        raise ProtocolError('private path segment in export')
    report['export'] = {'receipt': receipt, 'files': exported, 'file_count': len(exported),
                        'only_public_files': True, 'private_assets_not_exported': private_paths,
                        'export_dir': str(dest).replace('\\', '/'),
                        'export_view_sha256': file_hash(dest / 'task.json')}
    # String leak check.
    texts = {rel: (dest / rel).read_text(encoding='utf-8') for rel in exported}
    needles = private_needles(name, root, task)
    hits = []
    for needle, origins in sorted(needles.items()):
        where = [rel for rel, t in texts.items() if needle in t]
        if where:
            hits.append({'needle': needle[:200], 'private_origins': sorted(origins), 'found_in': where})
    canary_hits = []
    for c in CANARIES[name]:
        where = [rel for rel, t in texts.items() if c in t]
        if where:
            canary_hits.append({'canary': c, 'found_in': where})
    report['leak_check'] = {'method': 'Exact substring search of every exported file for (a) each >=40-char line/sentence of private assets, private-only fact statements and verification plans, (b) sibling-task-only public inputs, (c) task-specific canaries. Not semantic contamination review.',
                            'needle_count': len(needles), 'hit_count': len(hits), 'hits': hits,
                            'canaries': CANARIES[name], 'canary_hits': canary_hits,
                            'hits_in_compiled_task_json': [h for h in hits if 'task.json' in h['found_in']]}
    return report


if __name__ == '__main__':
    if EXPORTS.exists():
        raise ProtocolError('Fresh export directory required')
    results = {name: verify(name) for name in PACKAGES}
    print(json.dumps(results, ensure_ascii=False, indent=1))
