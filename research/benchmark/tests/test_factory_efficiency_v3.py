"""Offline v3 driver tests; no native model calls or scientific acceptance."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench import factory_efficiency_v3 as f
from mrhbench.io import ProtocolError, read_json, write_json

class DriverTests(unittest.TestCase):
    def fixture(self, root):
        benchmark = root / 'benchmark'
        for name in ('mrhbench/test.py', 'scripts/active/run_factory_efficiency_v3.py',
                     'prompts/material_efficiency_v1/repair.txt', 'prompts/material_efficiency_v1/review.txt',
                     'prompts/factory_v4/policy.md', 'prompts/material_efficiency_v3/repair.txt',
                     'prompts/material_efficiency_v3/review.txt', 'prompts/material_efficiency_v3/policy.md',
                     'prompts/material_efficiency_v3/adjudicator_review.txt',
                     'prompts/factory_v4/adjudicator_review.txt',
                     'prompts/factory_v4/review_adjudication.schema.json'):
            p = benchmark / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(name, encoding='utf8')
        import shutil
        shutil.copyfile(ROOT/'prompts/material_efficiency_v3/policy.md', benchmark/'prompts/material_efficiency_v3/policy.md')
        shutil.copyfile(ROOT/'prompts/material_efficiency_v3/adjudicator_review.txt', benchmark/'prompts/material_efficiency_v3/adjudicator_review.txt')
        shutil.copyfile(ROOT/'prompts/factory_v4/review_adjudication.schema.json', benchmark/'prompts/factory_v4/review_adjudication.schema.json')
        approval = root/'approval.json'
        write_json(approval, {'protocol_version':3,'ledger_baseline':608,'ledger_stop_at':625,
            'pair_max_calls':12,'prospective_max_calls':5,'authorized_to_freeze':True})
        binary = root / 'fake.exe' 
        binary.write_bytes(b'not executable')
        roles = benchmark / 'config/roles.json'
        write_json(roles, {'constructor': {'model': 'claude-opus-5-5', 'effort': 'medium'},
                          'judge': {'model': 'claude-opus-5-5', 'effort': 'medium'}, 'claude_binary_default': str(binary)})
        ledger = root / 'ledger.json'
        write_json(ledger, {'authorized_maximum': 1668, 'used_attempts': 608, 'attempts': [{'id': i, 'status': 'completed'} for i in range(1,609)]})
        ws = root / 'workspace'
        ws.mkdir()
        (ws / 'source.txt').write_text('source', encoding='utf8')
        write_json(ws / 'job.json', {'job_id': 'j', 'paper_id': 'p', 'sources': [{'local_path': 'source.txt'}]})
        write_json(ws / 'notes.json', {'repair_notes': ['repair']})
        write_json(ws / 'projection.json', {'projection': 'single-task'})
        write_json(ws / 'prior/j/constructor/output/package.json', {})
        case = {'case_id': 'a', 'workspace': str(ws), 'job_path': str(ws/'job.json'),
                'prior_batch': str(ws/'prior'), 'job_id': 'j', 'notes_path': str(ws/'notes.json'),
                'notes_key': 'repair_notes', 'projection_record_path': str(ws/'projection.json'),
                'round_no': 2, 'order': ['old', 'incremental'], 'frozen_inputs': [f.identity(ws/'source.txt')]}
        cases = root / 'cases.json'
        trial = root / 'trial'
        write_json(cases, {'cases': [case, {**case, 'case_id': 'b', 'order': ['incremental', 'old']}],
            'experiment_root': str(trial), 'protocol_version':3,'approval_record_path':str(approval), 'prospective_max_calls':5, 'ledger_baseline': 608, 'ledger_stop_at': 625,
            'pair_max_calls': 12, 'model': 'claude-opus-5-5', 'effort': 'medium'})
        return benchmark, roles, ledger, cases, trial, ws

    def test_freeze_actual_ledger_explicit_overlay_no_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            benchmark, roles, ledger, cases, trial, ws = self.fixture(Path(tmp))
            before = ledger.read_bytes()
            manifest = f.freeze(cases, benchmark, roles, ledger)
            f.verify_execution(trial)
            self.assertEqual(ledger.read_bytes(), before)
            self.assertEqual(manifest['ledger_baseline_observed'], 608)
            self.assertEqual(len(manifest['overlays']), len(f.OVERLAYS) + 1)
            adjudicator_prompt = (trial/'execution/snapshot/prompts/factory_v4/adjudicator_review.txt').read_text(encoding='utf8')
            self.assertIn('two required outputs of this SAME independent adjudication', adjudicator_prompt)
            self.assertIn('quality_coverage.json conforming to quality_coverage.schema.json', adjudicator_prompt)
            for row in manifest['overlays']:
                if not row.get('generated_from_policy'):
                    self.assertEqual(row['source']['sha256'], row['snapshot']['sha256'])
                self.assertNotEqual(row['original_snapshot']['sha256'], row['snapshot']['sha256'])
            with self.assertRaises(FileExistsError):
                f.freeze(cases, benchmark, roles, ledger)

    def test_changed_projection_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            benchmark, roles, ledger, cases, trial, ws = self.fixture(Path(tmp))
            f.freeze(cases, benchmark, roles, ledger)
            write_json(ws/'projection.json', {'changed': True})
            with self.assertRaises(ProtocolError): f.verify_execution(trial)

    def test_added_prior_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            benchmark, roles, ledger, cases, trial, ws = self.fixture(Path(tmp))
            f.freeze(cases, benchmark, roles, ledger)
            (ws/'prior/j/constructor/output/new.txt').write_text('new')
            with self.assertRaises(ProtocolError): f.verify_execution(trial)

    def test_baseline_budget_order_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            benchmark, roles, ledger, cases, trial, ws = self.fixture(Path(tmp))
            original = read_json(cases)
            for change in ({'ledger_baseline': 593}, {'ledger_stop_at': 626}, {'pair_max_calls': 13},
                           {'model': 'other'}, {'cases': original['cases'][::-1]}):
                with self.assertRaises(ProtocolError): f._validate_selection({**original, **change}, 608)
            with self.assertRaises(ProtocolError): f._validate_selection(original, 609)

    def test_second_pair_requires_runtime_and_independent_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, _, _, casespath, _, _ = self.fixture(root)
            cases = read_json(casespath)
            for arm in ('old', 'incremental'):
                write_json(root/'arms/a'/arm/'result.json', {'status': 'completed'})
                write_json(root/'runtime'/arm/'record.json', {'status': 'passed'})
            write_json(root/'audit.json', {'independent': True})
            gate = {'case_id': 'a', 'allow_next_case': True, 'quality_passed': True, 'reviewer': 'independent',
                    'findings': ['bounded review'], 'review_seconds': 10,
                    'result_hashes': {arm: f.file_hash(root/'arms/a'/arm/'result.json') for arm in ('old','incremental')},
                    'runtime_evidence': {arm: f.identity(root/'runtime'/arm/'record.json') for arm in ('old','incremental')},
                    'independent_evidence': [f.identity(root/'audit.json')]}
            write_json(root/'audits/a.json', gate)
            f.check_order(root, cases, 'b', 'incremental')
            for change in ({'quality_passed': False}, {'runtime_evidence': {}}, {'independent_evidence': []}):
                write_json(root/'audits/a.json', {**gate, **change})
                with self.assertRaises(ProtocolError): f.check_order(root, cases, 'b', 'incremental')
            write_json(root/'audits/a.json', gate)
            write_json(root/'runtime/old/record.json', {'status': 'failed'})
            with self.assertRaises(ProtocolError): f.check_order(root, cases, 'b', 'incremental')

    def test_failed_prior_does_not_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = {'cases': [{'case_id': 'a', 'order': ['old','incremental']}]}
            write_json(root/'arms/a/old/result.json', {'status':'failed_needs_attribution'})
            with self.assertRaises(ProtocolError): f.check_order(root, cases, 'a', 'incremental')

    def test_all_roles_wrapped_before_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark, roles, ledger, cases, trial, ws = self.fixture(root)
            manifest = f.freeze(cases, benchmark, roles, ledger)
            captured = []
            def batch(*args, **kwargs):
                for role in ('constructor','reviewer'):
                    wrapped = kwargs[role]
                    self.assertIsInstance(wrapped, f.QualityBoundRunner)
                    captured.append(wrapped.policy_hash)
                self.assertFalse(kwargs['incremental_repair'])
                return {'jobs': [{'status':'failed_needs_attribution'}]}
            (trial/'execution/snapshot/prompts/factory_v4/constructor_addendum.txt').write_text('fixture')
            with patch.object(f, 'verify_execution', return_value=(manifest,read_json(cases))), patch.object(f,'run_batch',side_effect=batch):
                result = f.run_arm(trial,'a','old',runner_factory=lambda *args: object())
                self.assertEqual(result['status'],'failed_needs_attribution')
                self.assertEqual(result['cost']['calls'],0)
                self.assertEqual(len(set(captured)),1)
                with self.assertRaises(ProtocolError): f.run_arm(trial,'a','old',runner_factory=lambda *args: object())

    def lifecycle(self, root, missing=False, mutate=False, real_batch=False, arm="old", invalid_rule=False):
        import shutil
        benchmark, roles, ledger, cases, trial, ws = self.fixture(root)
        manifest = f.freeze(cases, benchmark, roles, ledger)
        selection = read_json(cases)
        selection['cases'][0]['notes_key'] = None
        write_json(ws/'notes.json', ['whole list notes'])
        templates = trial/'execution/snapshot/prompts'
        shutil.copytree(ROOT/'prompts', templates, dirs_exist_ok=True)
        for target_rel, source_rel in f.OVERLAYS.items():
            shutil.copyfile(ROOT/'prompts'/source_rel, templates/target_rel)
        policy = templates/'factory_v4/policy.md'
        shutil.copyfile(ROOT/'prompts/material_efficiency_v3/policy.md', policy)
        bound, _ = f.bind_policy_rules(read_json(templates/'factory_v4/review_adjudication.schema.json'),policy.read_bytes())
        write_json(templates/'factory_v4/review_adjudication.schema.json', bound)
        received = []
        if real_batch:
            resources = dict(cpus=1,memory_mb=128,disk_mb=128,pids_limit=32,wall_seconds=60)
            job = dict(schema_version='material-job-1',job_id='j',paper_id='p',requested_task_types=['EXP'],
                scope_request='Synthetic fixture',first_disclosure={},
                environment_candidate=dict(gpu=False,network='none',scientific_rationale='Fixture',**resources),
                sources=[dict(source_id='s',url='https://example.invalid/p',version='v1',local_path='source.txt',
                    sha256=f.file_hash(ws/'source.txt'),role='paper_text')])
            write_json(ws/'job.json',job)
        class Inner:
            def __init__(inner, led, arm): inner.ledger, inner.arm = led, arm
            def run(inner, *, workspace, prompt, role):
                cid = inner.ledger.reserve(role=role, model='fake', effort='medium', request_hash='0'*64,
                    artifact_directory=str(inner.arm/'native_calls'/role))
                inner.ledger.finish(cid, status='completed', wall_seconds=1,
                    usage={'input_tokens':1,'cached_input_tokens':0,'cache_write_input_tokens':0,'output_tokens':1}, metadata={})
                received.append(role)
                if role == 'adjudicator':
                    self.assertIn('two required outputs of this SAME independent adjudication', prompt)
                    self.assertIn('quality_coverage.json conforming to quality_coverage.schema.json', prompt)
                    self.assertEqual((workspace/'policy.md').read_bytes(), (workspace/'quality_policy.md').read_bytes())
                if real_batch and role == 'constructor':
                    from test_material_pipeline_v2 import MaterialPipelineTests
                    out = workspace/'output'
                    package = MaterialPipelineTests()._valid_private_package(out)
                    package['facts'][0]['evidence'][0]['source_sha256'] = f.file_hash(ws/'source.txt')
                    write_json(out/'package.json',package)
                if mutate and role == 'constructor':
                    (workspace/'quality_policy.md').write_text('mutated',encoding='utf8')
                if role != 'constructor':
                    c = read_json(workspace/'quality_contract.json')
                    ids = list(c['public_inventory'])
                    checks = {}
                    for key in c['checks']:
                        checks[key] = {'status':'clear','rationale':'Synthetic test only',
                            'evidence':[{'surface_id':ids[0],'locator':'fixture','observation':'Synthetic'}],
                            **({'scope':'entire_bound_public_inventory'} if key in ('identity','author_scale','target_implementation')
                               else {'scope':'selected_surfaces','inspected_surface_ids':ids})}
                    if not missing or (missing == 'adjudicator' and role != 'adjudicator'):
                        write_json(workspace/'quality_coverage.json', {'contract_sha256':c['contract_sha256'],
                            'policy_sha256':c['policy_sha256'],'checks':checks})
                    if role == 'material_reviewer':
                        write_json(workspace/'review.json', {'schema_version':'material-review-1','paper_id':'p',
                            'decision':'pass_with_pending_runtime','findings':[]})
                    else:
                        write_json(workspace/'review_adjudication.json', {'schema_version':'factory-review-adjudication-1',
                            'project_id':'p','round':2,'action':'pass','finding_decisions':[{'finding_index':None,'decision':'accept','severity':'minor','repair_note':None,'rationale':'Synthetic policy citation only; resources proposed, runtime pending','policy_rules':['NO_RULE' if invalid_rule else 'J2','F4']}], 'repair_notes':[],
                            'drop_reason':None,'excluded_task_ids':[]})
                return {'call_id':cid}
        def batch(jobs, **kw):
            self.assertEqual(kw['repair_notes'], {'j':['whole list notes']})
            for key, role in (('constructor','constructor'),('reviewer','material_reviewer')):
                target = kw['batch_root']/'j'/key
                write_json(target/'request.json', {'paper_id':'p'})
                write_json(target/'structural_check.json', {})
                write_json(target/'output/package.json', {'facts':[], 'environment':{'resources':{'cpus':1}},
                    'tasks':[{'task_id':'t','task_type':'EXP','input_fact_ids':[], 'input_contract':{},'output_contract':{},'assets':[]}]})
                kw[key].run(workspace=target,prompt='fixture',role=role)
            return {'jobs':[{'status':'pass_with_pending_runtime'}]}
        with patch.object(f,'verify_execution',return_value=(manifest,selection)), patch.object(f,'run_batch', wraps=f.run_batch) if real_batch else patch.object(f,'run_batch',side_effect=batch):
            if arm == 'incremental':
                write_json(trial/'arms/a/old/result.json', {'status':'completed'})
            out = f.run_arm(trial,'a',arm,runner_factory=lambda role,led,arm:Inner(led,arm))
        return out, received, trial

    def test_three_fake_calls_actual_quality_wrappers_and_adjudication(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, roles, trial = self.lifecycle(Path(tmp))
            self.assertEqual(result['status'],'completed', result.get('error'))
            self.assertEqual(result['cost']['calls'],3)
            self.assertEqual(roles,['constructor','material_reviewer','adjudicator'])
            self.assertTrue((trial/'arms/a/old/adjudicator/quality_controller_validation.json').is_file())

    def test_real_batch_native_fake_three_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, roles, trial = self.lifecycle(Path(tmp),real_batch=True)
            self.assertEqual(result['status'],'completed', result)
            self.assertEqual(result['cost']['calls'],3)
            self.assertEqual(roles,['constructor','material_reviewer','adjudicator'])
            receipt = read_json(trial/'arms/a/old/batch/j/receipt.json')
            self.assertEqual(receipt['status'],'pass_with_pending_runtime')

    def test_real_incremental_batch_native_fake_three_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, roles, trial = self.lifecycle(Path(tmp),real_batch=True,arm='incremental')
            self.assertEqual(result['status'],'completed', result)
            self.assertEqual(result['cost']['calls'],3)
            self.assertEqual(roles,['constructor','material_reviewer','adjudicator'])
            self.assertTrue((trial/'arms/a/incremental/adjudicator/quality_controller_validation.json').is_file())

    def test_missing_coverage_stops_before_adjudicator(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, roles, _ = self.lifecycle(Path(tmp),missing=True)
            self.assertEqual(result['status'],'failed_needs_attribution')
            self.assertEqual(result['cost']['calls'],2)
            self.assertNotIn('adjudicator',roles)

    def test_mutated_policy_stops_after_constructor(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, roles, _ = self.lifecycle(Path(tmp),mutate=True)
            self.assertEqual(result['status'],'failed_needs_attribution')
            self.assertEqual(result['cost']['calls'],1)

    def test_missing_adjudicator_sidecar_is_terminal_after_three_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, roles, trial = self.lifecycle(Path(tmp), real_batch=True, missing='adjudicator')
            self.assertEqual(result['status'], 'failed_needs_attribution')
            self.assertEqual(result['cost']['calls'], 3)
            self.assertEqual(roles, ['constructor', 'material_reviewer', 'adjudicator'])
            self.assertTrue((trial/'arms/a/old/adjudicator/review_adjudication.json').is_file())
            self.assertFalse((trial/'arms/a/old/adjudicator/quality_controller_validation.json').exists())

    def test_invalid_rule_not_normalized_or_swallowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, roles, trial = self.lifecycle(Path(tmp),real_batch=True,invalid_rule=True)
            self.assertEqual(result['status'],'failed_needs_attribution')
            self.assertEqual(result['cost']['calls'],3)
            raw = read_json(trial/'arms/a/old/adjudicator/review_adjudication.json')
            self.assertEqual(raw['finding_decisions'][0]['policy_rules'][0],'NO_RULE')

    def test_policy_schema_all_ids_and_no_undefined(self):
        policy = (ROOT/'prompts/material_efficiency_v3/policy.md').read_bytes()
        base = read_json(ROOT/'prompts/factory_v4/review_adjudication.schema.json')
        bound, _ = f.bind_policy_rules(base,policy)
        f._verify_policy_schema(bound,policy)
        self.assertIn('J2',f.rule_ids(policy))
        self.assertIn('F4',f.rule_ids(policy))
        with self.assertRaises(Exception): f._verify_policy_schema(base,policy)

    def test_approval_missing_or_changed_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            benchmark, roles, ledger, cases, trial, ws = self.fixture(Path(tmp))
            selection = read_json(cases)
            approval = Path(selection['approval_record_path'])
            original = read_json(approval)
            write_json(approval,{**original,'authorized_to_freeze':False})
            with self.assertRaises(ProtocolError): f.freeze(cases,benchmark,roles,ledger)
            write_json(approval,original)
            f.freeze(cases,benchmark,roles,ledger)
            write_json(approval,{**original,'changed':True})
            with self.assertRaises(ProtocolError): f.verify_execution(trial)

if __name__ == '__main__': unittest.main()
