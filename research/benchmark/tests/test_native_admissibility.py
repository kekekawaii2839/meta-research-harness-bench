import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from mrhbench.io import canonical, digest, file_hash, write_json
from mrhbench.native_admissibility import assess_native_admissibility


class NativeAdmissibilityTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.allowed=['mcp__mrhbench__container_read']
        self.guard=self.root/'guard.json';self.hooks=self.root/'hooks';self.hooks.mkdir()
        write_json(self.guard,{'allowed_tools':self.allowed,'log_directory':str(self.hooks)})
        self.inv={'args':['codex','--enable','hooks','-c','hooks={}'],'tool_profile':'bounded_mcp',
                  'optional_hook_guard':{'config_sha256':file_hash(self.guard),'allowed_tools':self.allowed}}
        self.inv['config_hash']=digest(self.inv['args'])
        self.item={'type':'McpToolCall','id':'m1','server':'mrhbench','tool':'container_read',
                   'arguments':{'path':'/inputs/task'},'status':'completed','result':{'content':[{'type':'text','text':'data'}]}}
        self.rows=[{'type':'session_meta','payload':{'id':'s'}},
            {'type':'event_msg','payload':{'type':'task_started'}},
            {'type':'response_item','payload':{'type':'custom_tool_call','name':'exec','call_id':'c','input':'text(await tools.mcp__mrhbench__container_read({path:"/inputs/task"}));'}},
            {'type':'event_msg','payload':{'type':'item_completed','item':self.item}},
            {'type':'response_item','payload':{'type':'custom_tool_call_output','call_id':'c','output':[]}},
            {'type':'response_item','payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':'done'}]}},
            {'type':'event_msg','payload':{'type':'task_complete'}}]
        self.cli=[{'type':'thread.started','thread_id':'s'},{'type':'turn.started'},
                  {'type':'item.completed','item':{**self.item,'type':'mcp_tool_call'}},{'type':'turn.completed'}]
        self.hook={'session_id':'s','tool_use_id':'m1','tool_name':self.allowed[0],'decision':'allow',
                   'tool_input_sha256':hashlib.sha256(json.dumps(self.item['arguments'],sort_keys=True).encode()).hexdigest(),
                   'config_sha256':file_hash(self.guard)}
        write_json(self.hooks/'1.json',self.hook)
        self.state={'tool_calls':1,'tool_events':[{'name':'container_read','arguments':self.item['arguments']}]}
        self.flush()
    def flush(self):
        write_json(self.root/'invocation.json',self.inv)
        (self.root/'events.jsonl').write_bytes(b''.join(canonical(x)+b'\n' for x in self.cli))
        rp=self.root/'session_rollout.redacted.jsonl';rp.write_bytes(b''.join(canonical(x)+b'\n' for x in self.rows))
        write_json(self.root/'result.json',{'status':'completed','exit_code':0,'config_hash':self.inv['config_hash'],
            'rollout_capture':{'status':'captured','path':str(rp),'sha256':file_hash(rp),'row_count':len(self.rows),'session_id':'s'}})
        write_json(self.root/'state.json',self.state)
    def assess(self, **kwargs):
        options={'allowed_tools':self.allowed,'guard_path':self.guard,'hook_directory':self.hooks,'tool_state_path':self.root/'state.json'}
        options.update(kwargs);return assess_native_admissibility(self.root,**options)
    def approve(self, report):
        return {'status':'passed','binding':report['binding'],'reviewer':'test-only fixture reviewer',
            'notes':'Synthetic test approval, not an actual scientific review.',
            'reviewed_outer_calls':[{k:c[k] for k in ('call_id','payload_sha256')} for c in report['outer_calls_requiring_review']]}
    def test_pending_then_bound_review(self):
        r=self.assess();self.assertEqual(r['status'],'pending_code_mode_review')
        approved=self.assess(code_mode_review=self.approve(r));self.assertEqual(approved['status'],'development_admissible')
        self.assertFalse(approved['formal_isolation_verified'])
    def test_missing_rollout_fail_closed(self):
        (self.root/'session_rollout.redacted.jsonl').unlink()
        self.assertEqual(self.assess()['status'],'incomplete')
    def test_missing_hook_not_silently_allowed(self):
        (self.hooks/'1.json').unlink();r=self.assess()
        self.assertEqual(r['status'],'incomplete')
        self.assertEqual(self.assess(code_mode_review=self.approve(r))['status'],'incomplete')
    def test_unconfigured_hook_distinct(self):
        del self.inv['optional_hook_guard'];self.flush()
        r=self.assess(guard_path=None,hook_directory=None)
        self.assertEqual(r['hook_configuration'],'not_configured');self.assertEqual(r['status'],'pending_code_mode_review')
        self.assertEqual(self.assess(guard_path=None,hook_directory=None,code_mode_review=self.approve(r))['status'],'development_admissible')
    def test_disallowed_tool_cannot_review_override(self):
        self.rows[2]['payload']['name']='apply_patch';self.flush();r=self.assess()
        self.assertEqual(r['status'],'rejected_observed_activity')
        self.assertEqual(self.assess(code_mode_review=self.approve(r))['status'],'rejected_observed_activity')
    def test_missing_terminal_and_output(self):
        self.rows.pop();self.rows.pop(4);self.flush()
        r=self.assess();self.assertIn('outer_call_output_incomplete',r['errors']);self.assertEqual(r['status'],'incomplete')
    def test_mcp_hook_arguments_corruption(self):
        self.hook['tool_input_sha256']='0'*64;write_json(self.hooks/'1.json',self.hook)
        self.assertEqual(self.assess()['status'],'incomplete')
    def test_failed_allowed_mcp_still_requires_hook(self):
        self.item['status']='failed';self.cli[2]['item']['status']='failed';self.state['tool_events']=[];self.flush()
        self.assertEqual(self.assess()['status'],'pending_code_mode_review')
    def test_state_optional_explicit(self):
        r=self.assess(tool_state_path=None);self.assertFalse(r['controller_tool_state_verified'])
        self.assertEqual(r['status'],'pending_code_mode_review')
    def test_cli_mcp_mismatch(self):
        self.cli.pop(2);self.flush();self.assertIn('cli_rollout_mcp_activity_mismatch',self.assess()['errors'])
    def test_arbitrary_js_is_not_regex_certified(self):
        self.rows[2]['payload']['input']='const t="apply_"+"patch"; await tools[t]("arbitrary");';self.flush()
        self.assertEqual(self.assess()['status'],'pending_code_mode_review')
    def test_stale_review_rejected(self):
        review=self.approve(self.assess());self.rows[2]['payload']['input']='text("changed");';self.flush()
        self.assertEqual(self.assess(code_mode_review=review)['status'],'incomplete')


if __name__=='__main__':unittest.main()
