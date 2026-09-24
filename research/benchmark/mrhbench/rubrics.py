"""Versioned DEVELOPMENT judge rules; behavior acceptance is not implied by import.

These implement AGENTS.md's agreed dimensions. Each pair specifies level 0 / 4;
shared intermediate anchors require evidence-specific justification, not counting
keywords. WRITE_CONTENT and WRITE_EVIDENCE intentionally have different rules.
"""
from .io import digest
from .scoring import DIMENSIONS

RULE_VERSION = "development-0.1"
LEVELS = {
    "0": "Absent or fundamentally invalid for this dimension; identify the actual affected requirement, not merely a style dislike.",
    "1": "Some relevant work, but major defects leave most core requirements unsupported.",
    "2": "Partially sound and useful, with material gaps or limitations affecting central requirements.",
    "3": "Sound on the core requirements; limited, localized weaknesses or explicitly bounded uncertainty remain.",
    "4": "Strong, evidence-supported fulfillment within the task scope; no material unresolved deficiency. Not perfection or positive results by definition.",
}

RULES = {
    "LIT": {
        "purpose": "Evaluate historical, source-grounded synthesis and problem positioning, not invention of a new method.",
        "dimensions": {
            "factual_citation_accuracy": ["Central claims cite nonexistent, inaccessible or contradicting sources; widespread false attribution.", "Central factual claims are supported at the cited frozen versions/locations, with uncertainty and disagreements represented faithfully."],
            "evidence_coverage": ["The response omits essentially all evidence needed to answer the supplied question.", "Covers the important approaches, findings and counterevidence needed for the question, using any valid sources rather than a closed gold bibliography."],
            "comparative_synthesis": ["Disconnected titles or misleading comparisons provide no reliable synthesis.", "Explains meaningful differences, conditions, conflicts and limitations using evidence, not citation volume or polished prose alone."],
            "gap_grounding": ["Claimed gap is refuted by supplied evidence or unrelated to the question.", "Specific useful unresolved questions follow from the reviewed evidence and bounded search scope; no unjustified global novelty assertion."],
        },
        "checks": ["Validate source identity/version/cutoff and quoted location before semantic support.", "Do not penalize an unlisted but accessible valid reference or different grounded gap.", "Historical tool restrictions do not establish absence of model-memory contamination."],
        "required_evidence_roles": ["task", "submission", "platform_trace", "reference"],
    },
    "IDEA": {
        "purpose": "Evaluate one selected proposal with hypotheses, not similarity to the source paper's idea or completion of experiments.",
        "dimensions": {
            "grounding_value": ["Proposal rests on false premises or has no meaningful relation to the supplied problem.", "Motivation and intended value follow from the supplied scientific context and explicitly bounded claims."],
            "substantive_difference": ["Merely relabels existing work while claiming novelty, or offers no meaningful distinction.", "Clearly explains a substantive difference from supplied prior work; judge only the accessible reference scope, not global novelty."],
            "specificity_coherence": ["An unimplementable slogan or internally contradictory method.", "Mechanism, key choices and intended effects are concrete and mutually consistent; legitimate implementation freedom remains."],
            "feasibility": ["Core idea cannot be assessed or implemented with the supplied resources/permissions, without acknowledging this.", "There is a credible path to testing the proposal under the given constraints, with explicit assumptions and material risks."],
            "hypothesis_quality": ["No testable core claims, circular predictions, or replacement by irrelevant easy claims.", "Hypotheses cover the proposal's central claims, specify conditions/comparators/predictions and potential challenging evidence; distinguish performance, contribution and mechanism."],
        },
        "checks": ["Do not require reproducing the reference method or predetermined positive findings.", "Assess hypotheses against the entire proposal; do not reward cherry-picking easy weak claims.", "No demand for full implementation, experiment plan or newly executed research unless task explicitly includes it."],
        "required_evidence_roles": ["task", "submission", "reference"],
    },
    "EXP": {
        "purpose": "Evaluate a whole hypothesis-to-evidence investigation; no standalone report required, and sound negative results can score highly.",
        "dimensions": {
            "test_validity": ["Experiments do not test the fixed hypotheses or silently change the method/research object.", "Faithful, informative experiments address all input hypotheses and relevant alternatives, without assuming a unique author design."],
            "rigor": ["Central comparisons are confounded, evaluation leaks or cherry-picking makes conclusions uninterpretable.", "Appropriate comparisons, data boundaries, uncertainty and selection/deviation accounting support the claimed scope; statistical ritual is not required where inapplicable."],
            "execution_credibility": ["Claimed execution has no credible basis, is contradicted, or central results are fabricated.", "Platform records and frozen code/configuration/data/artifacts consistently establish actual execution and allow key numbers to be recomputed."],
            "conclusion_credibility": ["Conclusions contradict evidence or assert support from no relevant evidence.", "Per-hypothesis conclusions, uncertainty and limits are proportional to evidence, including counterexamples or negative findings; computation and scientific inference are distinguished."],
            "resource_reasonableness": ["No informative use of resources, or clear unjustified violation of task resource constraints.", "Resources are used effectively to obtain discriminating evidence within the stated constraints, with unfinished work honestly bounded."],
        },
        "checks": ["Map every fixed hypothesis to experiments, artifacts and brief conclusions; do not grade report length.", "Inspect actual code and platform execution evidence, not solver self-reported logs alone.", "Identify absence of evidence separately from evidence of absence, and valid negative results separately from invalid experiments.", "Doing nothing and declaring everything uncertain is not automatically rigorous.", "First four dimensions alone form equal-weight scientific quality. Resource grade and measured costs cannot compensate invalid science.", "For resource compliance inspect the full platform timeline, every failed/retried attempt, and the task resource definition; final successful CPU duration is not total task wall time. Do not certify compliance when task and controller budgets conflict. A controller configuration error is infrastructure failure, not solver scientific failure; preserve diagnostic observations separately.", "Check actual analysis code, configuration history and a purposeful sample of raw measurements supporting central statistics. Summary counts and supported flags are not verification of the underlying fit or evidence. Explicitly state unchecked portions, and do not call a criterion predeclared or unchanged without checking the recorded revisions."],
        "required_evidence_roles": ["task", "submission", "platform_trace", "reference"],
    },
    "WRITE_CONTENT": {
        "purpose": "Evaluate accurate coherent research exposition from fixed scientific facts; do not demand new experiments or discoveries.",
        "dimensions": {
            "fidelity": ["Central method, attribution, numeric result or conclusion contradicts the supplied authoritative material.", "Technical content, claims, comparisons and limitations faithfully express the supplied evidence without inventing implementation, approval, findings or certainty."],
            "completeness": ["Most requested scientific content is absent or key conditions required to understand it are omitted.", "Covers the requested contribution, relevant method/assumptions/evidence and necessary qualifications within scope/length, explicitly marking missing source facts."],
            "comprehensibility": ["Contradictory or disorganized exposition prevents understanding of the core argument.", "A coherent, technically understandable argument distinguishes motivation, method, evidence and scope; formal elegance or verbosity is not a substitute."],
            "traceability": ["Central claims and citations cannot be connected to the provided research materials.", "Relevant claims, methods, attribution and reproducibility statements can be traced to exact supplied assets/locations with no fabricated provenance."],
        },
        "checks": ["Check narrative claims and technical semantics, including pseudocode when requested.", "A faithful statement of unknown details is preferable to invented reproducibility or ethics information.", "No requirement to recreate original wording, section order, visual layout or complete paper PDF.", "Use cited support, not superficial textual similarity to the source paper."],
        "required_evidence_roles": ["task", "submission", "reference"],
    },
    "WRITE_EVIDENCE": {
        "purpose": "Evaluate figures/tables and their scientific explanation from fixed numeric evidence, not generate new research results.",
        "dimensions": {
            "fidelity": ["Central values, aggregation, metric direction, uncertainty or visual encoding misrepresent the supplied data.", "Values, aggregation, labels, units and uncertainty match the actual inputs; no fabricated runs, error bars, missing-as-zero or misleading axes."],
            "completeness": ["Required evidence presentation is unusably incomplete or omits essential comparisons/definitions.", "Required panels/tables, legends, units, sample/aggregation definitions, captions and relevant missing-data qualifications are included without inventing unavailable evidence."],
            "comprehensibility": ["The artifact is unreadable or its encoding obscures the scientific comparison.", "Labels, layout and encodings make the intended comparisons understandable at the intended size; text faithfully explains them without overstating support."],
            "traceability": ["Numbers cannot be linked to input rows and the supplied generation code cannot explain the output.", "Source values, transformations, generation code and rendered outputs correspond, with reproducible key quantities and explicit provenance for reported aggregates versus raw runs."],
        },
        "checks": ["Inspect actual rendered evidence as well as code/data; successful compilation is not visual/scientific acceptance.", "Aggregated input cannot support reconstruction of nonexistent replicates or standard errors.", "Recompute quantities with trusted tools, never execute submission code inside the judge context.", "If a required image is unavailable to the judging transport, mark evidence incomplete; do not hallucinate a visual inspection."],
        "required_evidence_roles": ["task", "submission", "reference", "rendered_artifact"],
    },
}


def rubric(task_type: str) -> dict:
    rule = RULES[task_type]
    if set(rule["dimensions"]) != set(DIMENSIONS[task_type]):
        raise ValueError("Rule dimensions disagree with the scoring protocol")
    return {"version": RULE_VERSION, "task_type": task_type, "levels": LEVELS, **rule}


def rubric_hash(task_type: str) -> str:
    return digest(rubric(task_type))
