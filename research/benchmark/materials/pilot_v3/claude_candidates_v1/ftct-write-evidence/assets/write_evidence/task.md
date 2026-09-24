# WRITE_EVIDENCE task: visual evidence for the FTCT architecture comparison (Table 1, N = 5, M = 3)

Status: development candidate, pending independent review.

## Goal

Design and build a **renderable scientific figure** that presents a published
architecture comparison faithfully and readably. The comparison covers five GPT-2-like
Transformer configurations and two MLPs trained on the synthetic FTCT task with causal
depth N = 5 and child chain length M = 3. Each model is shown at its optimal
chain-of-thought shot count (the count itself and the selection rule are not reported).
Alongside the figure, provide generation code, a caption, a source-linked numeric
manifest and a short interpretation.

The values are **author-reported table cells**: 7 models × 6 metrics plus reported
parameter counts. They are not raw runs, seeds or replications, and you do not train
anything.

## Public inputs (all paths relative to the task root)

| File | Content |
|---|---|
| `assets/write_evidence/task.md` | this specification |
| `assets/common/ftct_table1_values.csv` | values as printed (strings with 3 decimals), `params_reported` strings, row ids |
| `assets/common/ftct_table1_manifest.json` | metric definitions, units, directions, conditions, and a source cell locator for every value |
| `assets/common/facts_core.json` | fixed facts FTCT-F01..F09, R01, R07, U01..U05, S01..S03 (definitions, conditions, ambiguities, reporting rules) |
| `assets/common/table1_reader.py` | optional loader/validator: `load_rows`, `load_manifest`, `validate`, `cell_locator`. It has no plotting code. |
| `assets/common/SOURCE_NOTICE.md` | attribution and pending-rights notice |

The environment has Python 3.12, numpy and matplotlib (Agg backend), and no network.

## Fixed scientific constraints

1. **Completeness.** All 7 model rows and all 6 metric columns (42 values) must
   appear in the figure. The reported parameter counts must appear in the figure or
   the caption.
2. **Faithfulness.** Read every plotted or annotated value from the CSV/manifest at
   run time; do not hard-code the numbers in your script. Any value printed on the
   figure must match the source string exactly (e.g. `0.768`, not `0.77`), unless
   your caption says that labels are rounded.
3. **Data-driven code.** `make_figure.py` must work on **any consistent
   CSV/manifest pair** with the same schema (same row ids and column names, values
   that pass `table1_reader.validate`). Reviewers will re-run it on a copy in which
   values are changed consistently in both files. The figure and numeric manifest
   must then reflect the changed values.
4. **Scales.** Validation loss (lower is better, normalization unstated; FTCT-U03)
   and the accuracies (fractions in [0, 1], higher is better) must not share an
   axis or colour scale in a way that makes them look comparable. Make the
   in-distribution (Training) vs compositional (Testing) grouping readable.
5. **No invented uncertainty.** No error bars, confidence bands, significance
   markers or implied repeated runs (FTCT-U01, FTCT-S03). Categorical model
   configurations must not be drawn as if they were a time series or a continuous
   variable, unless the caption justifies the encoding.
6. **Conditions visible.** The caption must state N = 5 and M = 3 (with the
   "upper bound" wording note, FTCT-U04). It must also state the optimal-shot
   selection, and that neither the shot count nor the rule is reported (FTCT-U02).
   It must note the unstated aggregation (FTCT-U01), and that the rows are not
   matched on parameter count or input representation (FTCT-S02).

## Solver choices (not fixed)

Chart type(s), panel layout, encodings, ordering, colours, annotation density,
labels, figure size, and whether to add a derived view. A derived quantity must be
clearly marked as your own arithmetic on printed values.

## Required outputs (write to `submission/`)

1. `submission/make_figure.py`: regenerates the figure files and the numeric
   manifest (items 2 and 4) from the inputs, offline, with
   `python submission/make_figure.py --assets-dir assets/common --out-dir submission`.
   Use only the Python standard library, numpy and matplotlib. It must run within
   the resource limits below.
2. `submission/figure.png` (at least 150 dpi) **and** a vector version,
   `submission/figure.pdf` or `submission/figure.svg`.
3. `submission/caption.md`: figure caption, at most 200 words (written by you, not
   generated).
4. `submission/numeric_manifest.json`: one entry for **each of the 42 metric values
   plus the 7 parameter strings** shown:
   ```json
   {"row_id": "TF_2L1H", "column": "test_whole_acc", "value_as_printed": "0.766",
    "source_cell_locator": "S4.T1.2.1.5.8", "visual_element": "<where/how it appears, e.g. panel B, bar 3>"}
   ```
   Take `value_as_printed` and `source_cell_locator` from the input files at run time.
5. `submission/interpretation.md`: at most 250 words. Say what the figure shows
   about the Transformer configurations and Transformers vs MLPs, for vertex order
   and for values separately, and give the main uncertainties. Keep causal language
   no stronger than the evidence allows.

Markdown tables alone do not satisfy this task. The figure is the primary artifact.

## Resources

1 CPU, 1024 MB RAM, 512 MB disk, 64 processes, 600 s wall time for the whole
session. Rendering 49 values should take seconds.
