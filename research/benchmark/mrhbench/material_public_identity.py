"""Opt-in opaque task identity projection, not a semantic anonymity guarantee.

Private random maps persist across comparison arms. Projection changes only
controller task IDs; all scientific files retain their bytes. Exact known
identity scanning supplements, never replaces, independent semantic review of
the actual compiled/exported release. No production driver uses this implicitly.
"""
from copy import deepcopy
import json
from pathlib import Path
import secrets
import shutil
import unicodedata

from .io import ProtocolError, contained, digest, file_hash, read_json, write_json
from .material_public_surface import public_surface


def _safe(path, *, must_exist=True):
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or bool(getattr(parent.lstat(), 'st_file_attributes', 0) & 1024)):
            raise ProtocolError('Links/reparse paths are not admissible')
    if must_exist and not path.exists():
        raise ProtocolError('Required identity input missing')
    if path.is_file() and path.stat().st_nlink > 1:
        raise ProtocolError('Hardlinked identity input is not admissible')
    return path.resolve()


def _identity(path):
    path = _safe(path)
    return {'path':str(path),'sha256':file_hash(path),'bytes':path.stat().st_size}


def _verify(identity):
    if _identity(identity['path']) != {k:identity[k] for k in ('path','sha256','bytes')}:
        raise ProtocolError('Private identity map/receipt bytes changed')
    return Path(identity['path'])


def _outside(path, roots):
    path = _safe(path, must_exist=False)
    for root in roots:
        root = _safe(root)
        if path == root or path.is_relative_to(root):
            raise ProtocolError('Private map/receipt must be outside candidate and public roots')
    return path


def _tree(root):
    root = _safe(root)
    result = {}
    for p in sorted(root.rglob('*')):
        _safe(p)
        if p.is_file():
            result[p.relative_to(root).as_posix()] = {'sha256':file_hash(p),'bytes':p.stat().st_size}
    return result


def allocate_map(source_output, destination, *, aliases=()):
    """One exclusive random allocation; retain returned identity for every arm."""
    source = _safe(source_output)
    destination = _outside(destination,[source])
    if destination.exists():
        raise ProtocolError('Mapping already exists; verify and reuse rather than reallocate')
    package_path = source/'package.json'
    _safe(package_path)
    package = read_json(package_path)
    originals = [t['task_id'] for t in package['tasks']]
    if not originals or len(set(originals)) != len(originals) or any(not isinstance(x,str) or not x for x in originals):
        raise ProtocolError('Unique nonempty original task IDs required')
    if not isinstance(package.get('paper_id'),str) or not package['paper_id']:
        raise ProtocolError('Private source paper ID required')
    if not isinstance(aliases,(list,tuple)) or any(not isinstance(x,str) or not x.strip() for x in aliases):
        raise ProtocolError('Aliases must be nonempty explicit strings')
    mapping = {old:'task-'+secrets.token_hex(16) for old in originals}
    if len(set(mapping.values())) != len(mapping):
        raise ProtocolError('Random task ID collision; no partial allocation published')
    payload = {'schema_version':'material-public-identity-map-1',
        'source_package':_identity(package_path),'private_paper_id':package['paper_id'],
        'task_ids':mapping,'aliases':list(aliases),
        'scientific_acceptance':False,'id_generation':'cryptographic_random_128bit_not_source_hash'}
    write_json(destination,payload,exclusive=True)
    return _identity(destination)


def validate_map(map_identity, *, roots=()):
    path = _verify(map_identity)
    _outside(path, roots)
    data = read_json(path)
    if data.get('schema_version') != 'material-public-identity-map-1':
        raise ProtocolError('Unknown private identity map')
    _verify(data['source_package'])
    source = read_json(Path(data['source_package']['path']))
    ids = data['task_ids']
    if set(ids) != {t['task_id'] for t in source['tasks']} or data['private_paper_id'] != source['paper_id']:
        raise ProtocolError('Private map does not match immutable original package')
    import re
    if len(set(ids.values())) != len(ids) or any(not re.fullmatch(r'task-[0-9a-f]{32}',value) for value in ids.values()):
        raise ProtocolError('Invalid/duplicate opaque ID')
    return data


def remap_task_keys(values, map_identity):
    """Explicit controller budget/collection remapping; no missing/default keys."""
    mapping = validate_map(map_identity)['task_ids']
    if not isinstance(values,dict) or set(values) != set(mapping):
        raise ProtocolError('Budget/collection keys must exactly match all original tasks')
    return {mapping[key]:deepcopy(value) for key,value in values.items()}


def _needles(mapping):
    return sorted(set([mapping['private_paper_id'],*mapping['task_ids'],*mapping['aliases']]))


def _norm(value):
    return unicodedata.normalize('NFKC',value).casefold()


def _check_text(text, needles, locator):
    value = _norm(text)
    for needle in needles:
        if _norm(needle) in value:
            raise ProtocolError('Known private identity remains in public surface: '+locator)


def _json_scan(value, needles, locator='$'):
    if isinstance(value,dict):
        for key,item in value.items():
            _check_text(str(key),needles,locator+'[key]')
            _json_scan(item,needles,locator+'/'+str(key))
    elif isinstance(value,list):
        for index,item in enumerate(value):_json_scan(item,needles,locator+'/'+str(index))
    elif isinstance(value,str):
        _check_text(value,needles,locator)


def _asset_scan(root, rows, needles):
    unknown = []
    checked = []
    for row in rows:
        _check_text(row['path'],needles,'asset path')
        path = contained(root,row['path'],must_exist=True)
        _safe(path)
        actual = file_hash(path)
        if actual != row['sha256']:
            raise ProtocolError('Public asset changed before identity scan')
        raw = path.read_bytes()
        # Also inspect literal UTF-8 byte forms in binaries before reporting unknown.
        for needle in needles:
            if needle.encode('utf8').lower() in raw.lower():
                raise ProtocolError('Known private identity remains in public asset bytes: '+row['path'])
        json_checked = False
        try:
            text=raw.decode('utf-8-sig')
            if '\x00' in text:raise UnicodeError('binary NUL')
        except UnicodeError:
            unknown.append(row['path'])
        else:
            _check_text(text,needles,'asset '+row['path'])
            # JSON escapes can hide a known identity from the literal text scan.
            # Parse regardless of extension, but do not pretend arbitrary text,
            # compressed payloads or other encodings were semantically decoded.
            def reject_constant(value):
                raise ValueError('Non-standard JSON constant: '+value)
            try:
                decoded = json.loads(text, parse_constant=reject_constant,
                    object_pairs_hook=lambda pairs: [[key,value] for key,value in pairs])
            except (ValueError, RecursionError):
                pass
            else:
                _json_scan(decoded,needles,'JSON asset '+row['path'])
                json_checked = True
        checked.append({'path':row['path'],'sha256':actual,'bytes':len(raw),
                        'strict_json_keys_values_scanned':json_checked})
    return checked,unknown


def _scan_result(rows,unknown,public_hash):
    return {'schema_version':'material-public-identity-scan-1',
        'known_identity_matches':0,'status':'unknown_binary_requires_independent_review' if unknown else 'no_known_identity_match',
        'unknown_binary_assets':unknown,'assets':rows,'public_projection_sha256':public_hash,
        'semantic_anonymity_verified':False,'scientific_acceptance':False,
        'scope':'Known explicit identities only; independent full public-surface semantic review remains mandatory.'}


def scan_candidate(output_root, map_identity):
    root = _safe(output_root)
    mapping = validate_map(map_identity,roots=[root])
    package = read_json(root/'package.json')
    if {t['task_id'] for t in package['tasks']} != set(mapping['task_ids'].values()):
        raise ProtocolError('Candidate does not use exactly the allocated opaque task IDs')
    surface = public_surface(root)
    needles = _needles(mapping)
    _json_scan(surface['records'],needles)
    assets={a['path']:a for t in package['tasks'] for a in t['assets'] if a['visibility']=='public'}
    checked,unknown=_asset_scan(root,list(assets.values()),needles)
    return _scan_result(checked,unknown,digest(surface['records']))


def scan_release(public_root,map_identity):
    """Inspect the actual exported bytes, not a candidate-only approximation."""
    root = _safe(public_root)
    mapping = validate_map(map_identity,roots=[root])
    view=read_json(root/'task.json')
    if view.get('task_id') not in mapping['task_ids'].values():
        raise ProtocolError('Released task lacks allocated opaque ID')
    needles=_needles(mapping)
    _json_scan(view,needles)
    assets=view['asset_manifest']
    expected={'task.json',*[a['path'] for a in assets]}
    if set(_tree(root)) != expected:
        raise ProtocolError('Unlisted files in public release, possible private map/receipt exposure')
    checked,unknown=_asset_scan(root,assets,needles)
    return _scan_result(checked,unknown,file_hash(root/'task.json'))


def project_candidate(source_output,destination,map_identity,*,receipt_path):
    """Fresh copy; only tasks[].task_id is changed, never scientific assets."""
    source = _safe(source_output)
    destination = _safe(destination,must_exist=False)
    receipt = _safe(receipt_path,must_exist=False)
    if destination.exists() or destination == source or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ProtocolError('Projection requires separate fresh destination')
    if receipt.exists() or receipt == destination or receipt.is_relative_to(destination):
        raise ProtocolError('Exclusive private receipt outside output required')
    _outside(receipt,[source])
    mapping = validate_map(map_identity,roots=[source])
    map_path=Path(map_identity['path']).resolve()
    if map_path == destination or map_path.is_relative_to(destination):
        raise ProtocolError('Private map cannot be copied into candidate')
    if _identity(source/'package.json') != mapping['source_package']:
        raise ProtocolError('Mapping belongs to another original candidate')
    before = _tree(source)
    package = read_json(source/'package.json')
    projected = deepcopy(package)
    for task in projected['tasks']:task['task_id']=mapping['task_ids'][task['task_id']]
    shutil.copytree(source,destination)
    write_json(destination/'package.json',projected)
    after = _tree(destination)
    for name,row in before.items():
        if name != 'package.json' and after.get(name) != row:
            raise ProtocolError('Scientific asset changed during identity projection')
    if set(after) != set(before) or _tree(source) != before:
        raise ProtocolError('Original/copy membership changed during projection')
    scan=scan_candidate(destination,map_identity)
    record={'schema_version':'material-public-identity-projection-1','map':map_identity,
        'source_package':mapping['source_package'],'projected_package':_identity(destination/'package.json'),
        'source_inventory':before,'projected_inventory':after,'modified_json_paths':['/tasks/'+str(i)+'/task_id' for i in range(len(projected['tasks']))],
        'assets_byte_identical':True,'private_paper_id_preserved':projected['paper_id']==package['paper_id'],
        'scan':scan,'historical_reviews_transferred':False,'runtime_acceptance_transferred':False,
        'scientific_acceptance':False}
    write_json(receipt,record,exclusive=True)
    return {'receipt':_identity(receipt),'projected_package':record['projected_package'],'scan':scan}
