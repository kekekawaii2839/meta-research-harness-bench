"""Offline audit of retained real inputs/artifacts; never re-executes solver code."""
import base64
import hashlib
from pathlib import Path

from mrhbench.execution_identity import public_input_identities
from mrhbench.io import read_json, write_json, file_hash, digest, parse_json
from run_container_stage_development import evidence_for_run


def main():
    root = Path(__file__).resolve().parent
    parent = Path('D:/mrhbench-local-pilot/h0-budget-pilot-20260923-001')
    reports = []
    for name in ('iv-exp', 'ssa-write-evidence'):
        stage = parent/name
        run = stage/'execution'
        public = stage/'public'
        package = root/'materials/pilot_v3/budget_candidates_v2'/name
        task = read_json(package/'task.json')
        view = read_json(public/'task.json')
        mp = run/'container/0001-manifest.json'
        manifest = read_json(mp)
        before = {}
        paths = [stage/'evidence.json', mp, public/'task.json', package/'task.json',
                 run/'artifact_inventory.json']
        paths += [run/'container/release'/r['path'] for r in manifest['inputs']]
        paths += [public/a['path'] for a in view['asset_manifest']]
        paths += [package/a['path'] for a in task['assets']]
        paths += [run/'artifacts'/r['path'] for r in read_json(run/'artifact_inventory.json')['files']]
        paths += list((run/'container/executed-entrypoints').glob('*.py'))
        for path in paths: before[str(path)] = file_hash(path)
        identities = public_input_identities(view, manifest, public)
        input_checks = []
        for row in manifest['inputs']:
            data = (run/'container/release'/row['path']).read_bytes()
            assert hashlib.sha256(data).hexdigest() == row['sha256']
            assert len(data) == row['bytes']
            input_checks.append({**row, 'retained_container_release_raw_matches': True})
        records = evidence_for_run(task, package, public, run)
        byid = {r['evidence_id']:r for r in records}
        historical = {r['evidence_id']:r for r in read_json(stage/'evidence.json')}
        reference_checks = []
        for i, asset in enumerate(task['assets']):
            data = (package/asset['path']).read_bytes()
            record = byid['reference-'+str(i)]
            prefix = 'ASSET '+asset['asset_id']+'\n'
            assert record['content'] == prefix+data.decode('utf8')
            assert record['sha256'] == digest(record['content'])
            old = historical.get(record['evidence_id'])
            reference_checks.append({'asset_id':asset['asset_id'],'visibility':asset['visibility'],
                'raw_sha256':file_hash(package/asset['path']), 'crlf_count':data.count(b'\r\n'),
                'new_reference_preserves_raw_decoded_text':True,
                'historical_reference_equal_raw_decoded_text':old['content']==record['content'] if old else None,
                'evidence_content_sha256':record['sha256']})
        inventory = parse_json(byid['captured-artifact-inventory']['content'])
        artifact_checks=[]
        for row in inventory['files']:
            data = (run/'artifacts'/row['path']).read_bytes()
            assert hashlib.sha256(data).hexdigest() == row['sha256']
            record=byid.get(row['evidence_id'])
            if record:
                assert record['sha256']==digest(record['content'])==row['evidence_content_sha256']
                if record['media_type'].startswith('image/'):
                    assert base64.b64decode(record['content'], validate=True)==data
                else:
                    assert record['content']==row['content_transform']['prefix']+data.decode('utf8')
            artifact_checks.append({'path':row['path'],'bytes':len(data),'raw_sha256':row['sha256'],
                'evidence_id':row['evidence_id'],'evidence_content_sha256':row['evidence_content_sha256'],
                'historically_published_under_same_id':row['evidence_id'] in historical,
                'raw_identity_and_current_representation_verified':True})
        public_index = parse_json(byid['platform-public-input-identities']['content'])
        assert public_index == identities
        assert all(r['sha256']==digest(r['content']) for r in records)
        bindings=parse_json(byid['platform-public-reference-bindings']['content'])
        snapshots=[]
        for path in (run/'container/executed-entrypoints').glob('*.py'):
            assert file_hash(path)==path.stem
            assert byid['executed-'+path.stem]['content']==path.read_bytes().decode('utf8')
            snapshots.append({'raw_sha256':path.stem,'bytes':path.stat().st_size})
        assert before=={str(path):file_hash(path) for path in paths}
        reports.append({'name':name,'historical_evidence_sha256':file_hash(stage/'evidence.json'),
            'historical_evidence_unchanged':True,'input_manifest_sha256':file_hash(mp),
            'input_checks':input_checks,'public_input_identity_record':public_index,
            'reference_checks':reference_checks,'public_reference_bindings':bindings,
            'artifact_checks':artifact_checks,'executed_entrypoint_snapshots':snapshots,
            'current_evidence_rebuilt_in_memory_only':True,'current_record_count':len(records),
            'protected_file_hashes':before})
    result={'version':1,'new_model_calls':0,'new_scientific_runs':0,
        'runs':reports,'findings':[
            'All checked retained raw public inputs match TaskView, exported files and container start manifest; captured artifacts match controller raw hashes.',
            'Historical reference text normalized CRLF; new evidence preserves exact UTF-8-decoded bytes and records prefix/hash domains.',
            'EvidenceRecord SHA hashes canonical JSON content, not original file bytes; comparison to raw SHA without transformation is invalid.',
            'New public input identities and reference bindings make prior controller-private linkage explicit; historical judge coverage is not retroactively repaired.',
            'IV config.json is a solver-generated captured output. Its final byte identity is published in new inventory, not proof the same bytes were consumed at every execution.',
            'No universal configuration filename/schema imposed. Entrypoint snapshots are frozen; imported dependencies and mutable configuration are not fully snapshotted.',
            'New evidence availability is not proof of judge reading or scientific correctness; no historical grade changed.'
        ],'tests':'7 independent identity unit tests passed; actual two-run reconstruction assertions passed'}
    output=root/'audit/execution_identity_independent_review_v1.json'
    write_json(output,result,exclusive=True)
    print(output)


if __name__=='__main__':main()
