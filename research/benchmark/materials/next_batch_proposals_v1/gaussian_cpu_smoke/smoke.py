"""Maintainer-only CPU feasibility smoke for candidate iclr2025-tNn6Hskmti.

Independent minimal NumPy implementation written from arXiv 2503.00856v1
Sec. 2 (Eq. 1-7), Sec. 4 (A.2-A.8) and Theorem 4 (Eq. 16-17). It does NOT
import or execute the authors' notebook. Where a concrete constant is not
fixed by the paper (the paper only gives asymptotic orders), the choice below
follows the notebook Fig1b-alpha.ipynb at commit 257bcd5 and is marked
"[nb cellN]".

Purpose: (1) small-dimension algebraic consistency checks of the method
semantics adjudicated by the maintainer; (2) wall-clock timing of ONE
representative configuration.  It is not a reproduction of the paper's
results and does not validate any finding.

Output: a single JSON document on stdout.
"""

import json
import math
import os
import platform
import sys
import time

import numpy as np
from numpy.polynomial import hermite_e as He

# ---------------------------------------------------------------- model parts


def act(name):
    if name == "relu":
        return (lambda z: np.maximum(z, 0.0)), (lambda z: (z > 0).astype(z.dtype))
    if name == "tanh":
        return np.tanh, (lambda z: 1.0 - np.tanh(z) ** 2)
    if name == "sigmoid":
        s = lambda z: 1.0 / (1.0 + np.exp(-z))
        return s, (lambda z: s(z) * (1.0 - s(z)))
    raise ValueError(name)


def data_structure(rng, n, beta, alpha, d=1):
    """Two zero-mean components, Sigma_c = I + theta * g_c g_c^T (A.3, A.4, Eq.9).

    theta = n**(beta*(1-alpha)) exactly and equal for both components [nb cell9];
    paper only fixes ||Sigma|| order (A.2). Spike directions: random orthonormal
    (QR of Gaussian) [nb cell9]; align=0.
    """
    theta = n ** (beta * (1.0 - alpha))
    g = []
    for _ in range(2):
        q, _ = np.linalg.qr(rng.standard_normal((n, n)))
        g.append(q[:, :d])
    tr = n + d * theta  # Tr(Sigma_c), equal for both components (A.3)
    b = math.sqrt(n / tr)  # A.8 / Eq.16
    # Mixture covariance with rho=0.5 and zero means (A.3)
    sigma = np.eye(n) + 0.5 * theta * (g[0] @ g[0].T) + 0.5 * theta * (g[1] @ g[1].T)
    sig_norm = float(np.linalg.eigvalsh(sigma)[-1])  # ||Sigma|| (PSD => top eigenvalue)
    xi = rng.standard_normal((n, 1))
    xi = xi / (math.sqrt(sig_norm) * np.linalg.norm(xi))  # A.5 with C=1 [nb cell9]
    return dict(theta=theta, g=g, tr=tr, b=b, xi=xi, sig_norm=sig_norm)


def sample(rng, st, m, sampling="iid"):
    """Eq.2 mixture, label y = ReLU(xi^T x), delta=0.

    sampling="iid": component c ~ Bernoulli(0.5) per sample (literal Eq.2).
    sampling="stratified": exactly m//2 per component [nb cell5 variant].
    x | c = z + (sqrt(1+theta)-1) g_c g_c^T z, z~N(0,I)  => Cov = I + theta g g^T.
    """
    n = st["xi"].shape[0]
    if sampling == "iid":
        c = rng.integers(0, 2, size=m)
    else:
        c = np.repeat([0, 1], [m // 2, m - m // 2])
    z = rng.standard_normal((m, n))
    s = math.sqrt(1.0 + st["theta"]) - 1.0
    x = z.copy()
    for j in (0, 1):
        idx = c == j
        gj = st["g"][j]
        x[idx] += s * (z[idx] @ gj) @ gj.T
    y = np.maximum(x @ st["xi"], 0.0)
    return x, y


def hermite_surrogate(sigma, b, max_degree, n_nodes=100):
    """Eq.16 with max polynomial degree D = l-1 (theorem index l = D+1).

    h_j = E[He_j(z) sigma(b z)]; sigma_hat(x) = sum_{j<=D} h_j/j! He_j(x/b) + h*_l * N(0,1),
    h*_l = sqrt(E[sigma(bz)^2] - sum_{j<=D} h_j^2/j!). Gauss-Hermite(e) quadrature.
    """
    nodes, weights = He.hermegauss(n_nodes)
    weights = weights / math.sqrt(2 * math.pi)
    fz = sigma(b * nodes)
    coef = []
    var = float(weights @ fz ** 2)
    for j in range(max_degree + 1):
        hj = float(weights @ (He.hermeval(nodes, [0] * j + [1]) * fz))
        coef.append(hj / math.factorial(j))
        var -= hj ** 2 / math.factorial(j)
    h_star = math.sqrt(max(var, 0.0))
    coef = np.array(coef)

    def f(x, rng):
        return He.hermeval(x / b, coef) + h_star * rng.standard_normal(x.shape)

    return f, coef, h_star


def one_step(F, w, Xt, yt, sigma, dsigma, eta):
    """Eq.3-4: F_hat = F + eta*G, G = negative gradient of (1/(2m)) sum residual^2."""
    k = F.shape[0]
    m = Xt.shape[0]
    Z = F @ Xt.T  # k x m
    r = yt.T - (w.T @ sigma(Z)) / math.sqrt(k)  # 1 x m residual
    G = ((w @ r) * dsigma(Z) / math.sqrt(k)) @ Xt / m
    return F + eta * G


def ridge(Phi, y, lam):
    """Eq.5 argmin: Phi is k x m features already divided by sqrt(k)."""
    k, m = Phi.shape
    return np.linalg.solve(Phi @ Phi.T + lam * m * np.eye(k), Phi @ y)


def metrics(w_hat, Phi, y, lam):
    res = y - Phi.T @ w_hat
    sse = float(np.sum(res ** 2))
    m = y.shape[0]
    pen = 0.5 * lam * float(np.sum(w_hat ** 2))
    return dict(
        eq5_objective=0.5 * sse / m + pen,  # notebook "training loss" [nb cell6/13]
        eq6_training_error=0.5 * sse + pen,  # literal printed Eq.6
        mse=sse / m,  # Eq.7 estimator when evaluated on fresh data
        half_mse=0.5 * sse / m,  # notebook plotted "generalization error"
    )


# ---------------------------------------------------------------- checks


def algebraic_checks(rng):
    """Small-dimension checks of the adjudicated semantics (not scientific results)."""
    out = {}
    n, m, k = 12, 16, 9
    st = data_structure(rng, n, 0.74, 0.5)
    X, y = sample(rng, st, m)
    F = rng.standard_normal((k, n)) / math.sqrt(st["tr"])
    w = rng.standard_normal((k, 1)) / math.sqrt(k)
    sig, dsig = act("tanh")

    def half_mse_loss(Fm):
        return 0.5 * float(np.mean((y.T - (w.T @ sig(Fm @ X.T)) / math.sqrt(k)) ** 2))

    G = (one_step(F, w, X, y, sig, dsig, 1.0) - F)
    num = np.zeros_like(F)
    e = 1e-6
    for i in range(k):
        for j in range(n):
            Fp = F.copy(); Fp[i, j] += e
            Fm_ = F.copy(); Fm_[i, j] -= e
            num[i, j] = (half_mse_loss(Fp) - half_mse_loss(Fm_)) / (2 * e)
    out["eq4_G_equals_neg_grad_half_mse_max_abs_err"] = float(np.max(np.abs(G + num)))
    out["eq4_G_max_abs"] = float(np.max(np.abs(G)))
    lam = 1e-2
    Phi = sig(F @ X.T) / math.sqrt(k)
    wh = ridge(Phi, y, lam)
    grad5 = -(Phi @ (y - Phi.T @ wh)) / m + lam * wh
    out["ridge_solves_eq5_stationarity_max_abs"] = float(np.max(np.abs(grad5)))
    grad6 = -(Phi @ (y - Phi.T @ wh)) + lam * wh
    out["same_w_is_not_stationary_for_eq6_as_objective_max_abs"] = float(np.max(np.abs(grad6)))
    mt = metrics(wh, Phi, y, lam)
    pen = 0.5 * lam * float(np.sum(wh ** 2))
    out["eq6_minus_pen_over_eq5_minus_pen_equals_m"] = (mt["eq6_training_error"] - pen) / (mt["eq5_objective"] - pen)
    out["m"] = m
    # Hermite degree/index mapping: residual variance for ReLU at degree 3 == h*_4^2
    f, coef, hs = hermite_surrogate(act("relu")[0], st["b"], 3)
    out["hermite_degree3_coef_count"] = int(coef.size)
    out["hermite_degree3_h_star_l4"] = hs
    return out


# ---------------------------------------------------------------- timing


def timed_config(cfg):
    rng = np.random.default_rng(cfg["seed"])
    n, m, k = cfg["n"], cfg["m"], cfg["k"]
    beta, alpha, lam, D = cfg["beta"], cfg["alpha"], cfg["lambda"], cfg["max_hermite_degree"]
    eta = n ** (beta * alpha)  # [nb cell13]; paper A.2 gives order only
    t = {}
    t0 = time.perf_counter()
    st = data_structure(rng, n, beta, alpha)
    t["structure_s"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    dataF = sample(rng, st, m, cfg["sampling"])
    data = sample(rng, st, m, cfg["sampling"])
    test = sample(rng, st, cfg["test_multiplier"] * m, cfg["sampling"])
    t["three_datasets_s"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    surr = {a: hermite_surrogate(act(a)[0], st["b"], D) for a in cfg["activations"]}
    t["hermite_coeffs_s"] = time.perf_counter() - t0

    fits = []
    for trial in range(cfg["trials"]):
        F = rng.standard_normal((k, n)) / math.sqrt(st["tr"])  # A.6
        w = rng.standard_normal((k, 1)) / math.sqrt(k)  # A.6
        for a in cfg["activations"]:
            sig, dsig = act(a)
            t0 = time.perf_counter()
            F_hat = one_step(F, w, dataF[0], dataF[1], sig, dsig, eta)
            t_step = time.perf_counter() - t0
            for model in ("nn", "hermite"):
                t1 = time.perf_counter()
                if model == "nn":
                    phi = lambda Z: sig(Z)
                else:  # activation replaced only AFTER first-layer training (Thm 4)
                    phi = lambda Z: surr[a][0](Z, rng)
                Ptr = phi(F_hat @ data[0].T) / math.sqrt(k)
                Pte = phi(F_hat @ test[0].T) / math.sqrt(k)
                wh = ridge(Ptr, data[1], lam)
                mtr = metrics(wh, Ptr, data[1], lam)
                mte = metrics(wh, Pte, test[1], 0.0)
                el = time.perf_counter() - t1
                fits.append(dict(trial=trial, activation=a, model=model,
                                 first_step_s=t_step, readout_and_eval_s=el,
                                 fit_total_s=el + (t_step if model == "nn" else 0.0),
                                 train_eq5_objective=mtr["eq5_objective"],
                                 test_mse=mte["mse"], test_half_mse=mte["half_mse"]))
    per_fit = [f["readout_and_eval_s"] + f["first_step_s"] for f in fits]
    return dict(config=cfg, eta=eta, theta=st["theta"], b=st["b"],
                sigma_spectral_norm=st["sig_norm"], eta_times_sigma_norm=eta * st["sig_norm"],
                n_pow_beta=n ** beta, setup_timing_s=t, fits=fits,
                per_fit_seconds_including_first_step=dict(
                    min=min(per_fit), median=float(np.median(per_fit)), max=max(per_fit), count=len(per_fit)))


def main():
    cfg = dict(n=1000, m=1000, k=1000, beta=0.74, alpha=float(np.linspace(0, 1, 20)[10]),
               **{"lambda": 1e-4}, max_hermite_degree=3, test_multiplier=5, trials=2,
               activations=["relu", "tanh", "sigmoid"], sampling="iid", seed=20260924)
    if len(sys.argv) > 1:
        cfg.update(json.loads(sys.argv[1]))
    wall0 = time.perf_counter()
    checks = algebraic_checks(np.random.default_rng(7))
    res = timed_config(cfg)
    res["algebraic_checks"] = checks
    res["total_wall_s"] = time.perf_counter() - wall0
    res["env"] = dict(python=sys.version, numpy=np.__version__, platform=platform.platform(),
                      os_cpu_count=os.cpu_count(),
                      OPENBLAS_NUM_THREADS=os.environ.get("OPENBLAS_NUM_THREADS"),
                      uid=os.getuid() if hasattr(os, "getuid") else None)
    try:
        import resource
        res["env"]["max_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception as exc:  # pragma: no cover
        res["env"]["max_rss_kib"] = f"unavailable: {exc}"
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
