# WRITE_CONTENT task: results passage on the FTCT architecture comparison (Table 1, N = 5, M = 3)

Status: development candidate, pending independent review.

## Goal

Write a self-contained **results subsection** for a research paper. It should report
and interpret a published architecture comparison on the synthetic FTCT task
("Fragmented at Training, Chained at Testing"): five GPT-2-like Transformer
configurations and two MLPs, all trained on FTCT with causal depth N = 5 and child
chain length M = 3.

This is a writing task. Do not train, run or replicate anything. Every scientific
statement must come from the fixed facts provided below. Your passage is **not**
compared for similarity against any reference text. Reviewers judge it on accuracy,
support, calibration, coverage and clarity.

**Scope boundary.** This is a results passage, not a methods section. The fact
sheets give the task, data, metric and model definitions you need to set up the
comparison in a few sentences. You are not asked for a reproducible methodology.
Details the fact sheets do not give (for example training steps, batch size, seeds,
the shot count used in the table, or which MLP window was chosen) must not be
invented. Say that they are unreported where that matters.

## Public inputs (all paths relative to the task root)

| File | Content |
|---|---|
| `assets/write_content/task.md` | this specification |
| `assets/common/facts_core.json` | fact IDs FTCT-F01..F09 (task, data, metrics, implementation), FTCT-R01 (Table 1 values), FTCT-R07 (shot-count context), FTCT-U01..U05 (unstated or ambiguous details), FTCT-S01..S03 (scope and reporting rules) |
| `assets/write_content/facts_author_findings.json` | FTCT-R02..R06: the authors' readings and interpretations of Table 1, restated in maintainer wording |
| `assets/common/ftct_table1_values.csv` | the 7 × 6 table values, as printed, plus reported parameter counts |
| `assets/common/ftct_table1_manifest.json` | column definitions, units, per-cell source locators, condition notes |
| `assets/common/table1_reader.py` | optional stdlib-only loader and validator (no plotting) |
| `assets/common/SOURCE_NOTICE.md` | attribution and pending-rights notice |

You do not get the original paper. Locators in the fact sheets are provenance
references for reviewers.

## What the passage must do (fixed requirements)

1. **Setting.** State the task and comparison conditions: N = 5, M = 3, the model
   rows, and that each row is shown at its **optimal CoT shot count** (FTCT-F07).
   Do not state a specific shot count for Table 1. The source does not give one
   (FTCT-U02, FTCT-R07).
2. **Metrics.** Define the six criteria well enough for a reader: validation loss,
   training and testing vertices accuracy, training and testing values accuracy, and
   whole chain accuracy. Say which are in-distribution and which are compositional.
   Do not treat loss and accuracies as one scale.
3. **Findings.** Report what the table shows for (a) Transformer depth and head
   count, and (b) Transformers vs MLPs. Cover both vertex-order and value-deduction
   ability. Every number you cite must match the printed value (3 decimals, or the
   printed parameter string such as `48M`).
4. **Attribution.** Present FTCT-R02..R06 as the **authors'** readings and
   interpretations. Keep separate (i) what the Table 1 numbers show, (ii) what the
   authors infer, and (iii) what rests on evidence from other settings or theory
   (FTCT-R03 mechanism evidence uses a different setting; FTCT-R06 is an existence
   result). Where an author statement fits the numbers only partially, say so
   accurately. Do not suppress or exaggerate it. Words such as "significant" in the
   author findings are descriptive, not statistical.
5. **Limitations.** You must cover all of the following:
   - unstated aggregation and repeats (FTCT-U01);
   - optimal-shot post-selection with an unstated rule and shot count (FTCT-U02);
   - rows not matched on parameter count or input representation (FTCT-S02);
   - the ambiguity of M = 3, fixed length or upper bound (FTCT-U04).

   You must also cover **at least one** of FTCT-U03 (validation-loss details) or
   FTCT-U05 (two definitions of whole chain accuracy).

## Prohibited

- New numbers, derived statistics presented as source results, error bars,
  confidence intervals, p-values, significance claims, or "repeated runs".
  Simple arithmetic you do yourself (e.g. a difference between two printed cells)
  is allowed only if you label it as your own arithmetic on printed values.
- Stronger causal claims than the facts support (e.g. "attention causes ...",
  "proves that depth is necessary") unless you attribute them to the authors and
  qualify them.
- Claims about experiments, models, datasets or results not in the fact sheets.
- Presenting this as your own new experiment or as a replication.

## Solver choices (not fixed)

Title, structure, paragraph order, level of detail beyond the requirements, whether
to include a small in-text table, terminology (as long as it stays faithful to the
definitions), and which specific printed numbers to cite.

## Required outputs (write to `submission/`)

1. `submission/section.md`: the passage in Markdown, **450–900 words** of body text
   (headings and any optional table are not counted). Do not put fact-ID tags in the
   prose.
2. `submission/claims.json`: a JSON list covering **every sentence of section.md that
   makes a scientific or numeric claim**. Each item looks like:
   ```json
   {"claim_id": "C1",
    "sentence_excerpt": "<exact substring copied from section.md, >= 30 characters>",
    "fact_ids": ["FTCT-R01", "FTCT-F07"],
    "numbers": [{"row_id": "TF_2L1H", "column": "test_whole_acc", "value": "0.766"}],
    "claim_type": "table_observation | author_interpretation | definition | limitation | own_arithmetic"}
   ```
   `numbers` lists every table value cited in that sentence. Use `row_id` and `column`
   names from `ftct_table1_values.csv`, or `params_reported` for parameter counts.
   Use `[]` if no table value is cited.

## Resources

CPU-only container with no network. Python 3.12 with numpy and matplotlib is
available but not needed. Limits for this task: 1 CPU, 1024 MB RAM, 512 MB disk,
64 processes, 600 s wall time.
