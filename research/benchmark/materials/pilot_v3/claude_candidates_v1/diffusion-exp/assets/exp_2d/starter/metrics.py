"""Evaluation and logging helpers for the 2D Diffusion Evolution EXP task.

Generic, method-agnostic utilities (maintainer-written). They take a final
population and its fitness and return diagnostics; they do not run any optimiser.
Elite size k, grid resolution bins and coverage radius are the solver's choice:
they are required arguments with no defaults and must be reported with results.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np

from objectives import BOX_HIGH, BOX_LOW, Objective


class CountingObjective:
    """Wraps an Objective and counts how many points have been evaluated."""

    def __init__(self, objective: Objective):
        self.objective = objective
        self.evaluations = 0

    def _count(self, X) -> None:
        X = np.asarray(X, dtype=float)
        self.evaluations += int(np.prod(X.shape[:-1]))

    def fitness(self, X) -> np.ndarray:
        self._count(X)
        return self.objective.fitness(X)

    def log_fitness(self, X) -> np.ndarray:
        self._count(X)
        return self.objective.log_fitness(X)


def select_elites(Q, k: int) -> np.ndarray:
    """Indices of the k highest-fitness individuals (ties broken by lower index)."""
    Q = np.asarray(Q, dtype=float)
    k = min(int(k), Q.shape[0])
    return np.argsort(-Q, kind="stable")[:k]


def grid_entropy(points, bins: int, low: float = BOX_LOW,
                 high: float = BOX_HIGH) -> Tuple[float, int]:
    """Shannon entropy in bits, H = -sum_i P_i log2 P_i, of grid-cell occupancy.

    The square [low, high]^2 is split into bins x bins equal cells. Points outside
    the square are not counted; the number of points actually used is returned so
    the caller can report exclusions. Returns (nan, 0) if no point is inside.
    """
    P = np.asarray(points, dtype=float).reshape(-1, 2)
    counts, _, _ = np.histogram2d(P[:, 0], P[:, 1], bins=int(bins),
                                  range=[[low, high], [low, high]])
    n = int(counts.sum())
    if n == 0:
        return float("nan"), 0
    p = counts[counts > 0] / n
    return float(-(p * np.log2(p)).sum()), n


def nearest_optimum(points, optima) -> Tuple[np.ndarray, np.ndarray]:
    """For each point: index of the nearest known optimum and the Euclidean distance."""
    P = np.asarray(points, dtype=float).reshape(-1, 2)
    O = np.asarray(optima, dtype=float).reshape(-1, 2)
    d = np.sqrt(((P[:, None, :] - O[None, :, :]) ** 2).sum(axis=-1))
    idx = d.argmin(axis=1)
    return idx, d[np.arange(P.shape[0]), idx]


def optima_covered(points, optima, radius: float) -> int:
    """Number of distinct known optima with at least one point within `radius`."""
    idx, dist = nearest_optimum(points, optima)
    return int(np.unique(idx[dist <= radius]).size)


def summarise_population(objective: Objective, X, k: int, bins: int,
                         radius: float) -> Dict[str, Any]:
    """Convenience summary of a final population (no fitness-evaluation counting)."""
    X = np.asarray(X, dtype=float).reshape(-1, 2)
    Q = objective.fitness(X)
    elite = select_elites(Q, k)
    Xe = X[elite]
    H, n_used = grid_entropy(Xe, bins=bins)
    raw = objective.raw(Xe)
    return {
        "objective": objective.name,
        "population_size": int(X.shape[0]),
        "fraction_in_box": float(np.mean(np.all((X >= BOX_LOW) & (X <= BOX_HIGH), axis=1))),
        "k": int(Xe.shape[0]),
        "elite_mean_normalised_fitness": float(np.mean(Q[elite]) / objective.fitness_max),
        "elite_median_raw": float(np.median(raw)),
        "elite_entropy_bits": H,
        "elite_points_in_grid": n_used,
        "bins": int(bins),
        "radius": float(radius),
        "elite_optima_covered": optima_covered(Xe, objective.optima, radius),
        "n_known_optima": int(len(objective.optima)),
    }


def _to_jsonable(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    return obj


def append_jsonl(path, record: Dict[str, Any]) -> None:
    """Append one JSON record per line (numpy values converted)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_to_jsonable(record), allow_nan=True) + "\n")


def read_jsonl(path):
    with Path(path).open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
