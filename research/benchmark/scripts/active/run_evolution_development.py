"""Concrete opt-in native evolution wiring; initialization performs NO model calls.

All materials must remain development candidates. This does not authorize a study
split, claim judge acceptance, or override the shared subscription call ledger.
"""
import argparse
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.costs import CallLedger
from mrhbench.evolution_driver import DevelopmentEvolutionDriver, PendingEvaluationReview
from mrhbench.evolution_evaluator import StageEvaluationAdapter, ReadOnlyReviewResolver, review_template
from mrhbench.evolution_native import NativeDevelopmentBuilder
from mrhbench.io import ProtocolError, digest, file_hash, read_json, write_json
from mrhbench.materials import load_task

ROOT=Path(__file__).resolve().parents[2]


def implementation_manifest():
    paths=[Path(__file__),ROOT/'mrhbench/stage_controller.py']
    paths+=list((ROOT/'mrhbench').glob('*.py'))
    paths+=list((ROOT/'runtime').glob('*.py'))+list((ROOT/'runtime').glob('*.json'))
    paths+=list((ROOT/'prompts').glob('*.txt'))
    return [{'path':p.relative_to(ROOT).as_posix(),'sha256':file_hash(p)} for p in sorted(set(paths))]


def check_configuration(config):
    required={'development','root','builder_root','h0','tasks','packages','rounds','codex_binary','review_directory','native_builder'}
    if not required<=set(config) or set(config)-required-{'context_policy','roles'} or config['development'] is not True:
        raise ProtocolError('Explicit complete DEVELOPMENT configuration required')
    for key in ['root','builder_root','h0','codex_binary','review_directory']:
        if not Path(config[key]).is_absolute():raise ProtocolError('Explicit absolute configuration paths required')
    for path in config['packages'].values():
        if not Path(path).is_absolute():raise ProtocolError('Package paths must be absolute')
    code=Path(config['codex_binary'])
    if not code.is_file():raise ProtocolError('Native binary missing; no implicit model/transport substitution')
    review=Path(config['review_directory']).resolve();builder=Path(config['builder_root']).resolve()
    if review==builder or builder in review.parents or review in builder.parents:
        raise ProtocolError('Private review store must be separate from builder staging')
    keys={'image_id','resources','native_timeout_seconds','max_tool_calls','max_artifact_bytes','max_artifact_entries','use_hook_guard'}
    if set(config['native_builder'])!=keys:raise ProtocolError('Explicit native development resource profile required')
    if config.get('roles') is not None:
        from mrhbench.stage_controller import validate_roles
        validate_roles(config['roles'])
        if config.get('context_policy') is not None or config['native_builder']['use_hook_guard']:
            raise ProtocolError('Claude roles exclude the Codex context policy and Codex hook guard')
    # Constructor validates limits without opening Docker or invoking a model.
    builder_factory(config)(ledger=None,audit_root=Path(config['root'])/'native_builder')


def builder_factory(config):
    """Historical Codex builder by default; Claude Code builder when roles are configured (AGENTS §0.2.13)."""
    import functools
    roles=config.get('roles')
    if roles is None:
        return functools.partial(NativeDevelopmentBuilder,binary=config['codex_binary'],context_policy=config.get('context_policy'),**config['native_builder'])
    from mrhbench.claude_transport import ClaudeNativeRunner
    return functools.partial(NativeDevelopmentBuilder,binary=config['codex_binary'],runner_factory=ClaudeNativeRunner,
                             model=roles['builder']['model'],reasoning_effort=roles['builder']['effort'],
                             interface='interface_container_v4.json',**config['native_builder'])


def initialize(config):
    check_configuration(config)
    driver=DevelopmentEvolutionDriver.create(root=config['root'],builder_root=config['builder_root'],
        tasks=config['tasks'],packages=config['packages'],h0=config['h0'],rounds=config['rounds'])
    binding={'configuration':config,'configuration_hash':digest(config),
             'binary_sha256':file_hash(Path(config['codex_binary'])),'implementation_files':implementation_manifest(),
             'formal':False,'model':(config['roles']['builder']['model'] if config.get('roles') else 'gpt-5.6-sol'),
             'reasoning_effort':(config['roles']['builder']['effort'] if config.get('roles') else 'medium')}
    write_json(driver.root/'native_adapter_configuration.json',binding,exclusive=True)
    return {'status':'initialized_no_model_calls','root':str(driver.root),'formal':False}


def remaining_call_ceiling(driver,config):
    """Conservative transport-invocation bound, NOT credits or internal LLM steps."""
    state=driver.run._state();total=0
    rounds=state['round_limit']
    for number in range(rounds+1):
        version='H'+str(number)
        for task in state['tasks']:
            operation=driver.root/'operations'/('evaluate-'+digest([version,task['task_id']])+'.json')
            if operation.exists():
                row=read_json(operation)
                if row['status']!='complete':raise ProtocolError('Unresolved prior paid operation; no automatic retry')
                continue
            material=load_task(Path(config['packages'][task['task_id']])/'task.json')
            total+=material['public']['resources']['execution_budget']['model_calls']+1
    for number in range(rounds):
        p=driver.root/'operations'/('evolve-H'+str(number)+'.json')
        if p.exists():
            if read_json(p)['status']!='complete':raise ProtocolError('Unresolved native edit; do not retry')
        else:total+=1
    p=driver.root/'operations/select.json'
    if p.exists():
        if read_json(p)['status']!='complete':raise ProtocolError('Unresolved selection; do not retry')
    else:total+=1
    return total


def advance(config):
    check_configuration(config)
    driver=DevelopmentEvolutionDriver(config['root']);driver._verify()
    frozen=read_json(driver.root/'native_adapter_configuration.json')
    if (frozen['configuration_hash']!=digest(config) or frozen['configuration']!=config or
        frozen['binary_sha256']!=file_hash(Path(config['codex_binary'])) or frozen['implementation_files']!=implementation_manifest()):
        raise ProtocolError('Native implementation/configuration changed since initialization; do not mix protocols silently')
    ledger=CallLedger(ROOT/'audit/development_call_ledger.json')
    calls=ledger.summary();ceiling=remaining_call_ceiling(driver,config)
    remaining=calls['authorized_maximum']-calls['used_runs_including_failures']
    if ceiling>remaining:
        raise ProtocolError('Remaining authorized transport calls cannot cover configured conservative ceiling; no calls started')
    evaluator=StageEvaluationAdapter(binary=config['codex_binary'],context_policy=config.get('context_policy'),roles=config.get('roles'))
    reviewdir=Path(config['review_directory']);reviewdir.mkdir(parents=True,exist_ok=True)
    resolver=ReadOnlyReviewResolver(reviewdir)
    builder=builder_factory(config)(ledger=ledger,audit_root=driver.root/'native_builder')
    pending=[]
    def review(*,request,evaluation,binding):
        response=resolver(request=request,evaluation=evaluation,binding=binding)
        if response.get('status')=='pending_review':pending.append((request,evaluation))
        return response
    try:
        summary=driver.advance(evaluate=evaluator,evolve=builder.evolve,select=builder.select,review_evaluation=review)
    except PendingEvaluationReview:
        # Paid evaluation is ALREADY journaled complete. A convenience template
        # failure must never turn it into an unresolved operation or paid retry.
        template_errors=[]
        for request,evaluation in pending:
            try:
                path=reviewdir/(digest(request)+'.pending-template.json')
                template=review_template(request=request,evaluation=evaluation)
                if not path.exists():write_json(path,template,exclusive=True)
                elif read_json(path)!=template:raise ProtocolError('Pending template changed; inspect without replacing')
            except Exception as exc:
                template_errors.append({'error_type':type(exc).__name__,'error':str(exc)})
        return {'status':'awaiting_external_trajectory_and_semantic_review','root':str(driver.root),
                'automatic_retry':False,'formal':False,'template_errors':template_errors,
                'resume_instruction':'Inspect frozen stage/native trajectories; write bound approval separately. Advance resumes without rerunning the cached evaluation.'}
    return {'status':'completed_development_only','summary':summary,'formal':False}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--config',required=True,type=Path)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--initialize',action='store_true',help='Freeze configuration; zero model calls')
    mode.add_argument('--advance',action='store_true',help='Explicitly invoke native calls within existing authorization, stopping for external review')
    a=p.parse_args();config=read_json(a.config)
    print(initialize(config) if a.initialize else advance(config))
