"""Opt-in read scheduling advice, not evidence compression or a quality gate.

For a fresh, explicitly frozen protocol only. Place around native, inside
QualityBoundRunner; the existing wrappers still publish and enforce all inputs.
This module does not implement parallel tools, prove reading, or claim savings.
"""

EVIDENCE_READ_BATCHING_GUIDANCE = """
Optional evidence-read scheduling (no change to scientific requirements):
Where the native tool interface permits multiple independent Read requests in
one assistant turn, group those requests rather than inserting a separate
reasoning turn between each. Do not invent a parallel tool or use extra model
calls. Sequential reads remain correct when parallel requests are unsupported,
dependencies require earlier results, or an output limit would truncate a batch.

First locate the published files. Independently available policy, quality
contract, both output/coverage schemas, complete public-surface inventory,
request, original review and dispute evidence can be read in small batches.
Then read the complete candidate package (including private scientific
references), actual public asset bytes, necessary original sources and related
dependencies, resolving any discovered claims or conflicts. This is a suggested
order, not a restriction on evidence or a fixed checklist replacing your review.
Read the full current policy and preserve every existing full-package check.
The package and public surface are different evidence views: neither replaces
the other, actual asset contents, private references, original review, or source
verification. Navigation locates evidence; it never certifies scientific truth.

Avoid a repeated identical read only when its earlier complete result is still
available and sufficient for the current check. Re-read whenever needed for
correctness, context loss, truncation, dependency checks, or conflict resolution.
Never skip material merely because it is unchanged, verbose, or already covered
by another role. Do not substitute summaries or Grep hits for required complete
content. Check each tool result for truncation and retrieve every missing part.
Do not batch writes with reads or speculate about files not yet published.
All original instructions, outputs, schemas and acceptance gates remain in force.
"""


class EvidenceReadBatchingRunner:
    """Append advice for independent reviewer/adjudicator; one unchanged call.

No files, role outputs, response values, exceptions or budgets are rewritten.
Constructor is deliberately unchanged. Caller decides explicit arm assignment;
enabling this only on incremental compares a process bundle, not constructor-only
causality. Any real savings and reading completeness require new trace review.
"""

    def __init__(self, inner):
        self.inner = inner

    def run(self, *, workspace, prompt, role, **kwargs):
        if role in {"material_reviewer", "adjudicator"}:
            prompt += "\n" + EVIDENCE_READ_BATCHING_GUIDANCE
        return self.inner.run(workspace=workspace, prompt=prompt, role=role, **kwargs)
