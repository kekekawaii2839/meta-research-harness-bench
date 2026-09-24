"""Synthetic runner/auditor boundary; no model or scientific validity claim."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mrhbench.io import read_json,write_json
from mrhbench.native_judge import run_native_judge


class NativeToolAuditGateTests(unittest.TestCase):
    def exercise(self,status,*,auditor_error=False):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);output=root/'judge'
            runner=SimpleNamespace(binary=Path(sys.executable),model='gpt-5.6-sol',effort='medium',
                                   ledger=None,audit_root=root/'calls',timeout=30)
            candidate={'judgment':{},'feedback':{}}
            fake=Mock()
            def run(**kw):
                write_json(output/'tool_state.json',{})
                return {'response':json.dumps(candidate),'audit_directory':str(root/'synthetic'),
                        'call_id':'synthetic','status':'completed'}
            fake.run.side_effect=run
            with patch('mrhbench.native_codex.NativeCodexRunner',return_value=fake), \
                 patch('mrhbench.native_judge.restore_session'), \
                 patch('mrhbench.native_admissibility.assess_native_admissibility',
                       return_value={'status':status},side_effect=RuntimeError('synthetic') if auditor_error else None), \
                 patch('mrhbench.native_judge.validate_native_result',return_value={'acceptance_status':'awaiting_manual_trajectory_and_semantic_feedback_review'}) as validate:
                value=run_native_judge(runner=runner,task_id='synthetic',task_type='WRITE_CONTENT',
                    records=[],output=output,python_binary=Path(sys.executable))
            if status=='pending_code_mode_review' and not auditor_error:
                self.assertTrue((output/'result.json').exists());validate.assert_called_once()
                self.assertEqual(read_json(output/'result.json')['native_tool_admissibility_status'],status)
            else:
                self.assertFalse((output/'result.json').exists());validate.assert_not_called()
                self.assertEqual(value['status'],'awaiting_native_tool_review')
                self.assertFalse(value['automatic_scientific_zero'])
            self.assertTrue((output/'candidate_judgment.json').exists())
            self.assertTrue((output/'native_tool_audit.json').exists())

    def test_incomplete_and_observed_violation_do_not_produce_score(self):
        for status in ('incomplete','rejected_observed_activity'):
            with self.subTest(status=status):self.exercise(status)

    def test_auditor_failure_is_not_silent_acceptance(self):
        self.exercise('incomplete',auditor_error=True)

    def test_code_mode_candidate_remains_manual_not_formal(self):
        self.exercise('pending_code_mode_review')


if __name__=='__main__':unittest.main()
