"""Self-checks for the starter code (objectives, metrics, random-search baseline).

Run from this directory:  python test_starter.py
Uses only numpy; does not implement or run Diffusion Evolution. All sizes used
here are arbitrary test values, not recommended experiment settings.
"""

from __future__ import annotations

import inspect
import math
import sys

import numpy as np

from baseline_random_search import random_search
from metrics import (CountingObjective, grid_entropy, optima_covered, select_elites,
                     summarise_population)
from objectives import OBJECTIVES, TWO_PEAK_MAX, get_objective, in_box


def check_optima() -> None:
    for name, obj in OBJECTIVES.items():
        q = obj.normalised_fitness(obj.optima)
        assert np.all(q > 0.999), (name, q)
        if obj.direction == "min":
            assert np.all(obj.raw(obj.optima) < 1e-8), (name, obj.raw(obj.optima))
    assert abs(TWO_PEAK_MAX - 7.957747154594767) < 1e-9


def check_fitness_properties() -> None:
    rng = np.random.default_rng(123)
    X = rng.uniform(-4.0, 4.0, size=(5000, 2))
    for name, obj in OBJECTIVES.items():
        q = obj.fitness(X)
        lq = obj.log_fitness(X)
        assert np.all(q >= 0.0) and np.all(q <= obj.fitness_max * (1 + 1e-12)), name
        finite = np.isfinite(lq)
        assert np.allclose(np.exp(lq[finite]), q[finite], rtol=1e-12, atol=0.0), name
        if obj.direction == "min":
            assert np.all(finite), name  # transform never underflows in log domain
    # far from both peaks the density underflows but its log stays finite
    lq = get_objective("two_peak").log_fitness(np.array([[3.9, -3.9]]))
    assert np.isfinite(lq[0]) and get_objective("two_peak").fitness(np.array([[3.9, -3.9]]))[0] == 0.0


def check_out_of_box() -> None:
    X = np.array([[4.0, 4.0], [4.0 + 1e-9, 0.0], [0.0, -5.0], [-4.0, -4.0],
                  [1e200, 0.0], [np.nan, 0.0]])
    assert in_box(X).tolist() == [True, False, False, True, False, False]
    for name, obj in OBJECTIVES.items():
        q = obj.fitness(X)
        lq = obj.log_fitness(X)
        for i in (1, 2, 4, 5):
            assert q[i] == 0.0 and np.isneginf(lq[i]), (name, i)


def check_entropy() -> None:
    same = np.zeros((20, 2)) + 0.01
    H, n = grid_entropy(same, bins=40)
    assert n == 20 and abs(H) < 1e-12
    edges = np.linspace(-4, 4, 41)
    centres = (edges[:-1] + edges[1:]) / 2
    distinct = np.stack([centres[:32], np.full(32, centres[20])], axis=1)
    H, n = grid_entropy(distinct, bins=40)
    assert n == 32 and abs(H - 5.0) < 1e-12
    two = np.array([[1.0, 1.0]] * 16 + [[-1.0, -1.0]] * 16)
    H, _ = grid_entropy(two + 0.01, bins=40)
    assert abs(H - 1.0) < 1e-12
    H, n = grid_entropy(np.array([[10.0, 10.0]]), bins=40)
    assert n == 0 and math.isnan(H)


def check_elites_and_coverage() -> None:
    Q = np.array([0.1, 0.9, 0.9, 0.3])
    assert select_elites(Q, 2).tolist() == [1, 2]
    him = get_objective("himmelblau")
    assert optima_covered(him.optima, him.optima, 0.05) == 4
    assert optima_covered(him.optima[:1] + 0.01, him.optima, 0.05) == 1


def check_random_search() -> None:
    obj = get_objective("himmelblau")
    res = random_search(obj, budget=3000, n_keep=100, rng=np.random.default_rng(7))
    assert res["fitness_evaluations"] == 3000
    assert res["final_population"].shape == (100, 2)
    assert np.all(np.diff(res["final_fitness"]) <= 0)
    s = summarise_population(obj, res["final_population"], k=10, bins=40, radius=0.2)
    assert s["k"] == 10 and 0.0 <= s["elite_mean_normalised_fitness"] <= 1.0
    c = CountingObjective(obj)
    c.fitness(np.zeros((3, 4, 2)))
    assert c.evaluations == 12


def check_no_protocol_defaults() -> None:
    """Design parameters must be supplied explicitly by the solver."""
    required = {
        random_search: ("budget", "n_keep"),
        summarise_population: ("k", "bins", "radius"),
        grid_entropy: ("bins",),
        select_elites: ("k",),
    }
    for fn, names in required.items():
        params = inspect.signature(fn).parameters
        for name in names:
            assert params[name].default is inspect.Parameter.empty, (fn.__name__, name)


def main() -> int:
    checks = [check_optima, check_fitness_properties, check_out_of_box,
              check_entropy, check_elites_and_coverage, check_random_search,
              check_no_protocol_defaults]
    for fn in checks:
        fn()
        print(f"ok  {fn.__name__}")
    print("starter self-checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
