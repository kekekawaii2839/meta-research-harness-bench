# EXP: finite-size agreement of a Hermite surrogate with a one-step two-layer network across the alpha range

## Research question and scope

A two-layer network is trained by one gradient step on its first layer followed by a ridge readout, on structured two-component Gaussian-mixture inputs. A theoretical result (proportional asymptotic limit) states that, after first-layer training, replacing the activation by a truncated Hermite expansion plus an independent Gaussian residual term (the "Hermite model") leaves training and generalization errors asymptotically unchanged, for a degree that depends on a strength parameter `beta`.

At fixed `beta = 0.74` and the finite primary size `n = m = k = 1000`, does the Hermite model's held-out error track the original network's error across the weighting parameter `alpha ∈ [0,1]`, for ReLU, tanh and sigmoid activations; in which part of the `alpha` range (if any) does the agreement degrade; and how does the original network's held-out error itself vary with `alpha`?

This is a finite-size CPU numerical study. It cannot prove or refute the asymptotic theorem; conclusions must be stated for the tested finite configuration only. It does not cover other data sets, joint training of both layers, other values of `beta`, or real data. A negative, qualified or inconclusive conclusion is acceptable.

## Fixed objects and definitions

Use float64. Two-layer model `f(x) = k^{-1/2} w^T sigma(F x)` with `x ∈ R^n`, `F ∈ R^{k×n}`, `w ∈ R^k`.

**Scaling.** Strength `beta = 0.74` (fixed) and weighting `alpha ∈ [0,1]`. Spike strength `theta = n^{beta(1-alpha)}`, first-layer learning rate `eta = n^{beta alpha}`. The theory only fixes these as orders of growth; these concrete constants are the task's fixed choice. Note `eta ||Sigma||` is of order `n^beta` but not equal to it.

**Data (per `alpha`).** Two zero-mean components with probability 0.5 each, assigned independently per sample. Component covariances `Sigma_c = I_n + theta g_c g_c^T` (same `theta` for both), where `g_1, g_2` are independent uniformly random unit vectors (their alignment is not controlled). Mixture covariance `Sigma = I_n + (theta/2)(g_1 g_1^T + g_2 g_2^T)`, `Tr(Sigma) = n + theta`. Teacher: `y = ReLU(xi^T x)`, no label noise, with `xi` a uniformly random direction scaled to `||xi|| = 1/sqrt(||Sigma||)` (spectral norm). `assets/base_resources.py` (`make_structure`, `sample_mixture`) implements exactly this; a stratified exactly-half sampling option exists only as a declared variant, the primary data model is independent assignment.

**Initialization.** Rows of `F` i.i.d. `N(0, I_n / Tr(Sigma))`; `w ~ N(0, I_k / k)` (`init_weights`).

**Stage 1: one first-layer gradient step** on a first-stage sample `(X~, y~)` of size `m`, with `w` fixed at initialization:

```text
F_hat = F + eta * G
G = (1/m) [ (1/sqrt(k)) (w y~^T - (1/sqrt(k)) w w^T sigma(F X~^T)) ⊙ sigma'(F X~^T) ] X~
```

(`⊙` elementwise; `G` is the negative gradient of the half mean squared error). Implemented as `first_layer_step`. ReLU uses `sigma'(z) = 1[z>0]`.

**Stage 2: ridge readout** on a NEW independent sample `(X, y)` of size `m`, with `lambda = 1e-4` fixed:

```text
w_hat = argmin_w (1/(2m)) sum_i (y_i - k^{-1/2} w^T act(F_hat x_i))^2 + (lambda/2) ||w||^2
      = solution of (Phi Phi^T + lambda m I_k) w = Phi y,   Phi = act(F_hat X^T)/sqrt(k)
```

Implemented as `features`, `ridge_readout`. The training metric, if reported, is the value of this normalized objective at `w_hat` (`readout_objective`); name it as such.

**Held-out error (primary metric).** `G_err = E[(y - k^{-1/2} w_hat^T act(F_hat x))^2]` (full squared error, no factor 1/2), estimated by the empirical MSE on fresh test samples from the same mixture (`mse`). The test sample size is your choice; it is an estimate, not the population value.

**Original network ("NN model").** `act = sigma` in stage 2. `nn_reference` gives this reference model.

**Hermite model (method under test; you must implement it).** Maximum Hermite degree `D = 3`, theorem truncation index `l = D + 1 = 4`; `beta = 0.74` satisfies the theorem's condition `(l-2)/(l-1) < beta < (l-1)/l`, i.e. `2/3 < 0.74 < 3/4`. With `b = sqrt(n / Tr(Sigma))`, probabilists' Hermite polynomials `He_j` (`He_0=1, He_1=x, He_2=x^2-1, He_3=x^3-3x`), and `z ~ N(0,1)`:

```text
h_j     = E_z[ He_j(z) sigma(b z) ]                      (raw moments, j = 0..D)
h*_l    = sqrt( E_z[sigma(b z)^2] - sum_{j=0}^{D} h_j^2 / j! )
sigma_hat(u) = sum_{j=0}^{D} (h_j / j!) He_j(u / b) + h*_l * zeta
```

`zeta ~ N(0,1)` is drawn independently for every hidden unit and every sample, independently for readout-training features and for test features. (The theorem writes a single scalar Gaussian; this per-element independent reading is the task's fixed interpretation.) The residual term is part of the method; dropping it, or changing `D`, gives a different model. The expectations must be computed numerically with an accuracy you declare and check (method is your choice).

**Pairing and timing of replacement.** `F_hat` is computed once with the ORIGINAL `sigma` and `sigma'`. Within a replicate and activation, the NN model and Hermite model share the same structure, `F`, `w`, first-stage sample, `F_hat`, readout-training sample and test inputs; they differ only in the activation used to build readout features and test predictions. Training the first layer with the surrogate is not the Hermite model.

**Fixed configuration.** Primary sizes `n = m = k = 1000`; `beta = 0.74`; `lambda = 1e-4`; two components, weights 0.5, rank-one spikes; activations ReLU, tanh, sigmoid (all three are in scope). Supplementary runs at other equal-ratio sizes `n = m = k < 1000` are permitted as clearly labelled diagnostics; they do not replace the primary size.

**Assumption boundaries.** The theorem assumes a proportional limit (`n, m, k → ∞` with fixed ratios), an activation with bounded derivatives (ReLU does not literally satisfy this), and for generalization an additional technical condition. `alpha` jointly changes `eta`, `theta`, `||Sigma||`, `Tr(Sigma)`, `b` and the scale of `xi`; a trend in `alpha` is an observation about this joint parameterization, not evidence for any single factor unless you provide such evidence.

## Scoped hypotheses

- **H1 (agreement at finite size):** At the primary configuration, for each activation and each tested `alpha ∈ [0,1]`, the paired difference `G_err(Hermite) - G_err(NN)` is small relative to `G_err(NN)` — within an agreement criterion you declare (and whose sensitivity you report) — once replicate variability is taken into account.
- **H2 (regime dependence):** The relative Hermite–NN discrepancy shows no systematic dependence on `alpha` or on the activation over `[0,1]`. If it does, characterize where the agreement is weakest.
- **H3 (alpha trend):** At fixed `beta`, the NN model's held-out error `G_err` increases as `alpha` increases from 0 to 1, for each activation, and the Hermite model shows the same direction. Characterize the shape (monotone or not) and state what the trend does and does not imply given the joint parameterization.

Fixed scientific conditions: the equations above, constants (`beta, lambda, D, l, n=m=k=1000`), data model, initialization, two-stage training with independent samples, surrogate definition including the residual term, pairing and timing of replacement, and the three activations. Your choices: the `alpha` grid, replicate count and seeds, which random sources are resampled per replicate (structure, samples, initialization, surrogate noise) and therefore what your uncertainty refers to, test sample size, quadrature/integration method, agreement criterion, any additional diagnostics or normalizations, aggregation and failure handling. Declare them; do not silently discard or replace failed runs; do not tune on undisclosed results. Plan the work to fit the published wall-clock budget (one paired NN+Hermite evaluation at the primary size costs on the order of a second of CPU in this container; budget model/tool time too).

## Deliverables and JSON/JSONL interfaces

Submit runnable experiment code (`experiment.py` plus any modules), `config.json`, `replicate_results.jsonl`, and `report.json`; no separate prose research report. UTF-8 JSON, one object per JSONL line. IDs must be unique and references must resolve. Encode non-finite numbers as JSON `null` paired with a status/reason; never emit `NaN`/`Infinity` tokens.

`config.json`: `schema_version: "gmm-exp-config-1"`; `config_id`; `dtype: "float64"`; `n`, `m`, `k` (primary, 1000); `beta: 0.74`; `lambda: 0.0001`; `max_hermite_degree: 3`; `theorem_index_l: 4`; `activations` (exactly `["relu","tanh","sigmoid"]` for primary runs); `alpha_values` (nonempty, each in `[0,1]`); `sampling: "iid"` (or a declared supplementary variant); `test_samples`; `replicate_design` with `resampled_per_replicate` (subset of `structure`, `first_stage_sample`, `readout_sample`, `test_sample`, `init_weights`, `surrogate_noise`), `shared_across_alpha` (list, may be empty) and `estimand` (text); `replicates` (unique `{replicate_id, seed}`); `hermite_coefficient_method` (`method`, declared accuracy and the check performed); `agreement_criterion` (definition, and whether it was fixed before or after inspecting primary results); optional `supplementary_configs`; `resource_budget` (cpus, memory_mb, disk_mb, wall_seconds).

Each `replicate_results.jsonl` object: `schema_version: "gmm-exp-replicate-1"`; unique `experiment_id`; `config_id`, `replicate_id`, `seed`, `alpha`, `activation`, `n`, `m`, `k`, `test_samples`, `supplementary` (boolean); `status` (`completed|numerical_failure|budget_exceeded`); `structure` with `theta`, `eta`, `sigma_norm`, `trace_sigma`, `b`, `spike_overlap`; `hermite` with `coefficients` (the four values `h_j/j!`, `j=0..3`), `h_star`, and the declared quadrature check value; `nn` and `hermite_model`, each with `test_mse` and `train_readout_objective`; `paired` with `hermite_minus_nn_test_mse` and `relative_difference` (difference divided by NN `test_mse`); any additional diagnostics you use; `execution` with elapsed seconds and failure reason or null.

`report.json`: `schema_version: "gmm-exp-report-1"`; `config_id`; `experiments` (unique `experiment_id`s with artifact paths); `aggregates` keyed by `activation, alpha, metric, supplementary`, each with `independent_replicate_count`, included `experiment_id`s, and mean and median over listed finite values (plus any uncertainty summary you declare, with its definition); `hypotheses` (H1/H2/H3 with `status` in `supported|not_supported|inconclusive|untested`, linked experiment IDs and evidence paths); `conclusions` (brief `statement`, `uncertainty`, `limitations`, evidence paths); and `exclusions` explaining any excluded observation. Replicates that share data are not independent data replicates; say what varies. Do not fabricate confidence intervals or infer significance from rounded values.

## Verification plan (planned, not completed)

Deterministic checks: parse strict JSON/JSONL; verify IDs, linkage, seeds, constants, configuration fields and aggregate arithmetic; recompute `theta`, `eta`, `b` and Hermite coefficients; inspect code for the surrogate definition (degree, `1/j!`, `x/b`, residual term with per-element independent noise), for first-layer training with the original activation, for pairing, and for independent samples; rerun selected declared seeds and compare within a stated floating-point/noise policy.

Evidence-based review: whether the experiments actually probe H1–H3 at the primary configuration, whether the agreement criterion and uncertainty are appropriate and honestly declared, whether finite-size observations are kept separate from asymptotic claims, whether conclusions about `alpha` respect the joint parameterization, and whether failures and exclusions are preserved. This plan does not mean these checks have been completed.
