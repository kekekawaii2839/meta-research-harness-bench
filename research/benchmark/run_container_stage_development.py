"""One frozen builder harness + one fixed CPU stage + one native judge turn.

Development only. Caller chooses an approved candidate, never formal split data.
"""
import argparse
import base64
import hashlib
import json
import sys
import importlib.metadata
from pathlib import Path
from mrhbench.container_executor import run_container_harness
from mrhbench.costs import CallLedger
from mrhbench.io import read_json,write_json,file_hash,ProtocolError,digest,contained
from mrhbench.judge_runner import evidence_record
from mrhbench.materials import load_task,export_task
from mrhbench.providers import CodexJSONTransport,validate_application_schema
from mrhbench.native_codex import NativeCodexRunner
from mrhbench.native_judge import run_native_judge
from mrhbench.literature import LiteratureService
from mrhbench.literature_judge_evidence import build_literature_judge_evidence
from mrhbench.artifact_policy import collection_policy


def pretty(value):return json.dumps(value,ensure_ascii=False,indent=2)


def frozen_bytes(path, expected_sha256):
    """Verify the exact bytes being represented, not an earlier separate read."""
    data=Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest()!=expected_sha256:
        raise ProtocolError('Frozen evidence bytes changed')
    return data


def captured_artifact_records(run):
    """Expose complete supported files for bounded judge paging, plus all-file inventory.

    Availability is not a claim that the judge read or verified every byte.
    Unsupported encodings/binary formats are explicit, never silently omitted.
    """
    records=[]; inventory=read_json(run/'artifact_inventory.json'); entries=[]
    for i,row in enumerate(inventory['files']):
        path=contained(run/'artifacts',row['path'],must_exist=True)
        data=frozen_bytes(path,row['sha256'])
        suffix=path.suffix.lower();entry=dict(row)
        entry.update(evidence_id=None,raw_file_hash_kind='sha256_raw_file_bytes',evidence_content_sha256=None)
        if suffix in {'.png','.jpg','.jpeg'}:
            records.append(evidence_record('artifact-'+str(i),'rendered_artifact',base64.b64encode(data).decode(),media_type='image/png' if suffix=='.png' else 'image/jpeg'))
            entry.update(evidence_id='artifact-'+str(i),representation='encoded_image_requires_pixel_receipt')
            from mrhbench.image_views import PROVIDER_MAX_SIDE,full_resolution_tiles,image_size
            tiles=full_resolution_tiles(data)
            if tiles:
                # Controller-derived lossless crops so full-resolution detail reaches a model whose
                # transport downscales images above PROVIDER_MAX_SIDE; the original record is unchanged.
                entry['full_resolution_tiles']=[]
                entry['transport_delivery_note']=f'Original {image_size(data)} exceeds {PROVIDER_MAX_SIDE}px and may be delivered downscaled; tiles are exact crops.'
                for t in tiles:
                    tid=f"artifact-{i}-tile-r{t['row']}c{t['col']}"
                    records.append(evidence_record(tid,'rendered_artifact',base64.b64encode(t['png']).decode(),media_type='image/png'))
                    entry['full_resolution_tiles'].append({'evidence_id':tid,'box_left_top_right_bottom':t['box'],'evidence_content_sha256':records[-1]['sha256']})
                records_index=len(records)-len(tiles)-1
                entry['evidence_content_sha256']=records[records_index]['sha256']
        elif suffix in {'.json','.jsonl','.txt','.md','.csv','.py','.svg','.tex'}:
            try: content=data.decode('utf8')
            except UnicodeDecodeError:
                entry['representation']='unsupported_text_encoding_not_readable_by_current_judge'
            else:
                prefix='ARTIFACT '+row['path']+'\n'
                records.append(evidence_record('artifact-'+str(i),'submission',prefix+content))
                entry.update(evidence_id='artifact-'+str(i),representation='complete_text_available_for_paging_not_proof_of_reading',
                             content_transform={'encoding':'utf-8','newline_normalization':False,'prefix':prefix})
        else:entry['representation']='captured_binary_or_unsupported_format_not_exposed_as_content'
        if entry['evidence_id'] is not None and not entry.get('full_resolution_tiles'):entry['evidence_content_sha256']=records[-1]['sha256']
        entries.append(entry)
    records.append(evidence_record('captured-artifact-inventory','platform_trace',pretty({
        'files':entries,'scope':'Controller capture and representation availability, not scientific verification or judge reading coverage.',
        'hash_scope':'Each file sha256 hashes original raw bytes. evidence_content_sha256 is the EvidenceRecord content hash; text includes the declared prefix and no newline conversion. These hash domains are not interchangeable.'})))
    return records


def model_action_records(broker_dir):
    """Observed public actions, not hidden reasoning or a trusted solver narrative.

    The broker proves these messages crossed its boundary. A local error recorded
    by harness code is still an untrusted claim; absence of a cpu.run RPC alone
    must not be presented as proof of an external platform rejection.
    """
    records=[]; seen=set()
    for path in sorted(Path(broker_dir).glob('rpc-*.json')):
        row=read_json(path)
        if row.get('request',{}).get('operation')!='complete':continue
        request=row['request']['arguments']['request']
        value={'sequence':row['request']['sequence'],
               'model_response_observed':row['response'],
               'control_sent_by_harness_untrusted':request.get('control'),
               'scientific_status':'Proposed code or actions are not executed artifacts. Check actual tool receipts.'}
        records.append(evidence_record('model-action-'+path.stem,'platform_trace',pretty(value)))
        for event in request.get('event_history',[]):
            if not isinstance(event,dict) or event.get('kind') not in {'tool_error','tool_denied','model_error'}:continue
            key=digest(event)
            if key in seen:continue
            seen.add(key)
            records.append(evidence_record('harness-local-report-'+key,'platform_trace',pretty({
                'trust':'Controller observed worker reporting this; report contents are not independently trusted.',
                'report':event})))
    return records


def output_inventory_for_run(task_type, run):
    """Attest capture, not visual/scientific validity or solver self-report."""
    if task_type!='WRITE_EVIDENCE':return None
    run=Path(run)
    state=read_json(run/'run.json')
    captured=read_json(run/'artifact_inventory.json')['files']
    files=[]
    for row in captured:
        path=contained(run/'artifacts',row['path'],must_exist=True)
        if file_hash(path)!=row['sha256']:raise ProtocolError('Captured output changed')
        files.append({'path':row['path'],'sha256':row['sha256']})
    complete=state['status']=='completed_structural_development_check'
    has_image=any(Path(row['path']).suffix.lower() in {'.png','.jpg','.jpeg'} for row in files)
    return {'version':1,'collection_status':'complete' if complete else 'unknown',
        'evaluation_inputs_available':True,'expected_outputs':['task-required rendered visual'],
        'observed_files':files,'missing_outputs':[] if has_image else [{
            'requirement':'task-required rendered visual','role':'rendered_artifact',
            'reason':'solver_not_produced' if complete else 'unknown'}]}


def evidence_for_run(task,package,public,run):
    from mrhbench.execution_identity import public_input_identities
    view=read_json(public/'task.json');submission=read_json(run/'submission.json')
    records=[evidence_record('task','task',pretty(view)),evidence_record('submission','submission',pretty(submission))]
    manifests=list((run/'container').glob('*-manifest.json'))
    if len(manifests)!=1:raise ProtocolError('Missing or ambiguous controller input manifest; do not infer execution identity')
    identities=public_input_identities(view,read_json(manifests[0]),public)
    records.append(evidence_record('platform-public-input-identities','platform_trace',pretty(identities)))
    platform=(run/'platform.jsonl').read_text(encoding='utf8')
    records.append(evidence_record('platform-events','platform_trace',platform))
    config=read_json(next((run/'container').glob('*-inspect_start.json')))
    host=config['HostConfig']
    enforcement={k:host.get(k) for k in ('NanoCpus','Memory','MemorySwap','PidsLimit','Tmpfs','ReadonlyRootfs','NetworkMode','CapDrop','SecurityOpt','Privileged','DeviceRequests')}
    enforcement.update(user=config['Config']['User'],image_id=config['Image'],
        budget=read_json(run/'run.json')['budget'],task_elapsed_seconds=read_json(run/'run.json')['task_elapsed_seconds'],
        timing_note='Budget start/expires define task window. Per-command wall_seconds is NOT total session elapsed. Tool call count counts broker calls, not all CPU operations.',
        trace_limitations=['Execution snapshots cover entrypoint only; imports may change.','Worker statuses and artifact text are untrusted.','Container isolation diagnostics do not prove scientific correctness.'])
    records.append(evidence_record('platform-enforcement','platform_trace',pretty(enforcement)))
    records.extend(model_action_records(run/'broker'))
    for path in sorted((run/'broker').glob('rpc-*.json')):
        row=read_json(path)
        if row.get('request',{}).get('operation')=='tool':
            records.append(evidence_record('platform-'+path.stem,'platform_trace',pretty(row)))
    for path in sorted((run/'container/executed-entrypoints').glob('*.py')):
        records.append(evidence_record('executed-'+path.stem,'platform_trace',frozen_bytes(path,path.stem).decode('utf8')))
    public_bindings=[]
    for i,asset in enumerate(task['assets']):
        content=frozen_bytes(contained(package,asset['path'],must_exist=True),asset['sha256']).decode('utf8')
        prefix='ASSET '+asset['asset_id']+'\n'
        record=evidence_record('reference-'+str(i),'reference',prefix+content,visibility=asset['visibility'])
        records.append(record)
        if asset['visibility']=='public':
            public_bindings.append({'asset_id':asset['asset_id'],'raw_file_sha256':asset['sha256'],
                'evidence_id':record['evidence_id'],'evidence_content_sha256':record['sha256'],
                'content_transform':{'encoding':'utf-8','newline_normalization':False,'prefix':prefix}})
    records.append(evidence_record('platform-public-reference-bindings','platform_trace',pretty({
        'assets':public_bindings,
        'scope':'Public source byte hashes to declared judge representations only; no private source inventory. Raw file hashes and canonical EvidenceRecord content hashes are different domains.'})))
    records.extend(captured_artifact_records(run))
    check={'scope':'Application schema structure only, not scientific quality'}
    try:
        validate_application_schema(view['output_contract'],submission['content'],check_response=True);check['schema_valid']=True
    except Exception as exc:check.update(schema_valid=False,error=str(exc))
    records.append(evidence_record('output-contract-check','program_check',pretty(check)))
    return records


def validate_roles(roles):
    if not isinstance(roles,dict) or roles.get('schema_version')!='role-transport-1' or roles.get('transport')!='claude':
        raise ProtocolError('Unknown role configuration')
    for role in ('executor','judge'):
        spec=roles.get(role)
        if not isinstance(spec,dict) or not isinstance(spec.get('model'),str) or spec.get('effort') not in {'low','medium','high','xhigh','max'}:
            raise ProtocolError('Role configuration lacks model/effort for '+role)


def run_stage(package,harness,output,binary,skip_judge=False,context_policy=None,roles=None):
    root=Path(__file__).resolve().parent
    package,harness,output=Path(package).resolve(),Path(harness).resolve(),Path(output).resolve()
    if output.exists():raise ProtocolError('Fresh stage output required')
    if context_policy is not None:
        from mrhbench.context_policy import validate_policy
        validate_policy(context_policy,Path(binary))
    task=load_task(package/'task.json')
    # Controller dependencies must fail before starting a worker or a billed call.
    # Different Python installations on this host do not share optional packages.
    validate_application_schema(task['public']['output_contract'])
    collection=collection_policy(task['public']['resources'])
    dependency_versions={'jsonschema':importlib.metadata.version('jsonschema')}
    if task['private'].get('corpus_configuration'):
        import pypdf
        dependency_versions['pypdf']=pypdf.__version__
    output.mkdir(parents=True)
    write_json(output/'controller_environment.json',{'python':sys.executable,'version':sys.version,'dependencies':dependency_versions})
    export_task(task,package,output/'public',audience='development_executor')
    view=read_json(output/'public/task.json');literature=None
    corpus=task['private'].get('corpus_configuration')
    if corpus:
        manifest=root.parents[1]/corpus['corpus_manifest']
        if file_hash(manifest)!=corpus['corpus_sha256']:raise ProtocolError('Frozen R2 corpus manifest changed')
        docs=read_json(manifest)['documents']
        literature=LiteratureService(docs,root.parents[1],corpus['cutoff'],set(corpus['excluded_papers']),shared=True,
                                     excluded_aliases=corpus.get('excluded_aliases',()),
                                     allowed_versions=corpus.get('allowed_versions'))
    ledger=CallLedger(root/'audit/development_call_ledger.json')
    if context_policy is not None:write_json(output/'context_policy.json',context_policy,exclusive=True)
    if roles is not None:
        # AGENTS §0.2.13: explicit frozen role configuration; binary is the claude CLI.
        from mrhbench.claude_transport import ClaudeJSONTransport
        validate_roles(roles)
        write_json(output/'role_configuration.json',roles,exclusive=True)
        provider=ClaudeJSONTransport(binary=Path(binary),model=roles['executor']['model'],reasoning_effort=roles['executor']['effort'],ledger=ledger,audit_root=output/'executor_calls',timeout_seconds=view['resources']['execution_budget']['wall_seconds'])
    else:
        provider=CodexJSONTransport(binary=Path(binary),model='gpt-5.6-sol',reasoning_effort='medium',ledger=ledger,audit_root=output/'executor_calls',timeout_seconds=view['resources']['execution_budget']['wall_seconds'],context_policy=context_policy)
    result=run_container_harness(harness=harness,public_root=output/'public',image_id=view['resources']['image_id'],provider=provider,output=output/'execution',literature=literature,max_artifact_bytes=collection['max_total_bytes'],max_artifact_files=collection['max_entries'])
    records=evidence_for_run(task,package,output/'public',output/'execution')
    if literature is not None:
        records.extend(build_literature_judge_evidence(literature,allow_incomplete=True))
    write_json(output/'evidence.json',records)
    if not skip_judge:
        if roles is not None:
            from mrhbench.claude_transport import ClaudeNativeRunner
            runner=ClaudeNativeRunner(binary=Path(binary),model=roles['judge']['model'],reasoning_effort=roles['judge']['effort'],ledger=ledger,audit_root=output/'judge_calls',timeout_seconds=roles['judge'].get('timeout_seconds',600))
        else:
            runner=NativeCodexRunner(binary=Path(binary),model='gpt-5.6-sol',reasoning_effort='medium',ledger=ledger,audit_root=output/'judge_calls',permission_profile=':read-only',timeout_seconds=600,context_policy=context_policy)
        judge=run_native_judge(runner=runner,task_id=task['task_id'],task_type=task['task_type'],records=records,output=output/'judge',python_binary=Path(sys.executable),controller_output_inventory=output_inventory_for_run(task['task_type'],output/'execution'))
        write_json(output/'judge_run_result.json',judge)
    return {'submission_status':result['status'],'output':str(output),'formal':False,'manual_trajectory_review_required':True}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('package','harness','output','binary'):p.add_argument('--'+key,required=True)
    p.add_argument('--skip-judge',action='store_true');p.add_argument('--context-policy',type=Path);p.add_argument('--roles',type=Path);a=p.parse_args()
    if a.roles and a.context_policy:raise ProtocolError('Codex context policy and Claude roles are exclusive')
    print(run_stage(a.package,a.harness,a.output,a.binary,a.skip_judge,read_json(a.context_policy) if a.context_policy else None,read_json(a.roles) if a.roles else None))
