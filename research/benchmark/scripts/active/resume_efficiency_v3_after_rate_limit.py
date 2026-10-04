"""Explicit user-authorized fresh batch after call 609's terminal rate limit.

Zero-call prepare; one specified arm per run. The original frozen experiment,
failed call and output remain unchanged. This is not an automatic retry, and
new rate limits stop the new bounded ledger window as usual.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

BENCHMARK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCHMARK))
from mrhbench import factory_efficiency_v3 as engine
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, read_json, write_json, utc_now, digest

VERIFY_ORIGINAL = engine.verify_execution
EXPECTED = {"status":"user_continuation_authorization_not_provider_availability_proof",
            "ledger_baseline":609,"pair_max_calls":12,"pair_stop_at":621,
            "goal_original_baseline":605,"goal_stop_at":625,"remaining_total_calls":16,
            "prospective_remaining_after_full_pairs":4,"original_failed_attempt_retained":True,
            "new_429_stops_new_batch":True,"automatic_retries":False}


def tree(root):
    root = Path(root).resolve()
    return [engine.identity(p) for p in sorted(root.rglob('*')) if p.is_file()]


def validate_original_failure(root, manifest, cases, state):
    if cases['ledger_baseline'] != 608 or cases['ledger_stop_at'] != 625:
        raise ProtocolError('Not the original v3 boundary')
    if any(a['status'] == 'reserved' for a in state['attempts']):
        raise ProtocolError('Outstanding/uncertain attempt; do not restart')
    call = state['attempts'][608] if len(state['attempts']) >= 609 else {}
    first = cases['cases'][0]
    if first['case_id'] != 'exp_autonomy_repair' or first['order'] != ['old','incremental']:
        raise ProtocolError('Not the frozen first EXP arm')
    arm = Path(root)/'arms'/first['case_id']/'old'
    actual_arms = sorted(p.resolve() for p in (Path(root)/'arms').glob('*/*') if p.is_dir())
    if actual_arms != [arm.resolve()]:
        raise ProtocolError('Unexpected other original arm')
    if (call.get('id') != 609 or call.get('status') != 'failed' or call.get('role') != 'constructor'
        or call.get('metadata',{}).get('failure_class') != 'provider_rate_limit'
        or not Path(call.get('artifact_directory','')).resolve().is_relative_to(arm.resolve())):
        raise ProtocolError('Only the known terminal 609 provider-rate-limit is resumable')
    result = read_json(arm/'result.json')
    if result.get('status') != 'failed_needs_attribution' or result.get('cost',{}).get('call_ids') != [609]:
        raise ProtocolError('Original failure result does not match call 609')
    jobs = result.get('batch',{}).get('jobs',[])
    if len(jobs) != 1 or jobs[0].get('job_id') != first['job_id']:
        raise ProtocolError('Unexpected original batch result')
    output = arm/'batch'/first['job_id']/'constructor/output'
    if any(p.is_file() for p in output.rglob('*')) or (arm/'adjudicator').exists():
        raise ProtocolError('Original candidate/adjudication output exists; explicit attribution required')
    if (arm/'batch'/first['job_id']/'reviewer').exists():
        raise ProtocolError('Original review was already attempted')
    return {'call': deepcopy(call), 'failed_result':engine.identity(arm/'result.json'), 'arm_tree':tree(arm)}


def approval(path, original_root, new_root):
    record = read_json(Path(path))
    if any(record.get(k) != v for k,v in EXPECTED.items()):
        raise ProtocolError('Explicit matching resume authorization required')
    if not isinstance(record.get('user_message'),str) or not record['user_message'].strip():
        raise ProtocolError('User resume message must be preserved explicitly')
    if (Path(record['original_manifest']['path']).resolve().parents[1] != Path(original_root).resolve()
        or Path(record['new_experiment_root']).resolve() != Path(new_root).resolve()):
        raise ProtocolError('Authorization roots mismatch')
    engine.verify_files([record[k] for k in ('original_manifest','failed_result','independent_failure_audit')])
    return record


def prepare(original_root, new_root, approval_path):
    original_root, new_root, approval_path = [Path(p).resolve() for p in (original_root,new_root,approval_path)]
    if new_root.exists() or original_root == new_root or new_root.is_relative_to(original_root) or original_root.is_relative_to(new_root):
        raise ProtocolError('A separate entirely new resume root is required')
    for parent in (new_root,*new_root.parents):
        if any((parent/n).exists() for n in ('AGENTS.md','CLAUDE.md')):
            raise ProtocolError('Resume root inherits maintainer instructions')
    approval(approval_path,original_root,new_root)
    manifest,cases = VERIFY_ORIGINAL(original_root)
    ledger = CallLedger(Path(manifest['ledger_path']))
    with ledger._locked():
        state = ledger._read()
        if state['used_attempts'] != 609:
            raise ProtocolError('Prepare requires actual clean ledger boundary 609')
        failure = validate_original_failure(original_root,manifest,cases,state)
        new_root.mkdir(parents=True,exist_ok=False)
        execution = new_root/'execution'
        execution.mkdir()
        shutil.copytree(original_root/'execution/snapshot',execution/'snapshot')
        shutil.copyfile(Path(__file__),execution/'resume_adapter.py')
        adapted_cases = deepcopy(cases)
        adapted_cases.update(experiment_root=str(new_root),ledger_baseline=609,
                             pair_max_calls=12,ledger_stop_at=625,prospective_max_calls=4)
        write_json(execution/'cases.json',adapted_cases,exclusive=True)
        adapted_manifest = deepcopy(manifest)
        adapted_manifest.update(cases=engine.identity(execution/'cases.json'),
            ledger_baseline_observed=609, original_experiment_root=str(original_root),
            explicit_resume=True, original_failed_call=609)
        write_json(execution/'manifest.json',adapted_manifest,exclusive=True)
        amendment = {'schema_version':'factory-efficiency-v3-resume-execution-1','at':utc_now(),
            'original_root':str(original_root),'new_root':str(new_root),
            'approval':engine.identity(approval_path), 'script':engine.identity(Path(__file__)),
            'adapter_snapshot':engine.identity(execution/'resume_adapter.py'),
            'original_manifest':engine.identity(original_root/'execution/manifest.json'),
            'adapted_manifest':engine.identity(execution/'manifest.json'),
            'adapted_cases':engine.identity(execution/'cases.json'),
            'snapshot_files':tree(execution/'snapshot'),'failure':failure,
            'prior_ledger_digest':digest(state['attempts']),
            'retained_failure':True,'automatic_retry':False,'pair_stop_at':621,'goal_stop_at':625,
            'comparison_limit':'Fresh batch after explicit user resume; call609 cost retained separately and in cumulative goal cost; not a zero-cost restart.'}
        write_json(execution/'resume_amendment.json',amendment,exclusive=True)
    return amendment


def verify_resume(root):
    root = Path(root).resolve()
    amendment = read_json(root/'execution/resume_amendment.json')
    if amendment.get('schema_version') != 'factory-efficiency-v3-resume-execution-1' or Path(amendment['new_root']).resolve() != root:
        raise ProtocolError('Invalid resume amendment')
    engine.verify_files([amendment[k] for k in ('approval','script','adapter_snapshot','original_manifest','adapted_manifest','adapted_cases')])
    original_root = Path(amendment['original_root'])
    approval(amendment['approval']['path'],original_root,root)
    original_manifest,original_cases = VERIFY_ORIGINAL(original_root)
    ledger = CallLedger(Path(original_manifest['ledger_path']))
    with ledger._locked():
        state = ledger._read()
        if not 609 <= state['used_attempts'] <= 621:
            raise ProtocolError('Resume paired window exceeded')
        if digest(state['attempts'][:609]) != amendment['prior_ledger_digest']:
            raise ProtocolError('Historical ledger changed')
        failure = validate_original_failure(original_root,original_manifest,original_cases,state)
        if failure != amendment['failure']:
            raise ProtocolError('Original failed trace/output changed')
        if any(a.get('metadata',{}).get('failure_class') == 'provider_rate_limit' for a in state['attempts'][609:]):
            raise ProtocolError('New provider rate limit stops resumed batch')
    if tree(root/'execution/snapshot') != amendment['snapshot_files']:
        raise ProtocolError('Copied execution snapshot changed')
    expected_cases = deepcopy(original_cases)
    expected_cases.update(experiment_root=str(root),ledger_baseline=609,pair_max_calls=12,ledger_stop_at=625,prospective_max_calls=4)
    cases = read_json(root/'execution/cases.json')
    if cases != expected_cases:
        raise ProtocolError('Only explicit root/budget amendment is permitted')
    manifest = read_json(root/'execution/manifest.json')
    expected_manifest = deepcopy(original_manifest)
    expected_manifest.update(cases=engine.identity(root/'execution/cases.json'),ledger_baseline_observed=609,
                             original_experiment_root=str(original_root),explicit_resume=True,original_failed_call=609)
    if manifest != expected_manifest:
        raise ProtocolError('Unexpected adapted manifest changes')
    return manifest,cases


def run(root,case_id,arm,*,runner_factory=None):
    # Local command scope only; original verifier restored even on exception.
    # All scheduling, per-arm budgets, sidecars and no-retry rules stay unchanged.
    old = engine.verify_execution
    engine.verify_execution = verify_resume
    try:
        return engine.run_arm(root,case_id,arm,runner_factory=runner_factory)
    finally:
        engine.verify_execution = old


def main():
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare')
    prep.add_argument('--original-root',required=True,type=Path)
    prep.add_argument('--root',required=True,type=Path)
    prep.add_argument('--authorization','--approval',dest='approval',required=True,type=Path)
    start=sub.add_parser('run')
    start.add_argument('--root',required=True,type=Path)
    start.add_argument('--case',required=True)
    start.add_argument('--arm',required=True,choices=['old','incremental'])
    args=parser.parse_args()
    result=(prepare(args.original_root,args.root,args.approval) if args.command=='prepare'
            else run(args.root,args.case,args.arm))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
