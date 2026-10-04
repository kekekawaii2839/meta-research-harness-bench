"""Opt-in explanation of existing decision/coverage rules, not a repair layer.

Freeze this module with a new experiment. Historical prompts are unchanged.
The wrapper never reads, rewrites, retries or approves a model's output.
"""
from .io import ProtocolError


DECISION_GUIDANCE = """
Decision/coverage consistency (existing controller contract, not a new science rule):
Before submitting, reconcile your final decision with all six quality_coverage checks.
Any retained issue OR unknown makes pass, pass_partial and pass_with_pending_runtime
invalid, including an issue described as minor or nonblocking in narrative findings.
Do not relabel an unresolved issue clear merely to obtain a pass. If you reject an
allegation on substantive evidence, explain that reasoning and record the actual
resulting assessment; otherwise retain it and choose an allowed non-pass decision.
A reviewer uses decision=revise or reject as warranted; an adjudicator uses an action
allowed by its current round/schema (repair only when permitted, otherwise drop).
Do not invent another round or change the output schema to avoid this restriction.
An independently verified current release subset needs a new bound inventory; a
pass_partial label cannot hide an issue in the inventory you actually reviewed.
This consistency check is not a substitute for source-based independent scientific
review, and it does not make a retained scientific allegation true automatically.
""".strip()


class DecisionGuidanceRunner:
    def __init__(self, inner):
        self.inner = inner

    def run(self, *, workspace, prompt, role, **kwargs):
        if role not in {"constructor", "material_reviewer", "adjudicator"}:
            raise ProtocolError("Unsupported material decision-guidance role")
        if role != "constructor":
            prompt += "\n\n" + DECISION_GUIDANCE + "\n"
        return self.inner.run(workspace=workspace, prompt=prompt, role=role, **kwargs)
