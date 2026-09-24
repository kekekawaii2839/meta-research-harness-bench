"""Maintainer-only verification of assets/base_resources.py (NOT a released asset).

Run inside the package CPU container with the starter mounted at /starter and
(optionally) the earlier independent maintainer smoke implementation at /smoke.
Checks algebraic semantics and prints baseline ORIGINAL-activation numbers.
No Hermite surrogate is implemented here; these numbers are sanity values,
not findings. Output: one JSON document on stdout.
"""
import json
import math
import os
import platform
import sys
import time

sys.path.insert(0, "/starter")
import base_resources as br  # noqa: E402
import numpy as np  # noqa: E402


def algebra():
    out = {}
    rng = np.random.default_rng(11)
    n, m, k = 12, 16, 9
    st = br.make_structure(rng, n, 0.74, 0.5)
    X, y, _ = br.sample_mixture(rng, st, m)
    F, w = br.init_weights(rng, st, k)
    for name in br.ACTIVATIONS:
        sig, dsig = br.activation(name)
        # use tanh-like smooth check for all; ReLU derivative convention a.e.
        def loss(Fm):
            return 0.5 * float(np.mean((y - (w @ sig(Fm @ X.T)) / math.sqrt(k)) ** 2))
        G = br.first_layer_step(F, w, X, y, sig, dsig, 1.0) - F
        num = np.zeros_like(F)
        e = 1e-6
        for i in range(k):
            for j in range(n):
                Fp = F.copy(); Fp[i, j] += e
                Fm = F.copy(); Fm[i, j] -= e
                num[i, j] = (loss(Fp) - loss(Fm)) / (2 * e)
        out["eq4_G_plus_grad_half_mse_max_abs_" + name] = float(np.max(np.abs(G + num)))
        out["eq4_G_max_abs_" + name] = float(np.max(np.abs(G)))
    sig, _ = br.activation("tanh")
    lam = 1e-2
    Phi = br.features(F, X, sig)
    wh = br.ridge_readout(Phi, y, lam)
    grad = -(Phi @ (y - Phi.T @ wh)) / m + lam * wh
    out["ridge_eq5_stationarity_max_abs"] = float(np.max(np.abs(grad)))
    # logistic implementation vs textbook formula
    z = np.linspace(-30, 30, 1001)
    out["sigmoid_vs_textbook_max_abs"] = float(np.max(np.abs(br.activation("sigmoid")[0](z) - 1 / (1 + np.exp(-z)))))
    # closed-form ||Sigma|| vs eigvalsh
    errs = []
    for a in (0.0, 0.3, 1.0):
        st2 = br.make_structure(np.random.default_rng(3), 60, 0.74, a)
        S = np.eye(60) + 0.5 * st2["theta"] * (np.outer(*[st2["spikes"][0]] * 2) + np.outer(*[st2["spikes"][1]] * 2))
        errs.append(abs(float(np.linalg.eigvalsh(S)[-1]) - st2["sigma_norm"]))
        errs.append(abs(float(np.trace(S)) - st2["trace_sigma"]))
    out["sigma_norm_and_trace_closed_form_max_abs_err"] = max(errs)
    # sampling covariance along spikes: g_c^T Cov(x|c) g_c = 1 + theta; orthogonal dir = 1
    st3 = br.make_structure(np.random.default_rng(5), 40, 0.74, 0.0)
    Xs, ys, cs = br.sample_mixture(np.random.default_rng(6), st3, 200000)
    rel = []
    for j in (0, 1):
        g = st3["spikes"][j]
        v = float(np.var(Xs[cs == j] @ g))
        rel.append(abs(v / (1 + st3["theta"]) - 1))
    out["theta_40"] = st3["theta"]
    out["component_spike_variance_rel_err_max"] = max(rel)
    out["component_fraction_iid"] = float(np.mean(cs))
    Xst, _, cst = br.sample_mixture(np.random.default_rng(6), st3, 1001, sampling="stratified")
    out["stratified_counts"] = [int(np.sum(cst == 0)), int(np.sum(cst == 1))]
    # teacher scale: E[(xi^T x)^2] = xi^T Sigma xi <= 1 by construction
    out["xi_T_x_second_moment_empirical"] = float(np.mean((Xs @ st3["xi"]) ** 2))
    return out


def cross_implementation():
    """Compare with the earlier independent maintainer smoke implementation."""
    if not os.path.exists("/smoke/smoke.py"):
        return {"status": "smoke_not_mounted"}
    sys.path.insert(0, "/smoke")
    import smoke  # noqa: E402
    rng = np.random.default_rng(21)
    n, m, k = 50, 40, 30
    st = br.make_structure(rng, n, 0.74, 0.4)
    X, y, _ = br.sample_mixture(rng, st, m)
    X2, y2, _ = br.sample_mixture(rng, st, m)
    F, w = br.init_weights(rng, st, k)
    out = {}
    for name in br.ACTIVATIONS:
        sig, dsig = br.activation(name)
        ssig, sdsig = smoke.act(name)
        a = br.first_layer_step(F, w, X, y, sig, dsig, st["eta"])
        b = smoke.one_step(F, w[:, None], X, y[:, None], ssig, sdsig, st["eta"])
        out["first_step_max_abs_diff_" + name] = float(np.max(np.abs(a - b)))
        Pa = br.features(a, X2, sig)
        wa = br.ridge_readout(Pa, y2, 1e-4)
        wb = smoke.ridge(ssig(b @ X2.T) / math.sqrt(k), y2[:, None], 1e-4)[:, 0]
        out["ridge_max_abs_diff_" + name] = float(np.max(np.abs(wa - wb)))
    return out


def baseline(seed, alphas, reps, n=1000, beta=0.74, lam=1e-4, test_multiplier=5):
    """ORIGINAL-activation reference model only, fresh everything per replicate."""
    rows = []
    for alpha in alphas:
        for r in range(reps):
            rng = np.random.default_rng([seed, int(round(alpha * 1e6)), r])
            t0 = time.perf_counter()
            st = br.make_structure(rng, n, beta, alpha)
            first = br.sample_mixture(rng, st, n)[:2]
            train = br.sample_mixture(rng, st, n)[:2]
            test = br.sample_mixture(rng, st, test_multiplier * n)[:2]
            F, w = br.init_weights(rng, st, n)
            t_setup = time.perf_counter() - t0
            for name in br.ACTIVATIONS:
                t1 = time.perf_counter()
                _, res = br.nn_reference(F, w, first, train, test, name, st["eta"], lam)
                rows.append(dict(alpha=alpha, replicate=r, activation=name,
                                 theta=st["theta"], eta=st["eta"], sigma_norm=st["sigma_norm"],
                                 test_mse=res["test_mse"], train_mse=res["train_mse"],
                                 train_readout_objective=res["train_readout_objective"],
                                 label_variance_test=float(np.var(test[1])),
                                 label_second_moment_test=float(np.mean(test[1] ** 2)),
                                 fit_seconds=time.perf_counter() - t1, setup_seconds=t_setup))
    return rows


def main():
    cfg = {"seed": 20260924, "alphas": [0.0, 0.5263157894736842, 1.0], "reps": 2}
    if len(sys.argv) > 1:
        cfg.update(json.loads(sys.argv[1]))
    t0 = time.perf_counter()
    out = {"algebra": algebra(), "cross_implementation": cross_implementation()}
    t1 = time.perf_counter()
    out["baseline_rows"] = baseline(cfg["seed"], cfg["alphas"], cfg["reps"])
    fits = [r["fit_seconds"] for r in out["baseline_rows"]]
    out["timing"] = {"checks_s": t1 - t0, "baseline_total_s": time.perf_counter() - t1,
                     "nn_fit_seconds_min_median_max": [min(fits), float(np.median(fits)), max(fits)],
                     "nn_fit_count": len(fits)}
    out["config"] = cfg
    out["env"] = dict(python=sys.version, numpy=np.__version__, platform=platform.platform(),
                      os_cpu_count=os.cpu_count(), OPENBLAS_NUM_THREADS=os.environ.get("OPENBLAS_NUM_THREADS"),
                      uid=os.getuid() if hasattr(os, "getuid") else None)
    try:
        import resource
        out["env"]["max_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception as exc:  # pragma: no cover
        out["env"]["max_rss_kib"] = "unavailable: %s" % exc
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
