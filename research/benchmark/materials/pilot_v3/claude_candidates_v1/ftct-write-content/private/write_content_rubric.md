# PRIVATE: WRITE_CONTENT judging plan (ftct-table1-write-content)

This is a candidate plan and has not been run. The judge receives the original source
(`fragmented-paper-v1`) from the controller, `private/reference_notes.json`, the
public fact sheets and the submission.

## A. Deterministic checks (scripted; pass/fail)

1. `submission/section.md` and `submission/claims.json` exist; claims.json parses as a
   JSON list with the required keys.
2. The body word count of section.md, excluding headings and Markdown tables, is
   between 450 and 900.
3. Every `sentence_excerpt` is an exact substring of section.md and has at least 30
   characters.
4. Every `fact_ids` entry is one of the public input IDs: FTCT-F01..F09, R01..R07,
   U01..U05, S01..S03. Any private ID (U06, S04, P01, P02) is a violation.
5. Every `numbers` entry matches the CSV exactly (row_id, column, printed string).
6. Numeric scan: every token in section.md matching `\d\.\d{3}` or `\d+M` either
   appears in some `numbers` entry, or is a condition constant (N = 5, M = 3,
   window sizes 150/200/300, 720, 2048, 503, 50257, 1000, 5e-5), or is explicitly
   labelled as own arithmetic in claims.json (`claim_type: own_arithmetic`,
   recomputed and checked to ±0.0005).
7. Forbidden patterns in section.md (case-insensitive): `statistically significant`,
   `p <`, `p=`, `confidence interval`, `±`, `standard deviation of`, `error bar`,
   `seeds`, `we trained`, `our experiment`. Each hit is flagged for the judge to
   confirm; negated uses such as "no error bars are reported" are allowed.
8. Shot-count assertion scan: flag phrases such as `1-shot`, `one-shot`, `k = 1`,
   `single shot` near "Table" for judge review. Asserting that Table 1 uses a
   specific shot count is an error (FTCT-U02, FTCT-R07). Correctly attributed
   context ("the authors report elsewhere that performance peaks at one shot") is
   allowed.
9. Similarity is **not** scored. As a leakage guard only, flag any 12-word window
   copied verbatim from Section 4.3 of the original for judge review. Windows that
   also occur in the public fact sheets (`facts_core.json`,
   `facts_author_findings.json`) are discounted, because the solver was given that
   wording.

## B. Evidence-based LLM judgment (graded 0–2 each, with a written rationale)

1. **Numeric and definitional faithfulness.** Cited values, row labels and metric
   definitions match the facts. The six metrics are not conflated, and loss is not
   treated as an accuracy.
2. **Conditions.** N = 5 and M = 3 are stated. The optimal-shot selection is
   mentioned as a condition, and no Table 1 shot count is asserted.
3. **Findings coverage.** The passage covers the effect of TF depth and heads on
   vertices vs values accuracy, and TF vs MLP on values accuracy and on vertex order
   (train vs test).
4. **Attribution and calibration.** Author interpretations (R02–R06) are attributed.
   The mechanism (induction heads) is not presented as shown by Table 1; R03's
   evidence comes from a different setting. R06 is not presented as explaining
   trained behaviour. No claim that attention or depth "causes" the result without
   qualification. The authors' word "significant" (R02) must not be turned into a
   statistical claim.
5. **Consistency with the numbers** (see reference_notes S04). No false claims of a
   monotone testing-vertices drop. An unqualified "MLPs do well on test vertices" is
   penalised if it ignores 4L = 0.484. Pointing out the 1L2H train/test gap or the
   near-optimal training values is credited but not required.
6. **Limitations.** Required: U01 (aggregation), U02 (post-selection / unstated
   shot count), S02 (unmatched params/inputs) and U04 (M fixed vs upper bound),
   plus at least one of U03 or U05. This matches the public task.md exactly. No
   invented uncertainty.
7. **Scientific writing quality.** The passage is coherent, self-contained,
   appropriately concise and readable by a reader without the paper.

Any hallucinated result, experiment or statistic caps the total score at "fail",
whatever the other scores.
