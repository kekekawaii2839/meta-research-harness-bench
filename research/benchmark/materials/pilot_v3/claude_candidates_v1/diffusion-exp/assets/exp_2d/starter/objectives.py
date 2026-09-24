"""Two-dimensional objectives for the Diffusion Evolution EXP task.

Maintainer-written starter code (not author code). Every objective exposes:

* ``raw(X)``          -- the textbook function value, X has shape (..., 2)
* ``fitness(X)``      -- non-negative fitness Q used by every method (higher is better)
* ``log_fitness(X)``  -- log Q, computed stably; -inf outside the search box
* ``optima``          -- array (k, 2) of known optimum locations inside the box
* ``fitness_max``     -- fitness value at the optimum

Fixed conventions (see method_spec.md, section 5):

* Search box B = [-4, 4] x [-4, 4] (closed). For points outside B the fitness is 0
  (log-fitness -inf) for all methods. Points are never clipped or projected by
  this module.
* Minimisation objectives use F = eps / (eps + (f - f_star)^2 / s^2) with
  eps = 1e-3 and s = 1.0 (s is a fixed maintainer value, not a tunable default).
* The two-peak objective uses the raw mixture density as fitness (g = identity).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import numpy as np

BOX_LOW = -4.0
BOX_HIGH = 4.0
EPS_TRANSFORM = 1e-3
TRANSFORM_SCALE = 1.0

TWO_PEAK_SIGMA = 0.1
TWO_PEAK_MEANS = np.array([[1.0, 1.0], [-1.0, -1.0]])


def _as_points(X) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    if X.shape[-1] != 2:
        raise ValueError(f"expected trailing dimension 2, got shape {X.shape}")
    return X


def in_box(X) -> np.ndarray:
    """Boolean mask: True where the point lies in the closed box [-4, 4]^2."""
    X = _as_points(X)
    return np.all((X >= BOX_LOW) & (X <= BOX_HIGH), axis=-1)


# ---------------------------------------------------------------- raw functions

def rosenbrock_raw(X) -> np.ndarray:
    X = _as_points(X)
    x, y = X[..., 0], X[..., 1]
    return 100.0 * (y - x ** 2) ** 2 + (1.0 - x) ** 2


def beale_raw(X) -> np.ndarray:
    X = _as_points(X)
    x, y = X[..., 0], X[..., 1]
    return ((1.5 - x + x * y) ** 2
            + (2.25 - x + x * y ** 2) ** 2
            + (2.625 - x + x * y ** 3) ** 2)


def himmelblau_raw(X) -> np.ndarray:
    X = _as_points(X)
    x, y = X[..., 0], X[..., 1]
    return (x ** 2 + y - 11.0) ** 2 + (x + y ** 2 - 7.0) ** 2


def two_peak_log_density(X) -> np.ndarray:
    """log of [N(z; mu1, s^2 I) + N(z; mu2, s^2 I)] / 2 with normalised 2D Gaussians."""
    X = _as_points(X)
    var = TWO_PEAK_SIGMA ** 2
    d2 = ((X[..., None, :] - TWO_PEAK_MEANS) ** 2).sum(axis=-1)  # (..., 2)
    log_comp = -d2 / (2.0 * var) - math.log(2.0 * math.pi * var)
    return np.logaddexp(log_comp[..., 0], log_comp[..., 1]) - math.log(2.0)


def two_peak_raw(X) -> np.ndarray:
    return np.exp(two_peak_log_density(X))


# ---------------------------------------------------------------- objective type

@dataclass(frozen=True)
class Objective:
    name: str
    direction: str                 # "max" (raw is maximised) or "min" (raw is minimised)
    raw: Callable[[np.ndarray], np.ndarray]
    optima: np.ndarray             # (k, 2) known optimum locations inside the box
    f_star: float                  # optimal raw value
    scale: Optional[float]         # s in the transform; None for the two-peak density
    fitness_max: float             # fitness at an optimum

    def log_fitness(self, X) -> np.ndarray:
        X = _as_points(X)
        inside = in_box(X)
        # Far outside the box the raw polynomials can overflow; those points are
        # masked to -inf below, so the warnings carry no information.
        with np.errstate(over="ignore", invalid="ignore"):
            if self.direction == "max":
                logq = two_peak_log_density(X)
            else:
                dev = (self.raw(X) - self.f_star) / self.scale
                logq = math.log(EPS_TRANSFORM) - np.log(EPS_TRANSFORM + dev ** 2)
        return np.where(inside, logq, -np.inf)

    def fitness(self, X) -> np.ndarray:
        return np.exp(self.log_fitness(X))

    def normalised_fitness(self, X) -> np.ndarray:
        """fitness / fitness_max, in [0, 1]; a reporting convenience only."""
        return self.fitness(X) / self.fitness_max


# Himmelblau minima: standard literature values to 6 decimals (the source lists
# them rounded to 2 decimals); (3, 2) is exact.
HIMMELBLAU_OPTIMA = np.array([
    [3.0, 2.0],
    [-2.805118, 3.131312],
    [-3.779310, -3.283186],
    [3.584428, -1.848126],
])

TWO_PEAK_MAX = 1.0 / (4.0 * math.pi * TWO_PEAK_SIGMA ** 2)  # other peak adds ~exp(-400)

OBJECTIVES: Dict[str, Objective] = {
    "two_peak": Objective("two_peak", "max", two_peak_raw, TWO_PEAK_MEANS.copy(),
                          f_star=TWO_PEAK_MAX, scale=None, fitness_max=TWO_PEAK_MAX),
    "rosenbrock": Objective("rosenbrock", "min", rosenbrock_raw, np.array([[1.0, 1.0]]),
                            f_star=0.0, scale=TRANSFORM_SCALE, fitness_max=1.0),
    "beale": Objective("beale", "min", beale_raw, np.array([[3.0, 0.5]]),
                       f_star=0.0, scale=TRANSFORM_SCALE, fitness_max=1.0),
    "himmelblau": Objective("himmelblau", "min", himmelblau_raw, HIMMELBLAU_OPTIMA.copy(),
                            f_star=0.0, scale=TRANSFORM_SCALE, fitness_max=1.0),
}


def get_objective(name: str) -> Objective:
    try:
        return OBJECTIVES[name]
    except KeyError as exc:
        raise KeyError(f"unknown objective {name!r}; choose from {sorted(OBJECTIVES)}") from exc
