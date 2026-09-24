"""Development stage adapter and read-only, externally attested review resolver.

No review is inferred from a score. Filesystem hashes are controller integrity
bindings, not digital signatures or an OS sandbox. Review files must be written
only by the trusted maintainer/independent reviewer, never by the evaluated agent.
"""
from pathlib import Path
import base64
import copy

from .io import ProtocolError, contained, digest, file_hash, parse_json, read_json, write_json
from .judging import EvidenceSession
from .materials import load_task
from .scoring import validate_grade


def manifest(root):
    root = Path(root).resolve(strict=True)
    return [{'path':p.relative_to(root).as_posix(), 'sha256':file_hash(contained(root,p.relative_to(root).as_posix(),must_exist=True))}
            for p in sorted(root.rglob('*')) if p.is_file()]


def _file(path):
    path=Path(path).resolve(strict=True)
    return {'path':str(path),'sha256':file_hash(path)}


def _checked(binding):
    path=Path(binding['path'])
    if file_hash(path)!=binding['sha256']:
        raise ProtocolError('Bound evaluation evidence changed')
    return path


def _native_response(call):
    text=call['response'].strip()
    if text.startswith('```'):
        text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    return parse_json(text)


def project_public_evidence(records, state, destination):
    """Public-tag AND origin whitelist; never copy judgment or private checks.

    Semantic safety of the public projection remains an explicit review gate.
    Complete records are available, not automatically read by the builder.
    """
    destination=Path(destination).resolve()
    if destination.exists():raise ProtocolError('Fresh public projection required')
    EvidenceSession(records)  # Validate immutable content hashes and identities.
    destination.mkdir(parents=True)
    index=[]; public={}
    allowed={'task','submission','platform_trace','reference','rendered_artifact','program_check'}
    for row in records:
        if row['visibility']!='public' or row['origin'] not in allowed:continue
        key=row['evidence_id']; stem=digest(key)
        suffix={ 'text/plain':'.txt','image/png':'.png','image/jpeg':'.jpg'}[row['media_type']]
        name='records/'+stem+suffix; target=destination/name;target.parent.mkdir(exist_ok=True)
        data=row['content'].encode('utf-8') if row['media_type']=='text/plain' else base64.b64decode(row['content'],validate=True)
        target.write_bytes(data)
        index.append({'evidence_id':key,'path':name,'sha256':file_hash(target),
                      'origin':row['origin'],'visibility':'public','media_type':row['media_type'],'content_sha256':row['sha256']})
        public[key]=row
    receipts={}
    for rid, meta in state.get('receipts',{}).items():
        key=meta['evidence_id']
        if key not in public:continue
        row=public[key]
        if meta['source_sha256']!=row['sha256']:raise ProtocolError('Public receipt source mismatch')
        if row['media_type']=='text/plain':
            if 'start_char' in meta:
                content=row['content'][meta['start_char']:meta['end_char']]
            else:
                lines=row['content'].splitlines()
                content='\n'.join(f'{i+1}: {lines[i]}' for i in range(meta['start_line']-1,meta['end_line']))
            if digest({**meta,'content':content})!=rid:raise ProtocolError('Public receipt hash mismatch')
            receipts[rid]={**meta,'content':content}
        else:
            if digest({**meta,'content':row['content']})!=rid:raise ProtocolError('Public image receipt mismatch')
            receipts[rid]={**meta,'content_location':'See indexed image; receipt alone does not attest model pixel delivery.'}
    write_json(destination/'receipts.json',receipts,exclusive=True)
    write_json(destination/'index.json',{'schema_version':'public-evidence-projection-1','records':index,
        'receipts_path':'receipts.json','receipts':{k:{x:y for x,y in v.items() if x!='content'} for k,v in receipts.items()},
        'scope':'Public execution evidence and public judge-read receipt excerpts only. No private records, judge rationale, score, or review. Public program checks remain subject to projection semantic review. Availability is not inspected coverage.'},exclusive=True)
    files=manifest(destination)
    return {'root':str(destination),'files':files,'index_path':'index.json','manifest_hash':digest(files)}


def _verify_request(request):
    if request.get('development') is not True:raise ProtocolError('Development adapter only')
    identity=request['identity']; task=load_task(Path(request['package'])/'task.json')
    if task['split']!='development' or any(task[k]!=identity[k] for k in ('task_id','task_type','paper_id')):
        raise ProtocolError('Development package identity mismatch')
    package_hash=digest(manifest(request['package']))
    if request.get('package_hash',package_hash)!=package_hash:raise ProtocolError('Frozen package hash mismatch')
    harness=contained(Path(request['harness_directory']),'harness.py',must_exist=True)
    if digest(manifest(request['harness_directory']))!=request['harness_hash']:
        raise ProtocolError('Frozen harness tree hash mismatch')
    return task,harness,package_hash


def freeze_evaluation(request, *, stage_directory, destination, judge_directory=None, result_path=None):
    """Map existing actual stage/judge artifacts without invoking a model.

    Overrides select explicit historical judge/revalidation files; they do not
    grant acceptance or pretend those bytes belonged to a different invocation.
    """
    task,harness,package_hash=_verify_request(request)
    stage=Path(stage_directory).resolve(strict=True); destination=Path(destination).resolve()
    if destination.exists():raise ProtocolError('Fresh evaluation freeze required')
    judge=Path(judge_directory).resolve(strict=True) if judge_directory else stage/'judge'
    view=read_json(stage/'public/task.json'); invocation=read_json(stage/'execution/invocation.json')
    expected_view=copy.deepcopy(task['public'])
    expected_view.update(asset_manifest=[{'asset_id':a['asset_id'],'path':'assets/'+a['path'],'sha256':a['sha256']}
        for a in task['assets'] if a['visibility']=='public'],release_mode='development_not_formal_acceptance')
    if view!=expected_view:
        raise ProtocolError('Observed stage identity mismatch')
    if invocation['task_sha256']!=file_hash(stage/'public/task.json') or invocation['harness_sha256']!=file_hash(harness):
        raise ProtocolError('Observed stage task/harness mismatch')
    attachments={name:_file(path) for name,path in {
        'released_task':stage/'public/task.json','invocation':stage/'execution/invocation.json',
        'execution':stage/'execution/run.json','submission':stage/'execution/submission.json',
        'evidence_manifest':judge/'evidence_manifest.json','native_call':judge/'native_call.json',
        'candidate':judge/'candidate_judgment.json','tool_state':judge/'tool_state.json','prompt':judge/'prompt.txt'}.items()}
    candidate=read_json(_checked(attachments['candidate'])); call=read_json(_checked(attachments['native_call']))
    if call.get('status')!='completed' or _native_response(call)!=candidate:
        raise ProtocolError('Native invocation did not produce this same-turn candidate')
    if set(candidate)!={'judgment','feedback'}:raise ProtocolError('Same-turn judgment/feedback envelope required')
    evidence=read_json(_checked(attachments['evidence_manifest']))['records']
    evidence_task=[r for r in evidence if r['evidence_id']=='task']
    if len(evidence_task)!=1 or parse_json(evidence_task[0]['content'])!=view:
        raise ProtocolError('Judge evidence task differs from actual released stage')
    chosen=Path(result_path) if result_path else judge/'result.json'
    if chosen.exists():attachments['validated_result']=_file(chosen)
    if (judge/'native_tool_audit.json').exists():
        attachments['native_tool_audit']=_file(judge/'native_tool_audit.json')
    rollout=call.get('rollout_capture',{}).get('path')
    if rollout:
        attachments['native_rollout']=_file(rollout)
        if call['rollout_capture'].get('sha256')!=attachments['native_rollout']['sha256']:
            raise ProtocolError('Native exact-rollout capture hash mismatch')
    state=read_json(_checked(attachments['tool_state']))
    destination.mkdir(parents=True)
    bundle=project_public_evidence(evidence,state,destination/'public_evidence')
    binding={'task_id':task['task_id'],'task_type':task['task_type'],'paper_id':task['paper_id'],
             'routing_split':request['identity']['split'],'version_id':request['version_id'],
             'harness_hash':request['harness_hash'],'package_hash':package_hash,
             'released_task_sha256':attachments['released_task']['sha256'],
             'native_call_sha256':attachments['native_call']['sha256'],
             'candidate_sha256':attachments['candidate']['sha256'],
             'validated_result_sha256':attachments.get('validated_result',{}).get('sha256'),
             'evidence_manifest_sha256':attachments['evidence_manifest']['sha256'],
             'same_turn_feedback_hash':digest(candidate['feedback']),
             'public_evidence_bundle_hash':bundle['manifest_hash']}
    if 'native_tool_audit' in attachments:
        binding['native_tool_audit_sha256']=attachments['native_tool_audit']['sha256']
    evaluation={'schema_version':'development-evaluation-pending-1','status':'pending_review',
        'request_hash':digest(request),'identity':copy.deepcopy(request['identity']),
        'scientific_binding':binding,'attachments':attachments,'public_evidence_bundle':bundle,
        'native_call_id':call['call_id'],'native_judgment_status':candidate['judgment']['status'],
        'automatic_zero':False,'formal':False,'acceptance':'No trajectory, semantic feedback or image-delivery gate inferred from scoring.'}
    write_json(destination/'evaluation_pending.json',evaluation,exclusive=True)
    return evaluation


class StageEvaluationAdapter:
    def __init__(self, *, binary, stage_runner=None, context_policy=None, roles=None):
        self.binary=str(Path(binary).resolve())
        self.stage_runner=stage_runner
        self.context_policy=copy.deepcopy(context_policy)
        self.roles=copy.deepcopy(roles)
        if roles is not None and context_policy is not None:
            raise ProtocolError('Codex context policy and Claude roles are exclusive')
        if self.context_policy is not None:
            from .context_policy import validate_policy
            validate_policy(self.context_policy,Path(self.binary))

    def __call__(self, *, request):
        _verify_request(request)
        output=Path(request['output_directory']).resolve()
        if output.exists():raise ProtocolError('Fresh evaluation output required; pending review must resume without reevaluation')
        runner=self.stage_runner
        if runner is None:
            from run_container_stage_development import run_stage
            runner=run_stage
        # Controller-only request is not itself a model prompt. run_stage exports
        # only the fixed public TaskView, then executes the frozen harness.
        runner(package=request['package'],harness=str(Path(request['harness_directory'])/'harness.py'),
               output=str(output),binary=self.binary,skip_judge=False,
               **({'context_policy':self.context_policy} if self.context_policy is not None else {}),
               **({'roles':self.roles} if self.roles is not None else {}))
        return freeze_evaluation(request,stage_directory=output,destination=output/'evolution_review')


def review_template(*, request, evaluation):
    """Return an UNAPPROVED template. Caller may write a fresh review slot only.

    No score, reviewer, evidence or passing gate is invented. Supplying an actual
    file path here does not attest its content or image-delivery correctness.
    """
    if evaluation.get('request_hash')!=digest(request):
        raise ProtocolError('Template request differs from frozen evaluation')
    names=['trajectory','semantic_feedback','public_projection']
    state=read_json(_checked(evaluation['attachments']['tool_state']))
    if state.get('image_results_returned'):names.append('image_delivery')
    gates={name:{'status':'pending','reviewer':None,'note':None,'evidence':[]} for name in names}
    if 'image_delivery' in gates:
        gates['image_delivery'].update(receipt_ids=[],expected_receipt_ids=state['image_results_returned'])
    return {'schema_version':'development-evaluation-review-1','status':'pending',
        'binding':{'request_hash':digest(request),'evaluation_hash':digest(evaluation)},
        'scientific_binding':copy.deepcopy(evaluation['scientific_binding']),
        'gates':gates,'validated_result':copy.deepcopy(evaluation['attachments'].get('validated_result')),
        'review_scope':'Trajectory, current same-turn public feedback AND full public projection semantics; image delivery if applicable. Trusted reviewer only; no automated pass or score edit.'}


class ReadOnlyReviewResolver:
    """Pure reader. Externally authored approval file is <request_hash>.json.

    Each gate is {status:'passed', reviewer:..., evidence:[{path,sha256}], note:...}.
    Image runs additionally need image_delivery gate, with actual receipt_ids.
    A validated result must exist; pending visual runs may bind an externally
    produced revalidation file. Neither scores nor feedback may be edited here.
    """
    def __init__(self, review_directory):
        self.review_directory=Path(review_directory).resolve()

    def __call__(self, *, request, evaluation, binding):
        expected={'request_hash':digest(request),'evaluation_hash':digest(evaluation)}
        if binding!=expected or evaluation['request_hash']!=expected['request_hash']:
            raise ProtocolError('Review request/evaluation binding mismatch')
        _verify_request(request)
        for asset in evaluation['attachments'].values():_checked(asset)
        if 'native_tool_audit' in evaluation['attachments']:
            tool_audit=read_json(_checked(evaluation['attachments']['native_tool_audit']))
            if tool_audit.get('status') not in {'development_admissible', 'pending_code_mode_review'}:
                return {'status':'pending_review','reason':'Native tool audit failed or lacks required evidence; not a scientific zero.'}
        bundle=evaluation['public_evidence_bundle']
        if manifest(bundle['root'])!=bundle['files'] or digest(bundle['files'])!=bundle['manifest_hash']:
            raise ProtocolError('Public evidence projection changed')
        path=self.review_directory/(expected['request_hash']+'.json')
        if not path.exists():return {'status':'pending_review','reason':'External trajectory/semantic review not signed out.'}
        review=read_json(path)
        if review.get('binding')!=expected or review.get('scientific_binding')!=evaluation['scientific_binding']:
            raise ProtocolError('Review does not bind this exact task/harness/evidence/feedback/bundle')
        if review.get('status')!='approved':return {'status':'pending_review','reason':'External review is not approved.'}
        gates=review.get('gates',{})
        required=['trajectory','semantic_feedback','public_projection']
        state=read_json(_checked(evaluation['attachments']['tool_state']))
        if state.get('image_results_returned'):required.append('image_delivery')
        for name in required:
            gate=gates.get(name,{})
            if gate.get('status')!='passed':return {'status':'pending_review','reason':name+' gate not passed.'}
            if (not isinstance(gate.get('reviewer'),str) or not gate['reviewer'].strip() or
                not isinstance(gate.get('note'),str) or not gate['note'].strip() or
                not isinstance(gate.get('evidence'),list) or not gate['evidence']):
                raise ProtocolError('Passed review requires reviewer, rationale and evidence hashes')
            for source in gate['evidence']:_checked(source)
        if 'image_delivery' in required and set(gates['image_delivery'].get('receipt_ids',[]))!=set(state['image_results_returned']):
            raise ProtocolError('Image-delivery approval must cover every emitted image receipt')
        result_binding=review.get('validated_result') or evaluation['attachments'].get('validated_result')
        if result_binding is None:return {'status':'pending_review','reason':'Native result still awaits structural/image revalidation.'}
        if 'validated_result' in evaluation['attachments'] and result_binding!=evaluation['attachments']['validated_result']:
            raise ProtocolError('Cannot replace the frozen native result during approval')
        result=read_json(_checked(result_binding))
        candidate=read_json(_checked(evaluation['attachments']['candidate']))
        if result.get('judgment')!=candidate['judgment'] or result.get('feedback')!=candidate['feedback'] or result.get('same_turn_feedback') is not True:
            raise ProtocolError('Reviewed result changed original same-turn judgment or feedback')
        if result.get('status')!='scored' or candidate['judgment']['status']!='scored':
            return {'status':'pending_review','reason':'Judge/material/platform failure remains unresolved; not zero.'}
        dimensions={k:v['score'] for k,v in candidate['judgment']['dimensions'].items()}
        if result['dimension_scores']!=dimensions:raise ProtocolError('Validated grades differ from native candidate')
        identity=evaluation['identity']; score={**identity,'status':'scored','dimension_scores':dimensions}
        quality=validate_grade(identity['task_type'],score)
        if result.get('quality')!=quality:raise ProtocolError('Native overall score does not match dimension aggregation')
        records=read_json(_checked(evaluation['attachments']['evidence_manifest']))['records']
        if result['evidence_inventory_hash']!=EvidenceSession(records).inventory_hash or result['public_evidence_inventory_hash']!=EvidenceSession(records,public_only=True).inventory_hash:
            raise ProtocolError('Native result evidence inventory mismatch')
        public_receipts=read_json(Path(bundle['root'])/'receipts.json')
        for issue in candidate['feedback'].get('issues',[]):
            if any(ref not in public_receipts for ref in issue.get('refs',[])):
                raise ProtocolError('Feedback cites evidence not present in reviewed public bundle')
        feedback={'task_id':identity['task_id'],'task_type':identity['task_type'],'mode':'feedback',
            'feedback':copy.deepcopy(candidate['feedback']),'public_evidence_inventory_hash':result['public_evidence_inventory_hash']}
        envelope={'status':'accepted_development','result':score,'feedback':feedback,
            'judge_receipt':{'invocation_id':str(evaluation['native_call_id']), 'same_turn_feedback':True,
                             'trajectory_reviewed':True,'semantic_feedback_reviewed':True},
            'public_evidence_bundle':copy.deepcopy(bundle)}
        return {'status':'approved','binding':expected,'envelope':envelope,'envelope_hash':digest(envelope),
                'review_receipt_hash':file_hash(path)}
