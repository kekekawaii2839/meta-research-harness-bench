# PRIVATE reviewer/judge notes: diffusion-exp-2d-v1 (EXP, 2D branch)

Do not show these notes to solvers. Source references use source_id `diffusion-paper-v2`
(arXiv 2410.02543v2 HTML, sha256 992bd1adfaae19eaadf0019f9be5ae1f0dd614aa4b33d247a73a1deeec261e58).
The controller supplies the originals separately.

Status: candidate, repair attempt 1. Nothing here has been executed or independently
verified.

## 1. Where the fixed specification comes from

| spec item | source locator | maintainer adjudication |
|---|---|---|
| Algorithm steps | Algorithm 1 (`alg1`), lines 1–12 | Used exactly as printed: synchronous update from a frozen generation, loop t = T..2. The printed listing ends with two `end for` lines (l11, l12) and has no return statement. Returning `x_1` is the maintainer adjudication (audit diffusion_formula_alignment_v1). §3 `S3.p3` says the x0hat are used as goals "instead of the final solutions". |
| x0hat, Z, epshat | §3, Eq. 6–10 (paragraph `S3.p2`, sub-paragraphs `S3.p2.1`–`S3.p2.6`) | Eq. 8–9 sum over the current population `X_t`. The kernel is `N(x_t; sqrt(alpha_t) x, 1 - alpha_t)`. |
| update form | §3, Eq. 5 (from DDIM, Eq. 3); Alg. 1 line 10 | as printed |
| schedule constraints | Alg. 1 line 2: `alpha_0 ~ 1, alpha_T ~ 0, alpha_i > alpha_{i+1}, 0 < sigma_i < sqrt(1 - alpha_{i-1})` | See §2.3 below (F3). |
| cosine schedule | App. A.2 Eq. 16 (`A1.SS2.p2`, "used in both Figures 3 and 4"); §4.1 `S4.SS1.p2` | `alpha_t = cos(pi t/T)/2 + 1/2`. This equals `cos^2(pi t / (2T))`, i.e. Nichol & Dhariwal with offset s = 0. |
| sigma_t | App. A.2 Eq. 17 and `A1.SS2.p2` | `0 <= sigma_m <= 1`. The source says `sigma_m = 1` "for most experiments", except Fig. 2, which uses 0.1. The task fixes `sigma_m = 1` as primary. |
| excluded schedules | App. A.2 Eq. 14 (linear) and Eq. 15 (DDPM approximation), `A1.SS2.p1` | Eq. 14 as printed, `alpha_t = 1 - 1/T`, does not depend on t. Eq. 15 hyper-parameters are only implicitly defined (`alpha_0 = 1 - eps`, `alpha_T = eps`, `eps = 1e-4`). Both are excluded as ambiguous. |
| g mapping | §3 `S3.p1` (g is a chosen mapping); Alg. 1 line 5 | The source does not fix g for the 2D benchmarks. `g = identity` is a maintainer choice, not author fidelity. |
| two-peak objective | App. A.1, Eq. 13; `A1.SS1.p3`: mu1 = (1,1), mu2 = (-1,-1), sigma = 0.1 | The normalised isotropic 2D Gaussian (per-coordinate std 0.1) is a maintainer reading. The scale does not matter under g = identity, because the update is invariant to scaling Q. |
| Rosenbrock, Beale, Himmelblau | App. A.4, Table 2 (`A1.T2`) rows 1–3 | Formulas and optima as printed. Himmelblau optima are printed to 2 decimals; the starter uses standard 6-decimal values. |
| box | App. A.4 `A1.SS4.p1`: range constrained to (-4, 4) | Enforcement is not stated in the source. The task uses a closed box with zero fitness outside, for all methods, and no clipping. |
| fitness transform | App. A.4 Eq. 19, `A1.SS4.p3`: eps = 1e-3; s "determined by the standard deviation of fitness around their optimal points, with ranges adjusted" | No s values are reported. The task fixes s = 1.0 for all three functions (maintainer). |
| entropy | App. A.4.1 Eq. 20 (`A1.SS4.SSS1.p1`–`p3`), 80 x 80 grid on "the 2-D space" | As printed, Eq. 20 has no leading minus sign (the value would be <= 0). The task uses the standard `-sum P log2 P`. The grid region is not stated; bins and region are solver choices. |
| locality mechanism (H4) | §3 `S3.p2.6`, sentences after Eq. 10; Fig. 2 caption (`S3.F2`) | The source claims that locality "avoids global competition" and lets the algorithm maintain multiple solutions. The source runs no ablation of this. |
| diversity claim (H2/H3) | §4.1 `S4.SS1.p1`, `S4.SS1.p3`; Table 1 (`S4.T1`); Fig. 3 (`S4.F3`) | See §4 for the budget caveat. |
| accelerated sampling (H1) | §4.1 `S4.SS1.p2`; §4 `S4.p1` | The source's comparison against other schedules cannot be reproduced here because Eq. 14/15 are excluded. H1 therefore tests only quality at small T, not "cosine beats DDPM". |

## 2. Ambiguities, contradictions and adjudication records

### 2.1 Kernel variance notation

- Alg. 1 and Eq. 6–9 use `N(x_t; sqrt(alpha_t) x, 1 - alpha_t)`. The forward process (Eq. 1)
  fixes the third argument as a variance.
- App. A.3 Eq. 18 (`A1.SS3.p1`) writes the rewritten Gaussian with third argument
  `sqrt((1 - alpha_t)/alpha_t)`, i.e. a standard deviation. The text then gives
  `r^2 = (1 - alpha_t)/alpha_t`. Eq. 18 also shows a Jacobian factor `1/sqrt(alpha_t)`,
  which is dimension-agnostic notation.
- The notation is therefore inconsistent. The task adjudicates variance `(1 - alpha_t) I`.
  Constant factors cancel in x0hat.

### 2.2 F6 label correction (confirmed by maintainer root)

- The request text allows clamping "the Eq18 square-root argument".
- Eq. 18 contains no square root that can go negative.
- The permitted clamp applies to the Alg. 1 line 10 / Eq. 5 coefficient
  `sqrt(1 - alpha_{t-1} - sigma_t^2)`. The request's "Eq18" label is recorded as a
  mislabel.

### 2.3 F3 schedule identity and Alg. 1 line-2 bounds

- With `S_t = (1 - alpha_{t-1})(alpha_{t-1} - alpha_t)/((1 - alpha_t) alpha_{t-1})` and
  `sigma_t^2 = sigma_m^2 S_t`:
  - For `sigma_m = 1`: `1 - alpha_{t-1} - sigma_t^2 = (1 - alpha_{t-1})^2 alpha_t / (alpha_{t-1}(1 - alpha_t))`
    holds with **equality**.
  - For `sigma_m < 1`: the left side is `>=` that expression.
- Derivation: with `sigma_m = 1`, the left side is
  `(1 - alpha_{t-1})[1 - (alpha_{t-1} - alpha_t)/((1 - alpha_t) alpha_{t-1})] = (1 - alpha_{t-1}) (alpha_t - alpha_t alpha_{t-1}) / ((1 - alpha_t) alpha_{t-1})`.
- At `t = T` with `sigma_m = 1`, `alpha_T = 0` gives `sigma_T = sqrt(1 - alpha_{T-1})`.
  - Alg. 1 line 2 requires `sigma_i < sqrt(1 - alpha_{i-1})` strictly.
  - The fixed cosine/Eq. 17 setting meets the line-2 bounds, with **equality** at
    `t = T` for `sigma_m = 1`.
  - The fixed setting also has `alpha_0 = 1` and `alpha_T = 0` exactly, whereas the source
    writes `~`.
  - This is accepted, not treated as a violation that needs repair.
- For `2 <= t < T` and `sigma_m > 0`, the bound is strict, because `alpha_{t-1} < 1`.

### 2.4 F4 two-peak demonstration is not source-comparable

- A.2 `A1.SS2.p1` states that the linear schedule (Eq. 14) was "used in Figure 2".
- `A1.SS2.p2` states `sigma_m = 0.1` for the Figure 2 demonstration.
- So the source's two-peak demonstration used Eq. 14 (itself ambiguous as printed) and
  `sigma_m = 0.1`, not the fixed cosine / `sigma_m = 1` setting of this task.
- `two_peak` outcomes here are a **maintainer extension, not source-comparable**. Judges
  must not treat Figure 2 as an expectation for H2 or H4 on `two_peak`.

### 2.5 Return value

- The Alg. 1 listing has no output statement. `X_1` is the adjudicated output.

### 2.6 Ackley/Rastrigin excluded

- A.4 `A1.SS4.p1` says only Rastrigin is switched to maximisation.
- Table 2 says that for both Ackley and Rastrigin, "the maximal points are located at the
  four corners" of the box. The direction for Ackley is therefore contradictory.
- Under maximisation, values just outside the box exceed the in-box maximum, so the
  out-of-box policy would decide the outcome.

### 2.7 Initialisation

- Alg. 1 line 3 says `N(0, I)`.
- Author-code options (a uniform density flag, `h`, `noise = 0`) are not cached and must
  not be assumed.

### 2.8 Author protocol (private context only; F1)

`S4.SS1.p3` describes the authors' setup:

- 100 repeats per method, population 512, 25 iterations
- OpenES run for 1000 steps
- top-64 elites for entropy
- "fitness functions were rescaled from 0 to 1"

These numbers were removed from all public starter defaults and examples. A solver that
happens to choose similar values is not evidence of leakage, and a solver that chooses
different values is not penalised.

## 3. Deterministic property checks for `de_step` / `run_de` (reviewer-run at review time)

These follow from the public specification. Supply `W` explicitly; results must be
deterministic.

- **P1 (single individual, no noise).** With N = 1 and `sigma_t = 0`:
  - `X0_hat = X`
  - `X_next = X * ( sqrt(alpha_prev) + sqrt(1 - alpha_prev) * (1 - sqrt(alpha_t)) / sqrt(1 - alpha_t) )`
- **P2 (fitness scale invariance).** Adding a constant `c` to every entry of `log_q` leaves
  `X_next` and `X0_hat` unchanged, up to floating-point tolerance.
- **P3 (global step at t = T).** With `alpha_t = 0`, every row of `X0_hat` equals
  `sum_j softmax(log_q)_j X_j`.
- **P4 (synchronous / permutation equivariance).** Permuting the rows of `X`, `log_q` and
  `W` together permutes the rows of both array outputs in the same way.
- **P5 (locality).** Take two well-separated clusters (e.g. 5 points near (1,1) and 5 near
  (-1,-1)), equal `log_q`, `alpha_t = 0.99`. Each `X0_hat` row stays within its own
  cluster's convex hull, up to negligible weight.
- **P6 (clamp).** `cosine_alpha(T)` and `ddim_sigma(., 1.0)` for T in {2, 3, 7, 40} give
  finite `X_next` at t = T, with no NaN.
- **P7 (schedules).**
  - `cosine_alpha(T)[t] == 0.5 cos(pi t/T) + 0.5` to 1e-12.
  - `ddim_sigma` matches the Eq. 17 form for t = 1..T.
  - Entry 0 is NaN.
  - For `sigma_m = 1`, `1 - alpha_{t-1} - sigma_t^2` matches the §2.3 identity to 1e-12
    for t = 2..T.
- **P8 (budget).** In `runs.jsonl`, `fitness_evaluations` for the method equals
  `N*(T-1)`, or `N*T` if the solver declared final scoring as counted.
- **P9 (degenerate reporting, F2).**
  - If `log_q` is entirely `-inf`, `de_step` returns `n_degenerate == N` as an int.
  - For finite `log_q`, it returns `n_degenerate == 0`.
  - `run_de(...)["degenerate_rows"]` is an int equal to the sum over steps. It is 0 on
    ordinary starter-objective runs that use log-domain weights.
  - Degenerate-row values themselves are not checked. Any handling must appear in
    `deviations.json`.

A reviewer may also compare `de_step` against their own independent implementation of
`method_spec.md` §3 on random inputs, to 1e-10. No such reference implementation is
shipped in this package.

## 4. Source results: context only, NOT gold

- Table 1 (`S4.T1`) values are averages of top-64 elite entropy and fitness. They carry no
  dispersion, and budgets are unequal (OpenES 1000 steps versus 25).
- Table 1 rankings must not be used to grade the solver's numbers, rankings or verdicts.
- A solver outcome that contradicts the paper can be fully correct under the fixed
  `g = identity`, s = 1 and cosine conventions. An example is low Himmelblau coverage.
- The Figure 2 and Figure 3 qualitative pictures are not expectations (see §2.4).

## 5. LLM-judge rubric (evidence-based; cite files/lines)

- **J1 Fidelity.** Does the code implement the fixed §3 algorithm? Check:
  - `N(0, I)` initialisation
  - the frozen generation
  - loop T..2, returning `X_1`
  - `g = identity`
  - kernel variance `1 - alpha_t`
  - only the permitted stabilisations
  - degenerate counts reported through the specified channels
  - every other change declared
- **J2 Design.** Check each of the following:
  - independent seeds are used, and there are enough of them for the claims made
  - budget accounting is explicit, and comparisons are at matched or clearly declared
    budgets
  - the H3 baseline is genuinely convergent and reasonably tuned within the declared budget
  - H4 has a precisely defined control variant
  - thresholds were declared before the comparisons
  - "small T" is justified
- **J3 Evidence.** Verdicts follow from `results/`. Uncertainty is reported across runs,
  and aggregated means are not treated as independent samples. There are no claims beyond
  2D/CPU scope and no significance claims without a stated test.
- **J4 Reproducibility.** `RUN.md` regenerates the results inside the declared resources.
  Summary statistics can be recomputed from `runs.jsonl`.
- **J5 Integrity.** No paper numbers are used as targets, and no fabricated results appear.
  Negative verdicts are acceptable. `two_peak` results are judged as a maintainer
  extension.
