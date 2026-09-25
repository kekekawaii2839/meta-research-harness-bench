"""T13 development integration under the Claude role configuration (AGENTS §0.2.13).

One frozen H0 harness runs each of the five current development task packages once in
its own package container, then the Claude judge scores each run. No retry of any
paid step. Checks the remaining ledger allowance covers the conservative ceiling
(package executor model_calls + 1 judge each) before starting anything.
"""
import argparse
import json
import sys
from pathlib import Path

from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, file_hash, read_json, write_json
from mrhbench.native_judge import CLAUDE_VERSION
from run_container_stage_development import run_stage

ROOT = Path(__file__).resolve().parent
PACKAGES = ['ssa-write-content', 'idea', 'lit', 'ssa-write-evidence', 'iv-exp']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--harness', required=True, type=Path)
    p.add_argument('--harness-sha256', required=True)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--roles', type=Path, default=ROOT / 'config/role_transport_claude_v1.json')
    p.add_argument('--only', nargs='*')
    p.add_argument('--catalog', type=Path, default=ROOT / 'materials/pilot_v3/collection_candidates_v2')
    a = p.parse_args()
    if file_hash(a.harness) != a.harness_sha256:
        raise ProtocolError('Frozen H0 hash mismatch')
    roles = read_json(a.roles)
    binary = Path(roles['claude_binary_default'])
    catalog = a.catalog.resolve()
    default = PACKAGES if catalog == (ROOT / 'materials/pilot_v3/collection_candidates_v2').resolve() else sorted(d.name for d in catalog.iterdir() if (d / 'task.json').is_file())
    selected = [x for x in default if a.only is None or x in a.only]
    ceiling = sum(read_json(catalog / x / 'task.json')['public']['resources']['execution_budget']['model_calls'] + 1 for x in selected)
    summary = CallLedger(ROOT / 'audit/development_call_ledger.json').summary()
    remaining = summary['authorized_maximum'] - summary['used_runs_including_failures']
    if ceiling > remaining:
        raise ProtocolError(f'Conservative ceiling {ceiling} exceeds remaining authorization {remaining}; nothing started')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / 'integration_plan.json', {'harness': str(a.harness), 'harness_sha256': a.harness_sha256,
               'roles': roles, 'roles_sha256': file_hash(a.roles), 'catalog': str(catalog), 'packages': selected, 'conservative_call_ceiling': ceiling,
               'remaining_at_start': remaining, 'retry': False, 'formal': False,
               'judge_version_expected': CLAUDE_VERSION}, exclusive=True)
    results = []
    for name in selected:
        try:
            r = run_stage(catalog / name, a.harness, out / name, binary, roles=roles)
            judge = out / name / 'judge_run_result.json'
            j = read_json(judge) if judge.is_file() else None
            row = {'package': name, 'submission_status': r['submission_status'],
                   'judge_status': j.get('status') if j else None, 'quality': j.get('quality') if j else None,
                   'dimension_scores': j.get('dimension_scores') if j else None}
        except Exception as exc:
            row = {'package': name, 'status': 'stage_failed', 'error_type': type(exc).__name__, 'message': str(exc)[:600], 'retry': False}
        results.append(row)
        write_json(out / 'integration_summary.json', {'runs': results, 'manual_trajectory_review_complete': False, 'formal': False})
        print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
