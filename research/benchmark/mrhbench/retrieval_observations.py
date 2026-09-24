"""Descriptive literature exposure from controller RPC receipts, never a score.

Callers must supply authentic controller-owned RPC rows and the fixed task corpus.
This module does not authenticate arbitrary JSON or reapply historical access policy.
"""
from .io import ProtocolError, digest


def extract_retrieval_observations(*, rows, submission, documents):
    if not isinstance(rows, list) or not isinstance(documents, list) or not isinstance(submission, dict):
        raise ProtocolError('Expected structured RPC rows, submission and fixed corpus documents')
    corpus = {}
    for doc in documents:
        if not isinstance(doc, dict): raise ProtocolError('Invalid fixed document')
        did, version = doc.get('document_id'), doc.get('version')
        if not isinstance(did, str) or not did or not isinstance(version, str) or not version:
            raise ProtocolError('Fixed document requires explicit identity/version')
        versions = corpus.setdefault(did, {})
        if version in versions: raise ProtocolError('Duplicate fixed document/version')
        versions[version] = doc
    events = []
    invalid = []
    failures = []
    seen = set()

    def reject(reason, provenance, item=None):
        row = {'reason': reason, **provenance}
        if isinstance(item, dict):
            row.update(document_id=item.get('document_id'), version=item.get('version'))
        invalid.append(row)

    def identity(item, provenance, *, infer_version=False):
        if not isinstance(item, dict):
            reject('malformed_document_record', provenance); return None
        did, version = item.get('document_id'), item.get('version')
        if not isinstance(did, str) or did not in corpus:
            reject('unknown_or_missing_document_id', provenance, item); return None
        source = 'explicit'
        if 'version' not in item and infer_version:
            if len(corpus[did]) != 1:
                reject('ambiguous_missing_page_version', provenance, item); return None
            version = next(iter(corpus[did])); source = 'fixed_corpus_unique_version'
        if not isinstance(version, str) or version not in corpus[did]:
            reject('unknown_mismatched_or_missing_version', provenance, item); return None
        return {'document_id': did, 'version': version, 'version_source': source}

    names = {'literature.search': 'returned', 'literature.read': 'abstract_read',
             'literature.read_page': 'page_read'}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            reject('malformed_rpc_row', {'row_index': index}); continue
        request = row.get('request')
        if not isinstance(request, dict) or request.get('operation') != 'tool': continue
        wrapper = request.get('arguments')
        if not isinstance(wrapper, dict) or wrapper.get('name') not in names: continue
        name = wrapper['name']; sequence = request.get('sequence')
        provenance = {'row_index': index, 'sequence': sequence, 'tool': name,
                      'rpc_record_content_sha256': digest(row)}
        response = row.get('response')
        if type(sequence) is not int or sequence < 0 or sequence in seen:
            reject('invalid_or_duplicate_sequence', provenance); continue
        seen.add(sequence)
        if not isinstance(response, dict) or response.get('sequence') != sequence or type(response.get('sequence')) is not int:
            reject('response_sequence_mismatch', provenance); continue
        if response.get('ok') is False:
            failures.append({**provenance, 'error': response.get('error'), 'counted_as_read': False}); continue
        if response.get('ok') is not True:
            reject('missing_success_boolean', provenance); continue
        args = wrapper.get('arguments')
        if not isinstance(args, dict):
            reject('malformed_tool_arguments', provenance); continue
        value = response.get('value')
        if name == 'literature.search':
            if not isinstance(value, list):
                reject('malformed_search_result', provenance); continue
            for hit_index, item in enumerate(value):
                source = {**provenance, 'hit_index': hit_index}
                ident = identity(item, source)
                if ident: events.append({'stage':'returned', **ident, **source, 'trust':'controller_success_receipt'})
            continue
        ident = identity(value, provenance, infer_version=name=='literature.read_page')
        if not ident: continue
        if args.get('document_id') != ident['document_id']:
            reject('request_response_document_mismatch', provenance, value); continue
        if 'version' in args and args['version'] != ident['version']:
            reject('request_response_version_mismatch', provenance, value); continue
        if not isinstance(value.get('text'), str):
            reject('missing_read_text', provenance, value); continue
        extra = {}
        if name == 'literature.read_page':
            page = value.get('page_number')
            if type(page) is not int or page < 1 or type(args.get('page_number')) is not int or args['page_number'] != page:
                reject('invalid_or_mismatched_page', provenance, value); continue
            fixed = corpus[ident['document_id']][ident['version']]
            if 'source_sha256' in value and 'pdf_sha256' in fixed and value['source_sha256'] != fixed['pdf_sha256']:
                reject('page_source_hash_mismatch', provenance, value); continue
            if 'page_text_hash' in value and value['page_text_hash'] != digest(value['text']):
                reject('page_text_hash_mismatch', provenance, value); continue
            extra['page_number'] = page
        events.append({'stage':names[name], **ident, **provenance, **extra,
                       'trust':'controller_success_receipt'})

    content = submission.get('content', submission)
    mapping = content.get('claim_document_version_location_map', []) if isinstance(content, dict) else None
    if not isinstance(mapping, list):
        reject('malformed_explicit_adoption_map', {'stage':'adopted'})
    else:
        for index, item in enumerate(mapping):
            source = {'stage':'adopted', 'claim_map_index':index,
                      'submission_content_sha256':digest(submission)}
            ident = identity(item, source)
            if not ident: continue
            if not isinstance(item.get('location'), str) or not item['location'].strip() or not isinstance(item.get('claim'), str) or not item['claim'].strip():
                reject('missing_explicit_claim_or_location', source, item); continue
            events.append({**source, **ident, 'location':item['location'],
                           'trust':'submission-declared_not_semantically_verified'})
    stages = {}
    for stage in ('returned', 'abstract_read', 'page_read', 'adopted'):
        pairs = sorted({(e['document_id'],e['version']) for e in events if e['stage']==stage})
        stages[stage] = [{'document_id':d,'version':v} for d,v in pairs]
    return {'version':1, 'stages':stages, 'events':events, 'failed_calls':failures, 'invalid':invalid,
            'counts':{key:len(value) for key,value in stages.items()}, 'primary_score':None,
            'scope':'Unique document-version identities per stage; repeated calls/claims remain in events.',
            'limitations':[
                'RPC success establishes broker delivery to the harness, not forwarding into a model context or comprehension.',
                'Abstract reads are not full-paper reads; search snippets are not abstract-read receipts.',
                'Adopted identities come only from explicit submission claims; support, relevance and location validity need semantic review.',
                'Caller must provide controller-owned receipts and the applicable fixed corpus; this is not an authenticity or access-policy verifier.'
            ]}
