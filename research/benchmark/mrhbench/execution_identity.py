"""Public input byte identities, not scientific verification or an OS attestation.

The caller supplies a controller-owned container start manifest and the already
released TaskView. No source-package private paths or complete manifest are emitted.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .io import ProtocolError, contained, digest, parse_json, relative_path


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ProtocolError("Invalid raw SHA256 identity")
    return value


def public_input_identities(view: dict, manifest: dict, public_root: Path) -> dict:
    """Bind released task/assets to their recorded /inputs/public mount identities.

    Hashes are of raw bytes, preserving CRLF. TaskView hash is separately labeled
    canonical JSON. This reads no private assets and exposes no host paths. It
    cannot detect semantic misclassification inside an otherwise public asset.
    """
    if not isinstance(view, dict) or not isinstance(manifest, dict):
        raise ProtocolError("TaskView and controller manifest must be objects")
    if 'private' in view:
        raise ProtocolError("Private task object is not a released TaskView")
    assets = view.get('asset_manifest')
    rows = manifest.get('inputs')
    if not isinstance(assets, list) or not isinstance(rows, list):
        raise ProtocolError("Missing public asset or container input manifest")
    expected = {'task.json': {'role': 'released_task'}}
    ids = set()
    folded = {'task.json'}
    for asset in assets:
        if not isinstance(asset, dict) or set(asset) - {'asset_id', 'path', 'sha256', 'visibility'}:
            raise ProtocolError("Unsupported public asset identity fields")
        if asset.get('visibility', 'public') != 'public':
            raise ProtocolError("Nonpublic asset in public manifest")
        name = asset.get('path')
        relative_path(name)
        aid = asset.get('asset_id')
        if not isinstance(aid, str) or not aid or aid in ids:
            raise ProtocolError("Missing or duplicate asset id")
        if not name.startswith('assets/') or name.casefold() in folded:
            raise ProtocolError("Duplicate or non-asset public path")
        ids.add(aid); folded.add(name.casefold())
        expected[name] = {'role': 'released_asset', 'asset_id': aid,
                          'taskview_raw_sha256': _sha(asset.get('sha256'))}
    observed = {}
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ProtocolError("Invalid container input entry")
        name = row.get('path')
        relative_path(name)
        if name.casefold() in seen:
            raise ProtocolError("Duplicate container input path")
        seen.add(name.casefold())
        if not name.startswith('public/'):
            continue  # Harness/worker identities are not research input assets.
        released = name[len('public/'):]
        if released not in expected:
            raise ProtocolError("Unlisted file in container public input manifest")
        if row.get('visibility', 'public') != 'public':
            raise ProtocolError("Nonpublic container input")
        count = row.get('bytes')
        if type(count) is not int or count < 0:
            raise ProtocolError("Invalid input byte count")
        observed[released] = {'sha256': _sha(row.get('sha256')), 'bytes': count}
    if set(observed) != set(expected):
        raise ProtocolError("Released input missing from container manifest")
    entries = []
    for name, metadata in expected.items():
        path = contained(Path(public_root), name, must_exist=True)
        if not path.is_file():
            raise ProtocolError("Public input is not a regular file")
        data = path.read_bytes()
        raw = hashlib.sha256(data).hexdigest()
        if observed[name] != {'sha256': raw, 'bytes': len(data)}:
            raise ProtocolError("Released bytes do not match container input manifest")
        if metadata.get('taskview_raw_sha256', raw) != raw:
            raise ProtocolError("TaskView asset hash does not match released bytes")
        if name == 'task.json' and parse_json(data.decode('utf-8')) != view:
            raise ProtocolError("Released task bytes do not encode this TaskView")
        entries.append({**metadata, 'released_path': name,
                        'container_path': '/inputs/public/' + name,
                        'raw_sha256': raw, 'bytes': len(data)})
    return {
        'version': 1, 'identities': entries, 'taskview_canonical_json_sha256': digest(view),
        'raw_hash_scheme': 'sha256(original file bytes; no decoding or newline normalization)',
        'evidence_record_hash_scheme': 'sha256(canonical JSON serialization of record content); not a raw-file hash',
        'scope': 'Released task/assets match the controller-recorded container start input identities.',
        'limitations': [
            'Availability and identity do not prove reading, execution, or scientific correctness.',
            'This is a controller record, not an independent OS attestation.',
            'No claim about mutable solver-generated configuration at execution time.',
            'Public visibility is inherited from the released TaskView; semantic leakage requires review.'
        ]
    }
