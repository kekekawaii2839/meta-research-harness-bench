import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mrhbench.native_codex import NativeCodexRunner
from mrhbench.costs import CallLedger
from mrhbench.io import write_json
BASE=Path(__file__).resolve().parent
OUT=BASE/'audit/native_judge_v2_probe_001'
OUT.mkdir(exist_ok=False);WORK=OUT/'empty_workspace';WORK.mkdir()
manifest={'records':[],'state_path':str(OUT/'tool_state.json'),'max_tool_calls':12}
write_json(OUT/'manifest.json',manifest)
config={'mrhbench':{'command':sys.executable,'args':[str(BASE/'mrhbench/bounded_mcp.py'),'--manifest',str(OUT/'manifest.json')],'enabled_tools':['evidence_inventory','evidence_read'],'required':True,'tool_timeout_sec':30,'default_tools_approval_mode':'approve'}}
r=NativeCodexRunner(binary=Path('C:/Users/li_ha/AppData/Local/OpenAI/Codex/bin/80f78947ad880e6e/codex.exe'),model='gpt-5.6-sol',reasoning_effort='medium',ledger=CallLedger(BASE/'audit/development_call_ledger.json'),audit_root=OUT/'calls',permission_profile=':read-only',timeout_seconds=240,tool_profile='bounded_mcp',mcp_servers=config)
prompt='''This is a bounded tool availability probe, not research. Call evidence_inventory once. Then report every tool callable in your current context, including any host shell, filesystem, apply_patch, code mode, MCP resource, web or image tool. If a host shell or apply_patch is exposed, do NOT use it; report its exposure instead. Do not inspect any credentials, user files or external services. Return JSON {"inventory_called":boolean,"available_tools":[strings],"host_tools_exposed":boolean,"notes":string}.'''
write_json(OUT/'call.json',r.run(workspace=WORK,prompt=prompt,role='probe'))
