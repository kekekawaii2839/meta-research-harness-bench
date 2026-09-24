"""Native Codex builder with Docker tools, zero scientific tasks, development only."""
import argparse
import sys
import tempfile
from pathlib import Path
from mrhbench.costs import CallLedger
from mrhbench.io import ProtocolError, file_hash, read_json, write_json
from mrhbench.native_codex import NativeCodexRunner
from mrhbench.container_runtime import ContainerSession


def build(binary, output, repair_from=None):
    root=Path(__file__).resolve().parent;output=Path(output).resolve()
    if output.exists():raise ProtocolError('Fresh output required')
    output.mkdir(parents=True)
    clean=Path(tempfile.mkdtemp(prefix='mrhb-bounded-builder-'))
    resources={'cpus':1,'memory_mb':512,'disk_mb':128,'pids_limit':64,'wall_seconds':900}
    inputs={'BUILDER_PROMPT.txt':str(root/'prompts/builder_h0.txt'),'interface.json':str(root/'runtime/interface_container_v2.json')}
    if repair_from:
        previous=Path(repair_from)
        for name in ('harness.py','test_harness.py','build_manifest.json'):
            inputs['previous/'+name]=str(previous/name)
    session=ContainerSession(image_id='sha256:92e6b0ef5cb3a149905fa097ae1d1ae3dd907cd19c796e057d3564d8a8fcfe01',
        resources=resources,input_files={k:Path(v) for k,v in inputs.items()},input_hashes={k:file_hash(Path(v)) for k,v in inputs.items()},audit_dir=output/'controller_container').start()
    manifest={'records':[],'max_tool_calls':100,'state_path':str(output/'tool_state.json'),
              'container':{'image_id':'sha256:92e6b0ef5cb3a149905fa097ae1d1ae3dd907cd19c796e057d3564d8a8fcfe01',
                           'resources':resources,'input_files':{},'audit_dir':str(output/'server_container'),
                           'attached_session':{'cid':session.cid,'owner':session.owner,'deadline_monotonic':session.deadline}}}
    write_json(output/'server_manifest.json',manifest)
    names=['container_read','container_write','container_list','container_exec']
    mcp={'mrhbench':{'command':sys.executable,'args':[str(root/'mrhbench/bounded_mcp.py'),'--manifest',str(output/'server_manifest.json')],
                    'enabled_tools':names,'required':True,'tool_timeout_sec':120,'default_tools_approval_mode':'approve'}}
    runner=NativeCodexRunner(binary=Path(binary),model='gpt-5.6-sol',reasoning_effort='medium',
        ledger=CallLedger(root/'audit/development_call_ledger.json'),audit_root=output/'calls',
        permission_profile=':read-only',tool_profile='bounded_mcp',mcp_servers=mcp,timeout_seconds=880)
    write_json(output/'release.json',{'scientific_tasks_released':0,'files':{name:file_hash(Path(p)) for name,p in inputs.items()},
               'resources':resources,'formal_isolation_verified':False})
    prompt='''Build H0, one reusable research harness. No scientific tasks/search examples are available.
Only use tools.mcp__mrhbench__container_read/write/list/exec via the native tool bridge.
Do not use apply_patch, host filesystem/shell, collaboration, network, or other tools.
Read /inputs/BUILDER_PROMPT.txt and /inputs/interface.json using container_read.
Implement /work/harness.py, /work/build_manifest.json and stdlib fake-client interface tests.
All coding and tests happen inside this CPU container through container_write/exec.
interface.json is the authoritative actual ABI. The future harness runs from /work;
its only allowed imports are standard library and no project-specific SDK module.
Model responses and tool errors need robust handling. Tool return payloads should be
kept faithful in model context; image_ids enable real visual inspection.
Do not implement scientific fixture answers or benchmark judging. Do not create docs.
Run your actual tests for five task types, failures, budgets, artifacts, state reset.
Finish within 750 seconds to leave room for controller collection. Final response
states actual produced files, tests and limitations; no claimed scientific scores.
'''
    if repair_from:
        prompt+='''\nThis is an H0 ABI-debug repair, not scientific search/evolution. Previous source is
read-only at /inputs/previous/. A controller review found that _extract_capabilities
recognized exact tool names but ignored actual ABI capability groups artifact_read_write,
artifact_image_view, cpu_python_execution. Therefore real WRITE/EXP tasks were denied
their allowed tools, although your self-tests used another task shape and passed.
Fix against interface.json capability_groups and test the actual group-based TaskView
shape with abstract fake inputs. Preserve a single generic harness; no real tasks supplied.
Review other ABI mismatches yourself. Record this repair, not a scientific improvement.
'''
    result=None
    try:
        result=runner.run(workspace=clean,prompt=prompt,role='builder',timeout_seconds=min(880,session.remaining_seconds-5))
    finally:
        try:
            inventory=session.artifacts(output/'artifacts',max_bytes=8*1024*1024,max_files=500)
            write_json(output/'artifact_inventory.json',inventory)
        finally:
            session.close()
    write_json(output/'result.json',{'call':result,'harness_present':(output/'artifacts/harness.py').is_file(),
                                  'build_accepted':False,'formal_isolation_verified':False,'requires':'source and full trajectory review'})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--output',required=True);p.add_argument('--repair-from')
    a=p.parse_args();print(build(a.binary,a.output,a.repair_from))
