"""Metadata-only, cached pilot collection. Never executes upstream research code.

Default: offline normalization and deterministic sampling of cached conference data.
--fetch: also retrieve official conference JSON and selected repository metadata/readmes.
"""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / 'research/source_cache/iclr2025_pilot'
OUT = pathlib.Path(__file__).resolve().parent / 'iclr2025_pilot'
SOURCE = 'https://iclr.cc/static/virtual/data/iclr-2025-orals-posters.json'
VENUE = 'https://openreview.net/group?id=ICLR.cc/2025/Conference'
SEED = 'iclr2025-material-pilot-v1'
REPO = re.compile(r'https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)')


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def fetch(url, path):
    """Cache exact bytes plus source and hash; don't overwrite an existing snapshot."""
    if not path.exists():
        req = urllib.request.Request(url, headers={'User-Agent': 'ResearchMaterialPilot/0.1'})
        with urllib.request.urlopen(req, timeout=35) as response:
            data = response.read()
            resolved = response.url
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        save(path.with_suffix(path.suffix + '.provenance.json'), {
            'url': url, 'resolved_url': resolved,
            'retrieved_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        time.sleep(0.25)
    return path.read_bytes()


def repository_links(event):
    found = {}
    for field in ['url', 'abstract']:
        for match in REPO.finditer(event.get(field) or ''):
            owner, repo = match.groups()
            repo = repo.rstrip('.')
            if repo.endswith('.git'):
                repo = repo[:-4]
            if owner.lower() in {'features', 'topics', 'collections', 'orgs', 'settings'}:
                continue
            key = (owner + '/' + repo).lower()
            found.setdefault(key, {'url': 'https://github.com/' + owner + '/' + repo,
                                   'slug': owner + '/' + repo, 'evidence_fields': []})
            found[key]['evidence_fields'].append(field)
    return list(found.values())


def normalize(data):
    rows, excluded = {}, collections.Counter()
    source_hash = hashlib.sha256((CACHE / 'iclr-2025-orals-posters.json').read_bytes()).hexdigest()
    for event in data['results']:
        if event.get('sourceurl') != VENUE:
            excluded['non_main_conference_source'] += 1
            continue
        if not event.get('decision', '').startswith('Accept'):
            excluded['not_accept'] += 1
            continue
        # Official schedule contains separate oral events with negative sourceid
        # and synthetic "2025-Oral--..." forum IDs, not additional submissions.
        if event.get('sourceid', 0) <= 0:
            excluded['nonpositive_sourceid_presentation_duplicate'] += 1
            continue
        parsed = urllib.parse.urlparse(event.get('paper_url') or '')
        forum = urllib.parse.parse_qs(parsed.query).get('id', [None])[0]
        if parsed.netloc != 'openreview.net' or not forum:
            excluded['missing_openreview_forum'] += 1
            continue
        if forum in rows:
            excluded['duplicate_forum'] += 1
            continue
        rows[forum] = {
            'project_id': 'iclr2025-' + forum, 'forum_id': forum,
            'conference_submission_number': event['sourceid'], 'title': event['name'],
            'topic': event.get('topic') or 'Unknown',
            'topic_group': (event.get('topic') or 'Unknown').split('->')[0],
            'decision': event['decision'], 'openreview_url': event['paper_url'],
            'conference_url': 'https://iclr.cc' + event['virtualsite_url'],
            'project_url': event.get('url'), 'repository_candidates': repository_links(event),
            'source_event_id': event['id'], 'source_url': SOURCE,
            'source_sha256': source_hash,
            'reviews_status': 'not_fetched_api_challenge', 'review_score': None,
            'abstract': event.get('abstract'),
            'split': 'design_pilot_unassigned', 'family_dedup_status': 'not_audited',
            'runtime_verified': False, 'task_status': 'not_constructed',
        }
    return sorted(rows.values(), key=lambda r: r['forum_id']), dict(excluded)


def sample(rows, n=30):
    groups = collections.defaultdict(list)
    for row in rows:
        if row['repository_candidates']:
            groups[row['topic_group']].append(row)
    for group in groups.values():
        group.sort(key=lambda r: hashlib.sha256((SEED + ':' + r['forum_id']).encode()).hexdigest())
    result = []
    while len(result) < n and any(groups.values()):
        for key in sorted(groups):
            if groups[key] and len(result) < n:
                result.append(dict(groups[key].pop(0)))
    return result


def inspect_repo(candidate, network):
    slug = candidate['slug']
    prefix = CACHE / 'repos' / slug.replace('/', '__')
    metadata_path = prefix / 'repo.json'
    result = {**candidate, 'link_status': 'linked_from_conference_record_not_manually_authenticated',
              'runtime_verified': False, 'license_review_status': 'not_reviewed'}
    try:
        if network:
            fetch('https://api.github.com/repos/' + slug, metadata_path)
        if not metadata_path.exists():
            result['fetch_status'] = 'not_fetched'
            return result
        meta = json.loads(metadata_path.read_bytes())
        result.update({'fetch_status': 'metadata_fetched', 'canonical_slug': meta['full_name'],
                       'default_branch': meta['default_branch'], 'archived': meta['archived'],
                       'license_spdx': (meta.get('license') or {}).get('spdx_id'),
                       'pushed_at': meta.get('pushed_at'), 'size_kb': meta.get('size'),
                       'description': meta.get('description'), 'homepage': meta.get('homepage')})
        readme = prefix / 'README.txt'
        if network and not readme.exists():
            for name in ['README.md', 'readme.md', 'README.rst', 'README']:
                url = 'https://raw.githubusercontent.com/' + meta['full_name'] + '/' + meta['default_branch'] + '/' + name
                try:
                    fetch(url, readme)
                    break
                except urllib.error.HTTPError as error:
                    if error.code != 404:
                        raise
        result['readme_downloaded'] = readme.exists()
        result['snapshot_status'] = 'mutable_branch_readme_hashed_not_commit_pinned'
        if readme.exists():
            text = readme.read_text(encoding='utf-8', errors='replace')
            # Lexical hints only; not evidence of runnable experiments or full datasets.
            result['readme_lexical_hints'] = {k: bool(re.search(pattern, text, re.I)) for k, pattern in {
                'setup': r'pip install|conda|installation|requirements',
                'training': r'train', 'evaluation': r'eval|benchmark',
                'data': r'dataset|download', 'checkpoint': r'checkpoint|pretrained|pre-trained',
                'compute': r'GPU|CUDA|A100|H100|RTX|CPU',
            }.items()}
    except Exception as error:
        result['fetch_status'] = 'error'
        result['error'] = str(error)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    path = CACHE / 'iclr-2025-orals-posters.json'
    if args.fetch:
        fetch(SOURCE, path)
    data = json.loads(path.read_bytes())
    rows, excluded = normalize(data)
    selected = sample(rows)
    for index, row in enumerate(selected):
        # Don't silently choose one when multiple repositories are linked.
        row['repositories'] = [inspect_repo(c, args.fetch) for c in row['repository_candidates']]
        print(index + 1, row['title'], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'candidate_index.jsonl').open('w', encoding='utf-8') as handle:
        for row in rows:
            # Avoid republishing abstracts and author information in the index.
            handle.write(json.dumps({k: v for k, v in row.items() if k != 'abstract'}, ensure_ascii=False) + '\n')
    save(OUT / 'pilot30.json', [{k: v for k, v in row.items() if k != 'abstract'} for row in selected])
    with (OUT / 'pilot30.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['project_id','title','topic_group','decision','openreview_url','repository_urls','license_spdx','readme_downloaded','review_score','runtime_verified'])
        writer.writeheader()
        for row in selected:
            flat = {k: row.get(k) for k in writer.fieldnames}
            flat['repository_urls'] = '; '.join(r['url'] for r in row['repositories'])
            flat['license_spdx'] = '; '.join(str(r.get('license_spdx')) for r in row['repositories'])
            flat['readme_downloaded'] = '; '.join(str(r.get('readme_downloaded', False)) for r in row['repositories'])
            writer.writerow(flat)
    summary = {'source_url': SOURCE, 'source_count_field': data.get('count'), 'events_received': len(data['results']),
               'excluded': excluded, 'normalized_candidates': len(rows),
               'github_linked_candidates': sum(bool(r['repository_candidates']) for r in rows),
               'seed': SEED, 'sampling': 'round_robin_topic_group_then_sha256_seed_forum_not_population_representative',
               'pilot_projects': len(selected), 'pilot_topic_counts': dict(collections.Counter(r['topic_group'] for r in selected)),
               'repo_status': dict(collections.Counter(r['fetch_status'] for row in selected for r in row['repositories'])),
               'readmes_downloaded': sum(r.get('readme_downloaded', False) for row in selected for r in row['repositories']),
               'runtime_verified_projects': 0, 'review_scores_fetched': 0,
               'limitations': ['Official schedule snapshot is not a certified final accepted-paper census.',
                              'GitHub link extraction misses project websites, PDF-only links and other hosts.',
                              'Source-linked repository is not necessarily complete, licensed or runnable.',
                              'Current branch is not the original paper-time commit.',
                              'OpenReview API returned ChallengeRequiredError; no review scores inferred.']}
    save(OUT / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
