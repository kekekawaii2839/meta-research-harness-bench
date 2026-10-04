"""Opt-in opaque-ID assignment outside the unchanged QualityBoundRunner.

The constructor receives IDs before writing output and must use them itself.
No post-generation renaming or inherited scientific approval is performed.
"""
from pathlib import Path

from .io import ProtocolError, file_hash, read_json, write_json, digest
from .material_batch import _input_snapshot, _check_inputs
from .material_quality_runner import QualityBoundRunner
from .material_public_identity import validate_map, scan_candidate


class IdentityBoundRunner:
    """Preserve all underlying quality gates and add immutable ID assignment."""
    def __init__(self, inner, *, map_identity):
        if not isinstance(inner, QualityBoundRunner):
            raise ProtocolError('IdentityBoundRunner must wrap the complete QualityBoundRunner')
        self.inner = inner
        self.map_identity = dict(map_identity)
        mapping = validate_map(self.map_identity)
        original = read_json(Path(mapping['source_package']['path']))
        self.assignment = {'schema_version':'material-identity-assignment-1',
            'tasks':[{'task_id':mapping['task_ids'][task['task_id']],
                      'task_type':task['task_type']} for task in original['tasks']]}
        self.assignment_digest = digest(self.assignment)

    def _check_assignment(self, workspace):
        package = read_json(workspace/'output/package.json')
        actual = [(task['task_id'],task['task_type']) for task in package['tasks']]
        expected = [(task['task_id'],task['task_type']) for task in self.assignment['tasks']]
        if len(actual) != len(expected) or set(actual) != set(expected):
            raise ProtocolError('Generated task IDs/types differ from controller assignment; no post-hoc correction')

    def _check_output(self, workspace):
        self._check_assignment(workspace)
        return scan_candidate(workspace/'output',self.map_identity)

    def run(self, *, workspace, prompt, role, **kwargs):
        workspace = Path(workspace)
        if role not in {'constructor','material_reviewer','adjudicator'}:
            raise ProtocolError('Unsupported identity-bound material role')
        mapping = validate_map(self.map_identity,roots=[workspace])
        request = read_json(workspace/'request.json')
        if request.get('paper_id') != mapping['private_paper_id']:
            raise ProtocolError('Identity assignment and request belong to different private paper')
        assignment_file = workspace/'identity_assignment.json'
        write_json(assignment_file,self.assignment,exclusive=True)
        protected = ['identity_assignment.json']
        snapshot = _input_snapshot(workspace,protected)
        scan_before = None
        if role != 'constructor':
            scan_before = self._check_output(workspace)
        prompt += ('\nRead immutable identity_assignment.json. It lists the exact controller-allocated task IDs and task types. '
            'Constructor: produce exactly those task IDs/types in output/package.json from the start; never substitute source-derived '
            'IDs and never add, drop, or change task types. Reviewer/adjudicator: verify the same exact assignment. '
            'Prior candidate, source documents and private repair notes may contain historical identifiers; they are private context, '
            'not permission to expose them in public facts, contracts, filenames or asset bytes. Preserve scientific content and all '
            'quality-policy obligations; do not silently rewrite scientific assets merely to suppress a scanner. '
            'ID assignment is not scientific acceptance, and binary scan unknowns still require independent inspection.\n')
        result = self.inner.run(workspace=workspace,prompt=prompt,role=role,**kwargs)
        _check_inputs(workspace,protected,snapshot,role)
        if role == 'constructor':
            # The existing batch controller fills exact CONTROLLER_FILL hashes
            # only AFTER constructor.run returns. Do not pre-fill or duplicate
            # its original-byte receipt. Strict public scan occurs before the
            # reviewer native call, after that unchanged controller hash stage.
            self._check_assignment(workspace)
            scan_after = {'status':'pending_controller_hash_fill_then_pre_review_scan',
                'scientific_acceptance':False,'semantic_anonymity_verified':False}
        else:
            scan_after = self._check_output(workspace)
        # Private role bookkeeping only; never part of the released asset manifest.
        write_json(workspace/'identity_controller_validation.json',{
            'schema_version':'material-identity-role-validation-1','role':role,
            'assignment_sha256':file_hash(assignment_file),'assignment_digest':self.assignment_digest,
            'private_map_sha256':self.map_identity['sha256'],
            'scan_before':scan_before,'scan_after':scan_after,
            'scientific_acceptance':False,'post_generation_renaming':False,
            'binary_unknown_is_not_clear':True},exclusive=True)
        return result
