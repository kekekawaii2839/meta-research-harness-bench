"""Development-only orchestration with injected, trusted execution adapters.

Synthetic tests do not certify a native evolution run. The controller store and
adapter closures must remain inaccessible to builders; callbacks are NOT sandboxes.
Unresolved paid operations are deliberately not retried on resume (including
crashes after a billed call). Completed evaluations pending human/controller
review resume through a separate pure-reader phase without another model call.
"""
from __future__ import annotations

import copy
from pathlib import Path
import shutil
import re
import uuid

from .evolution import EvolutionRun
from .io import ProtocolError, contained, digest, file_hash, read_json, write_json
from .materials import load_task, export_task
from .scoring import TASK_TYPES, aggregate


def tree_manifest(root):
    root = Path(root).resolve(strict=True)
    return [{"path": p.relative_to(root).as_posix(), "sha256": file_hash(contained(root, p.relative_to(root).as_posix(), must_exist=True))}
            for p in sorted(root.rglob('*')) if p.is_file()]


class PendingEvaluationReview(ProtocolError):
    """Paid evaluation is cached; a later explicit advance may reread approval."""


def validate_envelope(task, envelope):
    required = {'status','result','feedback','judge_receipt'}
    if not required.issubset(envelope) or not set(envelope).issubset(required | {'public_evidence_bundle'}) or envelope['status'] != 'accepted_development':
        raise ProtocolError('Unresolved evaluation cannot enter scoring or feedback')
    receipt = envelope['judge_receipt']
    if set(receipt) != {'invocation_id','same_turn_feedback','trajectory_reviewed','semantic_feedback_reviewed'} or not receipt['invocation_id'] or any(receipt[k] is not True for k in ('same_turn_feedback','trajectory_reviewed','semantic_feedback_reviewed')):
        raise ProtocolError('Same-turn judge and reviewed public feedback required')
    aggregate([task], [envelope['result']], require_all_modules=False)
    if 'public_evidence_bundle' in envelope:
        verify_public_bundle(envelope['public_evidence_bundle'])


def verify_public_bundle(bundle):
    if set(bundle) != {'root','files','index_path','manifest_hash'} or bundle['manifest_hash'] != digest(bundle['files']):
        raise ProtocolError('Public evidence manifest binding invalid')
    root = Path(bundle['root']).resolve(strict=True)
    if not root.is_dir() or tree_manifest(root) != bundle['files']:
        raise ProtocolError('Public evidence files changed or unlisted')
    index = read_json(contained(root, bundle['index_path'], must_exist=True))
    if index.get('schema_version') != 'public-evidence-projection-1':
        raise ProtocolError('Unknown public evidence index')
    ids=set()
    files={r['path']:r['sha256'] for r in bundle['files']}
    for row in index['records']:
        if row['evidence_id'] in ids or row.get('visibility')!='public' or row['origin'] not in {'task','submission','platform_trace','reference','rendered_artifact','program_check'} or files.get(row['path']) != row['sha256']:
            raise ProtocolError('Invalid public evidence index record')
        ids.add(row['evidence_id'])
    if any(r['evidence_id'] not in ids for r in index['receipts'].values()):
        raise ProtocolError('Dangling public receipt reference')
    return root


class DevelopmentEvolutionDriver:
    """Adapters: evaluate(request)->immutable completion, evolve(request)->output,
    select(request)->{version_id, reason}. Requests are keyword-only `request`.

    Evaluator receives controller-only package paths; it must use a fresh task
    runner and return the same judge invocation's score and public feedback. It
    must not turn unknown platform/material/judge failures into model_failed.
    Builder adapters receive only staged public inputs, not evaluator requests.
    Never run untrusted callbacks in the controller process in a real deployment.
    Optional review_evaluation(request,evaluation,binding) is a trusted pure reader,
    never a model invocation. Without it, preaccepted synthetic/test envelopes are
    supported for compatibility, not certification of real acceptance.
    """

    @classmethod
    def create(cls, *, root, builder_root, tasks, packages, h0, rounds):
        root, builder_root = Path(root).resolve(), Path(builder_root).resolve()
        if root == builder_root or root in builder_root.parents or builder_root in root.parents:
            raise ProtocolError('Builder staging must be separate from private controller storage')
        if builder_root.exists():
            raise ProtocolError('Fresh builder staging root required')
        if set(packages) != {t['task_id'] for t in tasks}:
            raise ProtocolError('Exact package binding required')
        for split in ('search', 'test'):
            if {t['task_type'] for t in tasks if t['split'] == split} != set(TASK_TYPES):
                raise ProtocolError('Current aggregate needs all five task types in each development routing split')
        bindings = {}
        for identity in tasks:
            if set(identity) != {'task_id', 'task_type', 'paper_id', 'split'}:
                raise ProtocolError('Only minimal identities belong in routing manifest')
            package = Path(packages[identity['task_id']]).resolve(strict=True)
            task = load_task(package/'task.json')
            if task['split'] != 'development' or any(task[k] != identity[k] for k in ('task_id','task_type','paper_id')):
                raise ProtocolError('Only development material with exact identity is supported')
            bindings[identity['task_id']] = {'path': str(package), 'files': tree_manifest(package)}
        h0 = Path(h0).resolve(strict=True)
        initial = tree_manifest(h0)
        if not initial:
            raise ProtocolError('H0 cannot be empty')
        run = EvolutionRun.create(root, tasks, rounds, development=True)
        builder_root.mkdir(parents=True)
        config = {'development': True, 'builder_root': str(builder_root), 'packages': bindings,
                  'h0_path': str(h0), 'h0_files': initial, 'routing_hash': digest(tasks), 'rounds': rounds}
        write_json(root/'driver.json', {'configuration': config, 'configuration_hash': digest(config)}, exclusive=True)
        run.submit(h0, note='Externally built H0; construction provenance not certified by this driver')
        return cls(root)

    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.run = EvolutionRun(self.root)

    def _verify(self):
        saved = read_json(self.root/'driver.json'); c = saved['configuration']
        if digest(c) != saved['configuration_hash']:
            raise ProtocolError('Driver configuration hash mismatch')
        state = self.run._state()
        if c['routing_hash'] != digest(state['tasks']) or c['rounds'] != state['round_limit']:
            raise ProtocolError('Routing or round limit changed')
        for binding in c['packages'].values():
            if tree_manifest(Path(binding['path'])) != binding['files']:
                raise ProtocolError('Frozen material package changed')
        if tree_manifest(Path(c['h0_path'])) != c['h0_files']:
            raise ProtocolError('Original H0 input changed')
        for v in state['versions']:
            self.run.verify_snapshot(v['version_id'])
        for path in (self.root/'operations').glob('*.json'):
            row = read_json(path)
            if row['status'] == 'complete' and row['result_hash'] != digest(row['result']):
                raise ProtocolError('Cached operation result changed')
        for path in (self.root/'approved_reviews').glob('*.json'):
            record=read_json(path)
            if record['approval_hash'] != digest(record['approval']):
                raise ProtocolError('Frozen review changed')
        return c, state

    def _once(self, operation, request, callback):
        path = self.root/'operations'/(operation+'.json')
        request_hash = digest(request)
        if path.exists():
            old = read_json(path)
            if old['request_hash'] != request_hash:
                raise ProtocolError('Resume request changed')
            if old['status'] != 'complete':
                raise ProtocolError('Unresolved operation; explicit adjudication required, no automatic retry')
            if old['result_hash'] != digest(old['result']):
                raise ProtocolError('Cached operation result changed')
            return old['result']
        row = {'request_hash': request_hash, 'status': 'in_flight'}
        write_json(path, row, exclusive=True)
        try:
            result = callback(request=copy.deepcopy(request))
            row.update(status='complete', result=result, result_hash=digest(result))
            write_json(path, row)
            return result
        except Exception as exc:
            row.update(status='unresolved', error_type=type(exc).__name__, error=str(exc),
                       automatic_zero=False, quality_score=None)
            write_json(path, row)
            raise

    def _review(self, operation, request, evaluation, review_evaluation):
        """Trusted pure reader only: MUST NOT invoke a model or mutate evaluation.

        This Python callback contract is not a process-level side-effect sandbox.
        Pending review retries only this read, never the paid evaluate operation.
        """
        binding={'request_hash':digest(request),'evaluation_hash':digest(evaluation)}
        path=self.root/'approved_reviews'/(operation+'.json')
        if path.exists():
            record=read_json(path); approval=record['approval']
            if record['approval_hash'] != digest(approval):
                raise ProtocolError('Frozen approval mutated')
        else:
            approval=review_evaluation(request=copy.deepcopy(request),evaluation=copy.deepcopy(evaluation),binding=copy.deepcopy(binding))
            write_json(self.root/'review_attempts'/operation/(uuid.uuid4().hex+'.json'),
                       {'binding':binding,'response':approval,'automatic_zero':False},exclusive=True)
            if approval.get('status') == 'pending_review':
                raise PendingEvaluationReview('Evaluation cached; awaiting pure external review, not a paid retry')
        if set(approval) != {'status','binding','envelope','envelope_hash','review_receipt_hash'} or approval['status'] != 'approved' or approval['binding'] != binding:
            raise ProtocolError('Approval not bound to evaluated request and immutable result')
        if approval['envelope_hash'] != digest(approval['envelope']) or not isinstance(approval['review_receipt_hash'],str) or not re.fullmatch('[0-9a-f]{64}',approval['review_receipt_hash']):
            raise ProtocolError('Approval score/feedback or review receipt hash invalid')
        validate_envelope(request['identity'],approval['envelope'])
        if not path.exists():
            write_json(path,{'approval':approval,'approval_hash':digest(approval)},exclusive=True)
        return approval['envelope']

    def _evaluate(self, version, split, config, evaluate, review_evaluation):
        state = self.run._state()
        tasks = [t for t in state['tasks'] if t['split'] == split]
        rows, feedback = [], []
        for task in tasks:
            request = {'development': True, 'identity': task, 'version_id': version,
                       'harness_directory': str(self.root/'snapshots'/version),
                       'harness_hash': self.run.verify_snapshot(version)['hash'],
                       'package': config['packages'][task['task_id']]['path'],
                       'package_hash': digest(config['packages'][task['task_id']]['files']),
                       'output_directory': str(self.root/'evaluations'/version/digest(task['task_id']))}
            operation='evaluate-'+digest([version,task['task_id']])
            evaluation = self._once(operation, request, evaluate)
            envelope = self._review(operation,request,evaluation,review_evaluation) if review_evaluation is not None else evaluation
            validate_envelope(task,envelope)
            if split=='search' and 'public_evidence_bundle' in envelope:
                descriptor=self.root/'public_evidence_descriptors'/version/(digest(task['task_id'])+'.json')
                if descriptor.exists() and read_json(descriptor)!=envelope['public_evidence_bundle']:
                    raise ProtocolError('Published search evidence descriptor changed')
                if not descriptor.exists():write_json(descriptor,envelope['public_evidence_bundle'],exclusive=True)
            rows.append(envelope['result']); feedback.append(envelope['feedback'])
        if version not in state[split+'_done']:
            self.run.record_evaluation(version, split, rows)
        if split == 'search' and version not in self.run._state()['feedback_done']:
            self.run.publish_search_feedback(version, feedback)

    def _builder_request(self, config, operation, current):
        """No hidden identity, path, score, judge-private reference or controller path."""
        stage = Path(config['builder_root'])/operation
        expected = self.root/'staging_checks'/(operation+'.json')
        if not stage.exists():
            stage.mkdir()
            shutil.copytree(self.root/'snapshots'/current, stage/'harness')
            (stage/'search_evidence').mkdir()
            for version in self.run._state()['feedback_done']:
                for descriptor in sorted((self.root/'public_evidence_descriptors'/version).glob('*.json')):
                    bundle=read_json(descriptor);source=verify_public_bundle(bundle)
                    dest=stage/'search_evidence'/version/descriptor.stem
                    dest.mkdir(parents=True)
                    for item in bundle['files']:
                        target=contained(dest,item['path']);target.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(contained(source,item['path'],must_exist=True),target)
                        if file_hash(target)!=item['sha256']:raise ProtocolError('Public evidence changed during staging')
            for task in self.run._state()['tasks']:
                if task['split'] == 'search':
                    package = Path(config['packages'][task['task_id']]['path'])
                    export_task(load_task(package/'task.json'), package, stage/'search'/digest(task['task_id']), audience='development_executor')
            write_json(expected, tree_manifest(stage), exclusive=True)
        if not expected.exists():
            raise ProtocolError('Unattested partial builder staging; do not resume automatically')
        # Only original staged inputs are immutable; the adapter may add output/.
        for item in read_json(expected):
            if file_hash(contained(stage,item['path'],must_exist=True)) != item['sha256']:
                raise ProtocolError('Builder staged input mutated')
        return {'development': True, 'operation': operation, 'workspace': str(stage),
                'current_harness': str(stage/'harness'), 'search_directory': str(stage/'search'),
                'public_evidence_directory': str(stage/'search_evidence'),
                'builder_view': self.run.builder_view(), 'output_directory': str(stage/'output')}

    def advance(self, *, evaluate, evolve, select, review_evaluation=None):
        """Resume only completed operations; finish at most the configured rounds.

        Full mixed search per frozen version precedes next modification. Test
        evaluations start only after builder selection and never reenter a view.
        Adapter exceptions/unknown outcomes stop immediately, never become zeros.
        """
        config, state = self._verify()
        policy={'mode':'pure_external_review' if review_evaluation is not None else 'trusted_preaccepted_test_adapter'}
        policy_path=self.root/'review_policy.json'
        if policy_path.exists() and read_json(policy_path)!=policy:
            raise ProtocolError('Cannot change review policy during resume')
        if not policy_path.exists():write_json(policy_path,policy,exclusive=True)
        while state['builder_selected'] is None:
            current = state['versions'][-1]['version_id']
            self._evaluate(current, 'search', config, evaluate, review_evaluation)
            if len(state['versions']) == state['round_limit'] + 1:
                request = self._builder_request(config, 'select', current)
                choice = self._once('select', request, select)
                if set(choice) != {'version_id','reason'}:
                    raise ProtocolError('Invalid selection adapter output')
                self.run.select(choice['version_id'], choice['reason'])
            else:
                request = self._builder_request(config, 'evolve-'+current, current)
                result = self._once('evolve-'+current, request, evolve)
                self._builder_request(config, 'evolve-'+current, current)
                if set(result) != {'candidate_relative_path','files'}:
                    raise ProtocolError('Evolver must return candidate path and file hashes')
                candidate = contained(Path(request['workspace']), result['candidate_relative_path'], must_exist=True)
                if not candidate.is_relative_to(Path(request['output_directory'])) or tree_manifest(candidate) != result['files']:
                    raise ProtocolError('Candidate must be frozen observed output inside staged output directory')
                self.run.submit(candidate, note='Development injected evolver; not autonomous acceptance')
            config, state = self._verify()
        for version in state['versions']:
            self._evaluate(version['version_id'], 'test', config, evaluate, review_evaluation)
        summary = self.run.summary()
        write_json(self.root/'summary.json', {'development_only':True, 'summary':summary})
        return summary
