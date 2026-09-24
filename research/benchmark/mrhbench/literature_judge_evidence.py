"""Judge-only pinned full-text evidence from the SAME allowed R2 view.

This is reference availability, never evidence the executor read a paper. Page
text is not a rendered-figure/equation check. No source PDFs are publicly bundled.
"""
from __future__ import annotations
import copy,json
from .io import ProtocolError
from .judge_runner import evidence_record
from .literature import LiteratureService,SharedCorpusView,original_abstract


def _judge_service(service):
    if not isinstance(service,LiteratureService) or not isinstance(service.corpus,SharedCorpusView):
        raise ProtocolError('Judge literature evidence requires the actual shared task view')
    # Preserve its exact date/version/alias policy; do NOT synthesize a new cutoff.
    # Keep judge preloading out of the executor retrieval/reading receipts.
    clone=copy.copy(service);clone.trace=None;clone._readers={}
    return clone


def literature_page_record(service, document_id, page_number):
    """One complete raw extracted page, private reference with source binding."""
    svc=_judge_service(service)
    svc.corpus.read(document_id)  # policy before any file access
    original_abstract(svc.records[document_id],svc.workspace)  # immutable metadata too
    page=svc.read_page(document_id,page_number)  # verifies PDF bytes + bounds
    metadata={k:v for k,v in page.items() if k!='text'}
    content=json.dumps(metadata,ensure_ascii=False,sort_keys=True)+'\n'+page['text']
    return evidence_record(f'lit-page-{document_id}-{page["version"]}-{page_number}',
                           'reference',content,visibility='private')


def build_literature_judge_evidence(service, *, max_documents=1000, max_total_chars=25_000_000, allow_incomplete=False):
    """Index + one paginatable record per allowed paper, fail-closed by default.

    The native EvidenceSession reads records in bounded line ranges. The index
    maps original PDF page numbers to exact one-based text line ranges and
    zero-based Python string character ranges (exclusive end). No local
    relevance labels or private task answer facts enter these source records.
    A caller may persist the returned records outside solver releases and append
    them to its judge evidence list; this does not increase executor read counts.
    Development-only allow_incomplete reports Unicode extraction failures with
    original PDF identity/page and uncertainty, never replaces malformed text.
    """
    if any(isinstance(n,bool) or not isinstance(n,int) or n<1 for n in [max_documents,max_total_chars]):
        raise ProtocolError('Positive explicit judge source limits required')
    svc=_judge_service(service);ids=sorted(svc.corpus.docs)
    if len(ids)>max_documents:raise ProtocolError('Judge source document cap exceeded; nothing truncated')
    records=[];index=[];total=0;unavailable=[]
    for identity in ids:
        allowed=svc.corpus.read(identity)
        verified=original_abstract(svc.records[identity],svc.workspace)
        if verified['text']!=allowed['text']:raise ProtocolError('Allowed abstract differs from pinned original')
        first=svc.read_page(identity,1)
        metadata={'document_id':identity,'title':allowed['title'],'version':allowed['version'],
                  'published_date':allowed['published_date'],'source_url':first['source_url'],
                  'source_sha256':first['source_sha256'],'page_count':first['page_count'],
                  'provenance':'controller_preloaded_judge_reference_not_executor_read',
                  'extraction_notice':first['extraction_notice']}
        content=json.dumps(metadata,ensure_ascii=False,sort_keys=True)+'\n'
        ranges=[]
        for n in range(1,first['page_count']+1):
            try:page=first if n==1 else svc.read_page(identity,n)
            except UnicodeError as exc:
                # An explicitly reported extraction failure is not source text.
                # Never catch integrity/policy errors, which must fail closed.
                if not allow_incomplete:raise
                failure={'document_id':identity,'version':metadata['version'],'source_sha256':metadata['source_sha256'],
                         'source_url':metadata['source_url'],'pdf_page_number':n,'status':'unavailable_extraction_error','error_type':type(exc).__name__,
                         'required_next_step':'Render the pinned original PDF page to verify a critical claim; otherwise mark evidence uncertain.'}
                notice=json.dumps(failure,sort_keys=True)
                located={**failure,'start_line':len(content.splitlines())+1,
                         'end_line':len(content.splitlines())+1,
                         'start_char':len(content),'end_char':len(content)+len(notice),
                         'range_content':'unavailable_page_notice_not_original_source_text'}
                unavailable.append(located);ranges.append(located)
                content+=notice+'\n'
                continue
            if page['source_sha256']!=metadata['source_sha256'] or page['version']!=metadata['version']:
                raise ProtocolError('Source version changed during judge evidence construction')
            marker=json.dumps({'pdf_page_number':n,'page_text_hash':page['page_text_hash']},sort_keys=True)
            content+=marker+'\n'
            start=len(content.splitlines())+1
            start_char=len(content)
            content+=page['text']
            end_char=len(content)
            end=len(content.splitlines())
            if not content.endswith('\n'):content+='\n'
            ranges.append({'pdf_page_number':n,'start_line':start,'end_line':end,
                           'start_char':start_char,'end_char':end_char,
                           'range_content':'original_extracted_page_text','page_text_hash':page['page_text_hash']})
        total+=len(content)
        if total>max_total_chars:raise ProtocolError('Judge source text cap exceeded; nothing truncated')
        eid=f'lit-full-{identity}-{allowed["version"]}'
        row=evidence_record(eid,'reference',content,visibility='private');records.append(row)
        index.append({**metadata,'evidence_id':eid,'evidence_sha256':row['sha256'],'pages':ranges})
    contents=json.dumps({'index_schema_version':'3',
                         'character_offsets':'0-based Python Unicode string indices, end_char exclusive; not UTF-8 byte offsets. Use evidence_read(start_char=start_char,max_chars=end_char-start_char), splitting into permitted-size chunks when needed.',
                         'scope':'Pinned text from the same allowed historical shared view; not evidence of solver reading or field-complete coverage. Explicit unavailable pages are not verified text.',
                         'documents':index,'document_count':len(index),'total_source_text_chars':total,
                         'complete_text_extraction':not unavailable,'unavailable_pages':unavailable,
                         'visual_equation_verification':False},ensure_ascii=False,indent=2)
    if total+len(contents)>max_total_chars:raise ProtocolError('Judge index plus source text cap exceeded; nothing truncated')
    return [evidence_record('lit-source-index','reference',contents,visibility='private'),*records]
