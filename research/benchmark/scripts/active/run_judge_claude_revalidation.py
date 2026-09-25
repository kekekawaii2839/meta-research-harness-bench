"""Re-validate the judge under the Claude role configuration (AGENTS §0.2.13, §7.2).

Uses the ten synthetic fixture cases already frozen for the Codex v2.8 judge, all five
task types. Expected behaviour directions come verbatim from those earlier frozen plans
and are recorded before any call. At most one attempt per case, no retry, no prompt
tuning on these cases. Scores are candidates until full trajectory review.
"""
import argparse
import json
import sys
from pathlib import Path

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.claude_transport import ClaudeNativeRunner
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, file_hash, read_json, write_json
from mrhbench.judging import EvidenceSession
from mrhbench.native_judge import CLAUDE_VERSION, make_prompt, run_native_judge

PILOT = Path('D:/mrhbench-local-pilot')
CASES = [
    ('judge-v28-holdout-20260923-001', 'finite_alpha'), ('judge-v28-holdout-20260923-001', 'finite_beta'),
    ('judge-v28-holdout-20260923-001', 'passage_alpha'), ('judge-v28-holdout-20260923-001', 'passage_beta'),
    ('judge-v28-idea-lit-fixtures-20260923-002', 'proposal_alpha'), ('judge-v28-idea-lit-fixtures-20260923-002', 'proposal_beta'),
    ('judge-v28-idea-lit-fixtures-20260923-002', 'review_alpha'), ('judge-v28-idea-lit-fixtures-20260923-002', 'review_beta'),
    ('visual-holdout-20260923-003', 'visual_alpha'), ('visual-holdout-20260923-003', 'visual_beta'),
]


def expectations(source, name, fixture):
    plan = source / 'frozen_plan.json'
    if plan.is_file():
        data = read_json(plan)
        expected_hash = data['files'][name + '.fixture.json']
        if file_hash(source / (name + '.fixture.json')) != expected_hash:
            raise ProtocolError('Frozen fixture changed: ' + name)
        return {k: data[k] for k in ('expected_behavior', 'expected_direction', 'pair_control', 'private_feedback_check') if k in data}
    return {'review_expectations': fixture.get('review_expectations')}


def run(output, roles, only=None):
    base = Path(__file__).resolve().parents[2]
    roles = read_json(Path(roles))
    judge = roles['judge']
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    selected = [c for c in CASES if only is None or c[1] in only]
    frozen = {'protocol': CLAUDE_VERSION, 'native_judge_sha256': file_hash(base / 'mrhbench/native_judge.py'),
              'claude_transport_sha256': file_hash(base / 'mrhbench/claude_transport.py'),
              'claude_binary_sha256': file_hash(Path(roles['claude_binary_default'])), 'model': judge['model'], 'effort': judge['effort'],
              'max_attempts': len(selected), 'retry': False, 'prompt_tuning_on_cases': False, 'cases': []}
    for folder, name in selected:
        source = PILOT / folder
        fixture = read_json(source / (name + '.fixture.json'))
        prompt = make_prompt(name, fixture['task_type'], EvidenceSession(fixture['records']), transport='claude')
        (out / (name + '.frozen_prompt.txt')).write_text(prompt, encoding='utf8')
        frozen['cases'].append({'name': name, 'source': str(source), 'task_type': fixture['task_type'],
                                'fixture_sha256': file_hash(source / (name + '.fixture.json')),
                                'prompt_sha256': file_hash(out / (name + '.frozen_prompt.txt')),
                                'preregistered_expectations': expectations(source, name, fixture)})
    write_json(out / 'frozen_plan.json', frozen, exclusive=True)
    results = []
    for case in frozen['cases']:
        name = case['name']
        fixture = read_json(Path(case['source']) / (name + '.fixture.json'))
        if file_hash(base / 'mrhbench/native_judge.py') != frozen['native_judge_sha256']:
            raise ProtocolError('Judge code changed mid-run')
        runner = ClaudeNativeRunner(binary=Path(roles['claude_binary_default']), model=judge['model'], reasoning_effort=judge['effort'],
                                    ledger=CallLedger(base / 'audit/development_call_ledger.json'), audit_root=out / 'calls',
                                    timeout_seconds=judge.get('timeout_seconds', 600))
        try:
            r = run_native_judge(runner=runner, task_id=name, task_type=fixture['task_type'], records=fixture['records'],
                                 output=out / name, python_binary=Path(sys.executable))
            summary = {'case': name, 'status': r.get('status'), 'quality': r.get('quality'),
                       'dimension_scores': r.get('dimension_scores')}
        except Exception as exc:
            summary = {'case': name, 'status': 'judge_attempt_failed', 'error_type': type(exc).__name__, 'message': str(exc)[:500], 'retry': False}
        results.append(summary)
        write_json(out / 'run_summary.json', {'runs': results, 'manual_review_complete': False, 'formal_acceptance': False})
        print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--roles', default=str(Path(__file__).resolve().parents[2] / 'config/role_transport_claude_v1.json'))
    p.add_argument('--only', nargs='*')
    a = p.parse_args()
    run(a.output, a.roles, a.only)
