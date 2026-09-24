# EXP task: Diffusion Evolution on low-dimensional (2D) objectives

Status: development candidate. It has not been reviewed or accepted.

## Proposal (what is being tested)

Diffusion Evolution is a gradient-free, population-based optimiser. It treats fitness as
an unnormalised probability density over parameters and runs the reverse (denoising)
process of a DDIM-style diffusion sampler. No trained network produces the data estimate
`x0hat`. Instead, each individual computes its own fitness-weighted average of the current
population, weighted by a Gaussian kernel in parameter space. The kernel is broad early in
the run (small `alpha_t`) and narrows as `alpha_t -> 1`.

The proposal makes these claims:

- The increasing locality lets the population explore globally first and then converge
  **separately onto several optima**, instead of collapsing to a single solution.
- A cosine `alpha` schedule allows a small number of generations.

This task tests those claims **only in two dimensions, on CPU**. The objectives are a
two-peak Gaussian density and minimisation of Rosenbrock, Beale and Himmelblau. The task
says nothing about image generation, reinforcement-learning control, high-dimensional
parameters or latent-space variants.

`method_spec.md` fixes the exact algorithm, schedules, objectives, permitted numerical
stabilisations and degenerate-row reporting. You must implement Diffusion Evolution
yourself from that specification. No implementation of it is provided.

## Hypotheses to test

Evaluate each hypothesis with your own experiments. Report one verdict per hypothesis:
`supported`, `not_supported`, `inconclusive` or `not_tested`, with the reason. Negative or
inconclusive outcomes are acceptable if the evidence supports them. The label in brackets
gives each hypothesis's origin.

- **H1 (quality with few generations)** [proposal claim, scoped to 2D]. Use the fixed
  specification (cosine schedule, `sigma_m = 1`, `g = identity`, `N(0, I)` initialisation)
  with a small number of generations `T`, which you choose and justify. Under these
  conditions, Diffusion Evolution produces final populations `X_1` whose elite individuals
  reach near-optimal fitness on each of the four objectives. This task does not test the
  proposal's comparison between the cosine schedule and other schedules.
- **H2 (multiple optima are kept)** [proposal claim, scoped to 2D; the `two_peak` case under
  the fixed cosine setting is a maintainer extension]. Consider the objectives with
  several optima in the box: `two_peak` (2 maxima) and `himmelblau` (4 minima). On these,
  the final population of Diffusion Evolution typically places near-optimal individuals at
  more than one distinct optimum, rather than collapsing onto a single one.
- **H3 (diversity without a fitness penalty, versus convergent baselines)** [proposal claim,
  scoped to 2D; the baseline is your design]. Compare against at least one conventional
  single-solution-seeking evolutionary baseline that you implement and declare. The
  random-search floor alone is not sufficient. At a declared, comparable
  fitness-evaluation budget, Diffusion Evolution's elite sets are more diverse (grid
  entropy and/or optimum coverage), and their elite fitness is not materially worse.
- **H4 (locality is the mechanism)** [maintainer-formulated test of a mechanism the proposal
  asserts but does not ablate]. The shrinking Gaussian neighbourhood term is responsible
  for maintaining several optima. Define a control variant that removes or globalises the
  distance-dependence of the weights, with everything else unchanged. It loses
  multi-optimum coverage on `two_peak` and/or `himmelblau`. The control is a deviation by
  construction. Define it precisely and keep it separate from the specified method.

"Small", "near-optimal", "typically" and "materially worse" are not preset. You must
operationalise them with declared values, tolerances and thresholds **before** looking at
the comparison you use them in, and report them.

## Resources provided (public)

- `method_spec.md`: fixed method and objective definitions, the degenerate-row reporting
  channels, and the list of fixed conditions versus solver choices.
- `starter/objectives.py`: the four objectives. Provides `raw`, `fitness`, `log_fitness`,
  the box and out-of-box policy, and the known optima.
- `starter/metrics.py`: evaluation counter, elite selection, Shannon grid entropy
  (base 2), optimum coverage, JSONL logging. Design parameters (`k`, `bins`, `radius`)
  are required arguments with no defaults.
- `starter/baseline_random_search.py`: a validated random-search reference baseline.
  `budget` and `n_keep` are required. Its usage example uses arbitrary illustrative
  values, not recommended settings.
- `starter/test_starter.py`: self-checks for the starter code. Run `python test_starter.py`.

**Environment.** CPU-only container with Python 3.12, numpy 2.3.3 and matplotlib 3.10.6.
There is no network access and no other scientific packages; for example, no CMA-ES
library is available, so you must write any baseline yourself.

**Proposed per-container limits** (unmeasured; may be revised after a pilot):

- 2 CPUs
- 2048 MB memory
- 512 MB disk
- 128 processes
- 1200 s wall time

Your `experiments/RUN.md` must regenerate all results within these limits. Keep stored
populations compact, for example as float32, or store only the elites you analyse if you
declare this.

You may use or modify the starter code. If you change an objective, a metric or the
out-of-box policy, declare it as a deviation.

## What you decide

- `N` and `T`
- Number of independent runs and the seeds
- Which baselines, their hyper-parameters, and how their budgets are matched
- Elite size `k`, entropy grid, coverage radius and success tolerances
- Diagnostics and plots
- Optional secondary `sigma_m` values
- The H4 control variant
- Degenerate-row handling
- Statistical summaries

Report every choice. Each seed is one independent run. Aggregated means are not
independent runs, so state the number of independent runs behind every summary statistic.

## Required outputs (write under `submission/`)

1. `solution/diffusion_evolution.py` must expose these functions, using numpy arrays
   throughout:
   - `cosine_alpha(T) -> array (T+1,)`: `alpha_t` for `t = 0..T`.
   - `ddim_sigma(alpha, sigma_m) -> array (T+1,)`: `sigma_t` for `t = 1..T`; entry 0 is `nan`.
   - `de_step(X, log_q, alpha_t, alpha_prev, sigma_t, W) -> (X_next, X0_hat, n_degenerate)`.
     This is one synchronous generation. Arguments and returns:
     - `X`: shape (N, D).
     - `log_q`: shape (N,), the log-fitness.
     - `W`: shape (N, D), standard-normal noise supplied by the caller. The function must
       not draw random numbers itself.
     - `n_degenerate`: an `int`, as defined in `method_spec.md` section 5.
   - `run_de(objective, N, T, sigma_m, rng) -> dict`. `objective` is a starter `Objective`.
     Required keys:
     - `final_population`: the (N, 2) array `X_1`
     - `fitness_evaluations`: an `int`
     - `degenerate_rows`: an `int`, the total over all steps

     An optional per-generation history may also be included.
2. `experiments/`: all experiment code and configuration files, plus `RUN.md`. `RUN.md`
   gives the exact command(s) that regenerate every result from scratch inside the
   provided environment, with expected wall time.
3. `results/runs.jsonl`: one record per independent run. Each record contains:
   - `method`, `objective`, `seed`
   - all settings (`N`, `T`, `sigma_m`, baseline hyper-parameters)
   - `fitness_evaluations`
   - `final_population`
   - the per-run metrics you use
   - `degenerate_rows`, for Diffusion Evolution and DE-based controls
4. `results/summary.json`: aggregated metrics. For each entry, state the aggregation
   (e.g. median/IQR over seeds) and the number of runs.
5. `evidence/hypothesis_map.json`: for each of H1–H4, give:
   - the experiments and result keys that bear on it
   - the pre-declared values and thresholds
   - the verdict
   - a conclusion of at most 3 sentences
   - the main uncertainties and limitations
6. `evidence/deviations.json`: a list of every departure from `method_spec.md` (an empty
   list if none), each with its rationale and the results it affects.
7. Optional: `figures/`, together with the code that generated them.

Do not write a separate narrative research report.
