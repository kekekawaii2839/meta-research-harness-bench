"""Construct a version-pinned, source-faithful R2 candidate corpus (maintenance).

No task-specific digest enters public search/read content. All source additions
are written once under a new directory; prior sources are hash-checked unchanged.
This script does not freeze formal task coverage, labels, or publication rights.
"""
from __future__ import annotations
import argparse,datetime,hashlib,json,re,time,urllib.request,urllib.parse
from pathlib import Path
from html.parser import HTMLParser
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.io import ProtocolError,write_json,file_hash,utc_now,read_json
from mrhbench.literature import original_abstract,SharedCorpusView,LiteratureService

# Selection provenance is PRIVATE metadata, not solver-visible corpus fields.
CANDIDATES=[
 ('1906.00232','IV','bib.bib36','core','Kernel IV generalizes 2SLS; useful causal-identification and estimation baseline distinct from Transformer endogeneity.'),
 ('1910.12358','IV','bib.bib37','core','Dual saddle-point IV offers a distinct alternative to sequential stages; compare assumptions and optimization objects.'),
 ('2208.01066','IV','bib.bib9','core','In-context simple-function learning supplies the direct linear-regression ICL setup, without resolving endogeneity.'),
 ('2211.15661','IV','bib.bib11','core','Linear-model ICL algorithm identification and ridge/GD constructions provide the closest algorithmic background.'),
 ('2212.07677','IV','bib.bib12','core','Gradient-descent interpretation is close mechanistic background but not automatically a proof of IV recovery.'),
 ('2405.19463','IV','bib.bib39','core','Streaming stochastic IV optimization offers relevant update/convergence comparisons with different oracle assumptions.'),
 ('2402.05639','IV','bib.bib40','background','Nonparametric IV stochastic gradients broaden the estimation context; not interchangeable with finite-dimensional linear coupled updates.'),
 ('2310.17086','IV','bib.bib14','confusable','Higher-order optimization explanations for linear ICL are a natural competing near-neighbor, not a false or intrinsically irrelevant citation.'),
 ('2204.13263','SSA','bib.bib1','core','Precomputed source-statistics TTA is close input-condition background; its image-classification setting still needs distinction from scalar regression.'),
 ('2303.13325','SSA','bib.bib43','confusable','Domain-adaptation regression and inverse-Gram subspaces are highly relevant neighbors but source-access assumptions differ from source-free deployment.'),
 ('2101.10842','SSA','bib.bib27','core','Source-free distributional alignment with BN statistics is directly relevant to what stored source statistics can enable.'),
 ('1607.06450','SSA','bib.bib2','background','Layer normalization supports normalization-mechanism context; it is not itself a test-time regression adaptation method.'),
]
TARGETS={
 'SSA':{'paper_id':'iclr2025-SXtl7NRyE5','arxiv_id':'2410.03263','abstract':'first_snapshot/ssa-abstract-v1.source','paper':'first_snapshot/ssa-paper-v1.source','repo':'kzkadc/regression-tta'},
 'IV':{'paper_id':'iclr2025-QfhU3ZC2g1','arxiv_id':'2410.01265','abstract':'iv_snapshot/iv-abstract-v1.source','paper':'iv_snapshot/iv-paper-v1.source','repo':'harris-liang/IVTransformer'},
}

class Metadata(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.fields={}
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='meta' and a.get('name','').startswith('citation_'):self.fields[a['name']]=a.get('content','')

def version_metadata(html,identity):
 from bs4 import BeautifulSoup
 p=Metadata();p.feed(html);m=p.fields
 if m.get('citation_arxiv_id') not in {identity,identity+'v1'}:raise ProtocolError('arXiv identity mismatch')
 if not all(m.get(k) for k in ('citation_title','citation_date','citation_abstract')):raise ProtocolError('Missing primary metadata')
 soup=BeautifulSoup(html,'html.parser');history=soup.select_one('.submission-history')
 if history is None:raise ProtocolError('Submission-history evidence missing')
 text=history.get_text(' ',strip=True)
 match=re.search(r'\[v1\]\s*([A-Za-z]{3},\s*\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d\d:\d\d:\d\d\s+UTC)',text)
 if not match:raise ProtocolError('v1 timestamp not parsed')
 stamp=datetime.datetime.strptime(match.group(1),'%a, %d %b %Y %H:%M:%S UTC').replace(tzinfo=datetime.timezone.utc)
 if m['citation_date'].replace('/','-')!=stamp.date().isoformat():raise ProtocolError('Metadata date and version timestamp disagree')
 return {'title':m['citation_title'],'abstract':m['citation_abstract'],'published_date':stamp.date().isoformat(),
         'submitted_at':stamp.isoformat(),'v1_history_locator':match.group(0),'all_submission_history_private':text}

def fetch(url,target,budget,*,max_bytes=25*1024*1024):
 if target.exists():raise ProtocolError('Refusing to overwrite source bytes')
 u=urllib.parse.urlparse(url)
 if u.scheme!='https' or u.hostname not in {'arxiv.org','api.github.com'}:raise ProtocolError('Unapproved primary source')
 row={'url':url,'fetched_at':utc_now(),'path':target.as_posix()}
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'MetaResearchHarnessSourceAudit/0.1','Accept':'application/vnd.github+json' if u.hostname=='api.github.com' else '*/*'})
  with urllib.request.urlopen(req,timeout=60) as r:
   resolved=urllib.parse.urlparse(r.url)
   if resolved.scheme!='https' or resolved.hostname not in {'arxiv.org','api.github.com'}:raise ProtocolError('Unapproved redirect')
   bound=min(max_bytes,budget[0]);data=r.read(bound+1)
   if len(data)>bound:raise ProtocolError('Download/aggregate storage bound exceeded')
   row.update(resolved_url=r.url,content_type=r.headers.get('Content-Type'),link_header=r.headers.get('Link'))
  with target.open('xb') as f:f.write(data)
  budget[0]-=len(data);row.update(status='fetched',bytes=len(data),sha256=file_hash(target))
 except Exception as e:row.update(status='failed',error=type(e).__name__+': '+str(e))
 return row

def build(workspace):
 from bs4 import BeautifulSoup
 from pypdf import PdfReader
 workspace=workspace.resolve();cache=workspace/'research/source_cache';source_root=cache/'benchmark_materials';raw=source_root/'r2_v3'
 output=workspace/'research/benchmark/materials/pilot_v3/literature_v3'
 if raw.exists() or output.exists():raise ProtocolError('New source and material candidate directories required')
 original={str(p.relative_to(workspace)):file_hash(p) for p in cache.rglob('*') if p.is_file()}
 raw.mkdir();output.mkdir()
 budget=[100*1024*1024];fetches=[];new=[];labels=[];source_rows=[];errors=[]
 refs={}
 for key,t in TARGETS.items():
  text=(source_root/t['paper']).read_text(encoding='utf8')
  soup=BeautifulSoup(text,'html.parser');refs[key]={x.get('id'):x.get_text(' ',strip=True) for x in soup.select('.ltx_bibitem')}
 for identity,scope,reference,tier,reason in CANDIDATES:
  stem='arxiv-'+identity.replace('.','-')+'-v1';abstract=raw/(stem+'-abstract.source');pdf=raw/(stem+'-paper.source')
  a=fetch('https://arxiv.org/abs/'+identity+'v1',abstract,budget,max_bytes=1024*1024);fetches.append(a)
  b=fetch('https://arxiv.org/pdf/'+identity+'v1',pdf,budget);fetches.append(b)
  if a['status']!='fetched' or b['status']!='fetched':errors.append({'id':identity,'reason':'source_fetch_failed'});continue
  try:
   m=version_metadata(abstract.read_text(encoding='utf8'),identity)
   if not pdf.read_bytes()[:5]==b'%PDF-':raise ProtocolError('PDF signature mismatch')
   reader=PdfReader(pdf);pages=[p.extract_text() or '' for p in reader.pages]
   if not pages or len(pages)>200:raise ProtocolError('Unsupported page count')
   if not any(identity+'v1' in re.sub(r'\s+','',page) for page in pages[:2]):raise ProtocolError('PDF v1 stamp missing')
   if not all(p.strip() for p in pages):raise ProtocolError('At least one PDF page has no extractable text')
   text_record={'document_id':'doc-'+identity,'source_pdf_sha256':b['sha256'],'source_version':'arxiv-v1',
                'parser':'pypdf '+__import__('pypdf').__version__,'notice':'Raw text extraction, not visually verified equations/tables; no task-directed digest',
                'pages':[{'page_number':i+1,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()} for i,text in enumerate(pages)]}
   extracted=output/(stem+'-pages.json');data=json.dumps(text_record,ensure_ascii=False,sort_keys=True).encode('utf8')
   if len(data)>budget[0]:raise ProtocolError('Aggregate source/material storage cap exceeded')
   with extracted.open('xb') as f:f.write(data)
   budget[0]-=len(data)
   row={'document_id':'doc-'+identity,'paper_id':'background-arxiv-'+identity,'paper_aliases':[identity],
        'title':m['title'],'version':'arxiv-v1','version_number':1,'published_date':m['published_date'],
        'source_url':'https://arxiv.org/pdf/'+identity+'v1','text':m['abstract'],'text_kind':'verbatim_pinned_source_abstract',
        'abstract_source_path':abstract.relative_to(workspace).as_posix(),'abstract_sha256':a['sha256'],
        'pdf_source_path':pdf.relative_to(workspace).as_posix(),'pdf_sha256':b['sha256'],
        'published_evidence':{'url':a['url'],'sha256':a['sha256'],'locator':'citation_date + '+m['v1_history_locator']},
        'disclosure_status':'verified_background_version','index_approved':True}
   # Index approved means only approved for this development candidate's machinery.
   # Coverage/rights/formal-material acceptance remain separately pending.
   assert original_abstract(row,workspace)['text']==m['abstract']
   new.append(row)
   labels.append({'candidate_scope':scope,'paper_id':row['paper_id'],'tier':tier,'status':'candidate_not_gold','rationale':reason,
                  'reference_source':str((source_root/TARGETS[scope]['paper']).relative_to(workspace)).replace('\\','/'),
                  'reference_locator':reference,'reference_text':refs[scope][reference],
                  'source_reference_sha256':file_hash(source_root/TARGETS[scope]['paper'])})
   source_rows.append({'document_id':row['document_id'],'v1_submitted_at':m['submitted_at'],'version_metadata':m,
                       'pdf_pages':len(pages),'pdf_v1_stamp_verified':True,'raw_pdf_sha256':b['sha256'],
                       'page_text_path':extracted.relative_to(workspace).as_posix(),'page_text_sha256':file_hash(extracted),
                       'extracted_abstract_matches_public_metadata':True,'rights':'license/redistribution_review_pending_service_only'})
   print(identity,'verified',len(pages),'pages',b['bytes'],'bytes',flush=True)
  except Exception as e:errors.append({'id':identity,'reason':type(e).__name__+': '+str(e)});print(identity,'REJECTED',str(e),flush=True)
 # Repository metadata is disclosure-audit evidence ONLY; never library content.
 target_audits=[]
 for key,t in TARGETS.items():
  abstract=source_root/t['abstract'];m=version_metadata(abstract.read_text(encoding='utf8'),t['arxiv_id'])
  repofile=raw/(key.lower()+'-repo-metadata.source')
  reporow=fetch('https://api.github.com/repos/'+t['repo'],repofile,budget,max_bytes=1024*1024);fetches.append(reporow)
  repo=json.loads(repofile.read_text(encoding='utf8')) if reporow['status']=='fetched' else None
  commitfile=raw/(key.lower()+'-repo-commits-first-page.source')
  commitrow=fetch('https://api.github.com/repos/'+t['repo']+'/commits?per_page=1',commitfile,budget,max_bytes=1024*1024);fetches.append(commitrow)
  commit_records=[]
  if commitrow['status']=='fetched':
   commit_records.extend(json.loads(commitfile.read_text(encoding='utf8')))
   link=commitrow.get('link_header') or '';match=re.search(r'<([^>]+)>; rel="last"',link)
   if match:
    oldestfile=raw/(key.lower()+'-repo-oldest-current-branch-commit.source')
    oldestrow=fetch(match.group(1),oldestfile,budget,max_bytes=1024*1024);fetches.append(oldestrow)
    if oldestrow['status']=='fetched':commit_records.extend(json.loads(oldestfile.read_text(encoding='utf8')))
  target_audits.append({'target':key,'paper_id':t['paper_id'],'arxiv_id':t['arxiv_id'],'arxiv_v1_submitted_at':m['submitted_at'],
        'arxiv_metadata_path':abstract.relative_to(workspace).as_posix(),'arxiv_metadata_sha256':file_hash(abstract),
        'arxiv_v1_evidence':m['v1_history_locator'],
        'repo_url':'https://github.com/'+t['repo'],'repo_metadata_path':repofile.relative_to(workspace).as_posix() if repo else None,
        'repo_created_at':repo.get('created_at') if repo else None,'repo_pushed_at':repo.get('pushed_at') if repo else None,
        'observed_commit_timestamps':[{'sha':c['sha'],'author_date':c['commit']['author']['date'],'committer_date':c['commit']['committer']['date']} for c in commit_records],
        'earliest_verified_in_this_audit':'arxiv_v1_submission_record_only_not_global_first_disclosure',
        'recommended_candidate_cutoff':'2024-09-01','cutoff_status':'conservative_existing_development_date_not_globally_verified',
        'unresolved':['arXiv submission time is not necessarily exact announcement/public availability time','Git commit author/committer times and repository creation are not proof of public access at those times','No exhaustive audit of prior project sites, forks, talks, reports or OpenReview public-release history','A repository or other disclosure earlier than arXiv has not been ruled out'],
        'exclude_aliases':[t['paper_id'],t['arxiv_id'],'https://arxiv.org/abs/'+t['arxiv_id'],'https://github.com/'+t['repo']],
        'target_content_in_background_index':False})
 seed=read_json(workspace/'research/benchmark/materials/pilot_v2/shared_background_corpus.json')
 allrows=seed['documents']+new
 if len({d['paper_id'] for d in allrows})!=len(allrows):raise ProtocolError('Duplicate background identity')
 forbidden={t['arxiv_id'] for t in TARGETS.values()}
 if any(forbidden.intersection(set(d['paper_aliases'])) for d in allrows):raise ProtocolError('Target present in candidate corpus')
 corpus={'schema_version':'shared-background-1','documents':allrows,'selection_status':'candidate_cross_package_backgrounds_from_verified_original_references',
         'coverage_status':'not_accepted_for_field_coverage','full_text':'pinned_original_PDF_pages_available',
         'version_policy':'first_arxiv_version_only_not_claiming_latest_version_before_cutoff',
         'ranking':'deterministic_lexical_abstract_baseline_not_validated_retrieval_quality','relevance_labels':'private_per_candidate_scope_not_embedded',
         'rights':'service_only_no_blanket_redistribution_permission','formal_material_accepted':False,'new_document_count':len(new),'inherited_seed_count':len(seed['documents'])}
 write_json(output/'shared_background_corpus.json',corpus,exclusive=True)
 write_json(output/'private_literature_roles_candidates.json',{'visibility':'maintainer_private_never_solver_index','status':'candidate_not_gold','labels':labels,'note':'Only selected new references are labeled; no absent/default label should be inferred. Tier is task-relative and a confusable citation is not automatically wrong.'},exclusive=True)
 write_json(output/'source_time_audit.json',{'target_audits':target_audits,'background_versions':source_rows,'candidate_cutoff':'2024-09-01','unresolved_cutoff_scope':'See each target; not a guarantee of no earlier disclosure'},exclusive=True)
 write_json(raw/'manifest.json',{'fetched':fetches,'errors':errors,'raw_source_role':'maintainer_owned_service_cache','raw_bytes_immutable_after_snapshot':True},exclusive=True)
 changed=[name for name,sha in original.items() if not (workspace/name).is_file() or file_hash(workspace/name)!=sha]
 service=LiteratureService(allrows,workspace,'2024-09-01',forbidden,shared=True)
 full_text_verified=[]
 for row in new:
  result=service.read_page(row['document_id'],1)
  if not result['text'] or result['source_sha256']!=row['pdf_sha256']:raise ProtocolError('Source service page mismatch')
  full_text_verified.append(row['document_id'])
 audit={'created':utc_now(),'new_documents':len(new),'total_documents':len(allrows),'original_files_checked':len(original),'original_files_changed':changed,
        'new_raw_bytes':sum(p.stat().st_size for p in raw.rglob('*') if p.is_file()),
        'new_material_bytes':sum(p.stat().st_size for p in output.rglob('*') if p.is_file()),
        'storage_limit_bytes':100*1024*1024,'mechanical_full_text_checks':full_text_verified,'errors':errors,'formal_accepted':False,
        'coverage_limitations':['Two seed-paper neighborhoods, not representative AI/ML research coverage','Reference-seeded acquisition has author-selection bias','No exhaustive nearest-neighbor relevance judgment','v1-only excludes legitimate intermediate updates','Target early repository/public disclosure remains only partially audited','No new formal LIT task, hidden split, expert gold, or model-based evaluation created']}
 if changed:raise ProtocolError('Original source bytes changed')
 if audit['new_raw_bytes']+audit['new_material_bytes']>100*1024*1024:raise ProtocolError('Aggregate storage cap exceeded')
 write_json(workspace/'research/benchmark/audit/shared_background_v3_construction.json',audit,exclusive=True)
 print(json.dumps(audit),flush=True)
 return audit

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[4]);a=parser.parse_args();build(a.workspace)

