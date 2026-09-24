"""Source-grounded development LIT/IDEA packages with a pinned small corpus.

Needs BeautifulSoup for metadata extraction. Digests are ORIGINAL short summaries;
full PDFs remain immutable source snapshots served locally, not bundled in task
exports. This 8-paper dev corpus is NOT claimed sufficient for a formal survey.
"""
from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import file_hash, read_json, write_json
from mrhbench.materials import check_task
from mrhbench.rubrics import rubric

# Source-grounded summaries, not verbatim abstracts. Page indices are one-based.
DIGESTS = {
    "2006.10726": ("2020-06-18", [2, 3], "The v1 study adapts a pretrained predictive model using unlabeled target inputs, without source examples. Its objective reduces predictive entropy and its adjustable components are feature-wise affine modulations. Experiments concern image/digit classification. The method discussion explicitly also allows compatible probabilistic regressors with predictive variance; therefore 'entropy adaptation is categorically impossible for regression' misstates this source. That observation does not automatically provide a distribution or useful entropy objective for a deterministic scalar regressor. Claims of benefit remain scoped to the source's evaluated settings."),
    "1909.13231": ("2019-09-29", [2, 3], "Test-time training jointly prepares a main prediction task and an auxiliary self-supervised task sharing a feature extractor. At deployment the auxiliary loss updates shared parameters using unlabeled input. Rotation prediction is the image-specific example, not a universal requirement. Standard per-instance and stateful online variants differ in whether updates are retained. The paper gives a convex-model discussion involving gradient alignment; this is not an unconditional guarantee of improvement for any auxiliary task. The preparation stage and availability of a suitable self-supervised task differ from adapting an arbitrary off-the-shelf checkpoint."),
    "2002.08546": ("2020-02-20", [3, 4], "SHOT studies source-free unsupervised domain adaptation for classification: retain the trained classifier while adapting a target feature extractor without source examples. Information maximization combines confident individual predictions with diversity across the target collection; self-supervised pseudo-label refinement is another component. Its setting is not identical to one-pass adaptation of a scalar regressor. Class probabilities, class diversity and pseudo-label definitions must be distinguished from continuous regression outputs. The source is evidence that source-free adaptation is already studied, not proof that all source-free tasks are solved."),
    "2006.16971": ("2020-06-30", [2, 3], "This study replaces source-estimated batch-normalization statistics with statistics from unlabeled corrupted target images. It evaluates classification robustness under explicit adaptation access conditions, including how many similarly corrupted examples are available together. Such access differs from an isolated query or a changing mixed stream. No new classification entropy objective is required for this statistics-based baseline. Observed gains on common-corruption benchmarks do not establish that every distribution shift or regression target benefits from moment adjustment."),
    "1607.01719": ("2016-07-06", [2, 3], "Deep CORAL penalizes differences between source and target feature covariance matrices while learning deep representations. Its training setup combines labeled source data and unlabeled target data, unlike deployment with only a source model. The covariance-matching objective gives prior art for feature-distribution alignment but does not by itself establish a source-free deployment procedure or guarantee preservation of a regression function. The paper also situates covariance matching among related distribution-alignment approaches; alignment is not a novel concept merely because used in a new proposal."),
    "1502.03167": ("2015-02-11", [3, 4], "Batch normalization normalizes activations using mini-batch statistics and learns a scale and offset per activation channel. Training and inference statistics must be distinguished. This is architectural and optimization background, not itself evidence of successful target-domain adaptation. The source attributes its training benefits to reducing internal covariate shift; a survey should distinguish that source's interpretation from an established universal explanation or a guarantee under external distribution shift."),
    "1706.04599": ("2017-06-14", [4, 5, 6], "This classification calibration study distinguishes prediction confidence from empirical correctness, reports miscalibration in modern networks, and evaluates post-processing methods such as temperature scaling. Calibration fitting uses a labeled validation set, unlike label-free target adaptation. It is useful background against equating confidence with correctness, but is not a direct experiment on adaptation of deterministic regression models. Neither calibration quality nor increased confidence alone establishes improved target regression error."),
    "1505.07818": ("2015-05-28", [1, 2, 3], "Domain-adversarial learning trains representations to support labeled-source prediction while reducing a domain classifier's ability to distinguish source and target examples. A gradient-reversal component implements the adversarial update. The study uses source examples and unlabeled target examples during training, so it is not directly a source-free test-time method. Domain indistinguishability and task-discriminative structure play different roles. This broader adaptation prior art is relevant for comparing information assumptions, not proof of feasibility under stricter deployment constraints."),
}


def build():
    cache = ROOT.parent / "source_cache/benchmark_materials/background_v1"
    records = {r["source_id"]: r for r in read_json(cache / "manifest.json")["sources"]}
    corpus = []
    for arxiv, (date, pages, summary) in DIGESTS.items():
        prefix = "background-" + arxiv.replace(".", "-") + "-v1-"
        abstract, paper = records[prefix + "abstract"], records[prefix + "paper"]
        for record in (abstract, paper):
            if record["status"] != "fetched" or file_hash(cache / record["file"]) != record["sha256"]:
                raise ValueError("Background source missing/changed")
        soup = BeautifulSoup((cache / abstract["file"]).read_text(encoding="utf8"), "html.parser")
        actual_date = soup.find("meta", attrs={"name": "citation_date"})["content"].replace("/", "-")
        if actual_date != date or "[v1]" not in soup.find(class_="submission-history").get_text():
            raise ValueError("Pinned publication metadata mismatch")
        corpus.append({"document_id": "doc-" + arxiv, "paper_id": "background-arxiv-" + arxiv,
                       "title": soup.find("meta", attrs={"name": "citation_title"})["content"],
                       "version": "arxiv-v1", "source_url": paper["url"], "published_date": date,
                       "published_evidence": {"url": abstract["url"], "sha256": abstract["sha256"], "locator": "citation_date and v1 submission-history entry"},
                       "text": summary, "text_kind": "maintainer_written_digest_not_full_paper", "support_pages": pages,
                       "pdf_source_path": (cache / paper["file"]).relative_to(ROOT.parents[1]).as_posix(), "pdf_sha256": paper["sha256"]})
    write_json(ROOT / "materials/background_corpus.json", {"schema_version": "0.1", "visibility": "service_only_not_wholesale_public_export", "documents": corpus,
        "coverage_status": "8_paper_development_corpus_insufficient_for_formal_field_coverage", "selection": "Core adaptation methods plus broader architecture/calibration/domain-alignment background; not a target-paper-only reference list", "redistribution": "Original brief digests; source PDFs retained locally for controlled reading; publication rights review pending"})
    constraints = {"task_setting": "A pretrained deterministic scalar regression model faces changed input distributions. Deployment has unlabeled target inputs and no source examples or target labels. Source preparation may retain a documented finite summary of aggregate statistics, not original source examples. Do not assume the model already provides a predictive probability distribution.",
        "development_scope": "A bounded research situation, not a recovered historical author trajectory; no target-method or target-result facts are given.",
        "cutoff": "2024-09-01", "corpus_notice": "Only eight pinned background papers are available in this development service. Bound conclusions to this library; it cannot establish global novelty or exhaustiveness.",
        "source_summary_storage": {"numeric_byte_limit": None, "development_rule": "No numerical storage ceiling is imposed in this prototype. Specify the retained statistics, dimensions/storage scaling and preparation access; do not retain original source examples. A judge must not invent an unstated size limit."},
        "constraints": ["No online browsing or corpus bypass.", "Do not use unavailable source examples or target labels in a proposed deployment step.", "A proposal may justify extra source preparation and a finite summary, but must declare its information and storage requirements explicitly."]}
    report = {
        "kind": "maintainer_constructed_reviewed_LIT_style_context_not_solver_output",
        "question": constraints["task_setting"],
        "evidence_summary": [{"document_id": d["document_id"], "version": d["version"], "summary": d["text"], "source_url": d["source_url"], "support_pages": d["support_pages"]} for d in corpus],
        "synthesis": [
            "Methods differ in source-data access, preparation needs, predictive output type and target-data access. Those differences constrain direct transplantation.",
            "The evidence does not justify equating more confidence, matched distributions or a lower auxiliary loss with better target regression error in every setting.",
            "These papers motivate investigating label-free adaptation for the specified scalar prediction setting, but do not establish that no relevant regression work exists outside this bounded library.",
        ],
        "candidate_questions_not_fixed_method": ["Which task-relevant signal can be obtained under these information constraints?", "When should an adaptation step help, fail, or leave the predictor unchanged?", "Which assumptions and measurable failure indicators would make a proposed approach testable?"],
        "not_given": ["Target paper, original novel method, target results or source-specific feature-geometry discoveries.", "An endorsed unique solution or predetermined positive outcome."],
    }
    private = {"kind": "maintainer_constructed_evaluation_context", "target_paper_id": "iclr2025-SXtl7NRyE5",
               "historical_service": {"corpus_manifest": "research/benchmark/materials/background_corpus.json", "cutoff": "2024-09-01", "excluded_papers": ["iclr2025-SXtl7NRyE5"]},
               "checks": ["Separate fully test-time, source-free DA, prepared self-supervision and source/target joint training.",
                          "Tent v1 p3 explicitly mentions compatible probabilistic regressors; no categorical claim that entropy cannot concern any regression model.",
                          "A deterministic scalar alone is not a supplied predictive distribution; extra uncertainty assumptions/preparation must be justified.",
                          "Calibration evidence is adjacent classification evidence, not a direct proof about scalar-regression adaptation.",
                          "A valid different proposal/gap is acceptable; source SSA method and outcomes are not a gold answer.",
                          "Hypotheses should cover core proposal claims and conditions; no reward for weak irrelevant claims or ungrounded universal guarantees."],
               "read_evidence": [{"document_id": d["document_id"], "pdf_sha256": d["pdf_sha256"], "support_pages": d["support_pages"]} for d in corpus],
               "temporal_audit": "ArXiv v1 metadata pinned; target earliest disclosure including project/code not yet independently established. No claim of complete historical or model-memory isolation."}
    for kind, folder, task_id in [("LIT", "ssa_lit", "dev-lit-001"), ("IDEA", "ssa_idea", "dev-idea-001")]:
        package = ROOT / "materials" / folder
        write_json(package / "public/research_setting.json", constraints)
        if kind == "IDEA":
            write_json(package / "public/background_report.json", report)
        task_private = {**private, "task_type": kind, "checks": list(private["checks"])}
        if kind == "LIT":
            task_private["checks"] = [c for c in private["checks"] if not c.startswith("Hypotheses should")]
            task_private["checks"].append("Evaluate grounded unresolved questions and literature synthesis; do not require a new proposal, method or generated hypotheses in LIT.")
        write_json(package / "private/evaluation.json", task_private)
        public_assets = [("setting", "public/research_setting.json")]
        if kind == "IDEA":
            public_assets.append(("background-report", "public/background_report.json"))
        assets = [{"asset_id": id, "path": path, "visibility": "public", "sha256": file_hash(package/path)} for id, path in public_assets]
        assets.append({"asset_id": "evaluation", "path": "private/evaluation.json", "visibility": "private", "sha256": file_hash(package/"private/evaluation.json")})
        prompt = ("Use the controlled historical search/read service to map approaches relevant to the supplied research setting. Explain evidence, assumptions, conflicts and limitations and identify grounded unresolved questions. Cite document versions and pages/locations. Do not propose a new method, claim an exhaustive global survey or treat this small library as proof of global novelty." if kind == "LIT" else
                  "From the fixed reviewed background, propose one concrete research idea for the supplied setting. Explain the mechanism, information requirements, meaningful difference, feasibility and core hypotheses with potential challenging evidence. You may refine or question the candidate gaps with evidence. Do not assume a unique target-paper answer or require positive findings. No full implementation, paper or experimental execution is requested.")
        outputs = (["source-grounded_synthesis", "evidence_and_limitations", "grounded_gaps", "claim_document_version_location_map"] if kind == "LIT" else ["selected_proposal", "mechanism_and_assumptions", "difference_and_feasibility", "core_hypotheses_with_conditions_comparators_and_challenging_evidence"])
        task = {"schema_version": "0.1", "task_id": task_id, "task_type": kind, "paper_id": "iclr2025-SXtl7NRyE5", "split": "development",
                "public": {"task_id": task_id, "task_type": kind, "prompt": prompt, "inputs": [id for id,_ in public_assets],
                           "output_contract": {"required": outputs}, "resources": {"gpu_allowed": False, "network": "controlled_corpus_only", "cutoff": "2024-09-01", "budget_status": "development_prototype_not_formal_frozen_budget"},
                           "tools": ["model_client", "literature.search", "literature.read", "literature.read_page"], "public_rubric": rubric(kind)},
                "private": {"evidence_asset_ids": ["evaluation"], "formal_eligible": False, "corpus_configuration": private["historical_service"]}, "assets": assets,
                "gates": {"source_semantics": {"status": "pending", "evidence": "Eight primary sources inspected at listed pages and metadata. Small corpus is not yet sufficient for formal coverage; background report still requires independent input audit."},
                          "rights": {"status": "pending", "evidence": "Original brief summaries in public inputs; full source PDFs local/service-only. Corpus and asset redistribution review not complete."},
                          "input_leakage": {"status": "pending", "evidence": "Target source/method/results absent from task inputs and excluded in service. Earliest disclosure audit, sandbox bypass prevention and independent semantic audit incomplete."},
                          "runtime": {"status": "pending", "evidence": "Pinned local corpus and search/read prototype; actual model/tool execution and isolated runtime still need acceptance."},
                          "judge_behavior": {"status": "pending", "evidence": "No task-specific model trajectory acceptance yet."}}}
        check_task(task, package)
        write_json(package / "task.json", task)
        print(task_id, "development only; corpus/rights/temporal/judge gates remain pending")


if __name__ == "__main__":
    build()
