# Task: Present UTKFace corruption results from Table 4

Using the supplied CSV and provenance JSON, create an original, readable scientific visual artifact (PNG or SVG), its executable Python generation code, a caption, a JSON numeric manifest linking every method/column/cell to the source Table 4 locator while preserving the source strings, and a 150–220 word interpretation.

The visual must represent all 10 methods, all 13 corruption types, and Mean. Choose and justify an encoding that permits comparison across methods and corruptions and visibly preserves negative values. Metric is test R² (unitless; higher is better). The data are Table 4 reported aggregate cells at three decimal places; independent-run observations and dispersion are absent. Mean is a reported aggregate, not an independent run. Do not fabricate intervals or infer significance, causality, or run-level variation from rounded cells.

Identify UTKFace, image corruption at severity 5, test R², source location, and aggregation limitation in the caption/interpretation. Oracle fine-tunes using test labels and is described as an upper-bound comparator; separate it from unlabeled TTA claims. SSA is not best in every corruption: Pixelate is FR 0.946, RSD 0.941, SSA 0.943 (source row cells S4.T4.6.1.7.8, .9.8, .10.8). Avoid an unqualified universal-best statement. All remaining pairwise/comparative descriptions must agree with the supplied data and remain descriptive.

## Evidence and provenance

- E1: Table 4 reports UTKFace image-corruption test R² scores, unitless, higher is better. Source: ssa-paper-v1, SHA256 77cbdd9cbe5498f49625dc0c0c269c3d85a8bc18707f581d6ed1b2783c8dad60, Section 4.3.2, Table 4 caption, HTML id S4.T4.
- E2: The supplied CSV preserves all 140 method-by-corruption/Mean cell strings at three decimal places. They are reported aggregates; independent-run observations and dispersion are not supplied. Source: same source/hash, Table 4 data rows S4.T4.6.1.2–11.
- E3: Oracle fine-tunes using labels during testing and is described as an upper-bound comparator. SSA is not highest for Pixelate; FR is 0.946, SSA 0.943, RSD 0.941. Source: same source/hash, Section 4.2 paragraph S4.SS2.p3; Table 4 cells S4.T4.6.1.7.8, S4.T4.6.1.9.8, S4.T4.6.1.10.8.
- E4: UTKFace is age prediction; source training uses original images; evaluation uses 13 ImageNet-C corruption types at severity 5. Source: same source/hash, Section 4.1 paragraph S4.SS1.p3.

The JSON manifest records cell-level source locators. Generation code must load supplied data and generate the visual, but must not be supplied with a preselected target chart design/renderer. The visual design and implementation are part of this task. Submit the artifact, code, caption, manifest, and interpretation. Include [E1]–[E4] citations in the caption and/or interpretation.
