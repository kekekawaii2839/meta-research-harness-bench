# EXP v4: finite sample behavior of coupled IV gradient updates

## Research question and scope

On the fixed synthetic IV designs below, how do positive constant inner and outer rates affect the finite-iteration coefficient estimate's distance to sample 2SLS, and how do finite-iteration and OLS/2SLS control errors to generated true `beta` compare? This is a CPU numerical study of the equation-defined method, not a Transformer/GPU claim or whole-paper reproduction. A negative or inconclusive empirical conclusion is acceptable.

## Fixed objects and definitions

Use float64, no intercept, `Z ∈ R^(n×q)`, `X ∈ R^(n×p)`, `Y ∈ R^n`, `Theta ∈ R^(q×p)`. Define `Theta_hat = argmin_T ||Z T-X||_F^2`; then `beta_2SLS = argmin_b ||Z Theta_hat b-Y||_2^2`, and OLS control `beta_OLS = argmin_b ||Xb-Y||_2^2`. The starter computes these by `numpy.linalg.lstsq(..., rcond=None)`.

For each full-rank primary replicate, require `rank(Z)=q` and `rank(Z Theta_hat)=p`; report these ranks and condition numbers. Report `rank(X)` too. The paper's population Assumption 1 states `q≥p`, assumes `Z,X` full rank without loss of generality, requires `Corr(z,x)≠0`, and `Corr(z,epsilon_1)=0`. A finite sample rank check does not establish population correlation assumptions. The specified random generator is a known synthetic design, not a claim about arbitrary datasets.

Initialize `Theta^(0)=0_(q×p)` and `beta^(0)=0_p`. For every `t=0,1,...`, calculate both next states from the same frozen old state:

```text
Theta^(t+1) = Theta^(t) - eta Z^T (Z Theta^(t)-X)
beta^(t+1)  = beta^(t)  - alpha Theta^(t)^T Z^T (Z Theta^(t) beta^(t)-Y)
```

There is no division by `n` in either gradient. `alpha` and `eta` are fixed positive scalars throughout a trajectory; do not use a schedule or sequentially feed `Theta^(t+1)` into the beta update. On each sample compute `A_alpha=2/sigma_max(Z Theta_hat)^2` and `A_eta=2/sigma_max(Z)^2`. Theorem 3.1 gives sufficient conditions `0<alpha<A_alpha` and `0<eta<A_eta`, with `sigma_max` the largest singular value. These asymptotic conditions do not guarantee a chosen finite budget meets a numerical tolerance. A rate strictly beyond a bound is an exploratory stress condition, not a theorem prediction.

## Fixed synthetic data

Use `assets/base_resources.py`, a task-local `numpy.random.Generator`, `noise=1`, `p=5`, `q=10`, and `n ∈ {50,100,150}`. Per replicate the starter draws in order: `Z ~ N(0,1)^(n×q)`, true `Theta ~ N(0,1)^(q×p)`, true `beta ~ N(0,1)^p`, `Phi ~ N(0,1)^(p×p)`, `phi ~ N(0,1)^p`, `U ~ N(0,1)^(n×p)`, `E2 ~ N(0,1)^(n×p)`, `E1 ~ N(0,1)^n`; then `X=Z Theta + noise U Phi + E2` and `Y=X beta + noise U phi + E1`. Each replicate must use a recorded seed and an independent generator. The sample sizes, dimensions, Gaussian distributions and structural equations are fixed. Rate values, seed set, independent replicate count, iteration budget, stopping tolerance, diagnostics, aggregation, and transparent rank-failure handling are solver choices; do not silently discard or replace deficient samples. Do not tune using undisclosed results.

## Scoped hypotheses

- **H1:** For chosen settings inside both per-replicate sufficient bounds, the distance `||beta^(t)-beta_2SLS||_2` approaches the solver-declared numerical tolerance within its declared budget on full-rank replicates. Report outcomes, not a guaranteed success.
- **H2:** The observed distance trajectory depends on the selected `alpha` and `eta`; characterize that dependence and whether any tested beyond-bound setting misses the same declared tolerance within budget. Beyond-bound behavior is empirical.
- **H3:** Finite-iteration `||beta^(t)-beta||_2` need not be smaller than `||beta_2SLS-beta||_2`; report paired replicate errors and aggregates without inferring H3 from H1.

The iteration equations, states, constant-rate semantics, no-normalization convention, data distribution/draw order, dimensions, sample sizes and bound formula are fixed scientific conditions. The solver designs rates, repeats/seeds, budget, tolerance, diagnostics, aggregation, stopping and rank-failure policy. Do not preselect those choices by reproducing an author recipe. Theorem asymptotic convergence and empirical behavior under a finite budget must be discussed separately.

## Deliverables and JSONL/JSON interfaces

Submit runnable experiment code, `config.json`, `replicate_results.jsonl`, and `report.json`; no separate prose research report. UTF-8 JSON, one object per JSONL line. Reject duplicate IDs and dangling references. Encode non-finite numbers as JSON `null` and pair them with a status/reason field; never emit nonstandard `NaN` or `Infinity` tokens. Numeric values use JSON numbers (float64 computations); units are explicit below.

`config.json` is an object with: `schema_version: "iv-exp-config-1"`; unique `config_id`; `method_id`; `dtype: "float64"`; `n_values` (nonempty subset of `[50,100,150]`); `p: 5`; `q: 10`; `noise: 1.0`; `rate_settings` (nonempty array of unique `{setting_id, alpha, eta}` with positive finite constant rates); `replicates` (nonempty array of unique `{replicate_id, seed, n}`); positive integer `max_iterations`; nonnegative finite `tolerance` with metric exactly `beta_2sls_l2`; `stopping_rule` (declared rule and whether stopping is shared across settings); `rank_policy` (declared policy; failures retained); and `resource_budget` (cpus, memory_mb, disk_mb, wall_seconds). A rate-bound relationship is computed and recorded for each generated sample, since bounds are sample-specific.

Each `replicate_results.jsonl` object has: `schema_version: "iv-exp-replicate-1"`; a unique `experiment_id` per trajectory and references `replicate_id`, `config_id`, `setting_id`, plus `seed`, `n`. Referenced IDs may repeat across settings; only experiment_id and the (replicate_id, setting_id) trajectory key must be unique; `status` (`completed|rank_deficient|numerical_failure|budget_exceeded`); `rank_diagnostics` with integer ranks for `Z`, `X`, `ZTheta_hat`, plus 2-norm condition numbers or `null` with reasons; `rate_diagnostics` with positive `alpha`, `eta`, `A_alpha`, `A_eta`, booleans `within_alpha_bound`, `within_eta_bound`, and `gamma_alpha`, `kappa_eta`, `Lambda` (spectral radii, dimensionless), defined by `gamma_alpha=rho(I_p-alpha Theta_hat^T Z^T Z Theta_hat)`, `kappa_eta=rho(I_q-eta Z^T Z)`, `Lambda=max(gamma_alpha,kappa_eta)`; `iterations` array including iteration 0 and each computed iterate, each with integer `t`, `beta_2sls_l2=||beta^(t)-beta_2SLS||_2`, `beta_true_l2=||beta^(t)-beta||_2`, `beta_ols_l2=||beta_OLS-beta||_2`, and `beta_2sls_true_l2=||beta_2SLS-beta||_2` (all coefficient-vector L2 norm; control errors are constant within a replicate), and optional finite-state diagnostic fields; `stopping` with reason, stopped boolean and iteration; `execution` with elapsed wall seconds, configured budget, and failure reason or null. Retain actual values at every iteration for every replicate; do not substitute only aggregate curves.

`report.json` has `schema_version: "iv-exp-report-1"`; `config_id`; `experiments` array with unique `experiment_id`, setting reference, replicate references and artifact paths; `aggregates` array keyed by `setting_id,n,metric,iteration`, each declaring `independent_replicate_count`, included replicate IDs, and mean and median over the listed finite replicate values; `hypotheses` array with each `hypothesis_id` (H1/H2/H3), `status` (`supported|not_supported|inconclusive|untested`), linked experiment IDs and evidence paths; and `conclusions` array of brief `statement`, `uncertainty`, `limitations`, and evidence paths. Explain any excluded observations and why. Aggregated means do not count as independent runs. Optimization tolerance is not statistical uncertainty; do not fabricate confidence intervals or infer significance from rounded values.

## Verification plan (planned, not completed)

Deterministic checks: validate these field/type relationships and IDs; parse strict JSON/JSONL and ensure non-finite values are null with status; verify config/result/report linkage, seed linkage, iteration indexing, declared constant rates, resource records, rank/condition diagnostics, rate-bound calculations, metric calculations and aggregate arithmetic; inspect code for simultaneous frozen-old-state updates and no gradient division by `n`; rerun selected declared seeds and compare within a stated floating-point policy.

Evidence-based review: assess that experiment choices actually probe H1-H3, distinguish theorem asymptotics from finite-budget observations, treat beyond-bound settings as empirical, preserve all rank failures, interpret paired coefficient errors correctly, map equations and synthetic-data provenance accurately, and keep conclusions within this CPU scope. This plan does not mean these checks have been completed.
