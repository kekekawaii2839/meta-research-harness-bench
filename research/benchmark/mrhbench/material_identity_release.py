"""Opt-in, runtime-bound compilation and actual release identity inspection.

Outputs are private review staging, not solver admission. All semantic gates stay
pending. Callers must not mount these releases until independent release review.
"""
from pathlib import Path

from .io import ProtocolError, read_json, write_json, digest, file_hash
from .factory_runtime import compile_tasks
from .materials import export_task
from .material_public_identity import scan_candidate, scan_release, validate_map, _safe


def compile_identity_release(output_root, destination, map_identity, *, runtime_record,
                             package_slug, source_manifest, execution_budgets,
                             artifact_collections, require_visual_png_preview=True,
                             per_task_resources=False):
    """Compile with explicit opaque-ID keys; inspect final controller-added fields.

    No legacy budget fallback, fact suppression, review transfer or gate promotion.
    A historical runtime record fails existing package hash/digest verification.
    Unknown binary content remains pending; known identifier matches raise.
    """
    source = _safe(output_root)
    dest = _safe(destination, must_exist=False)
    if dest.exists() or dest.is_relative_to(source) or source.is_relative_to(dest):
        raise ProtocolError('Identity release requires a separate fresh private staging root')
    mapping = validate_map(map_identity, roots=[source])
    private_map = Path(map_identity['path']).resolve()
    if private_map == dest or private_map.is_relative_to(dest):
        raise ProtocolError('Private identity map must be outside release staging')
    package = read_json(source / 'package.json')
    ids = {t['task_id'] for t in package['tasks']}
    if ids != set(mapping['task_ids'].values()):
        raise ProtocolError('Compilation requires the allocated opaque task IDs')
    if (not isinstance(execution_budgets, dict) or set(execution_budgets) != ids
            or not isinstance(artifact_collections, dict) or set(artifact_collections) != ids
            or any(not isinstance(v, dict) or not v for v in artifact_collections.values())):
        raise ProtocolError('Explicit exact opaque budget and collection keys required')
    for budget in execution_budgets.values():
        if not isinstance(budget, dict) or set(budget) != {'model_calls', 'tool_calls', 'wall_seconds'}:
            raise ProtocolError('Every execution budget must explicitly specify all three limits')
    from .material_adapter import task_container
    for task in package['tasks']:
        resources = package['environment']['resources']
        container = task_container(task, resources) if per_task_resources else resources
        if execution_budgets[task['task_id']]['wall_seconds'] != container['wall_seconds']:
            raise ProtocolError('Explicit execution walltime differs from task resources')
    candidate_scan = scan_candidate(source, map_identity)
    records = compile_tasks(source, package, runtime_record, dest / 'compiled',
        package_slug=package_slug, source_manifest=source_manifest,
        execution_budgets=execution_budgets, artifact_collections=artifact_collections,
        compose_fact_statements=True, review_path=None,
        require_visual_png_preview=require_visual_png_preview,
        per_task_resources=per_task_resources)
    releases = []
    for record in records:
        task_root = Path(record['dir'])
        task = read_json(task_root / 'task.json')
        release = dest / 'review_releases' / task['task_id']
        export_task(task, task_root, release, audience='development_executor')
        scan = scan_release(release, map_identity)
        releases.append({'task_id': task['task_id'], 'release_root': str(release),
            'task_json_sha256': file_hash(release / 'task.json'), 'scan': scan,
            'compiled_manifest_sha256': file_hash(task_root / 'task.json'),
            'independent_release_review': 'pending', 'solver_admitted': False})
    result = {'schema_version': 'identity-bound-release-staging-1',
        'status': 'pending_independent_release_review',
        'package_sha256': file_hash(source / 'package.json'),
        'runtime_record_digest': digest(runtime_record),
        'candidate_scan': candidate_scan, 'releases': releases,
        'model_calls': 0, 'formal_accepted': False, 'solver_admitted': False,
        'historical_review_transferred': False,
        'notice': 'Private review staging only; no known match is not semantic anonymity.'}
    write_json(dest / 'identity_release_record.json', result, exclusive=True)
    return result
