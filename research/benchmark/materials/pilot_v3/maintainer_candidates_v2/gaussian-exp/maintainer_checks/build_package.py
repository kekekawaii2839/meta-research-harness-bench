"""Maintainer-only builder for the gaussian-exp development candidate (repair round v2).

v2 applies the root-adjudicated repairs R1-R8 of
research/benchmark/audit/gaussian_exp_independent_review_v1.json to the v1
package (maintainer_candidates_v1/gaussian-exp, kept unchanged as history).

Writes private/reference.json and task.json (with asset hashes) from the
hand-authored assets. Not a released asset; no model calls; no network.
Run with any Python >= 3.10 from anywhere:  python build_package.py
Refuses to overwrite existing outputs.
"""
import hashlib
import json
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
WS = PKG.parents[5]  # workspace root (meta-research-harness-bench)
SRC = "research/source_cache/benchmark_materials/"
TASK_ID = "gaussian-onestep-hermite-alpha-exp-maint-v2"
PREDECESSOR = "research/benchmark/materials/pilot_v3/maintainer_candidates_v1/gaussian-exp"
REVIEW = "research/benchmark/audit/gaussian_exp_independent_review_v1.json"
REPAIR_AUDIT = "research/benchmark/audit/gaussian_exp_candidate_repair_v2.json"
PAPER_ID = "iclr2025-tNn6Hskmti"

SOURCES = [
    ("gaussian-mixtures-paper-v1", SRC + "gaussian_prescreen_v1/gaussian-mixtures-paper-v1.source",
     "paper_html", "https://arxiv.org/html/2503.00856v1", "arxiv-v1"),
    ("gaussian-mixtures-abstract-v1", SRC + "gaussian_prescreen_v1/gaussian-mixtures-abstract-v1.source",
     "version_and_license_metadata", "https://arxiv.org/abs/2503.00856v1", "arxiv-v1-page-retrieval-snapshot"),
    ("gaussian-mixtures-fig1b-notebook", SRC + "gaussian_code_prescreen_v1/gaussian-mixtures-fig1b-notebook.source",
     "author_analysis_notebook_private_only",
     "https://raw.githubusercontent.com/KU-MLIP/2-Layer-NNs-with-Gaussian-Mixtures-Data/257bcd539ab3adef9aeae9d78604f681ea204017/Fig1b-alpha.ipynb",
     "257bcd539ab3adef9aeae9d78604f681ea204017"),
    ("gaussian-mixtures-license", SRC + "gaussian_code_prescreen_v1/gaussian-mixtures-license.source",
     "repository_license",
     "https://raw.githubusercontent.com/KU-MLIP/2-Layer-NNs-with-Gaussian-Mixtures-Data/257bcd539ab3adef9aeae9d78604f681ea204017/LICENSE",
     "257bcd539ab3adef9aeae9d78604f681ea204017"),
    ("gaussian-mixtures-pinned-tree", SRC + "gaussian_tree_prescreen_v1/gaussian-mixtures-pinned-tree.source",
     "repository_tree_metadata",
     "https://api.github.com/repos/KU-MLIP/2-Layer-NNs-with-Gaussian-Mixtures-Data/git/trees/2e1c1c1739f2c0057ea3dcdd2d576efdf58289af?recursive=1",
     "257bcd539ab3adef9aeae9d78604f681ea204017"),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


H = {sid: sha(WS / p) for sid, p, *_ in SOURCES}
PAPER, NB, LIC = "gaussian-mixtures-paper-v1", "gaussian-mixtures-fig1b-notebook", "gaussian-mixtures-license"
ADJ = "research/benchmark/audit/gaussian_adjudication_cpu_feasibility_v1.json"
CONTRACT = "research/benchmark/audit/gaussian_source_contract_review_v1.json"


def ev(source_id, locator):
    return {"source_id": source_id, "source_sha256": H[source_id], "locator": locator}


INPUT_FACTS = [
    {"fact_id": "F_SETTING", "kind": "source_fact", "discloses_target_contribution": False,
     "statement": "Two-layer model k^{-1/2} w^T sigma(F x); one gradient step on F with w fixed at initialization using a first-stage sample, then a ridge readout for w on a new independent sample.",
     "evidence": [ev(PAPER, "Section 2, Eq1, Eq3-Eq5 (HTML S2.E1, S2.E3-S2.E5), 'Training procedure' paragraph")]},
    {"fact_id": "F_METRIC", "kind": "source_fact", "discloses_target_contribution": False,
     "statement": "Generalization error is the expected full squared error of the trained model on unseen data (no factor 1/2).",
     "evidence": [ev(PAPER, "Section 2, Eq7 (HTML S2.E7)")]},
    {"fact_id": "F_SCALING", "kind": "source_fact", "discloses_target_contribution": False,
     "statement": "Strength beta and weighting alpha in [0,1]: eta*||Sigma|| of order n^beta, ||Sigma|| of order n^{beta(1-alpha)}, eta of order n^{beta alpha} (orders only).",
     "evidence": [ev(PAPER, "Section 2, 'Scalings of data spread and learning rate' paragraph; Section 4 (A.2)")]},
    {"fact_id": "F_DATA", "kind": "source_fact", "discloses_target_contribution": False,
     "statement": "Zero-mean mixture components with equal traces, finite-rank-plus-identity covariances; ||xi|| = C/||Sigma^{1/2}||; F rows N(0, I/Tr(Sigma)), w ~ N(0, I/k); b = sqrt(n/Tr(Sigma)); probabilists' Hermite expansion of sigma with h_j = E[He_j(z) sigma(bz)].",
     "evidence": [ev(PAPER, "Section 4 (A.3)-(A.6), Eq9, (A.8) Eq10")]},
    {"fact_id": "F_HERMITE", "kind": "source_fact", "discloses_target_contribution": True,
     "statement": "Theorem (equivalence): for (l-2)/(l-1) < beta < (l-1)/l, sigma_hat_l(x) = sum_{j=0}^{l-1} h_j/j! He_j(x/b) + h*_l z with h*_l = sqrt(E[sigma(bz)^2] - sum_{j<l} h_j^2/j!), substituted AFTER first-layer training; training and (under A.9) generalization errors converge to the same values asymptotically. The resulting model is called the Hermite model.",
     "evidence": [ev(PAPER, "Section 5, Theorem 4, Eq16-Eq17 (HTML Thmtheorem4, S5.E16)")]},
    {"fact_id": "F_CONSTANTS", "kind": "source_fact", "discloses_target_contribution": False,
     "statement": "Concrete constants fixed by this task: theta = n^{beta(1-alpha)} for both components, eta = n^{beta alpha}, ||xi|| = 1/sqrt(||Sigma||) (C=1), beta = 3/4 - 0.01 = 0.74, lambda = 1e-4, rank-one spikes, two components with weights 0.5, n=m=k=1000, ReLU teacher without label noise.",
     "evidence": [ev(NB, "cells[8] n, m, lambd, delta=0 (no label noise); cells[9] generate_data_structure; cells[13] beta, eta, k=m; cells[5] data_generator"),
                  ev(PAPER, "Section 5 Figure 1 caption (HTML S5.F1): n=m=1000, C=2, d1=d2=1, rho=0.5, lambda=1e-4, ReLU labels")]},
    {"fact_id": "M_DEGREE", "kind": "maintainer_scope", "discloses_target_contribution": False,
     "statement": "Maximum degree D=3 with theorem index l=D+1=4, satisfying the theorem condition 2/3 < 0.74 < 3/4.",
     "private_note": "Notebook code index l=3 keeps coefficients 0..3 and the residual after degree 3; it corresponds to D=3 / theorem l=4 (not a public index).",
     "evidence": [ev(NB, "cells[10], cells[11], cells[13] l=3"), ev(PAPER, "Theorem 4 condition, Eq16")],
     "adjudication": ADJ + "#hermite_degree_index_l"},
    {"fact_id": "M_NOISE", "kind": "maintainer_scope", "discloses_target_contribution": False,
     "statement": "Residual Gaussian drawn independently per hidden unit and per sample, fresh for train and test features; the task's fixed interpretation (the theorem writes a single scalar Gaussian).",
     "private_note": "Interpretation consistent with the authors' notebook (cells[10] randn(*x.shape) per call).",
     "evidence": [ev(NB, "cells[10] act_func uses randn(*x.shape) each call"), ev(PAPER, "Eq16")],
     "adjudication": ADJ + "#hermite_replacement_timing_and_noise"},
    {"fact_id": "M_SAMPLING", "kind": "maintainer_scope", "discloses_target_contribution": False,
     "statement": "Primary data model is independent per-sample component assignment; an exactly-half (stratified) draw is available only as a declared 'stratified' variant.",
     "private_note": "Independent assignment is the literal Eq2 model; the authors' notebook draws exactly half per component (cells[5]).",
     "evidence": [ev(PAPER, "Eq2"), ev(NB, "cells[5] m//2 per component")],
     "adjudication": ADJ + "#mixture_sampling_stratified_vs_iid"},
    {"fact_id": "M_SCOPE", "kind": "maintainer_scope", "discloses_target_contribution": False,
     "statement": "Finite-size CPU study at n=m=k=1000, beta=0.74, alpha in [0,1], three activations; no asymptotic proof, no other beta, no other data distributions, spike structures or real data.", "evidence": []},
]
for f in INPUT_FACTS:
    f["allowed_stages"] = ["EXP"]

HYPOTHESIS_DISCLOSURES = [
    {"fact_id": "HD_ALPHA_TREND", "kind": "hypothesis_disclosure", "allowed_stages": ["EXP"], "discloses_target_contribution": True,
     "statement": "Published in task.md only as untested hypothesis H3: increasing alpha (strength shifted from data spread to first-layer learning rate) worsens the NN model's generalization performance for each activation, with the Hermite model in the same direction, to be assessed on a solver-justified basis comparable across alpha. No source value, figure evidence or interpretation is disclosed.",
     "private_counterpart": "R_ALPHA_TREND",
     "evidence": [ev(PAPER, "Section 6, paragraph 'High data spread instead of high learning rate' (HTML S6.SS0.SSS0.Px2.p1.1)")]},
    {"fact_id": "HD_AGREEMENT", "kind": "hypothesis_disclosure", "allowed_stages": ["EXP"], "discloses_target_contribution": True,
     "statement": "Published in task.md only as untested hypotheses H1/H2: the Hermite model's held-out error agrees with the NN model's at the finite primary size across alpha and activations. The asymptotic equivalence statement itself is the public fact F_HERMITE; no finite-size source evidence is disclosed.",
     "private_counterpart": "R_AGREEMENT",
     "evidence": [ev(PAPER, "Section 5 Theorem 4; Section 6 closing sentence of 'Properties of Gaussian mixture' discussion")]},
]

PRIVATE_FACTS = [
    {"fact_id": "R_ALPHA_TREND", "kind": "source_result", "allowed_stages": [], "discloses_target_contribution": True,
     "statement": "PRIVATE part only (the direction is public as hypothesis HD_ALPHA_TREND/H3): the paper's reported evidence for the alpha trend (Figure 1(b) curves at beta=3/4^-, k/m=1, plotted, per the authors' notebook, as half the empirical test MSE on an absolute scale) and its interpretation that data-structure strength is more beneficial than first-layer learning-rate strength. The paper's trend is on an absolute error scale that, under the fixed C normalisation, is entangled with the alpha-dependent label scale; the paper's plotted values were not extracted.",
     "evidence": [ev(PAPER, "Section 6, paragraph 'High data spread instead of high learning rate' (HTML S6.SS0.SSS0.Px2.p1.1); Figure 1(b) (HTML S5.F1)")]},
    {"fact_id": "R_AGREEMENT", "kind": "source_result", "allowed_stages": [], "discloses_target_contribution": True,
     "statement": "PRIVATE part only (agreement is public as hypotheses HD_AGREEMENT/H1-H2): the paper's reported evidence that across Figures 1 and 2 the neural network's generalization errors align closely with the equivalent Hermite model, including Figure 1(b) curves for ReLU/tanh/sigmoid against alpha. Plotted values were NOT extracted (figure is an image) and no pixel-level verification was done.",
     "evidence": [ev(PAPER, "Section 6 closing sentence of 'Properties of Gaussian mixture' discussion; Figure 1 caption (HTML S5.F1)")]},
    {"fact_id": "R_FIG1_CAPTION", "kind": "source_result", "allowed_stages": [], "discloses_target_contribution": True,
     "statement": "Figure 1 caption: 20 Monte Carlo simulations; maximum Hermite degree limited to l=5 for numerical stability. The notebook for panel (b) uses code l=3 (degree 3, theorem l=4); the caption's 'l=5' is an unresolved caption/notation discrepancy, not used to override D=3.",
     "evidence": [ev(PAPER, "Figure 1 caption (HTML S5.F1)"), ev(NB, "cells[13] l=3")],
     "adjudication": ADJ + "#hermite_degree_index_l"},
    {"fact_id": "S_NOTEBOOK_DESIGN", "kind": "source_result", "allowed_stages": [], "discloses_target_contribution": True,
     "statement": "Notebook design: alpha = linspace(0,1,20); 20 trials per alpha that redraw F, w and surrogate noise while the structure and the three samples are drawn once per alpha (repeats are conditional on fixed data; alpha points not paired on data); test sample 5m; stratified exactly-half component sampling; plotted 'generalization error' is half the empirical test MSE; saved backend output 'gpu'. Author code was not executed by maintainers. This is a source design, not a required solver recipe, and must not be called an author bug.",
     "evidence": [ev(NB, "cells[2] seed, cells[5], cells[6] loss_calc, cells[13] loops, cells[15] plotting")],
     "adjudication": ADJ + "#repeat_unit_fixed_data_per_alpha; #generalization_metric_mse_vs_half_mse"},
    {"fact_id": "U_EQ6", "kind": "unknown", "allowed_stages": [], "discloses_target_contribution": False,
     "statement": "Printed Eq6 training error sums without 1/m while Eq5 averages; the task uses the normalized Eq5 objective as training metric. Author intent for Eq6 not determined.",
     "evidence": [ev(PAPER, "Eq5, Eq6 (HTML S2.E5, S2.E6)")],
     "adjudication": ADJ + "#training_objective_normalization_eq5_vs_eq6"},
    {"fact_id": "U_ASSUMPTIONS", "kind": "maintainer_scope", "allowed_stages": [], "discloses_target_contribution": False,
     "statement": "ReLU does not literally satisfy A.8 (bounded derivatives); generalization equivalence also needs A.9 (Appendix B, not audited). Finite n=1000 results cannot verify or refute the asymptotic theorem.",
     "evidence": [ev(PAPER, "Section 4 (A.8); Theorem 4 (ii)")],
     "adjudication": ADJ + "#activation_assumption_A8_relu"},
    {"fact_id": "U_DISCLOSURE", "kind": "unknown", "allowed_stages": [], "discloses_target_contribution": False,
     "statement": "Earliest disclosure not verified (arXiv v1 2025-03-02 does not exclude earlier review/project disclosure); arXiv v1 not asserted byte-equal to the ICLR camera-ready.",
     "evidence": [ev("gaussian-mixtures-abstract-v1", "arXiv v1 version metadata")]},
    {"fact_id": "M_RIGHTS", "kind": "maintainer_scope", "allowed_stages": [], "discloses_target_contribution": False,
     "statement": "Repository MIT license (copyright 2025 KU-MLIP) recorded as provenance; arXiv paper license is a non-exclusive distribution license, not open redistribution. No repository code or paper text is released; rights review of newly authored assets pending.",
     "evidence": [ev(LIC, "full text"), ev("gaussian-mixtures-abstract-v1", "license link on arXiv abstract page")]},
    {"fact_id": "M_PROVENANCE", "kind": "maintainer_scope", "allowed_stages": [], "discloses_target_contribution": False,
     "statement": "Provenance moved out of the public NOTICE in v2 (review R2): the data model, one-step first-layer update, ridge readout and held-out error follow Sections 2 and 4 of arXiv 2503.00856v1 (HTML v1), restated in new wording and notation; concrete constants that the paper fixes only as orders of growth follow the authors' public repository KU-MLIP/2-Layer-NNs-with-Gaussian-Mixtures-Data at pinned commit 257bcd539ab3adef9aeae9d78604f681ea204017 (MIT, copyright 2025 KU-MLIP). No repository code is copied or released; no repository output is used as a verified result. Implementation differences: NumPy instead of JAX; spike directions drawn as normalized Gaussian vectors (same law of g g^T as the repository's QR draw); ||Sigma|| in closed form; independent per-sample component assignment (the repository draws exactly half per component; exposed only as the declared 'stratified' variant). Attribution to be restored in public release metadata after rights review.",
     "evidence": [ev(PAPER, "Sections 2 and 4"), ev(LIC, "full text"), ev("gaussian-mixtures-pinned-tree", "pinned tree listing")]},
    {"fact_id": "S_RESOURCE_EXTRAPOLATION", "kind": "maintainer_scope", "allowed_stages": [], "discloses_target_contribution": False,
     "statement": "Removed from the public resource rationale in v2 (review R3): the v1 constructor extrapolated a source-scale sweep of the notebook design (2400 fits) to ~866 s (545-1130 s) of compute from the measured per-fit timing; not re-derived by the reviewer. The per-fit timing was measured with a 5m test set.",
     "evidence": [ev(NB, "cells[13] loops")]},
]

MAINTAINER_OBSERVATIONS = {
    "status": "sanity_values_not_findings",
    "source": "maintainer_checks/verify_starter.py in container; outputs D:/mrhbench-local-pilot/gaussian-exp-candidate-20260924-001/run3_export.json (run1/run2 identical on shared replicates)",
    "scope": "ORIGINAL-activation NN model only, 3 replicates x alpha in {0, 0.5263, 1}, fresh structure/samples/weights per replicate, test 5m. No Hermite model run for this package.",
    "observations": [
        "Label scale depends strongly on alpha under the C=1 teacher normalization: empirical test label second moment ~0.006-0.007 at alpha=0, ~0.072-0.074 at alpha=0.526, ~0.32-0.33 at alpha=1 (approximately xi^T Sigma xi / 2, i.e. about 1/(2||Sigma||), since xi^T Sigma xi * ||Sigma|| is about 1; v2 corrects the v1 factor-2 error flagged as review R5).",
        "Absolute NN test MSE rose with alpha for all three activations (e.g. ReLU ~0.0036-0.0040, ~0.047-0.052, ~0.189-0.192), consistent in direction with the paper's statement, but the MSE divided by test label variance showed no clear monotone trend (ReLU ~0.79-0.96, ~0.93-1.00, ~0.81-0.88; ranges overlap with 3 replicates).",
        "tanh readout (no bias) test MSE exceeded the test label variance at every tested alpha (ratio ~1.38-1.53); sigmoid (~0.71-0.82) and ReLU were below it. Sanity only.",
    ],
    "reviewer_observation": "Independent reviewer container spot-check (review v1 finding R1): over 200 seeds median E[y^2] 0.0064 (alpha=0), 0.066 (alpha=0.5), 0.331 (alpha=1), about 52x; NN MSE / E[y^2] 0.29-1.06 with no consistent alpha direction in 2 reps x 3 alphas. Sanity values, not findings.",
    "judge_use": "Not a gold answer and never to be disclosed. v2 H3 requires a solver-justified comparison basis across alpha; the judge must not treat any particular normalisation (or the maintainer's normalised observation above) as the expected answer or the required basis. A justified basis with any direction of result (worse, not worse, non-monotone, activation-dependent) is acceptable. H3 evaluated from absolute Eq7 errors alone, without a justified comparable basis, does not count as testing H3 (the absolute increase is largely fixed by the alpha-dependent label scale and would be reproduced by a trivial predictor).",
}

JUDGE_CHECKS = {
    "method_fidelity": [
        "Surrogate uses degree 0..3 probabilists' Hermite He_j(u/b) with coefficients h_j/j!, h_j = E[He_j(z) sigma(bz)], b = sqrt(n/Tr(Sigma)) = sqrt(n/(n+theta)).",
        "Residual term h*_4 * zeta present, h*_4 computed from E[sigma(bz)^2] minus sum_{j<=3} h_j^2/j!; zeta independent per hidden unit and per sample, fresh for readout-training and test features.",
        "F_hat computed once with the ORIGINAL activation and derivative; Hermite and NN models share structure, F, w, first-stage sample, F_hat, readout-training sample and test inputs within a replicate.",
        "Readout ridge uses lambda=1e-4 with normal equation (Phi Phi^T + lambda m I) w = Phi y; primary n=m=k=1000, beta=0.74, three activations, independent first-stage/readout/test samples.",
        "Primary metric is full empirical test MSE; any half-MSE use must be declared.",
        "Quadrature/integration accuracy declared and checked (e.g., compare with a second method or node count).",
    ],
    "rigor_and_conclusions": [
        "Replicate unit and estimand declared (which random sources vary); uncertainty statements refer to that estimand.",
        "Agreement criterion declared with sensitivity; if chosen after seeing results, disclosed.",
        "Finite-size observations kept separate from asymptotic theorem claims; ReLU/A.8 caveat acknowledged where relevant.",
        "H3 is assessed on an explicitly named comparison basis that the solver justifies as comparable across alpha (the label scale changes with alpha under the fixed C=1 teacher normalisation); an increase of absolute G_err alone does NOT count as testing H3 and supports at most 'untested' or 'inconclusive' for H3. Absolute G_err must still be reported. No specific normalisation is required; judge the justification, not agreement with a maintainer choice.",
        "The justified basis should be checked against trivial references where relevant (e.g. whether the claimed trend would also be produced by a predictor that ignores the inputs); this is an example of a check, not a mandatory recipe.",
        "H3 interpretation respects that alpha jointly changes eta, theta, ||Sigma||, Tr(Sigma), b and teacher scale; no single-factor causal claim without evidence.",
        "Failures/exclusions preserved; no fabricated intervals.",
    ],
    "acceptable_outcomes": [
        "H1/H2 supported, partially supported (e.g. degraded agreement in some alpha sub-range or activation), or not supported, if backed by paired evidence at the primary size.",
        "H3 supported, not supported, non-monotone, activation-dependent or inconclusive, if assessed on a justified basis comparable across alpha and consistent with the recorded rows. An absolute-MSE increase alone, even with a qualified interpretation, is NOT an acceptable test of H3.",
        "Smaller alpha grids or fewer replicates than the source design are acceptable when uncertainty is stated honestly; the source's 20x20 design is not required.",
    ],
    "invalidating_or_serious_defects": [
        "Hermite model without the residual noise term, with wrong degree/normalization, or used during first-layer training (changes the method).",
        "Unpaired comparison (different F_hat or data between models) presented as paired agreement evidence.",
        "Reusing the first-stage sample for the readout, or joint training of both layers.",
        "Primary conclusions only from shrunken sizes presented as n=1000 results, or claiming the theorem is proved/refuted.",
        "Reported numbers not traceable to executed code and recorded rows.",
        "H3 declared supported (or not supported) solely from absolute G_err across alpha without a justified comparable basis: H3 counts as not validly tested (test_validity/conclusion_credibility for H3), affecting H3 judgments only, not H1/H2.",
    ],
}

reference = {
    "schema_version": "maintainer-exp-reference-1",
    "construction": "maintainer_constructed_candidate",
    "construction_note": "Constructed by a maintainer-side Claude Code collaborator (material_pipeline) from adjudicated sources; not produced by a construction model (construction-model choice pending with the user). Not a gold answer; negative or qualified results remain acceptable. v2 = one explicit maintainer repair round of v1 per root adjudication of the independent review; v1 is kept unchanged as history.",
    "formal_accepted": False,
    "paper_id": PAPER_ID,
    "task_id": TASK_ID,
    "adjudication_inputs": [ADJ, CONTRACT, "research/benchmark/audit/gaussian_fulltext_prescreen_v1.json",
                            "research/benchmark/audit/material_candidates_root_review_v2.json"],
    "input_facts_with_evidence": INPUT_FACTS,
    "hypothesis_disclosures": HYPOTHESIS_DISCLOSURES,
    "predecessor": {"package": PREDECESSOR, "task_id": "gaussian-onestep-hermite-alpha-exp-maint-v1",
                    "review": REVIEW, "repair_audit": REPAIR_AUDIT},
    "private_facts": PRIVATE_FACTS,
    "maintainer_observations": MAINTAINER_OBSERVATIONS,
    "judge_checks": JUDGE_CHECKS,
    "private_source_ids": [s[0] for s in SOURCES],
    "source_manifest": [{"source_id": sid, "path": p, "role": role, "sha256": H[sid], "url": url, "version": ver}
                        for sid, p, role, url, ver in SOURCES],
    "verification_plan": {
        "deterministic": ["Validate JSON/JSONL structure, IDs, linkage, constants and aggregate arithmetic; recompute theta, eta, b, Hermite coefficients and h*; rerun selected seeds.",
                          "Inspect code for surrogate definition, residual noise semantics, first-layer training with original activation, pairing and independent samples."],
        "evidence_based": ["Assess H1-H3 coverage at the primary size, declared agreement criterion and estimand, finite vs asymptotic separation, H3 assessed on a justified basis comparable across alpha (not absolute error alone), joint-parameterization caveat for alpha, failures preserved."],
        "status": "planned_not_completed"},
}

GENERIC_RUBRIC_FROM = PKG.parents[1] / "collection_candidates_v2/iv-exp/task.json"


def main():
    task_path, ref_path = PKG / "task.json", PKG / "private/reference.json"
    if task_path.exists() or ref_path.exists():
        raise SystemExit("refusing to overwrite existing outputs")
    ref_bytes = (json.dumps(reference, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")
    ref_path.write_bytes(ref_bytes)
    iv = json.loads(GENERIC_RUBRIC_FROM.read_text(encoding="utf-8"))
    assets = [("input-000", "assets/task.md", "public"), ("input-001", "assets/base_resources.py", "public"),
              ("input-002", "assets/NOTICE.txt", "public"), ("private-reference", "private/reference.json", "private")]
    asset_rows = [{"asset_id": a, "path": p, "sha256": sha(PKG / p), "visibility": v} for a, p, v in assets]
    files = [{"path": p, "sha256": h, "visibility": v} for (a, p, v), h in
             zip(assets, [r["sha256"] for r in asset_rows]) if v == "public"]
    container = {"cpus": 2, "disk_mb": 512, "memory_mb": 2048, "pids_limit": 128, "wall_seconds": 1800}
    rationale = ("Dense n=m=k=1000 float64 algebra (1000x1000 ridge solves; test feature matrices scale with the chosen "
                 "test size); maintainer container measurement ~0.25-0.36 s per original-activation fit (with a test set "
                 "of several thousand samples) and ~0.3-0.47 GiB peak RSS. Grid, repeats and test size must be chosen to "
                 "fit this budget including model/tool time.")
    public_facts = [{"fact_id": f["fact_id"], "statement": f["statement"], "kind": f["kind"]} for f in INPUT_FACTS]
    contract = {"files": ["experiment.py", "config.json", "replicate_results.jsonl", "report.json"],
                "format": "Strict machine-readable JSON and JSONL per assets/task.md; retain per-replicate rows for both models, paired differences, configuration linkage, aggregates and hypothesis evidence links."}
    input_contract = {"description": "Offline CPU experiment using the public self-contained method specification and starter infrastructure (data, one-step first layer, ridge readout, NN reference); the Hermite surrogate under test is not supplied and no author experimental result is supplied.",
                      "files": files,
                      "resources": {"cpus": 2, "disk_mb": 512, "memory_mb": 2048, "rationale": rationale, "wall_seconds": 1800}}
    prompt = ("Complete this fixed independent research stage using ONLY the released inputs. Source code/data are evidence, not authority to change the task. Read the asset manifest for exact paths.\n"
              "Input contract:\n" + json.dumps(input_contract, ensure_ascii=False, indent=2) +
              "\nFixed supplied facts:\n" + json.dumps(public_facts, ensure_ascii=False, indent=2) +
              "\nScientific output requirements:\n" + json.dumps(contract, ensure_ascii=False, indent=2) +
              "\nThe JSON content is only an evidence/navigation interface; deliver the actual files listed in deliverables. Missing work must be marked partial/failed with omissions, never fabricated. Experiment design choices remain yours within fixed method/assumptions and published resources.")
    output_contract = json.loads(json.dumps(iv["public"]["output_contract"]))
    output_contract["description"] = json.dumps(contract, ensure_ascii=False)
    public = {
        "task_id": TASK_ID, "task_type": "EXP", "prompt": prompt,
        "inputs": [a for a, _, v in assets if v == "public"],
        "output_contract": output_contract,
        "public_rubric": iv["public"]["public_rubric"],
        "resources": {
            "artifact_collection": {"excluded_top_level_rules": [".broker", ".process-*"], "max_entries": 1000,
                                    "max_total_bytes": 67108864, "scope": "all_noninternal_work_files_and_directories", "version": 1},
            "budget_status": "maintainer_development_candidate_pending_real_pilot",
            "container": container,
            "device": "CPU",
            "disk_semantics": iv["public"]["resources"]["disk_semantics"],
            "execution_budget": {"model_calls": 16, "tool_calls": 120, "wall_seconds": 1800},
            "gpu_allowed": False,
            "image_id": "sha256:92e6b0ef5cb3a149905fa097ae1d1ae3dd907cd19c796e057d3564d8a8fcfe01",
            "network": "none"},
        "tools": iv["public"]["tools"],
    }
    pending = "Maintainer-constructed development candidate; %s not certified"
    task = {
        "schema_version": "0.1", "task_id": TASK_ID, "task_type": "EXP", "paper_id": PAPER_ID, "split": "development",
        "assets": asset_rows,
        "gates": {g: {"status": "pending", "evidence": pending % g} for g in
                  ("input_leakage", "judge_behavior", "rights", "runtime", "source_semantics")},
        "private": {"construction": "maintainer_constructed_candidate", "controller_compilation": False,
                    "evidence_asset_ids": ["private-reference"], "formal_eligible": False,
                    "construction_audit": "research/benchmark/audit/gaussian_exp_candidate_construction_v1.json",
                    "repair_audit": REPAIR_AUDIT, "predecessor_task_id": "gaussian-onestep-hermite-alpha-exp-maint-v1",
                    "source_disclosure_note": "Method intentionally disclosed for EXP. v2 removes explicit paper/arXiv/repository identifiers from public assets (provenance private in reference.json M_PROVENANCE), but the paper remains inferable from the equations and setting; metadata masking is not a contamination guarantee. LIT/IDEA must never receive this package."},
        "public": public,
    }
    task_path.write_bytes((json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    print(json.dumps({"task_sha256": sha(task_path), "assets": asset_rows}, indent=1))


if __name__ == "__main__":
    main()
