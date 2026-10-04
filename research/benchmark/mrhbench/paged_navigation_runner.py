"""Fresh-run opt-in navigation publication; does not change scientific policy."""
from pathlib import Path
import json

from .io import ProtocolError, read_json, write_json, contained, file_hash
from .incremental_repair import _safe_path
from .material_batch import _input_snapshot, _check_inputs
from .paged_source_navigation import publish_pages, verify_pages


class PagedNavigationRunner:
    def __init__(self, inner):
        self.inner = inner

    def run(self, *, workspace, prompt, role, **kwargs):
        ws = _safe_path(Path(workspace))
        request = read_json(ws / 'request.json')
        sources = {}
        for row in request['sources']:
            if row['source_id'] in sources:
                raise ProtocolError('Duplicate navigation source identity')
            sources[row['source_id']] = row
        dest = ws / 'paged_source_navigation'
        if dest.exists():
            raise ProtocolError('Fresh paged navigation directory required')
        original = ws / 'source_navigation'
        navs = sorted(original.glob('*.json')) if original.exists() else []
        rows = []
        for i, nav in enumerate(navs):
            nav = _safe_path(nav)
            info = read_json(nav)
            source = sources.get(info.get('source_id'))
            if source is None or source['sha256'] != info.get('source_sha256'):
                raise ProtocolError('Navigation not bound to published request source')
            path = _safe_path(contained(ws, source['path'], must_exist=True))
            if file_hash(path) != source['sha256']:
                raise ProtocolError('Published source bytes changed')
            target = dest / ('source-%04d' % i)
            record = {'source_id': source['source_id'], 'source_path': source['path'],
                      'original_navigation': nav.relative_to(ws).as_posix()}
            try:
                publish_pages(nav, path, target)
            except ProtocolError as exc:
                # Never hide source-binding/structure failures. Only the two
                # explicit size-limit cases have a lossless original fallback.
                if not (str(exc).startswith('Indivisible unit exceeds page bound;')
                        or str(exc).startswith('Index or metadata exceeds page bound;')):
                    raise
                if target.exists():
                    raise ProtocolError('Size fallback unexpectedly wrote partial pages') from exc
                record.update(status='use_original_size_fallback', reason=str(exc))
            else:
                checked = verify_pages(target, nav, path)
                record.update(status='paged_losslessly', index=(target/'index.json').relative_to(ws).as_posix(),
                              units=checked['units'], pages=checked['pages'])
            rows.append(record)
        catalog = {'schema_version': 'paged-navigation-catalog-1', 'sources': rows,
                   'model_read_verified': False,
                   'notice': 'Navigation only, never independent evidence or scientific approval. Original sources and navigation remain authoritative and available. Size fallback does not omit the original.'}
        raw = (json.dumps(catalog, ensure_ascii=False, indent=2)+'\n').encode('utf8')
        if len(raw) > 16000:
            raise ProtocolError('Navigation catalog exceeds read bound; no model call')
        dest.mkdir(parents=True, exist_ok=True)
        with (dest/'catalog.json').open('xb') as f:
            f.write(raw)
        protected = ['paged_source_navigation'] + (['source_navigation'] if original.exists() else [])
        before = _input_snapshot(ws, protected)
        prompt += ('\nOptional complete, lossless source navigation is indexed in '
                   'paged_source_navigation/catalog.json. Each page is at most16000 UTF-8 bytes. '
                   'Read the catalog then relevant complete pages; verify claims against the original source. '
                   'An unchanged unit or a successful paging check is NOT scientific approval. '
                   'Do not reduce full current-policy public-surface review or omit related scientific dependencies. '
                   'Explicit size fallbacks require reading the original; do not mistake them for empty evidence.\n')
        result = self.inner.run(workspace=ws, prompt=prompt, role=role, **kwargs)
        _check_inputs(ws, protected, before, role)
        write_json(ws/'paged_navigation_receipt.json', {
            'schema_version': 'paged-navigation-publication-receipt-1',
            'catalog_sha256': file_hash(dest/'catalog.json'), 'published_files': before,
            'unchanged_after_role': True, 'model_read_verified': False,
            'scientific_acceptance': False, 'role': role}, exclusive=True)
        return result
