"""Read-only bounded independent code/evidence review; no model calls."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PILOT = Path('D:/mrhbench-local-pilot/collection-lifecycle-abd5e6f341')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            h.update(block)
    return h.hexdigest()


def main():
    targets = ['mrhbench/artifact_policy.py','scripts/prepare/prepare_collection_contract.py',
               'mrhbench/material_adapter.py','mrhbench/stage_controller.py',
               'mrhbench/container_executor.py','scripts/audits/audit_collection_lifecycle.py',
               'mrhbench/evolution_driver.py','mrhbench/evolution.py']
    snapshots = {p:sha(ROOT/p) for p in targets}
    results = []
    for pattern in ['test_artifact_policy.py','test_material_adapter.py',
                    'test_stage_controller_evidence.py','test_evolution_driver.py']:
        run = subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-p',pattern,'-v'],
                             text=True,capture_output=True)
        results.append({'test_file':pattern,'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
    result = read(PILOT/'results.json')
    task = read(PILOT/'public/task.json')
    inv = read(PILOT/'run/invocation.json')
    inventory = read(PILOT/'run/artifact_inventory.json')
    submission = read(PILOT/'run/submission.json')
    run = read(PILOT/'run/run.json')
    artifact = PILOT/'run/artifacts/outputs/large.bin'
    cid = result['cleanup'][0]['container_id']
    probe = subprocess.run(['docker','inspect',cid],text=True,capture_output=True)
    checks = {
        'actual_25MiB': artifact.stat().st_size == 25*1024**2,
        'controller_and_collected_and_submission_hash_match': sha(artifact)==inventory['files'][0]['sha256']==submission['artifacts'][0]['sha256'],
        'published_policy_matches_invocation':task['resources']['artifact_collection']==inv['artifact_collection'],
        'zero_model_calls':run['budget']['used']['model']==0,
        'completed_development_lifecycle':run['status']=='completed_structural_development_check' and run['formal'] is False,
        'exact_owned_container_still_absent':probe.returncode!=0 and 'No such' in probe.stderr,
    }
    report = {
        'schema_version':'collection-evolution-independent-code-review-1',
        'new_model_calls':0,'production_code_modified_by_reviewer':False,
        'reviewed_code_sha256':snapshots,'tests':results,
        'real_lifecycle_evidence': {'directory':str(PILOT),'original_results_sha256':sha(PILOT/'results.json'),
            'independent_read_only_checks':checks,'actual_file_sha256':sha(artifact),
            'container_id':cid,'inspect_returncode':probe.returncode,'inspect_stderr':probe.stderr,
            'scope':'Existing synthetic25MiB success run reverified; no rerun or model. Not a scientific H0 result, full overflow lifecycle test, or cross-host proof.'},
        'findings':[
            {'id':'CE01','severity':'functional_evidence_gap',
             'file':'run_container_stage_development.py:evidence_for_run',
             'finding':'At initial review, text suffix allowlist omitted .jsonl although IV requires replicate_results.jsonl. Collection repair allows this25MiB artifact, but ordinary judge evidence construction still silently omits it. Manual enriched_evidence in historical IV run does not repair future driver runs.',
             'remedy':'Include full immutable JSONL as paginated text evidence; do not force full reading, truncate or treat inclusion as actual judge inspection. Add a regression test.',
             'reported_to_owner_before_changes':True},
            {'id':'CE02','severity':'published_resource_semantics_gap',
             'file':'mrhbench/material_adapter.py:compile_package',
             'finding':'Initial adapter publishes collection numeric/scope policy correctly, but disk_semantics only says total writable tmpfs. Migration script additionally reveals80/20 work/tmp split, memory charging and hard-deadline capture loss. Freshly compiled packages should not omit those operative constraints while migrated packages disclose them.',
             'remedy':'Use one shared public resource-semantics helper for new compilation and migration; preserve historical task bytes.',
             'reported_to_owner_before_changes':True},
            {'id':'CE03','severity':'positive',
             'finding':'Collection policy requires explicit version1 fields, positive integer limits and package-disk bound, exact implemented exclusions and files+directories scope. Runner rejects mismatched collector caps/image/deadline before container execution. Migration copies only manifest assets to a fresh development package, retains pending gates and records unchanged execution budgets.'},
            {'id':'CE04','severity':'positive_with_scope',
             'finding':'Driver dependency/schema/collection preflight occurs before billed calls. R2 LiteratureService receives allowed_versions and shared=True; search/read/judge-page extraction share filtered service. This code does not prove corpus disclosure metadata scientifically correct. Development export rejects search/test packages through materials.export_task.'},
            {'id':'CE05','severity':'development_only_not_formal',
             'file':'mrhbench/evolution_driver.py',
             'finding':'Offline orchestration makes honest non-sandbox/development claims. Minimal task identities are paper-split checked; actual packages must be development; only public search assets/feedback staged; all mixed search and feedback precede next version; selection freezes before every version test evaluation. Resume caches completed operations and does not retry uncertain/failed calls or convert them to zeros. Hashes check snapshots/material/config/cached results.',
             'development_gate':'Suitable for synthetic trusted-adapter orchestration and resume/round-routing tests; the13 tests exercise private canaries and gating at request/projection level.',
             'formal_gate':'Not accepted: callbacks execute in controller process; separate directories are not permissions. judge_receipt reviewed booleans are trusted adapter declarations, not verified native trajectory attestations. Need actual isolated builder/evolver adapters, public-feedback semantic acceptance, bound execution/judge receipts and formal accepted material/splits before native/formal claims. No actual H0 evolution experiment follows from these tests.'}
        ],
        'conclusion':'Collection repair has credible successful25MiB end-to-end evidence and explicit per-task caps. Fix CE01/CE02 before claiming future new-package evidence/constraint disclosure path complete. Offline evolution driver is useful development scaffolding, not autonomous evolution or formal isolation acceptance.',
        'tests_all_pass':all(r['returncode']==0 for r in results),
        'source_snapshot_stable_during_automated_review':{p:sha(ROOT/p)==h for p,h in snapshots.items()},
    }
    dest=ROOT/'audit/collection_evolution_independent_review_v1.json'
    if dest.exists():raise RuntimeError('Historical audit is immutable')
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'audit':str(dest),'checks':checks,'tests_all_pass':report['tests_all_pass']}))


if __name__=='__main__':main()
