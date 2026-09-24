"""Compile two repaired Claude-constructed material candidates into development TaskViews.

Development-only controller step (0 model calls). Reuses mrhbench.material_adapter.compile_package
(which runs material_pipeline.validate_package) and then applies explicitly recorded controller
publication decisions. Source material outputs are never modified. No gate is promoted.

Run with the controller venv from research/benchmark:
  D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe -X utf8 materials/pilot_v3/claude_candidates_v1/compile_claude_candidates_v1.py
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parents[2]
sys.path.insert(0, str(BENCH))

from mrhbench.io import ProtocolError, file_hash, read_json, write_json, utc_now, digest  # noqa: E402
from mrhbench.material_adapter import compile_package  # noqa: E402
from mrhbench.materials import check_task, load_task  # noqa: E402
from mrhbench.rubrics import rubric  # noqa: E402
from mrhbench.artifact_policy import make_collection_policy, collection_policy  # noqa: E402

BATCH = Path('D:/mrhbench-local-pilot/material-claude-20260924-004-repair')
STAGING = Path('D:/mrhbench-local-pilot/claude-candidates-compile-v1')
MIB = 1024 * 1024
ORIGIN = 'claude_constructor_round1_repaired'

JOBS = {
    'ftct-write-v2': {
        'image_id': 'sha256:61ba1829927d6cd34424374b1206adf836950f8f9fd08722371d7ca397371009',
        'container': dict(cpus=1, memory_mb=1024, disk_mb=512, pids_limit=64, wall_seconds=600),
        'tasks': {
            'ftct-table1-write-content': {'dir': 'ftct-write-content', 'model_calls': 4, 'tool_calls': 60,
                                          'collection': (16 * MIB, 500)},
            'ftct-table1-write-evidence': {'dir': 'ftct-write-evidence', 'model_calls': 12, 'tool_calls': 60,
                                           'collection': (64 * MIB, 1000)},
        },
        'relocate_private': {},
    },
    'diffusion-exp-2d-v1': {
        'image_id': 'sha256:70114ade2b01a967b630faca376fed62bc3c40cd416543802aee88c12b2c0483',
        'container': dict(cpus=2, memory_mb=2048, disk_mb=512, pids_limit=128, wall_seconds=1200),
        'tasks': {
            'diffusion-exp-2d-v1-exp': {'dir': 'diffusion-exp', 'model_calls': 16, 'tool_calls': 120,
                                        'collection': (128 * MIB, 2000)},
        },
        # Reviewer R6 / runtime audit: judge-only notes must not live under the public assets/ tree.
        'relocate_private': {'assets/exp_2d/private/review_notes.md': 'private/review_notes.md'},
    },
}

BUDGET_BASIS = ('Unmeasured development candidate chosen by analogy to comparable existing collection_candidates_v2 '
                'packages (WRITE_CONTENT 4 model calls, WRITE_EVIDENCE 12, EXP 16; tool calls 60/60/120). '
                'No executor pilot on this task has measured sufficiency; not a formal budget.')

FACTS_NOTE = ('Fixed supplied facts: the authoritative fixed inputs are the public asset files listed in the input '
              'contract above (task statement, fact sheets / specification, data and starter code). Fact IDs used in '
              'those files are provenance labels; fact statements are not restated in this prompt, and no other '
              'material-package wording is part of the task.')


def controller_notes(container, collection, budget):
    total_mib = collection['max_total_bytes'] // MIB
    return ('\nController publication notes (development candidate; limits not formally frozen):\n'
            '1. Released paths: a document path written in the task files, such as assets/<...>, refers to the material '
            'package; its released copy is listed in asset_manifest with the extra prefix "assets/" (for example '
            'assets/assets/<...>) under the read-only public input root. Relative paths for your deliverables '
            '(for example submission/..., results/...) are inside your writable work directory.\n'
            f'2. Container: {container["cpus"]} CPU, {container["memory_mb"]} MB memory, {container["disk_mb"]} MB total '
            'writable tmpfs (80% work directory, 20% /tmp; counted against memory), '
            f'{container["pids_limit"]} processes, {container["wall_seconds"]} s total task wall time; no network, no GPU.\n'
            f'3. Artifact collection quota: at most {total_mib} MiB ({collection["max_total_bytes"]} bytes) of file bytes '
            f'and at most {collection["max_entries"]} entries (files AND directories) under the work directory, excluding '
            'top-level .broker and .process-*. If your outputs exceed this quota, collection is recorded as a failure and '
            'outputs may be lost or not evaluated; keep raw logs and per-step trajectories compact and save only what is '
            'needed as evidence.\n'
            f'4. Model/tool budget: {budget["model_calls"]} model calls and {budget["tool_calls"]} controller broker tool '
            f'calls within {budget["wall_seconds"]} s (unmeasured development candidate values).')


def rebuild_prompt(prompt, notes):
    head, sep, rest = prompt.partition('\nFixed supplied facts:\n')
    if not sep:
        raise ProtocolError('Unexpected compiled prompt layout')
    _, sep2, tail = rest.partition('\nScientific output requirements:\n')
    if not sep2:
        raise ProtocolError('Unexpected compiled prompt layout')
    return head + '\n' + FACTS_NOTE + '\nScientific output requirements:\n' + tail + notes


def compile_all(output_root=HERE):
    if STAGING.exists():
        raise ProtocolError('Fresh staging directory required: ' + str(STAGING))
    records = []
    for job, spec in JOBS.items():
        src = BATCH / job / 'constructor/output'
        request = read_json(BATCH / job / 'constructor/request.json')
        package_before = file_hash(src / 'package.json')
        source_tree_before = {str(p.relative_to(src)).replace('\\', '/'): file_hash(p) for p in src.rglob('*') if p.is_file()}
        budgets, collections = {}, {}
        for task_id, t in spec['tasks'].items():
            budgets[task_id] = {'model_calls': t['model_calls'], 'tool_calls': t['tool_calls'],
                                'wall_seconds': spec['container']['wall_seconds']}
            collections[task_id] = make_collection_policy(max_total_bytes=t['collection'][0], max_entries=t['collection'][1])
        package = read_json(src / 'package.json')
        declared = package['environment']['resources']
        if {k: declared[k] for k in spec['container']} != spec['container']:
            raise ProtocolError('Package resources differ from root-adjudicated resources for ' + job)
        stage = STAGING / job
        result = compile_package(src, request, stage, execution_budgets=budgets, image_id=spec['image_id'],
                                 public_rubrics={k: rubric(k) for k in ('WRITE_CONTENT', 'WRITE_EVIDENCE', 'EXP')},
                                 artifact_collections=collections, require_visual_png_preview=True)
        for task_id, t in spec['tasks'].items():
            compiled_root = stage / task_id
            compiled = read_json(compiled_root / 'task.json')
            final_root = output_root / t['dir']
            if final_root.exists():
                raise ProtocolError('Fresh output required: ' + str(final_root))
            task = copy.deepcopy(compiled)
            relocations = []
            for asset in task['assets']:
                new_path = spec['relocate_private'].get(asset['path'])
                if new_path is not None:
                    if asset['visibility'] != 'private':
                        raise ProtocolError('Only private assets are relocated')
                    relocations.append({'from': asset['path'], 'to': new_path, 'sha256': asset['sha256']})
                    asset['path'] = new_path
            for asset in task['assets']:
                source = compiled_root / next((r['from'] for r in relocations if r['to'] == asset['path']), asset['path'])
                target = final_root / asset['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                if file_hash(target) != asset['sha256']:
                    raise ProtocolError('Asset changed during copy')
            view = task['public']
            notes = controller_notes(view['resources']['container'], view['resources']['artifact_collection'],
                                     view['resources']['execution_budget'])
            view['prompt'] = rebuild_prompt(view['prompt'], notes)
            view['resources']['budget_status'] = 'explicit_development_candidate_pending_task_feasibility'
            task['private'].update({
                'material_origin': ORIGIN,
                'source_batch': str(BATCH / job).replace('\\', '/'),
                'source_package_json_sha256': package_before,
                'reviewer_decision': read_json(BATCH / job / 'reviewer/review.json')['decision'],
                'reviewer_review_sha256': file_hash(BATCH / job / 'reviewer/review.json'),
                'runtime_verification_audit': 'research/benchmark/audit/material_runtime_verification_round1.json',
                'execution_budget_basis': BUDGET_BASIS,
                'controller_publication_decisions': {
                    'fact_statements_not_composed_into_prompt': 'Package fact statements are provenance summaries that differ in wording from the public fact sheets and, for SRC-ENTROPY-DEF, contain an author-protocol value (reviewer finding R1). Public assets are the authoritative fixed inputs; statements remain in private/reference.json.',
                    'private_asset_relocations': relocations,
                    'controller_notes_appended': True,
                    'visual_png_preview_rule_applied_to_write_evidence': True,
                },
                'formal_eligible': False,
            })
            if task['public']['resources']['image_id'] != spec['image_id']:
                raise ProtocolError('image mismatch')
            for name, gate in task['gates'].items():
                gate['status'] = 'pending'
            task['gates']['runtime']['evidence'] = ('Image built from pinned base digest and package smoke passed in a locked-down container '
                '(audit/material_runtime_verification_round1.json); no executor trajectory, resource-sufficiency measurement or '
                'OOM/PID/disk stress on this task. Pending.')
            task['gates']['source_semantics']['evidence'] = ('Independent Claude material reviewer decision pass_with_pending_runtime; '
                'open minor findings recorded in audit/claude_candidates_v1_compilation.json. Not formal acceptance. Pending.')
            task['gates']['input_leakage']['evidence'] = ('Controller string leak check of the development export against private files '
                'and private-only facts (audit/claude_candidates_v1_compilation.json); not semantic contamination acceptance. Pending.')
            task['gates']['rights']['evidence'] = 'Source licence and benchmark reuse/redistribution rights not reviewed. Pending.'
            task['gates']['judge_behavior']['evidence'] = 'No judge run or trajectory audit for this task. Pending.'
            check_task(task, final_root)
            write_json(final_root / 'task.json', task, exclusive=True)
            load_task(final_root / 'task.json')
            collection_policy(task['public']['resources'])
            provenance = {
                'compilation_tool': 'mrhbench.material_adapter.compile_package + controller publication decisions',
                'compiler_script': 'research/benchmark/materials/pilot_v3/claude_candidates_v1/compile_claude_candidates_v1.py',
                'compiler_script_sha256': file_hash(Path(__file__)),
                'material_adapter_sha256': file_hash(BENCH / 'mrhbench/material_adapter.py'),
                'source_output': str(src).replace('\\', '/'), 'source_package_json_sha256': package_before,
                'staging_compiled_task_sha256': file_hash(compiled_root / 'task.json'),
                'final_task_sha256': file_hash(final_root / 'task.json'),
                'task_id': task['task_id'], 'material_origin': ORIGIN,
                'published_policy': task['public']['resources']['artifact_collection'],
                'execution_budget': task['public']['resources']['execution_budget'],
                'container': task['public']['resources']['container'], 'image_id': spec['image_id'],
                'formal': False,
                'interpretation': 'Development compilation of a reviewed candidate; not scientific, runtime-sufficiency, rights or judge acceptance.'}
            write_json(final_root / 'collection_contract_provenance.json', provenance, exclusive=True)
            records.append({'job': job, 'task_id': task_id, 'dir': t['dir'], 'provenance': provenance,
                            'compile_result_hash': digest(result)})
        after = {str(p.relative_to(src)).replace('\\', '/'): file_hash(p) for p in src.rglob('*') if p.is_file()}
        if after != source_tree_before:
            raise ProtocolError('Source material output changed during compilation')
    return records


if __name__ == '__main__':
    print(json.dumps(compile_all(), ensure_ascii=False, indent=1))
