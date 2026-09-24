# Method and object specification: Diffusion Evolution on 2D objectives

This document is self-contained. Where it fixes a choice that the underlying proposal
left open, it says so. Items marked **FIXED** are scientific conditions of the task.
Items marked **SOLVER CHOICE** are yours to design and report.

## 1. Notation

- Population size `N`, parameter dimension `D = 2`, number of generations `T` (integer, `T >= 2`).
- Population at step `t`: `X_t = (x_t^(1), ..., x_t^(N))`, each `x_t^(i)` in R^2.
- Fitness `Q_j >= 0` of individual `j` (higher is better), from `starter/objectives.py`.
- Fitness-to-density mapping `g`: **FIXED** `g = identity`, i.e. `Q_j = fitness(x_t^(j))`.
  This is a maintainer choice for this task. It is not claimed to be the proposal authors'
  mapping, which is not specified for these objectives.

## 2. Schedules (FIXED)

Diffusion schedule: cosine with zero offset, for `t = 0, 1, ..., T`:

    alpha_t = 0.5 * cos(pi * t / T) + 0.5

This equals `cos^2(pi t / (2T))`. It gives `alpha_0 = 1` and `alpha_T = 0` exactly (in
IEEE float64, `cos(pi) = -1`), and `alpha_t` is strictly decreasing in `t`.

Noise schedule, for `t = 1, ..., T`:

    sigma_t = sigma_m * sqrt( (1 - alpha_{t-1}) / (1 - alpha_t) ) * sqrt( 1 - alpha_t / alpha_{t-1} )

- **FIXED primary setting:** `sigma_m = 1`. Every hypothesis test must include this setting.
- **SOLVER CHOICE (optional):** other `sigma_m` values in `[0, 1]`, as a declared secondary
  sensitivity analysis only.

Other schedule families (linear, DDPM-style exponential) are out of scope for this task.

### 2.1 Consequences of the fixed schedules (derived, not extra rules)

Write `S_t = (1 - alpha_{t-1}) (alpha_{t-1} - alpha_t) / ((1 - alpha_t) alpha_{t-1})`, so that
`sigma_t^2 = sigma_m^2 * S_t`. Then, for `t = 2, ..., T`:

- With `sigma_m = 1`, **equality** holds:
  `1 - alpha_{t-1} - sigma_t^2 = (1 - alpha_{t-1})^2 * alpha_t / (alpha_{t-1} * (1 - alpha_t))`.
- With `0 <= sigma_m < 1`, the argument is larger, giving the bound
  `1 - alpha_{t-1} - sigma_t^2 >= (1 - alpha_{t-1})^2 * alpha_t / (alpha_{t-1} * (1 - alpha_t)) >= 0`.
- At `t = T` with `sigma_m = 1`, `alpha_T = 0` makes the argument exactly 0 and
  `sigma_T = sqrt(1 - alpha_{T-1})`. Rounding can make the computed argument slightly negative.
  This is why clamping is permitted (section 4).
- The proposal's generic schedule requirements are
  `alpha_0 ~ 1, alpha_T ~ 0, alpha_t > alpha_{t+1}, 0 < sigma_t < sqrt(1 - alpha_{t-1})`.
  The fixed setting meets them, except that at `t = T` with `sigma_m = 1` the noise bound
  holds with **equality**, not strictly. This is accepted as part of the fixed setting.
  For `2 <= t < T`, `0 < sigma_t < sqrt(1 - alpha_{t-1})` holds strictly when `sigma_m > 0`.

## 3. The Diffusion Evolution algorithm (FIXED)

    Input: N, T, sigma_m, objective (fitness), random generator
    1. Draw X_T: N independent samples from the standard normal N(0, I_2).
       (Not uniform on the box. Individuals are never clipped or projected.)
    2. For t = T, T-1, ..., 2:
       a. Evaluate fitness once for every individual of the CURRENT population:
          Q_j = fitness(x_t^(j)), j = 1..N. Cache it; do not re-evaluate within the step.
       b. For every i = 1..N, using only the frozen X_t and Q (synchronous update):
            weights   u_ij = Q_j * K_t(x_t^(i), x_t^(j)),  j = 1..N   (j = i included)
            K_t(a, b) = Normal density of `a` under mean sqrt(alpha_t) * b and
                        covariance (1 - alpha_t) * I_2   (a VARIANCE, not a standard deviation)
                      ∝ exp( -||a - sqrt(alpha_t) * b||^2 / (2 * (1 - alpha_t)) )
            Z_i       = sum_j u_ij
            x0hat_i   = (1 / Z_i) * sum_j u_ij * x_t^(j)
            epshat_i  = (x_t^(i) - sqrt(alpha_t) * x0hat_i) / sqrt(1 - alpha_t)
            w_i       ~ N(0, I_2), drawn independently for every i and every t
            x_{t-1}^(i) = sqrt(alpha_{t-1}) * x0hat_i
                          + sqrt(1 - alpha_{t-1} - sigma_t^2) * epshat_i
                          + sigma_t * w_i
       c. Only after all i are computed, replace X_t by X_{t-1}.
    3. Return X_1, the population produced by the step t = 2. This is the method's final
       population. The estimates x0hat are internal targets, not the output.

Notes that follow from the definition (not extra rules):

- Note that the kernel compares `x_t^(i)` with `sqrt(alpha_t) * x_t^(j)`, not with `x_t^(j)`.
- The kernel's normalising constant is the same for every `j`, so it cancels in `x0hat_i`.
  Multiplying all `Q_j` by the same positive constant leaves the update unchanged.
- Individuals with `Q_j = 0` contribute exactly zero weight.
- At `t = T`, `alpha_T = 0`, so `K_T` does not depend on `j`. Every `x0hat_i` then equals the
  Q-weighted mean of the whole population. As `alpha_t -> 1`, the kernel standard deviation
  `sqrt(1 - alpha_t)` shrinks, so the weighting becomes increasingly local.
- Fitness-evaluation count for one run: `N * (T - 1)` evaluations inside the loop.
  Scoring the returned `X_1` costs another `N`. Report whether you count that final scoring.

## 4. Permitted numerical stabilisations (FIXED list)

Only these two are part of the method:

1. **Log-domain weights.** Compute
   `l_ij = log Q_j - ||x_t^(i) - sqrt(alpha_t) x_t^(j)||^2 / (2 (1 - alpha_t))`, then normalise
   over `j` with a max-shift or log-sum-exp. `starter/objectives.py` provides `log_fitness`
   (with `-inf` for zero fitness).
2. **Clamping at 0** the square-root argument `1 - alpha_{t-1} - sigma_t^2` of the `epshat`
   coefficient in the update (step 2b) before taking the square root.

Anything else counts as a **declared deviation**. It must be listed in
`evidence/deviations.json` and kept separate from the specified method. Examples: clipping
or projecting individuals into the box, weight temperatures, fitness normalisation beyond
the objective definitions, elitism, restarts, returning `x0hat` instead of `X_1`,
re-evaluating fitness inside a step, or asynchronous (in-place) updates.

## 5. Degenerate weight rows: mandatory reporting (FIXED mechanism, handling is yours)

Row `i` of a step is **degenerate** when the normaliser `Z_i` cannot be formed as a finite
positive number. For example, the log-sum-exp over `j` of `l_ij` is `-inf` or not finite. The
kernel is strictly positive, so in exact arithmetic this happens if and only if `Q_j = 0` for
every `j`, and then every row of that step is degenerate. Without log-domain weights,
underflow can also make individual rows degenerate.

Reporting is mandatory and uses exactly these channels:

- `de_step` returns a third value `n_degenerate`: an `int`, the number of degenerate rows
  in that step (0 when none).
- `run_de` returns the key `degenerate_rows`: an `int`, the sum of `n_degenerate` over all
  steps of the run.
- Each record in `results/runs.jsonl` for Diffusion Evolution (and for any DE-based control)
  carries `degenerate_rows` as that integer.

What your code writes into degenerate rows, and whether the run continues, is not
specified. Examples are stopping the run, a recovery rule, or leaving values undefined. Any
such handling is a declared deviation and must be listed in `evidence/deviations.json`.
The count must be reported regardless.

## 6. Objectives (FIXED; implemented in `starter/objectives.py`)

Search box `B = [-4, 4] x [-4, 4]` (closed). The same out-of-box policy applies to every
method you run: **fitness is 0 (log-fitness `-inf`) outside B**. The objective applies no
clipping, projection or resampling to any method's individuals. If you want such a
mechanism for a baseline, it is part of that baseline's design and must be declared.

| name | raw function f(x, y) | goal | known optima in B | fitness Q |
|---|---|---|---|---|
| `two_peak` | `[N((x,y); (1,1), 0.1^2 I) + N((x,y); (-1,-1), 0.1^2 I)] / 2`, where each `N` is a normalised 2D isotropic Gaussian density with per-coordinate standard deviation 0.1 | maximise | (1, 1), (-1, -1); max ≈ 7.957747 = 1/(4π·0.01) | `Q = f` in B |
| `rosenbrock` | `100 (y - x^2)^2 + (1 - x)^2` | minimise | (1, 1); f* = 0 | `F` below |
| `beale` | `(1.5 - x + xy)^2 + (2.25 - x + xy^2)^2 + (2.625 - x + xy^3)^2` | minimise | (3, 0.5); f* = 0 | `F` below |
| `himmelblau` | `(x^2 + y - 11)^2 + (x + y^2 - 7)^2` | minimise | (3, 2), (-2.805118, 3.131312), (-3.779310, -3.283186), (3.584428, -1.848126); f* = 0 | `F` below |

Transform for the three minimisation objectives:

    F(x, y) = eps / (eps + (f(x, y) - f*)^2 / s^2),   eps = 1e-3,  s = 1.0

`F` lies in `(0, 1]` inside `B` and equals 1 at the optima. The value `s = 1.0` is a fixed
maintainer value, applied identically to all methods. `objective.normalised_fitness`
divides by the optimum fitness to give a `[0, 1]` reporting scale for every objective.

## 7. Diagnostics provided (optional to use; all parameters are SOLVER CHOICE)

`starter/metrics.py` provides the following. All design parameters are required arguments
with no defaults.

- `grid_entropy(points, bins)`: standard Shannon entropy in bits, `H = -sum_i P_i log2 P_i`,
  of cell occupancy on a `bins x bins` grid over `B`. If you use entropy, use this sign
  convention.
- `select_elites(Q, k)`: the top-`k` individuals by fitness.
- `nearest_optimum` / `optima_covered(points, optima, radius)`: basin coverage within a
  radius of the known optima.
- `summarise_population(objective, X, k, bins, radius)`: a convenience bundle of the above.
- `CountingObjective`: counts fitness evaluations.
- `append_jsonl` / `read_jsonl`: result logging.

## 8. Fixed conditions vs solver choices (summary)

FIXED: everything in sections 2–6, namely:

- Algorithm steps
- Synchronous update from a frozen generation
- Loop `t = T..2`, returning `X_1`
- `N(0, I)` initialisation
- Kernel covariance `(1 - alpha_t) I`
- Cosine schedule, and `sigma_t` formula with `sigma_m = 1` as the primary setting
- `g = identity`
- The two permitted stabilisations
- The degenerate-row reporting channels
- Objective definitions, box and out-of-box policy

SOLVER CHOICE: all of the following, each of which must be reported:

- `N` and `T`
- Number of independent runs and the seeds
- Baselines and their hyper-parameters
- Evaluation budgets and how budgets are matched
- Elite size, entropy grid, coverage radius and success tolerances
- Diagnostics
- Secondary `sigma_m` values
- Any declared ablations or control variants
- Degenerate-row handling (declared)
- Statistical summaries and uncertainty estimates
