"""Versioned development-only LIT/IDEA publication; original packages unchanged.

Migration follows a separately recorded maintenance semantic inspection. It does
not grant material, historical-coverage, runtime or judge acceptance.
"""
from __future__ import annotations
import copy,json
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.io import read_json,write_json,file_hash,utc_now
from mrhbench.materials import export_task,check_task

IMAGE='sha256:399341648ce68031cef84e225a8b4985fed3125fd020ec96a8d6c5d6563036d0'
CORPUS='research/benchmark/materials/pilot_v3/literature_v3/shared_background_corpus.json'
TIME_AUDIT='research/benchmark/materials/pilot_v3/literature_v3/source_time_audit.json'
LIMITS=dict(cpus=1,memory_mb=1024,disk_mb=512,pids_limit=64,wall_seconds=600)


def content_schema(keys,task_type):
 descriptions={
 'source-grounded_synthesis':'Synthesis of relevant existing approaches and their supported findings, with no new-method requirement.',
 'evidence_and_limitations':'Evidence, assumptions, disagreements, access conditions, and limits of the literature examined.',
 'grounded_gaps':'Specific unresolved questions justified within the searched corpus; no global-novelty guarantee.',
 'claim_document_version_location_map':'Map central claims to document identities, pinned versions and supporting page/location references.',
 'selected_proposal':'One selected, concrete research proposal within the supplied setting; not a list of unexplained options.',
 'mechanism_and_assumptions':'How the proposal is intended to work, what information it needs, and its assumptions.',
 'difference_and_feasibility':'Substantive difference from the fixed supplied background and feasible testing path, with limits and risks.',
 'core_hypotheses_with_conditions_comparators_and_challenging_evidence':'A set covering central proposal claims, conditions, comparators, predictions and potential challenging evidence.'}
 return {'type':'object','required':list(keys),'properties':{k:{'type':['string','object','array'],'description':descriptions[k]} for k in keys},
         'additionalProperties':True,'description':task_type+' scientific content; prose or structured representations are allowed. The outer harness submission also carries status/artifacts/omissions.'}


def migrate(workspace):
 workspace=workspace.resolve();materials=workspace/'research/benchmark/materials';output=materials/'pilot_v3/released_stage_candidates'
 if output.exists():raise ValueError('New candidate output directory required')
 originals={str(p.relative_to(workspace)):file_hash(p) for old in ['ssa_lit','ssa_idea'] for p in (materials/old).rglob('*') if p.is_file()}
 corpus=read_json(workspace/CORPUS);rows=corpus['documents'];by_id={r['document_id']:r for r in rows}
 output.mkdir(parents=True)
 package_rows=[]
 for stage,old,new_id,mc,tc in [('lit','ssa_lit','dev-lit-r2-002',12,120),('idea','ssa_idea','dev-idea-fixed-002',6,60)]:
  origin=materials/old;root=output/stage;(root/'public').mkdir(parents=True);(root/'private').mkdir()
  task=copy.deepcopy(read_json(origin/'task.json'));setting=copy.deepcopy(read_json(origin/'public/research_setting.json'))
  evaluation=copy.deepcopy(read_json(origin/'private/evaluation.json'))
  kind=task['task_type'];task['task_id']=new_id;task['public']['task_id']=new_id
  task['public']['output_contract']=content_schema(task['public']['output_contract']['required'],kind)
  task['public']['resources']={**task['public']['resources'],'budget_status':'explicit_development_configuration_not_formally_frozen',
    'container':dict(LIMITS),'execution_budget':{'model_calls':mc,'tool_calls':tc,'wall_seconds':600},
    'gpu_allowed':False,'network':'controller_shared_corpus_only' if stage=='lit' else 'none',
    'resource_scope':'Limits govern this task execution; this is not an empirical future-experiment cost estimate.',
    'image_id':IMAGE,'platform':'linux/amd64','tool_call_metric':'controller broker API calls; direct worker CPU/file operations remain bounded by container resources, not counted as API calls'}
  task['public']['tools']=['model_client','asset.read','artifact_read_write']
  task['private']['formal_eligible']=False
  task['private']['migration_source']={'task_manifest':str((origin/'task.json').relative_to(workspace)).replace('\\','/'),'sha256':file_hash(origin/'task.json')}
  task['private']['source_time_audit']=TIME_AUDIT
  if stage=='lit':
   setting['constraints']=['No open-network browsing or corpus bypass.',
     'When comparing existing methods, distinguish source preparation from deployment; deployment has no source examples or target labels.',
     'Explain what retained source summaries a reviewed method requires, including information assumptions and storage scaling; do not prescribe a new method.']
   setting['corpus_notice']=('A shared development library of '+str(len(rows))+' pinned background papers is accessible through the controlled search/read broker. '
     'It combines multiple research neighborhoods, not a task-specific answer list. Queries are free within the library; time/version/target exclusions apply to results and reads. '
     'The library is not exhaustive and cannot establish global novelty. Raw index metadata and private relevance labels are not exposed.')
   setting['source_summary_storage']['development_rule']=('The research setting places no numerical ceiling on permitted aggregate source summaries. '
     'Compare retained statistics, storage scaling and preparation access; source examples themselves are unavailable at deployment. '
     'This scientific information-access condition does not override the task container CPU/RAM/storage/time limits.')
   task['public']['tools']+=['literature.search','literature.read','literature.read_page']
   cfg={'corpus_manifest':CORPUS,'corpus_sha256':file_hash(workspace/CORPUS),'cutoff':'2024-09-01','shared':True,
        'required_view':'SharedCorpusView','excluded_papers':['iclr2025-SXtl7NRyE5','iclr2025-QfhU3ZC2g1'],
        'excluded_aliases':['2410.03263','2410.01265'],'allowed_versions':{r['paper_id']:['arxiv-v1'] for r in rows}}
   task['private']['corpus_configuration']=cfg;evaluation['historical_service']=cfg
   evaluation['checks']=[x.replace('A valid different proposal/gap is acceptable; source SSA method and outcomes are not a gold answer.',
       'Different grounded gaps are acceptable; the target paper method and outcomes are not a unique gold answer.') for x in evaluation['checks']]
   evaluation['checks']+=['The 18-paper shared candidate library is not field-complete; do not convert a missing library paper into a solver omission.',
       'Core/background/confusable tiers are candidate maintenance labels, not a closed mandatory citation list. Appropriate comparisons to near-neighbors are not automatic errors.',
       'Evaluate the literature process from actual controller search/read receipts; a solver-authored bibliography alone does not establish retrieval or reading.']
   for identity in ['doc-2204.13263','doc-2101.10842','doc-1607.06450']:
    evaluation['read_evidence'].append({'document_id':identity,'pdf_sha256':by_id[identity]['pdf_sha256'],'support_pages':[1],
       'scope':'Original abstract/setting overview only; further specific claims require the actual supporting pages, not automatic approval.'})
   evaluation['reference_coverage_status']='candidate_partial_coverage_not_required_bibliography'
   task['public']['prompt']=('Use the controlled shared historical search/read service to map approaches relevant to the supplied research setting. '
      'Choose queries freely within this library; compare evidence, assumptions, conflicts and limitations, and identify grounded unresolved questions. '
      'Cite document identities, versions and supporting pages/locations. Do not propose a new method, claim an exhaustive global survey, or treat this bounded library as proof of global novelty.')
  else:
   task['private'].pop('corpus_configuration',None);evaluation.pop('historical_service',None)
   setting['corpus_notice']=('This IDEA task supplies a fixed report summarizing eight pinned background references. No additional search/read service is enabled in this development configuration. '
       'The report is not exhaustive and does not establish global novelty; it is independent of any LIT solver output.')
   background=copy.deepcopy(read_json(origin/'public/background_report.json'))
   background['kind']='maintainer_constructed_fixed_LIT_style_context_not_solver_output'
   background['development_access_notice']='Fixed background only; no additional corpus retrieval in this development task.'
   write_json(root/'public/background_report.json',background,exclusive=True)
   evaluation['fixed_reference_scope']={'document_ids':[x['document_id'] for x in background['evidence_summary']],
      'additional_executor_retrieval':False,'judging_boundary':'Assess substantive difference against the supplied fixed report and supportable facts; do not penalize failure to discuss unprovided new R2 references or assume access to the target paper.'}
   evaluation['checks']+=['Do not require recovering the target method, PCA/subspace construction, regression-head weighting, or any particular proposal.',
       'The fixed report is a deliberately bounded developmental starting point, not a comprehensive literature review. Missing unprovided literature is a material-coverage limitation, not by itself a solver failure.',
       'Model/tool execution budget is not evidence that a future experimental program has been measured to cost the same amount.']
   task['public']['prompt']=('From the supplied fixed background report, propose one concrete research idea for the research setting. '
      'Explain mechanism, information requirements, substantive difference, feasibility and a set of core hypotheses with potential challenging evidence. '
      'You may refine or question candidate gaps with evidence. No extra literature retrieval is available for this development task. '
      'Do not assume a unique target-paper answer or require positive findings. No full implementation, paper or experimental execution is requested.')
  evaluation['temporal_audit']=('Pinned arXiv v1 and known official repository creation metadata are recorded in '+TIME_AUDIT+
      '. Other earlier project/repository/report disclosure is not excluded; no complete historical or model-memory isolation is claimed.')
  write_json(root/'public/research_setting.json',setting,exclusive=True)
  write_json(root/'private/evaluation.json',evaluation,exclusive=True)
  for a in task['assets']:a['sha256']=file_hash(root/a['path'])
  for gate in task['gates'].values():gate['status']='pending'
  task['gates']['input_leakage']['evidence']='Maintenance inspection compared public setting/fixed background with target SSA section 3: no target-specific PCA/head-weighted subspace recipe, target formula/table/result directly supplied. This is not exhaustive semantic contamination acceptance.'
  task['gates']['source_semantics']['evidence']='Candidate migration preserves the original problem and fixed independent inputs; task-target leakage inspected, but original eight-paper summary facts were not comprehensively re-audited in this migration. Shared R2 coverage remains limited.'
  task['gates']['runtime']['evidence']='Frozen CPU dependency image exists; candidate task budget and isolated broker configuration explicitly set. No real executor trajectory on this migrated task has been accepted.'
  task['gates']['judge_behavior']['evidence']='Native task judge calibration/trajectory audit remains separate; no new model call in this migration.'
  task['gates']['rights']['evidence']='Original source cache and PDFs are service-only; blanket redistribution and derived material rights remain unapproved.'
  write_json(root/'task.json',task,exclusive=True)
  check_task(task,root,formal=False)
  release=root/'release';export_receipt=export_task(task,root,release,audience='development_executor',formal=False)
  package_rows.append({'stage':kind,'task_id':new_id,'paper_id':task['paper_id'],'full_task':str((root/'task.json').relative_to(workspace)).replace('\\','/'),
    'public_root':str(release.relative_to(workspace)).replace('\\','/'),'private_reference':str((root/'private/evaluation.json').relative_to(workspace)).replace('\\','/'),
    'task_sha256':file_hash(root/'task.json'),'released_task_sha256':file_hash(release/'task.json'),'image_id':IMAGE,'export_receipt':export_receipt,
    'execution_budget':task['public']['resources']['execution_budget'],'container':LIMITS,'formal_eligible':False})
 changed=[name for name,sha in originals.items() if file_hash(workspace/name)!=sha]
 if changed:raise ValueError('Original stage package changed')
 semantic={'reviewed':utc_now(),'review_type':'maintenance_read_and_target_method_comparison_not_formal_material_acceptance',
  'inspected_originals':originals,'target_comparison':{'source':'research/source_cache/benchmark_materials/first_snapshot/ssa-paper-v1.source',
      'sha256':file_hash(workspace/'research/source_cache/benchmark_materials/first_snapshot/ssa-paper-v1.source'),'locations':['S3.1','S3.2','Eq.5','Eq.6','Eq.7','Eq.8']},
  'observations':[{'finding':'LIT copied setting used proposal wording and only-eight-library notice.','action':'Removed proposal construction demands and replaced access notice with controlled 18-paper shared R2 search.'},
    {'finding':'IDEA fixed report provides general feature-alignment/normalization/entropy prior art and applicability caveats.','assessment':'Legitimate fixed upstream context under agreed contract; similarity of broad prior-art terms to the target approach alone is not target-answer leakage.'},
    {'finding':'No explicit target PCA top-K selection, regression-head basis weighting, target weighted symmetric KL recipe, target feature-geometry discovery, or target result table observed in public inputs.','assessment':'No direct target-answer leak found by this inspection, not a proof against implicit steering or model memory.'},
    {'finding':'IDEA old report emphasizes predetermined pitfalls and only eight early references.','remaining_risk':'Input may over-scaffold reasoning and omit relevant pre-cutoff work; scientific discrimination and coverage need separate evaluation.'},
    {'finding':'Original private evaluation does not present an original-target solution as mandatory gold.','action':'Retained broad scientific checks; removed executor corpus configuration from IDEA and made fixed-reference judging boundary explicit.'}],
  'not_done':['No new LLM call or solver/judge trajectory acceptance','No exhaustive revalidation of all prior-art summaries','No formal field coverage or source rights acceptance','No formal split/leaderboard admission','No claim that source-paper earliest public disclosure is exhaustively established'],
  'original_files_changed':changed,'public_target_method_canaries_checked':['Significant-subspace Alignment','alpha_d = 1 +','2410.03263','SXtl7NRyE5','Table 4','UTKFace'],
  'development_configuration_only':True}
 write_json(output/'migration_manifest.json',{'created':utc_now(),'candidates':package_rows,'no_upstream_solver_output_used':True,'formal_accepted':False},exclusive=True)
 write_json(workspace/'research/benchmark/audit/stage_migration_v3_semantic_review.json',semantic,exclusive=True)
 print(json.dumps(package_rows),flush=True)
 return package_rows

if __name__=='__main__':migrate(Path(__file__).resolve().parents[4])
