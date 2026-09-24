"""Read-only receipt/delivery audit of the historical IV native judge call 179.

Never executes submitted code or calls a model. Semantic findings are an
independent maintainer review, not a replacement scientific score.
"""
from pathlib import Path
import hashlib
import json
from mrhbench.io import digest


BASE = Path('D:/mrhbench-local-pilot/h0-budget-pilot-20260923-001/iv-exp/judge-native-v1')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    paths = list(BASE.iterdir())
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
    manifest, state, result, call = [load(BASE / name) for name in
        ('evidence_manifest.json', 'tool_state.json', 'result.json', 'native_call.json')]
    records = {r['evidence_id']: r for r in manifest['records']}
    rollout_path = Path(call['rollout_capture']['path'])
    rows = [json.loads(line) for line in rollout_path.read_text(encoding='utf-8').splitlines()]
    delivered, errors, calls = {}, [], []
    for row in rows:
        p = row.get('payload', {})
        if p.get('type') == 'custom_tool_call':
            calls.append({'call_id': p['call_id'], 'name': p.get('name'), 'input': p['input']})
        if p.get('type') != 'custom_tool_call_output':
            continue
        for block in p.get('output', []):
            try:
                envelope = json.loads(block.get('text', ''))
            except (ValueError, TypeError):
                continue
            if not isinstance(envelope, dict):
                continue
            for inner in envelope.get('content', []):
                if envelope.get('isError'):
                    errors.append({'call_id': p['call_id'], 'message': inner.get('text')})
                    continue
                try:
                    receipt = json.loads(inner.get('text', ''))
                except (ValueError, TypeError):
                    continue
                if isinstance(receipt, dict) and 'receipt_id' in receipt:
                    delivered[receipt['receipt_id']] = {'call_id': p['call_id'], 'result': receipt}
    checked = []
    for rid, metadata in state['receipts'].items():
        record = records[metadata['evidence_id']]
        content = record['content'][metadata['start_char']:metadata['end_char']]
        base = {**metadata, 'content': content}
        expected = digest(base)
        actual = delivered[rid]['result']
        checks = {
            'source_hash_valid': digest(record['content']) == record['sha256'] == metadata['source_sha256'],
            'receipt_recomputed': expected == rid,
            'actual_model_input_exact': all(actual[k] == v for k, v in base.items()),
        }
        assert all(checks.values()), (rid, checks)
        checked.append({'receipt_id': rid, **metadata, 'visibility': record['visibility'],
                        'delivered_in_call': delivered[rid]['call_id'], **checks})
    assert set(delivered) == set(state['receipts'])
    coverage = []
    for eid, record in records.items():
        ranges = sorted([r['start_char'], r['end_char']] for r in checked if r['evidence_id'] == eid)
        merged = []
        for lo, hi in ranges:
            if merged and lo <= merged[-1][1]:
                merged[-1][1] = max(hi, merged[-1][1])
            else:
                merged.append([lo, hi])
        coverage.append({'evidence_id': eid, 'visibility': record['visibility'],
            'total_chars': len(record['content']), 'read_ranges': merged,
            'unique_read_chars': sum(hi-lo for lo, hi in merged),
            'fully_read': merged == [[0, len(record['content'])]]})
    ref_checks = []
    def check_refs(obj, path='result'):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == 'refs':
                    ref_checks.append({'path': path, 'refs': v,
                       'all_actually_delivered': all(r in delivered for r in v),
                       'all_public': all(records[state['receipts'][r]['evidence_id']]['visibility'] == 'public' for r in v)})
                else:
                    check_refs(v, f'{path}.{k}')
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check_refs(v, f'{path}[{i}]')
    check_refs(result)
    assert all(r['all_actually_delivered'] for r in ref_checks)
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
    assert before == after
    audit = {
        'schema_version': 'iv-native-judge-independent-review-1', 'call_id': call['call_id'],
        'scope': 'Historical native judge actions and exact delivered evidence; independent semantic review. No new model or submitted-code execution.',
        'source_hashes': before, 'rollout_path': str(rollout_path),
        'rollout_sha256': hashlib.sha256(rollout_path.read_bytes()).hexdigest(),
        'new_model_calls': 0, 'historical_files_unchanged': before == after,
        'observed_score_preserved': result['quality'], 'dimension_scores_preserved': result['dimension_scores'],
        'score_replaced': False, 'formal_acceptance': False,
        'trace': {'outer_tool_calls': len(calls), 'evidence_read_attempts': state['tool_calls'],
           'successful_exact_delivery_receipts': len(checked), 'failed_reads': errors,
           'text_chars': state['returned_text_chars_with_repeats'],
           'text_budget': manifest['max_text_chars'], 'tool_budget': manifest['max_tool_calls'],
           'tool_calls': calls, 'receipts': checked, 'coverage': coverage,
           'all_output_refs_delivered': True, 'reference_checks': ref_checks,
           'judge_container_execution': False,
           'actual_delivery_not_proof_of_cognitive_attention': True},
        'findings': [
          {'id': 'IVJ01', 'severity': 'acceptance_blocking_feedback_boundary',
           'location': 'feedback.limitations[0]',
           'finding': 'Independent numerical reproduction was intentionally sampled is private audit-scope information. The only supplied evidence establishing actual independent numerical replay is private iv-independent-program-check. Public verify_artifacts.py only parses/counts/hashes, and public task says selected-seed verification is planned, not completed.',
           'evidence': ['iv-independent-program-check chars158000:164491', 'artifact-4 full', 'reference-0 full'],
           'boundary': 'No target answer or hidden numerical value leaked by this sentence, but semantic public-only feedback contract is violated despite all explicit feedback refs being public.',
           'recommendation': 'Keep actual private audit scope in internal judgment uncertainty; public feedback limitations must be supported by public trace or explicitly public controller evidence. Do not silently relabel old private evidence.'},
          {'id': 'IVJ02', 'severity': 'rubric_overconstraint_risk',
           'location': 'judgment.dimensions.rigor.rationale; feedback.issues[1]',
           'finding': 'Joint alpha/eta variation prevents independent attribution, but H2 requires characterization of selected rate-pair dependence and empirical beyond-bound outcomes; it does not require individual causal attribution or a factorial design. Submission and report explicitly limit claims to four selected pairs. Treating this as an unconditional scientific defect adds an unstated requirement.',
           'recommendation': 'Make separate-effect comparisons conditional on an actual individual-parameter claim; otherwise record scope limitation without mandatory penalty. No mandated grid or repeat count.',
           'score_boundary': 'Rigor3 also cites the real H2 denominator defect. This audit cannot infer the counterfactual score or replace quality3.5.'},
          {'id': 'IVJ03', 'severity': 'correct_scientific_detection',
           'finding': 'Judge identified completed-only H2 selection producing0/0 while all13 beyond-bound trajectories failed numerically, distinguished retained raw evidence from defective report summary, and acknowledged explicit submission disclosure. Negative empirical outcomes were not mistaken for missing runs.',
           'mechanical_facts': {'trajectories':48,'completed_inside_both':35,'beyond_numerical_failure':13,'inside_tolerance_hits':30,'completed_final_error_below_2sls':20}},
          {'id': 'IVJ04', 'severity': 'correct_scope_and_implementation',
           'finding': 'Judge read all delivered experiment code, config, public method/generator specification and successful entrypoint receipt. Frozen-old-state updates, no division by n, generator and bounds agree with prior independent audit. H1 finite3000-iteration tolerance outcomes were not called refutation of the asymptotic theorem. H3 paired dependence and finite-sample scope were retained.',
           'prior_audit': 'research/benchmark/audit/iv_budget_independent_review_v1.json'},
          {'id': 'IVJ05', 'severity': 'coverage_limit_not_hidden',
           'finding': 'Direct raw reading is only chars0:6000, a prefix of the first trajectory; report reading is only0:6000. Full48-row/432-aggregate claims rely on the separately supplied controller program check, whose summary and partial replay scope were actually delivered. Judge explicitly disclosed partial reading; do not call this direct full-raw inspection or judge-autonomous recomputation.',
           'unread_private_reference': 'reference-3 contains source locators/facts/rights/provenance and planned checks. Not read; main scientific conditions duplicated in fully-read public task. Thus absence does not by itself invalidate this run, but source-paper provenance was not independently verified by judge.',
           'replay_scope': 'Prior maintainer check:8 prefixes,2seeds,t<=64,2400metric comparisons; not all48 full trajectories.'},
          {'id': 'IVJ06', 'severity': 'resource_scope',
           'finding': 'Complete published event timeline was delivered;14/16model,13/120tool,737.485/1200seconds consistent with prior executor audit. resource4 separately reported. Old32MiB/1000collection policy was not explicitly public in this historical TaskView; this is platform admission debt, not a solver violation. The run did not hit collection cap.'}
        ],
        'check_adjudication': [
            {'check_id': c['check_id'], 'original_state': c['state'],
             'assessment': ('Qualified: resource/science separation is structurally correct, but stated rate-attribution weakness has IVJ02 overconstraint risk.' if c['check_id']=='scientific_quality_not_offset_by_resources' else
                            'Supported within stated sampled/raw and entrypoint-only scope; no claim all dependencies or all numerical trajectories independently rerun by judge.')}
            for c in result['judgment']['checks']],
        'conclusion': 'Real improvement in scientific evidence use: not schema-only and not blindly accepting solver H2 report. Retain historical3.5 as development result, but feedback semantic boundary and rate-attribution rubric calibration require remediation before acceptance. No score change or prompt change performed.'
    }
    out = Path(__file__).parent/'audit'/'iv_native_judge_independent_review_v1.json'
    if out.exists():
        raise RuntimeError('Refusing to overwrite historical audit')
    out.write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'audit':str(out),'receipts':len(checked),'errors':errors,'score_preserved':result['quality'],'files_unchanged':before==after}))


if __name__ == '__main__':
    main()
