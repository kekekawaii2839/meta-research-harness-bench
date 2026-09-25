"""Private historical retrieval diagnostic; never changes tasks or quality scores."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from pypdf import PdfReader

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.io import ProtocolError, contained, file_hash, read_json, write_json
from mrhbench.literature import retrieval_diagnostics
from mrhbench.retrieval_observations import extract_retrieval_observations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--review', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    corpus = root/'research/benchmark/materials/pilot_v3/literature_v3/shared_background_corpus.json'
    documents = read_json(corpus)['documents']
    view = read_json(args.stage/'public/task.json')
    public_hashes = {row['sha256'] for row in view['asset_manifest']}
    for asset in view['asset_manifest']:
        if file_hash(contained(args.stage/'public', asset['path'], must_exist=True)) != asset['sha256']:
            raise ProtocolError('Historical public asset changed')
    roles, reviews = {}, []
    for path in args.review:
        review = read_json(path)
        if review['visibility'] != 'maintainer_private_never_solver_index':
            raise ProtocolError('Only private source-reviewed labels are accepted')
        if review['task_binding']['research_setting_sha256'] not in public_hashes:
            raise ProtocolError('Historical task does not contain the reviewed research setting')
        checks = []
        for label in review['labels']:
            paper = label['paper_id']
            if paper in roles:
                raise ProtocolError('Duplicate or conflicting reviewed paper')
            matches = [d for d in documents if d['document_id'] == label['document_id']]
            if len(matches) != 1 or matches[0]['paper_id'] != paper or matches[0]['version'] != label['version']:
                raise ProtocolError('Reviewed identity does not match pinned corpus')
            source = root/label['pdf_source_path']
            if file_hash(source) != label['pdf_sha256'] or matches[0]['pdf_sha256'] != label['pdf_sha256']:
                raise ProtocolError('Reviewed PDF identity changed')
            pdf = PdfReader(source)
            words = 0
            for location in label['evidence']:
                page = re.sub(r'\s+', ' ', pdf.pages[location['pdf_page_1based']-1].extract_text()).strip()
                if hashlib.sha256(page.encode()).hexdigest() != location['normalized_page_sha256']:
                    raise ProtocolError('Reviewed page extraction changed')
                if page[location['start_char']:location['end_char']] != location['quote']:
                    raise ProtocolError('Incorrect source locator')
                words += len(location['quote'].split())
            if words > 25:
                raise ProtocolError('Source quote allowance exceeded')
            # 'unrelated' is an explicitly source-reviewed no-role label (no penalty), not an unknown paper.
            if label['proposed_tier'] not in {'core', 'background', 'confusable', 'unrelated'}:
                raise ProtocolError('Do not turn unknown labels into a negative category')
            roles[paper] = label['proposed_tier']
            checks.append({'paper_id': paper, 'source_and_locators_verified': True})
        reviews.append({'path': str(path), 'sha256': file_hash(path), 'checks': checks})
    broker = args.stage/'execution/broker'
    paths = sorted(broker.glob('rpc-*.json'))
    submission_path = args.stage/'execution/submission.json'
    observations = extract_retrieval_observations(
        rows=[read_json(p) for p in paths], submission=read_json(submission_path), documents=documents)
    stages = observations['stages']
    diagnostic = retrieval_diagnostics(
        retrieved=[x['document_id'] for x in stages['returned']],
        read=[x['document_id'] for k in ('abstract_read', 'page_read') for x in stages[k]],
        adopted=[x['document_id'] for x in stages['adopted']],
        documents=documents, private_roles=roles)
    # Root reviews the proposed taxonomy separately. These descriptive diagnostics
    # neither promote it to gold nor assert semantic support for adopted citations.
    result = {'version': 1, 'visibility': 'maintainer_private_never_solver_index',
              'status': 'historical_development_diagnostic_not_quality_score',
              'stage': str(args.stage), 'corpus_sha256': file_hash(corpus),
              'public_task_sha256': file_hash(args.stage/'public/task.json'),
              'submission_sha256': file_hash(submission_path), 'source_reviews': reviews,
              'broker_inputs': [{'file': p.name, 'sha256': file_hash(p)} for p in paths],
              'private_candidate_roles': roles, 'observations': observations,
              'paper_level_descriptive_counts': diagnostic,
              'read_union_definition': 'Successful abstract OR page receipt, not full-paper reading.',
              'primary_score': None,
              'limitations': ['Labels remain task-relative diagnostic candidates, not mandatory citations.',
                             'Unknown papers are not negative examples.',
                             'RPC success is delivery at the broker boundary, not proof of comprehension.',
                             'Submission-declared adoption does not prove citation support.',
                             'Historical task budgets may differ; shared research-setting byte identity is checked.',
                             'No original task, grade, raw paper, or trajectory is changed.']}
    write_json(args.output, result, exclusive=True)
    print(args.output)


if __name__ == '__main__':
    main()
