"""Released Gaussian generator and exact comparators, copied from asset baseline (SHA-256 c7f54513353ac2025f8fdc68058bd1662f29d9e224c88cc1231ea3cba932b321)."""
from __future__ import annotations
import numpy as np

def generate(seed: int, n: int = 50, p: int = 5, q: int = 10, noise: float = 1.0) -> dict:
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

def ordinary_least_squares(x, y):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("expected finite X[n,p], Y[n]")
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if rank != x.shape[1]:
        raise ValueError("rank-deficient X")
    return beta
