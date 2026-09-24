import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.native_tool_guard import decide, response_for, hook_configuration
from mrhbench.native_codex import NativeCodexRunner


class GuardTests(unittest.TestCase):
    def test_exact_names_and_default_denial(self):
        c={'allowed_tools':['mcp__mrhbench__evidence_read']}
        for name in ['Bash','apply_patch','spawn_agent','exec','mcp__other__read','mcp__mrhbench__evidence_read_extra']:
            self.assertEqual(decide({'hook_event_name':'PreToolUse','tool_name':name},c)[0],'deny')
        self.assertEqual(decide({'hook_event_name':'PreToolUse','tool_name':'mcp__mrhbench__evidence_read'},c)[0],'allow')
        self.assertEqual(response_for('allow','ok'),{})
        self.assertEqual(response_for('deny','reason')['hookSpecificOutput']['permissionDecision'],'deny')

    def test_malformed_and_missing_config_emit_valid_deny(self):
        script=Path(__file__).resolve().parents[1]/'mrhbench/native_tool_guard.py'
        p=subprocess.run([sys.executable,str(script),'--config','missing-guard-config'],input='bad-json',text=True,capture_output=True)
        self.assertEqual(p.returncode,0)
        self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'],'deny')

    def test_optional_runner_config_no_default_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);logs=root/'logs';logs.mkdir();config=root/'config.json'
            config.write_text(json.dumps({'allowed_tools':['mcp__mrhbench__ping_allowed'],'log_directory':str(logs)}))
            base=dict(binary=Path(sys.executable),model='gpt-5.6-sol',reasoning_effort='medium',ledger=None,audit_root=root,permission_profile=':read-only',tool_profile='bounded_mcp',mcp_servers={'mrhbench':{'command':'python'}})
            old=NativeCodexRunner(**base).command(root,root/'out')
            new=NativeCodexRunner(**base,hook_guard={'config_path':config,'python_binary':Path(sys.executable)}).command(root,root/'out')
            self.assertNotIn('hooks=', ' '.join(old))
            self.assertTrue(any(x.startswith('hooks=') for x in new))
            self.assertEqual(new[new.index('hooks')-1],'--enable')
            self.assertNotIn('--dangerously-bypass-hook-trust', old)
            self.assertIn('--dangerously-bypass-hook-trust', new)

    def test_allow_and_deny_actual_helper_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);logs=root/'logs';logs.mkdir();config=root/'config.json'
            config.write_text(json.dumps({'allowed_tools':['mcp__mrhbench__ping_allowed'],'log_directory':str(logs)}))
            script=Path(__file__).resolve().parents[1]/'mrhbench/native_tool_guard.py'
            for name in ['mcp__mrhbench__ping_allowed','apply_patch']:
                p=subprocess.run([sys.executable,str(script),'--config',str(config)],input=json.dumps({'hook_event_name':'PreToolUse','tool_name':name,'tool_use_id':name}),text=True,capture_output=True)
                self.assertEqual(p.returncode,0)
            rows=[json.loads(x.read_text()) for x in logs.glob('*.json')]
            self.assertEqual({x['decision'] for x in rows},{'allow','deny'})


if __name__=='__main__':unittest.main()
