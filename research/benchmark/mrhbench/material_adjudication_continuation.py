"""One explicit paid-evidence diagnostic adjudication; never revive failed flow."""
from pathlib import Path
import shutil
import time
import jsonschema

from .io import ProtocolError, read_json, write_json, file_hash, digest, utc_now
from .factory_efficiency import identity, verify_files, adjudicate, cost_summary
from .factory_efficiency_regression import verify_execution
from .costs import CallLedger
from .bounded_ledger import BoundedCallLedger
from .claude_transport import ClaudeNativeRunner
from .material_batch import _input_snapshot, _check_inputs
from .material_quality_contract import verify_contract, validate_coverage
from .material_public_surface import public_surface
from .material_public_identity import _tree
from .material_quality_runner import QualityBoundRunner
from .material_identity_runner import IdentityBoundRunner
from .paged_navigation_runner import PagedNavigationRunner

ERROR='Cannot pass unresolved full-package checks: core_science'
AUTH_IDENTITIES=('original_failed_result','independent_conflict_audit','science_review','runtime_record','release_record','goal_authorization')


def validate_inputs(root,authorization_path):
    root=Path(root).resolve();manifest,cases=verify_execution(root)
    auth=read_json(Path(authorization_path));case=cases['cases'][0]
    expected={'schema_version':'material-adjudication-continuation-authorization-1','decision':'allow_adjudication_only',
        'case_id':case['case_id'],'arm':'old','ledger_baseline':615,'ledger_current':617,'phase_stop_at':621,'max_new_calls':1}
    if any(auth.get(k)!=v for k,v in expected.items()):raise ProtocolError('Exact diagnostic-only authorization required')
    verify_files([auth[k] for k in AUTH_IDENTITIES])
    if auth['goal_authorization']!=cases['goal_authorization']:raise ProtocolError('Different goal authorization')
    arm=root/'arms'/case['case_id']/'old';result_path=arm/'result.json';result=read_json(result_path)
    if identity(result_path)!=auth['original_failed_result'] or result.get('status')!='failed_needs_attribution':
        raise ProtocolError('Original flow must remain its exact failed record')
    if (result.get('error')!={'type':'ProtocolError','message':'Constructor/reviewer pipeline failed; no automatic retry'}
        or result.get('cost',{}).get('call_ids')!=[616,617] or len(result.get('batch',{}).get('jobs',[]))!=1
        or result['batch']['jobs'][0].get('error')!={'type':'ProtocolError','message':ERROR}):
        raise ProtocolError('Not the narrowly audited call617 quality-decision contradiction')
    if (arm/'adjudicator').exists():raise ProtocolError('Adjudication already attempted')
    ledger=CallLedger(Path(manifest['ledger_path']))
    state=ledger._read()
    if state['used_attempts']!=617 or any(a['status']=='reserved' for a in state['attempts']):
        raise ProtocolError('Requires clean terminal ledger617; no retry/concurrent continuation')
    for number,role in ((616,'constructor'),(617,'material_reviewer')):
        row=state['attempts'][number-1]
        if row['status']!='completed' or row['role']!=role or not Path(row['artifact_directory']).resolve().is_relative_to(arm):
            raise ProtocolError('Both original native calls must be completed in the original arm')
    reviewer=arm/'batch'/case['job_id']/'reviewer'
    review=read_json(reviewer/'review.json');coverage=read_json(reviewer/'quality_coverage.json')
    contract=read_json(reviewer/'quality_contract.json');surface=public_surface(reviewer/'output')
    jsonschema.validate(review,read_json(reviewer/'quality_output.schema.json'))
    if review.get('decision')!='pass_with_pending_runtime' or review.get('paper_id')!=read_json(Path(case['job_path']))['paper_id']:
        raise ProtocolError('Not the exact raw reviewer pass decision under conflict')
    verify_contract(contract,reviewer/'quality_policy.md',public_inventory=surface['inventory'],package_sha256=surface['package_sha256'])
    # Structural coverage validation deliberately omits a decision only to check
    # the retained ISSUE evidence. This does NOT turn the raw pass into valid pass.
    checked=validate_coverage(coverage,contract)
    if checked['unresolved_checks']!=['core_science'] or coverage['checks']['core_science']['status']!='issue':
        raise ProtocolError('Only the original explicit core_science issue is covered')
    try:validate_coverage(coverage,contract,action=review['decision'])
    except ProtocolError as exc:
        if str(exc)!=ERROR:raise
    else:raise ProtocolError('Original conflict is not present; no diagnostic exception')
    audit=read_json(Path(auth['independent_conflict_audit']['path']))
    required={'schema_version':'review-conflict-independent-audit-1','decision':'eligible_for_explicit_adjudication_only',
        'original_failed_result':auth['original_failed_result'],'original_review':identity(reviewer/'review.json'),
        'original_coverage':identity(reviewer/'quality_coverage.json'),'quality_contract':identity(reviewer/'quality_contract.json'),
        'blocking_findings':[],'scientific_acceptance':False}
    if any(audit.get(k)!=v for k,v in required.items()):raise ProtocolError('Independent complete conflict audit does not authorize this diagnostic')
    for key in ('original_failed_result','original_review','original_coverage','quality_contract'):verify_files([audit[key]])
    if not isinstance(audit.get('evidence_bindings'),list) or not audit['evidence_bindings']:
        raise ProtocolError('Complete independent evidence binding inventory required')
    verify_files(audit['evidence_bindings'])
    ctor=arm/'batch'/case['job_id']/'constructor/output/package.json';package=read_json(ctor)
    if file_hash(ctor)!=surface['package_sha256']:raise ProtocolError('Reviewer candidate differs from completed constructor')
    runtime=read_json(Path(auth['runtime_record']['path']));release=read_json(Path(auth['release_record']['path']))
    if (runtime.get('status')!='passed' or runtime.get('package_json_sha256')!=file_hash(ctor)
        or runtime.get('package_digest')!=digest(package) or Path(runtime.get('output_dir','')).resolve()!=ctor.parent.resolve()
        or release.get('package_sha256')!=file_hash(ctor) or release.get('runtime_record_digest')!=digest(runtime)):
        raise ProtocolError('Independent runtime/release evidence does not bind this candidate')
    return manifest,cases,case,arm,reviewer,state


def prepare(root,destination,authorization_path):
    root,destination,authorization_path=[Path(p).resolve() for p in (root,destination,authorization_path)]
    manifest,cases,case,arm,reviewer,state=validate_inputs(root,authorization_path)
    if destination.exists() or not destination.is_relative_to(root/'continuations'):
        raise ProtocolError('Fresh separate continuation directory under experiment/continuations required')
    destination.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(Path(__file__),destination/'adapter_snapshot.py')
    record={'schema_version':'paid-adjudication-continuation-1','at':utc_now(),'root':str(root),
        'destination':str(destination),'authorization':identity(authorization_path),'original_manifest':identity(root/'execution/manifest.json'),
        'original_arm_inventory':_tree(arm),'ledger_through617_digest':digest(state['attempts']),
        'implementation':identity(Path(__file__)),'snapshot':identity(destination/'adapter_snapshot.py'),
        'original_failed_preserved':True,'raw_review_is_valid_acceptance':False,'automatic_retry':False,'allowed_new_calls':1}
    write_json(destination/'continuation_manifest.json',record,exclusive=True)
    return record


class ConflictEvidenceRunner:
    def __init__(self,inner,reviewer):
        self.inner,self.reviewer=inner,reviewer
        self.integrity_result=None
    def run(self,*,workspace,prompt,role,**kwargs):
        if role!='adjudicator':raise ProtocolError('Continuation only permits adjudicator')
        names=[]
        for original in ('quality_coverage.json','quality_contract.json','quality_coverage.schema.json'):
            target='original_reviewer_'+original
            with (workspace/target).open('xb') as handle:handle.write((self.reviewer/original).read_bytes())
            names.append(target)
        write_json(workspace/'original_review_conflict.json',{'raw_review_decision':'pass_with_pending_runtime',
            'controller_error':ERROR,'original_flow_status':'failed_needs_attribution',
            'raw_review_is_valid_acceptance':False,'core_science_issue_retained':True,
            'purpose':'Independent diagnostic adjudication only; judge the retained issue under the unchanged policy. No prior acceptance is granted.'},exclusive=True)
        names.append('original_review_conflict.json');snapshot=_input_snapshot(workspace,names)
        prompt+='\nRead original_review_conflict.json and original_reviewer_quality_coverage.json in full. The original reviewer pass was INVALID under its retained core_science ISSUE, not accepted. Assess the complete original issue/evidence under the same policy and explicitly adjudicate it; accept or reject arguments on their evidence, never silently normalize the original decision or discard its issue. Your own output must satisfy all original quality gates.\n'
        primary=None
        try:
            return self.inner.run(workspace=workspace,prompt=prompt,role=role,**kwargs)
        except BaseException as exc:
            primary=exc
            raise
        finally:
            try:
                _check_inputs(workspace,names,snapshot,'Diagnostic adjudicator')
                self.integrity_result={'status':'passed','expected':snapshot}
            except Exception as integrity:
                self.integrity_result={'status':'failed','expected':snapshot,
                    'error':{'type':type(integrity).__name__,'message':str(integrity)}}
                if primary is None:raise
                # Preserve the original native/quality exception and expose this
                # secondary integrity failure in the controller continuation row.



def run(destination,*,runner_factory=None):
    destination=Path(destination).resolve();record=read_json(destination/'continuation_manifest.json')
    verify_files([record[k] for k in ('authorization','original_manifest','implementation','snapshot')])
    if Path(record['destination']).resolve()!=destination:raise ProtocolError('Continuation root mismatch')
    root=Path(record['root']);manifest,cases,case,arm,reviewer,state=validate_inputs(root,record['authorization']['path'])
    if _tree(arm)!=record['original_arm_inventory'] or digest(state['attempts'])!=record['ledger_through617_digest']:
        raise ProtocolError('Original paid evidence changed since continuation freeze')
    started=destination/'started.json'
    write_json(started,{'at':utc_now(),'classification':'development_regression','raw_review_is_valid_acceptance':False},exclusive=True)
    ledger=BoundedCallLedger(Path(manifest['ledger_path']),baseline=615,stop_at=621,experiment_root=root,
                             arm_root=destination,arm_maximum=1)
    templates=root/'execution/snapshot/prompts/factory_v4';start=time.monotonic()
    row={'status':'started','original_failed_result':identity(arm/'result.json'),'original_failed_preserved':True,
         'raw_review_is_valid_acceptance':False,'classification':'development_regression','scientific_acceptance':False}
    runner=None
    try:
        native=(runner_factory(ledger,destination) if runner_factory else ClaudeNativeRunner(
            binary=Path(manifest['binary']['path']),model=cases['model'],reasoning_effort=cases['effort'],ledger=ledger,
            audit_root=destination/'native_calls',timeout_seconds=manifest['timeout_seconds'],tool_profile='material_workspace'))
        quality=QualityBoundRunner(native,policy_path=templates/'policy.md',
            project_id=read_json(Path(case['job_path']))['paper_id'],round_no=3)
        runner=ConflictEvidenceRunner(PagedNavigationRunner(IdentityBoundRunner(quality,map_identity=case['identity_map'])),reviewer)
        row['adjudication']=adjudicate(reviewer,destination/'adjudicator',templates,runner,
            read_json(Path(case['job_path']))['paper_id'],3,['pass','pass_partial','drop'])
        row['status']='completed_diagnostic_adjudication_pending_independent_audit'
    except Exception as exc:
        row.update(status='failed_needs_attribution',error={'type':type(exc).__name__,'message':str(exc)})
    finally:
        latest=ledger._read();fresh=[a for a in latest['attempts'][617:] if Path(a.get('artifact_directory','')).resolve().is_relative_to(destination)]
        row.update(new_call_cost=cost_summary(fresh),paid_evidence_total_cost=cost_summary(latest['attempts'][615:617]+fresh),
            elapsed_seconds=time.monotonic()-start,finished_at=utc_now(),ledger_used=latest['used_attempts'])
        row['original_conflict_input_integrity']=getattr(runner,'integrity_result',None)
        try:
            row['original_arm_unchanged']=_tree(arm)==record['original_arm_inventory']
        except Exception as integrity:
            row['original_arm_unchanged']=None
            row['original_arm_integrity_error']={'type':type(integrity).__name__,'message':str(integrity)}
        if row['original_arm_unchanged'] is not True:
            row.update(status='failed_needs_attribution',integrity_error='Original evidence changed or unreadable; primary error retained')
        write_json(destination/'continuation_result.json',row,exclusive=True)
    return row
