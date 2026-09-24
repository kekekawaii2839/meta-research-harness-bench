"""New benchmark starter: structured Gaussian-mixture data, one first-layer
gradient step, ridge readout and held-out error for a two-layer network.

Newly authored for this development candidate; see NOTICE.txt. It supplies
base infrastructure and the ORIGINAL-ACTIVATION reference model only. It
deliberately contains NO Hermite surrogate: the method under test must be
implemented by the solver from assets/task.md.

Conventions (float64 throughout):
  X has shape (samples, n); y has shape (samples,).
  F has shape (k, n); w has shape (k,).
  Feature matrices Phi have shape (k, samples) and already include 1/sqrt(k).

Thread note: the container has a 2-CPU quota but may report more CPUs; the
controller sets OPENBLAS_NUM_THREADS/OMP_NUM_THREADS. setdefault below only
applies if you import this module before numpy in a fresh process.
"""
import math
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")

import numpy as np  # noqa: E402

ACTIVATIONS = ("relu", "tanh", "sigmoid")


def activation(name):
    """Return (sigma, sigma_prime) for 'relu', 'tanh' or 'sigmoid'.

    The ReLU derivative uses the convention 1[z > 0].
    """
    if name == "relu":
        return (lambda z: np.maximum(z, 0.0)), (lambda z: (z > 0).astype(np.float64))
    if name == "tanh":
        return np.tanh, (lambda z: 1.0 - np.tanh(z) ** 2)
    if name == "sigmoid":
        def sig(z):
            return 0.5 * (1.0 + np.tanh(0.5 * z))  # overflow-free logistic
        return sig, (lambda z: sig(z) * (1.0 - sig(z)))
    raise ValueError("unknown activation: %r" % (name,))


def make_structure(rng, n, beta, alpha):
    """Two-component zero-mean mixture structure with rank-one spikes.

    Component covariances Sigma_c = I_n + theta * g_c g_c^T (c = 1, 2) with the
    SAME theta = n**(beta*(1-alpha)); g_1, g_2 are independent uniformly random
    unit vectors (alignment is not controlled; their overlap is recorded).
    Mixture weights 0.5/0.5, so Cov(x) = Sigma = I + 0.5*theta*(g1 g1^T + g2 g2^T)
    and Tr(Sigma_c) = Tr(Sigma) = n + theta.
    Learning rate eta = n**(beta*alpha).
    Teacher direction xi: uniformly random direction scaled so that
    ||xi|| = 1 / sqrt(||Sigma||) (spectral norm; constant C = 1).
    """
    if not (0.0 <= alpha <= 1.0 and 0.0 <= beta <= 1.0):
        raise ValueError("alpha and beta must lie in [0, 1]")
    theta = float(n) ** (beta * (1.0 - alpha))
    eta = float(n) ** (beta * alpha)
    spikes = []
    for _ in range(2):
        g = rng.standard_normal(n)
        spikes.append(g / np.linalg.norm(g))
    overlap = float(spikes[0] @ spikes[1])
    # Top eigenvalue of I + 0.5*theta*(g1 g1^T + g2 g2^T), exact for unit g1, g2.
    sigma_norm = 1.0 + 0.5 * theta * (1.0 + abs(overlap))
    trace_sigma = n + theta
    xi = rng.standard_normal(n)
    xi = xi / (np.linalg.norm(xi) * math.sqrt(sigma_norm))
    return {
        "n": int(n), "beta": float(beta), "alpha": float(alpha),
        "theta": theta, "eta": eta, "spikes": spikes, "spike_overlap": overlap,
        "sigma_norm": sigma_norm, "trace_sigma": float(trace_sigma), "xi": xi,
    }


def sample_mixture(rng, structure, m, sampling="iid"):
    """Draw m samples x from the mixture and labels y = ReLU(xi^T x) (no label noise).

    sampling="iid": component c ~ Bernoulli(0.5) independently per sample.
    sampling="stratified": exactly m//2 samples from component 1, rest from 2
    (a variant; same per-sample marginal, removes component-count randomness).
    Returns X (m, n), y (m,), c (m,) with c in {0, 1}.
    """
    n = structure["n"]
    if sampling == "iid":
        c = rng.integers(0, 2, size=m)
    elif sampling == "stratified":
        c = np.repeat(np.array([0, 1]), [m // 2, m - m // 2])
    else:
        raise ValueError("sampling must be 'iid' or 'stratified'")
    z = rng.standard_normal((m, n))
    s = math.sqrt(1.0 + structure["theta"]) - 1.0  # (1+s)^2 - 1 = theta
    X = z.copy()
    for j in (0, 1):
        idx = c == j
        g = structure["spikes"][j]
        X[idx] += s * np.outer(z[idx] @ g, g)
    y = np.maximum(X @ structure["xi"], 0.0)
    return X, y, c


def init_weights(rng, structure, k):
    """F rows ~ N(0, I_n / Tr(Sigma)); w ~ N(0, I_k / k)."""
    n = structure["n"]
    F = rng.standard_normal((k, n)) / math.sqrt(structure["trace_sigma"])
    w = rng.standard_normal(k) / math.sqrt(k)
    return F, w


def first_layer_step(F, w, X_tilde, y_tilde, sigma, sigma_prime, eta):
    """One gradient step on F with w fixed: F_hat = F + eta * G, where

    G = (1/m) [ (1/sqrt(k)) (w y~^T - (1/sqrt(k)) w w^T sigma(F X~^T)) (*) sigma'(F X~^T) ] X~

    ((*) = elementwise product). G is the negative gradient of
    (1/(2m)) sum_i (y~_i - k^{-1/2} w^T sigma(F x~_i))^2 with respect to F.
    Always pass the ORIGINAL activation and its derivative here.
    """
    k = F.shape[0]
    m = X_tilde.shape[0]
    pre = F @ X_tilde.T                                   # (k, m)
    residual = y_tilde - (w @ sigma(pre)) / math.sqrt(k)  # (m,)
    G = ((np.outer(w, residual) / math.sqrt(k)) * sigma_prime(pre)) @ X_tilde / m
    return F + eta * G


def features(F_hat, X, act):
    """Phi = act(F_hat X^T) / sqrt(k), shape (k, samples). act is applied elementwise."""
    k = F_hat.shape[0]
    return act(F_hat @ X.T) / math.sqrt(k)


def ridge_readout(Phi, y, lam):
    """Closed-form minimizer of (1/(2m)) sum_i (y_i - w^T Phi[:, i])^2 + (lam/2)||w||^2,

    i.e. (Phi Phi^T + lam * m * I_k) w = Phi y.
    """
    k, m = Phi.shape
    return np.linalg.solve(Phi @ Phi.T + lam * m * np.eye(k), Phi @ y)


def readout_objective(w_hat, Phi, y, lam):
    """Value of the normalized readout objective above at w_hat (training metric)."""
    r = y - Phi.T @ w_hat
    return 0.5 * float(np.mean(r ** 2)) + 0.5 * lam * float(w_hat @ w_hat)


def mse(w_hat, Phi, y):
    """Empirical mean squared error (full squared error, no factor 1/2)."""
    r = y - Phi.T @ w_hat
    return float(np.mean(r ** 2))


def fit_and_evaluate(F_hat, readout_act, X_train, y_train, X_test, y_test, lam):
    """Fit the ridge readout with features built by readout_act and evaluate.

    readout_act(z) must map a (k, samples) pre-activation array to features of
    the same shape. Returns w_hat and train/test metrics.
    """
    Phi_tr = features(F_hat, X_train, readout_act)
    w_hat = ridge_readout(Phi_tr, y_train, lam)
    Phi_te = features(F_hat, X_test, readout_act)
    return {
        "w_hat": w_hat,
        "train_readout_objective": readout_objective(w_hat, Phi_tr, y_train, lam),
        "train_mse": mse(w_hat, Phi_tr, y_train),
        "test_mse": mse(w_hat, Phi_te, y_test),
    }


def nn_reference(F, w, first_stage, readout_train, test, act_name, eta, lam):
    """Original-activation two-layer model: step with sigma, readout with sigma.

    first_stage, readout_train, test are (X, y) pairs drawn independently.
    Returns (F_hat, metrics). F_hat can be reused for any model that shares
    the same first-layer training.
    """
    sigma, sigma_prime = activation(act_name)
    F_hat = first_layer_step(F, w, first_stage[0], first_stage[1], sigma, sigma_prime, eta)
    out = fit_and_evaluate(F_hat, sigma, readout_train[0], readout_train[1], test[0], test[1], lam)
    return F_hat, out
