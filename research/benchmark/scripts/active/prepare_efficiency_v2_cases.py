"""Explicit, byte-preserving single-task projections; no model calls.

CLI consumes a case-candidate audit, but does not run at import. Historical
reviews remain defect leads, never current-policy approval certificates.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mrhbench.incremental_repair import _safe_path, _tree, _disjoint

TYPES = ['LIT', 'IDEA', 'EXP', 'WRITE_CONTENT', 'WRITE_EVIDENCE']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')


def relative(value):
    if not isinstance(value, str) or '\\' in value or ':' in value:
        raise ValueError('Expected portable relative path')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or not p.parts or str(p) != value:
        raise ValueError('Unsafe relative path')
    return value


def read_bound(path, expected=None):
    path = _safe_path(Path(path))
    if not path.is_file():
        raise ValueError('Missing regular input file')
    data = path.read_bytes()
    if expected and digest(data) != expected:
        raise ValueError('Input hash mismatch: ' + str(path))
    return data


def project(case, destination):
    """Preflight all bytes before writing an entirely new destination tree."""
    destination = _safe_path(Path(destination))
    workspace = _safe_path(Path(case['workspace']))
    _disjoint(workspace, destination)
    if destination.exists():
        raise ValueError('Destination must not exist; no overwrite/resume')
    for key in ['job', 'prior_package', 'prior_review', 'prior_adjudication_and_notes']:
        _disjoint(_safe_path(Path(case[key]['path'])), destination)
        read_bound(case[key]['path'], case[key]['sha256'])
    job = json.loads(read_bound(case['job']['path']))
    package_path = Path(case['prior_package']['path'])
    original = json.loads(read_bound(package_path))
    files = _tree(package_path.parent)
    for row in case.get('prior_candidate_inventory', []):
        read_bound(row['path'], row['sha256'])
    task_id = case['recommended_task_id']
    matches = [t for t in original['tasks'] if t['task_id'] == task_id]
    if len(matches) != 1:
        raise ValueError('Expected exactly one selected task')
    task = copy.deepcopy(matches[0])
    kind = task['task_type']
    if kind != case['recommended_single_task_type'] or kind not in TYPES:
        raise ValueError('Task type mismatch')
    kept = set()
    for row in task.get('assets', []) + task.get('input_contract', {}).get('files', []):
        name = relative(row['path'])
        if name not in files or digest(files[name]) != row['sha256']:
            raise ValueError('Selected asset missing/hash mismatch: ' + name)
        kept.add(name)
    kept.update(name for name in files if name.startswith('environment/'))
    for field in ['dockerfile', 'smoke_test']:
        name = relative(original['environment'][field])
        if name not in kept:
            raise ValueError('Environment file missing')
    references = set(task.get('input_fact_ids', []) + task.get('private_fact_ids', []))
    facts = original['facts']
    if len({f['fact_id'] for f in facts}) != len(facts):
        raise ValueError('Duplicate fact IDs')
    if references - {f['fact_id'] for f in facts}:
        raise ValueError('Missing referenced facts')
    package = copy.deepcopy(original)
    package['tasks'] = [task]
    package['facts'] = [f for f in facts if f['fact_id'] in references]
    package['coverage'] = [
        {'task_type': ty, 'status': 'candidate' if ty == kind else 'deferred',
         'reason': ('Selected unchanged task for controller projection; unaccepted repair candidate.' if ty == kind
                    else 'Controller single-task projection excludes this type; NOT a claim that the paper does not support it.')}
        for ty in TYPES]
    # Preserve resource numbers, smoke, scientific content and all fact fields.
    selected_sources = []
    source_files = {}
    source_mappings = []
    source_allowlist = {str(_safe_path(Path(r['path']))): r for r in case['source_inventory']}
    for index, source in enumerate(job['sources']):
        value = source['local_path']
        path = _safe_path(Path(value) if Path(value).is_absolute() else workspace / relative(value))
        _disjoint(path, destination)
        if str(path) not in source_allowlist:
            raise ValueError('Source outside explicit whitelist')
        data = read_bound(path, source['sha256'])
        read_bound(path, source_allowlist[str(path)]['sha256'])
        row = copy.deepcopy(source)
        projected_path = 'source_inputs/%03d-%s' % (index, relative(path.name))
        row['local_path'] = projected_path
        source_files[projected_path] = data
        source_mappings.append({'original_absolute_path': str(path), 'projected_path': projected_path, 'sha256': digest(data)})
        selected_sources.append(row)
    source_ids = {s['source_id'] for s in selected_sources}
    needed_sources = set(task.get('private_source_ids', []))
    needed_sources.update(e['source_id'] for f in package['facts'] for e in f.get('evidence', []))
    if needed_sources - source_ids:
        raise ValueError('Missing referenced sources')
    # Prepopulated files are retained only when required by this task. Resolve
    # the original source from the explicit whitelist; never fetch or transform.
    prepop = []
    for index, row in enumerate(job.get('prepopulated_output_files', [])):
        target = relative(row['to'])
        if target not in kept:
            continue
        raw = row['from']
        src = _safe_path(Path(raw) if Path(raw).is_absolute() else workspace / relative(raw))
        if str(src) not in source_allowlist:
            raise ValueError('Prepopulated source outside whitelist')
        data = read_bound(src, row['sha256'])
        if data != files[target]:
            raise ValueError('Prepopulated and prior selected asset differ')
        item = copy.deepcopy(row)
        projected_path = 'prepop_inputs/%03d-%s' % (index, relative(src.name))
        item['from'] = projected_path
        source_files[projected_path] = data
        source_mappings.append({'original_absolute_path': str(src), 'projected_path': projected_path, 'sha256': digest(data)})
        prepop.append(item)
    old_scope = job.get('scope_request', '')
    job['requested_task_types'] = [kind]
    job['sources'] = selected_sources
    job['prepopulated_output_files'] = prepop
    job['scope_request'] = (
        'EXPLICIT CONTROLLER SINGLE-TASK PROJECTION. Retain only task ' + task_id +
        '. Other tasks in the historical construction order below are context, not construction requests. '
        'Do not construct them. Do not change scientific content except documented repairs verified against sources. '
        'Prior reviews are defect leads, not current-policy attestations. Apply the full current policy.\n\n'
        'HISTORICAL CONSTRUCTION ORDER (single-task boundary above controls scope):\n' + old_scope)
    notes = json.loads(read_bound(case['prior_adjudication_and_notes']['path']))['repair_notes']
    projection_note = (
        'CONTROLLER-INDUCED PROJECTION WORK, NOT AN ORIGINAL MODEL SCIENTIFIC FAILURE: '
        'the unchanged historical environment smoke may require files from excluded tasks. '
        'Adapt smoke to check ONLY the selected stage input whitelist and never read other-stage assets. '
        'Do not restore excluded-stage mounts or change resource numbers. Scientific content and smoke bytes '
        'were not hand-repaired by the projection controller. This identical repair burden applies to both trial arms.')
    scoped_notes = [projection_note, 'Retained task: ' + task_id + '. Scope map: ' + '; '.join(case['proposed_retained_notes_scope']) +
                    '. Full historical notes follow unchanged; apply all implications for this task and its dependencies. '
                    'Do not construct excluded stages, silently discard scientific caveats, or treat prior review as current-policy approval.'] + notes
    output = {('prior/' + job['job_id'] + '/constructor/output/' + name): files[name] for name in sorted(kept)}
    output.update(source_files)
    prefix = 'prior/' + relative(job['job_id'])
    output[prefix + '/constructor/output/package.json'] = encode(package)
    output[prefix + '/reviewer/review.json'] = read_bound(case['prior_review']['path'])
    output['job.json'] = encode(job)
    output['repair_notes.json'] = encode(scoped_notes)
    output['historical_full_repair_notes.json'] = encode(notes)
    output['historical_adjudication.json'] = read_bound(case['prior_adjudication_and_notes']['path'])
    provenance = {'schema_version': 'single-task-projection-1', 'task_id': task_id,
                  'source_case': case, 'controller_only_metadata_changes': ['tasks filter', 'facts reference filter', 'coverage projection', 'job single-task scope/byte-preserved local source copies'],
                  'source_copy_mapping': source_mappings,
                  'scientific_asset_bytes_changed': False, 'environment_bytes_changed': False,
                  'prior_review_current_policy_approval': False,
                  'projection_induced_work': projection_note,
                  'removed_files': sorted(set(files) - kept - {'package.json'}),
                  'output_inventory': {n: {'sha256': digest(b), 'bytes': len(b)} for n, b in output.items()}}
    output['projection_provenance.json'] = encode(provenance)
    # Validate all output names before the first write.
    for name in output:
        relative(name)
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in output.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
    return provenance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--paper-id', required=True)
    args = parser.parse_args()
    cases = json.loads(args.candidates.read_text(encoding='utf8'))['recommended_cases']
    matched = [c for c in cases if c['paper_id'] == args.paper_id]
    if len(matched) != 1:
        raise ValueError('Expected exactly one candidate')
    project(matched[0], args.destination)


if __name__ == '__main__':
    main()
