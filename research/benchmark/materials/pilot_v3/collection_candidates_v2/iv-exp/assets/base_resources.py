"""New benchmark starter: synthetic IV data and least-squares controls.

The structural design and draw order are based on private source notebook
cell 4; see NOTICE.txt. This module deliberately contains no GD target method.
"""
import numpy as np


def generate_data(rng, n, q=10, p=5, noise=1.0):
    Z = rng.normal(size=(n, q))
    theta = rng.normal(size=(q, p))
    beta = rng.normal(size=p)
    Phi = rng.normal(size=(p, p))
    phi = rng.normal(size=p)
    U = rng.normal(size=(n, p))
    E2 = rng.normal(size=(n, p))
    E1 = rng.normal(size=n)
    X = Z @ theta + noise * (U @ Phi) + E2
    Y = X @ beta + noise * (U @ phi) + E1
    return Y, X, Z, beta, theta


def ols(y, design):
    return np.linalg.lstsq(design, y, rcond=None)[0]


def two_sls(y, X, Z):
    theta_hat = ols(X, Z)
    return ols(y, Z @ theta_hat)
