"""Concrete development native evolver/selector adapters, not formal isolation.

The Codex host process has a fresh empty cwd and controller-owned MCP tools.
Released search inputs and code enter a credential-free offline Docker container.
The optional hook is defense in depth, not proof against hook-engine fail-open.
Each callback makes at most ONE native invocation; failures are never retried here.
"""
from __future__ import annotations
import copy
import json
import re
from pathlib import Path
import shutil
import sys
from .container_runtime import ContainerSession
from .docker_pilot import resource_args
from .evolution_driver import tree_manifest
from .io import ProtocolError, contained, digest, file_hash, read_json, write_json
from .native_codex import NativeCodexRunner


def released_builder_inputs(request, destination):
    """Publish only the driver's explicitly staged public directories and view."""
    required={'development','operation','workspace','current_harness','search_directory','builder_view','output_directory'}
    if not required <= set(request) or set(request)-required-{'public_evidence_directory'} or request['development'] is not True:
        raise ProtocolError('Explicit development builder request required, no extra controller fields')
    for key in ['workspace','current_harness','search_directory','output_directory','public_evidence_directory']:
        if key in request and not Path(request[key]).is_absolute():
            raise ProtocolError('Builder staging paths must be absolute')
    workspace=Path(request['workspace']).resolve(strict=True)
    view=request['builder_view']
    if set(view)!={'phase','search_tasks','versions','search_scores','search_feedback'} or view['phase']!='search':
        raise ProtocolError('Only a projected search-phase builder view is allowed')
    if not view['versions'] or any(set(v)!={'version_id','hash'} for v in view['versions']):
        raise ProtocolError('Frozen search version identities required')
    target=Path(request['output_directory']).resolve()
    if not target.is_relative_to(workspace) or target==workspace:
        raise ProtocolError('Builder outputs must stay under staging workspace')
    inputs={}
    for key, label in [('current_harness','previous'),('search_directory','search'),('public_evidence_directory','search_evidence')]:
        if key not in request: continue
        path=Path(request[key]).resolve(strict=True)
        if (not path.is_dir() or path==workspace or not path.is_relative_to(workspace)
                or path.is_relative_to(target) or target.is_relative_to(path)):
            raise ProtocolError('Builder input directory is outside its independently staged public tree')
        # Check the original path too; resolving first must not hide a symlink.
        original=Path(request[key])
        contained(workspace,original.absolute().relative_to(workspace).as_posix(),must_exist=True)
        for row in tree_manifest(path):
            inputs[label+'/'+row['path']]=contained(path,row['path'],must_exist=True)
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    write_json(destination/'builder_view.json',view,exclusive=True)
    inputs['builder_view.json']=destination/'builder_view.json'
    return inputs


class NativeDevelopmentBuilder:
    def __init__(self, *, binary, ledger, audit_root, image_id, resources,
                 native_timeout_seconds, max_tool_calls, max_artifact_bytes, max_artifact_entries,
                 use_hook_guard=True, session_factory=ContainerSession, runner_factory=NativeCodexRunner, context_policy=None,
                 model='gpt-5.6-sol', reasoning_effort='medium', interface='interface_container_v2.json'):
        self.binary=Path(binary);self.ledger=ledger;self.audit_root=Path(audit_root).resolve()
        self.image_id=image_id;self.resources=copy.deepcopy(resources)
        self.timeout=native_timeout_seconds;self.tool_calls=max_tool_calls
        self.artifact_bytes=max_artifact_bytes;self.artifact_entries=max_artifact_entries
        self.guard=use_hook_guard;self.session_factory=session_factory;self.runner_factory=runner_factory
        self.context_policy=copy.deepcopy(context_policy)
        # Explicit role configuration (AGENTS §0.2.13); defaults keep the historical Codex builder.
        self.model,self.effort=model,reasoning_effort
        if interface not in {'interface_container_v2.json','interface_container_v3.json','interface_container_v4.json'}:
            raise ProtocolError('Unknown released interface')
        self.interface=interface
        if self.context_policy is not None:
            from .context_policy import validate_policy
            validate_policy(self.context_policy,self.binary)
        if not isinstance(resources,dict):raise ProtocolError('Explicit development container resources required')
        resource_args(resources)  # Pure shared validation before any journal/container/model side effect.
        if not isinstance(image_id,str) or not re.fullmatch('sha256:[0-9a-f]{64}',image_id):
            raise ProtocolError('Explicit immutable development image ID required')
        if type(use_hook_guard) is not bool or type(max_tool_calls) is not int or not 1<=max_tool_calls<=500:
            raise ProtocolError('Explicit bounded development tool profile required')
        if type(native_timeout_seconds) not in (int,float) or not 0<native_timeout_seconds<resources['wall_seconds']:
            raise ProtocolError('Native development deadline must leave container collection time')
        if type(max_artifact_bytes) is not int or not 0<max_artifact_bytes<=resources['disk_mb']*1024**2:
            raise ProtocolError('Explicit development artifact byte limit required')
        if type(max_artifact_entries) is not int or not 0<max_artifact_entries<=100000:
            raise ProtocolError('Explicit development artifact entry limit required')

    def evolve(self, *, request): return self._run(request, selection=False)
    def select(self, *, request): return self._run(request, selection=True)

    def _run(self,request,*,selection):
        operation=request.get('operation')
        if not isinstance(operation,str) or (operation!='select' if selection else re.fullmatch('evolve-H[0-9]+',operation) is None):
            raise ProtocolError('Wrong native builder operation')
        # Stable request-specific path is a second guard against accidental retries.
        audit=self.audit_root/digest(request)
        if audit.exists():raise ProtocolError('Native operation already attempted; adjudicate, never silently rerun')
        audit.mkdir(parents=True)
        inputs=released_builder_inputs(request,audit/'release')
        root=Path(__file__).resolve().parents[1]
        write_json(audit/'release/development_limits.json',{
            'container_resources':self.resources,'native_timeout_seconds':self.timeout,
            'max_tool_calls':self.tool_calls,'max_collected_bytes':self.artifact_bytes,
            'max_collected_entries':self.artifact_entries,
            'scope':'Development invocation safety limits only, not formal outer research budgets.',
            'collection':'All noninternal /work artifacts count, not only /work/candidate; leave time for controller collection.'},exclusive=True)
        # The file-only release protocol otherwise drops empty directories.
        # Materialize a truthful controller inventory rather than promise a
        # directory that will not exist inside the container.
        evidence_status=audit/'release/search_evidence_status.json'
        if 'search_evidence/_controller_availability.json' in inputs:
            raise ProtocolError('Public evidence collides with reserved controller inventory name')
        write_json(evidence_status,{'origin':'controller_public_inventory',
            'released_evidence_file_count':sum(name.startswith('search_evidence/') for name in inputs),
            'scope':'Only files from the independently reviewed public evidence staging; this inventory is not scientific evidence.'},exclusive=True)
        inputs.update({'interface.json':root/'runtime'/self.interface,
                       'EVOLVER_PROMPT.txt':root/'prompts/evolver.txt',
                       'development_limits.json':audit/'release/development_limits.json',
                       'search_evidence/_controller_availability.json':evidence_status})
        clean=audit/'empty_native_workspace';clean.mkdir()
        hashes={name:file_hash(path) for name,path in inputs.items()}
        write_json(audit/'release_manifest.json',{'inputs':hashes,'request_hash':digest(request),
            'purpose':'selection' if selection else 'harness_edit','formal':False,
            'limits_scope':'Development smoke safety limits, not the research outer evolution stopping rule.',
            'container_resources':self.resources,'native_timeout_seconds':self.timeout,
            'max_tool_calls':self.tool_calls,'artifact_limits':{'bytes':self.artifact_bytes,'entries':self.artifact_entries},
            'new_executor_or_judge_runs':0,'hidden_task_release':False},exclusive=True)
        session=self.session_factory(image_id=self.image_id,resources=self.resources,input_files=inputs,
            input_hashes=hashes,audit_dir=audit/'container')
        result=None;primary=None
        try:
            session.start()
            names=['container_read','container_list'] if selection else ['container_read','container_list','container_write','container_exec']
            manifest={'records':[],'max_tool_calls':self.tool_calls,'allowed_tools':names,'state_path':str(audit/'tool_state.json'),
                'container':{'image_id':self.image_id,'resources':self.resources,'input_files':{},
                    'audit_dir':str(audit/'server_container'),
                    'attached_session':{'cid':session.cid,'owner':session.owner,'deadline_monotonic':session.deadline}}}
            write_json(audit/'server_manifest.json',manifest)
            mcp={'mrhbench':{'command':sys.executable,'args':[str(root/'mrhbench/bounded_mcp.py'),'--manifest',str(audit/'server_manifest.json')],
                'enabled_tools':names,'required':True,'tool_timeout_sec':120,'default_tools_approval_mode':'approve'}}
            guard=None
            if self.guard:
                logs=audit/'hook_events';logs.mkdir()
                write_json(audit/'guard.json',{'allowed_tools':['mcp__mrhbench__'+n for n in names],'log_directory':str(logs)})
                guard={'config_path':audit/'guard.json','python_binary':Path(sys.executable)}
            runner=self.runner_factory(binary=self.binary,model=self.model,reasoning_effort=self.effort,ledger=self.ledger,
                audit_root=audit/'calls',permission_profile=':read-only',timeout_seconds=self.timeout,
                tool_profile='bounded_mcp',mcp_servers=mcp,hook_guard=guard,
                **({'context_policy':self.context_policy} if self.context_policy is not None else {}))
            prompt=('Use ONLY the provided mrhbench container tools. Do not use host tools, network or collaboration. '
                'Read /inputs/EVOLVER_PROMPT.txt, /inputs/interface.json, /inputs/development_limits.json, and /inputs/builder_view.json. '
                'Previous code is /inputs/previous; released search tasks are /inputs/search; '
                'reviewed public evidence and feedback-ref mappings are /inputs/search_evidence. '
                'No hidden task, score or private judge rationale is available. All inputs are read-only. ')
            schema=None
            if selection:
                choices=[v['version_id'] for v in request['builder_view']['versions']]
                schema={'type':'object','properties':{'version_id':{'type':'string','enum':choices},'reason':{'type':'string'}},
                        'required':['version_id','reason'],'additionalProperties':False}
                prompt+='Select exactly one existing frozen version using visible search evidence. Return the requested JSON only; do not modify code or request another evaluation.'
            else:
                prompt+=('Improve ONE reusable harness and put its complete runnable package under /work/candidate, '
                    'including harness.py, change_manifest.json and actual interface tests. Do not copy task inputs/results into the package or hardcode scientific answers. '
                    'Use fake clients for interface tests; no executor/model API, new scientific evaluation or additional judge is available here. '
                    'The controller, not you, will reevaluate the entire search set after freezing. '
                    'Finish tests and files before the stated development deadline to leave collection time. '
                    'Report real tests and limitations, not predicted score improvements.')
            result=runner.run(workspace=clean,prompt=prompt,output_schema=schema,role='builder',
                timeout_seconds=min(self.timeout,session.remaining_seconds-5))
            write_json(audit/'native_result.json',result,exclusive=True)
            if selection:
                # NativeCodexRunner returns a decoded object when output_schema
                # is provided, unlike its plain text response mode.
                choice=copy.deepcopy(result['response'])
                if isinstance(choice,str):choice=json.loads(choice)
                if not isinstance(choice,dict):raise ProtocolError('Native selection must be a JSON object')
                if set(choice)!={'version_id','reason'} or choice['version_id'] not in choices or not isinstance(choice['reason'],str) or not choice['reason'].strip():
                    raise ProtocolError('Native selection must name an available version and a nonempty reason')
                write_json(audit/'selection.json',choice,exclusive=True)
                return choice
            inventory=session.artifacts(audit/'artifacts',max_bytes=self.artifact_bytes,max_files=self.artifact_entries,exclude_internal=True)
            write_json(audit/'artifact_inventory.json',inventory,exclusive=True)
            candidate=audit/'artifacts/candidate'
            for name in ['harness.py','change_manifest.json']:
                if not contained(candidate,name,must_exist=True).is_file():raise ProtocolError('Missing native candidate deliverable')
            files=tree_manifest(candidate)
            target=Path(request['output_directory'])/'candidate'
            if target.exists():raise ProtocolError('Refusing to overwrite staged candidate')
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(candidate,target)
            if tree_manifest(target)!=files:raise ProtocolError('Candidate bytes changed during publication')
            output={'candidate_relative_path':target.relative_to(Path(request['workspace'])).as_posix(),'files':files}
            write_json(audit/'candidate_result.json',{'result':output,'native_call_id':result.get('call_id'),
                'formal_accepted':False,'source_and_trajectory_review':'pending','test_evidence_status':'native_self_report_until_reviewed'},exclusive=True)
            return output
        except Exception as exc:
            primary=exc
            try:
                write_json(audit/'failure.json',{'type':type(exc).__name__,'message':str(exc),'automatic_retry':False,
                    'artifact_completeness':'unknown','automatic_scientific_zero':False})
            except Exception:
                # Best-effort audit must not turn a transport failure into an unrelated storage error.
                pass
            raise
        finally:
            try:session.close()
            except Exception as exc:
                try:
                    write_json(audit/'cleanup_failure.json',{'type':type(exc).__name__,'message':str(exc),'primary_failure_present':primary is not None})
                except Exception:pass
                if primary is None:raise
