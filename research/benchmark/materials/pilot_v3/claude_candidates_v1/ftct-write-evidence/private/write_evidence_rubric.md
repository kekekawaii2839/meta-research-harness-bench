# PRIVATE: WRITE_EVIDENCE judging plan (ftct-table1-write-evidence)

This is a candidate plan and has not been run. The judge receives the original source
(`fragmented-paper-v1`), `private/reference_notes.json`, the public assets and the
submission.

## A. Deterministic checks (scripted; pass/fail)

1. Re-run `python submission/make_figure.py --assets-dir assets/common --out-dir <fresh_dir>`
   in a fresh, network-disabled container with the package environment (1 CPU,
   1024 MB, 600 s). The exit code must be 0.
2. The fresh run produces `figure.png`, which decodes with matplotlib.image.imread
   and has at least 150 dpi (from PNG metadata where present; otherwise pixel size
   ≥ 1000 px on the long side). It also produces `figure.pdf` or `figure.svg` with
   non-zero size, and `numeric_manifest.json`.
3. `numeric_manifest.json` has exactly 49 entries: 42 metric cells plus 7
   `params_reported`. Each `value_as_printed` equals the CSV string, and each
   `source_cell_locator` equals the locator in `ftct_table1_manifest.json`.
4. Hard-coding heuristic: the script should not contain the 3-decimal literals from
   the table (e.g. `0.768`, `1.446`) or the parameter strings. Hits are flagged for
   review, not failed automatically.
5. **Consistent perturbation test.** Make a copy of `assets/common/`. In that copy,
   change several metric values and at least one `params_reported` string in
   `ftct_table1_values.csv`, and change the matching `"value"` fields in
   `ftct_table1_manifest.json` to the same strings. Leave all `"cell"` locators and
   row ids unchanged. Keep accuracies in [0, 1] and loss > 0, so that
   `table1_reader.validate(rows, manifest)` still passes on the copy. Re-run
   `make_figure.py --assets-dir <copy> --out-dir <fresh_dir2>` and check that:
   (a) it exits 0; (b) the PNG differs from the unperturbed run; (c) the regenerated
   `numeric_manifest.json` carries the perturbed strings with unchanged locators;
   (d) if value labels are drawn, SVG/PDF text shows the perturbed strings. The
   public task.md tells solvers the code must work on any consistent CSV/manifest
   pair.
6. Only stdlib, numpy and matplotlib are imported (importing the public
   `table1_reader` helper is allowed); the script makes no network or subprocess
   calls.
7. Word limits: caption ≤ 200 words, interpretation ≤ 250 words.
8. Caption text contains `N = 5`/`N=5`, `M = 3`/`M=3`, a mention of optimal shots
   and a mention of unstated aggregation or runs. Forbidden: `±`,
   `confidence interval`, `statistically significant`, `p <`. Negated uses are
   judge-reviewed. Flag any assertion of a specific Table 1 shot count
   (e.g. "1-shot") for review. It is an error unless it is attributed context.
9. If available, SVG text extraction checks that any printed value labels match CSV
   strings, or that rounding is declared in the caption.

## B. Evidence-based LLM judgment (graded 0–2 each, with rationale; the judge views the PNG)

1. **Visual faithfulness.** Encoded magnitudes match the values (spot-check at least
   10 cells against the manifest). Axes are labelled with metric names and ranges.
   Accuracy axes are [0, 1] or otherwise clearly declared. Loss is on its own scale.
2. **Readability of the comparison.** A reader can see (a) the TF depth/head effect
   on training/testing vertices accuracy with values accuracy near 1, and (b) that
   MLPs have low values accuracy, with testing vertices higher than training
   vertices for the MLPs. The Training vs Testing grouping is clear.
3. **No invented uncertainty or trend.** No error bars and no connected lines that
   suggest continuity across categorical configurations without justification.
   Emphasis is not presented as significance.
4. **Caption.** It is accurate, self-contained and states the conditions and
   limitations (N, M ambiguity, optimal shots with unreported count/rule,
   aggregation unknown, unmatched params/inputs), with the metric directions.
5. **Interpretation.** It is concise and consistent with the numbers (see
   reference_notes S04: no false monotone test-vertices claim; MLP 4L vs 2L), and
   its causal language is calibrated. The judge may compare it with the authors'
   claims (R02–R06, private for this task) to check for unwarranted extra claims,
   but agreement with the authors is not required. Correct, well-qualified
   divergence is acceptable.
6. **Code quality.** The script is readable and deterministic, reads its data from
   the inputs, and passed the consistent perturbation test (A5).
