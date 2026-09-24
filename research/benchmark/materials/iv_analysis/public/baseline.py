"""CPU-only starting resources, NOT an implementation of the evaluated iteration.

Generator follows the Gaussian structural model in the MIT-licensed author
simulation notebook; NumPy implementation and validation written for this task.
See LICENSE.source.txt. No stored outcomes or target-method implementation.
"""
from __future__ import annotations

import numpy as np


def generate(seed: int, n: int = 50, p: int = 5, q: int = 10, noise: float = 1.0) -> dict:
    """Return one independent dataset; latent truths are for evaluation, not fitting.

    Parameter draws and observed samples are both refreshed per seed. This uses
    NumPy Generator, not the author's legacy RNG: identical seeds do NOT mean
    identical author samples. No intercept is added to the centered model.
    """
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (seed, n, p, q)):
        raise ValueError("seed and dimensions must be integers")
    if seed < 0 or not n > q >= p >= 1 or not np.isfinite(noise) or noise < 0:
        raise ValueError("require seed >= 0, n > q >= p >= 1, finite noise >= 0")
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n, q))
    theta = rng.standard_normal((q, p))
    beta = rng.standard_normal(p)
    phi_matrix = rng.standard_normal((p, p))
    phi_vector = rng.standard_normal(p)
    u = rng.standard_normal((n, p))
    x = z @ theta + noise * (u @ phi_matrix) + rng.standard_normal((n, p))
    y = x @ beta + noise * (u @ phi_vector) + rng.standard_normal(n)
    return {"Z": z, "X": x, "Y": y, "beta_true": beta, "theta_true": theta}


def _observations(z, x, y):
    z, x, y = (np.asarray(a, dtype=np.float64) for a in (z, x, y))
    if z.ndim != 2 or x.ndim != 2 or y.ndim != 1 or len(z) != len(x) or len(y) != len(x):
        raise ValueError("expected Z[n,q], X[n,p], Y[n]")
    if not all(np.isfinite(a).all() for a in (z, x, y)):
        raise ValueError("nonfinite observations")
    return z, x, y


def two_stage_least_squares(z, x, y) -> dict:
    """Full-rank, no-intercept 2SLS comparator; not the target gradient algorithm."""
    z, x, y = _observations(z, x, y)
    theta, _, rank_z, _ = np.linalg.lstsq(z, x, rcond=None)
    fitted_x = z @ theta
    beta, _, rank_fitted, _ = np.linalg.lstsq(fitted_x, y, rcond=None)
    if rank_z != z.shape[1] or rank_fitted != x.shape[1]:
        raise ValueError("rank-deficient case outside this baseline's identified regime")
    return {"theta": theta, "beta": beta, "rank_Z": int(rank_z), "rank_fitted_X": int(rank_fitted)}


def ordinary_least_squares(x, y):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("expected finite X[n,p], Y[n]")
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if rank != x.shape[1]:
        raise ValueError("rank-deficient X")
    return beta
