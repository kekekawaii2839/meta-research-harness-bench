"""Fresh single-task projection retaining an original structural failure.

No fabricated prior review and no scientific file edits. This preparation tool
does not call models or grant acceptance. All original coverage rows are retained
so constructor, not projection code, must repair a malformed coverage matrix.
"""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mrhbench.io import ProtocolError, file_hash, read_json, write_json, contained
from mrhbench.incremental_repair import _safe_path, _tree, _disjoint
from mrhbench.material_pipeline import validate_job


def prepare(workspace, destination, *, task_id, notes, entry_audit):
    ws, dst = _safe_path(Path(workspace)), _safe_path(Path(destination))
    _disjoint(ws, dst)
    if dst.exists():
        raise ProtocolError('Fresh projection destination required')
    job = read_json(ws/'job.json')
    validate_job(job,ws)
    if not isinstance(notes,list) or any(not isinstance(n,str) or not n.strip() for n in notes):
        raise ProtocolError('Explicit nonempty repair-note strings required')
    if job.get('prepopulated_output_files'):
        raise ProtocolError('Prepopulated inputs need a separately audited projection')
    prior = ws/'construct'/job['job_id']
    if (prior/'reviewer/review.json').exists():
        raise ProtocolError('This entry is only for an honestly missing original review')
    root = prior/'constructor/output'
    files = _tree(root)
    package = read_json(root/'package.json')
    chosen = [t for t in package['tasks'] if t['task_id']==task_id]
    if len(chosen)!=1:
        raise ProtocolError('Unique selected original task required')
    task = chosen[0]
    if task['paper_id']!=job['paper_id']:
        raise ProtocolError('Original task/job paper mismatch')
    selected = set()
    for asset in task['assets']+task['input_contract'].get('files',[]):
        path = contained(root, asset['path'], must_exist=True)
        if file_hash(path)!=asset['sha256']:
            raise ProtocolError('Original selected asset hash mismatch')
        selected.add(asset['path'])
    selected.update(name for name in files if name.startswith('environment/'))
    facts = set(task['input_fact_ids']+task['private_fact_ids'])
    projected = copy.deepcopy(package)
    projected['tasks'] = [copy.deepcopy(task)]
    projected['facts'] = [f for f in package['facts'] if f['fact_id'] in facts]
    if {f['fact_id'] for f in projected['facts']}!=facts:
        raise ProtocolError('Missing selected facts')
    # Intentionally do NOT normalize the original defective coverage rows.
    assert projected['coverage']==package['coverage']
    payloads = {}
    source_bindings = []
    for index, source in enumerate(job['sources']):
        raw = source['local_path']
        path = _safe_path(Path(raw) if Path(raw).is_absolute() else contained(ws,raw,must_exist=True))
        if file_hash(path)!=source['sha256']:
            raise ProtocolError('Original source hash mismatch')
        rel = 'source_inputs/%03d-%s' % (index,path.name)
        payloads[rel] = path.read_bytes()
        source_bindings.append({'original':str(path),'copy':rel,'sha256':source['sha256']})
        source['local_path'] = rel
    prefix = 'prior/'+job['job_id']
    payloads.update({prefix+'/constructor/output/'+name:files[name] for name in selected})
    receipt = prior/'receipt.json'
    if not receipt.is_file():
        raise ProtocolError('Missing original structural failure receipt')
    original_failure = read_json(receipt)
    if (original_failure.get('job_id') != job['job_id']
            or original_failure.get('status') != 'failed_needs_attribution'
            or original_failure.get('error',{}).get('message') != 'Explicit five-type coverage matrix required'):
        raise ProtocolError('Not the identified original coverage failure')
    payloads[prefix+'/receipt.json'] = receipt.read_bytes()
    job['requested_task_types'] = [task['task_type']]
    header = ('CONTROLLER SINGLE-TASK ENTRY: construct only '+task_id+'. Other stages are excluded by controller projection, '
        'not scientifically unsupported. The original malformed coverage is intentionally retained for you to repair to exactly '
        'one row per each of the five task types, preserving relevant scope/exclusion reasons; mark other task types deferred '
        'solely for this projection. No original independent review exists; the original structural error is not a scientific '
        'verdict. Apply full current policy and the separate immutable identity_assignment.json; its opaque output task ID '
        'takes precedence over historical source-derived task IDs. Do not reconstruct excluded tasks.\n\n')
    job['scope_request'] = header+'HISTORICAL MULTITASK ORDER (the single-task boundary above controls):\n'+job['scope_request']
    def enc(x): return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    payloads[prefix+'/constructor/output/package.json'] = enc(projected)
    payloads['job.json'] = enc(job)
    payloads['repair_notes.json'] = enc([header]+list(notes))
    # Audit is private evidence, never a prior-review substitute.
    audit = _safe_path(Path(entry_audit))
    proof = {'schema_version':'missing-review-single-task-projection-1',
        'original_package':{'path':str(root/'package.json'),'sha256':file_hash(root/'package.json')},
        'entry_audit':{'path':str(audit),'sha256':file_hash(audit)},
        'original_receipt':{'path':str(receipt),'sha256':file_hash(receipt)},
        'missing_prior_review':True,'prior_review_fabricated':False,
        'source_bindings':source_bindings,'coverage_preserved_for_model_repair':True,
        'scientific_asset_bytes_changed':False,'environment_bytes_changed':False,
        'metadata_changes':['selected task/facts only','single-task scope and repair instructions','relative byte-preserved source copies'],
        'model_calls':0,'scientific_acceptance':False}
    dst.mkdir(parents=True)
    for rel,data in payloads.items():
        p=contained(dst,rel);p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(data)
    validate_job(job,dst)
    proof['output_inventory']={name:{'sha256':file_hash(dst/name),'bytes':len(data)} for name,data in payloads.items()}
    write_json(dst/'projection_provenance.json',proof,exclusive=True)
    return proof
