"""Faithful implementation and exact comparators for the coupled IV iteration."""
from __future__ import annotations
import numpy as np

def exact_targets(Z, X, Y):
    Z = np.asarray(Z, dtype=np.float64); X = np.asarray(X, dtype=np.float64); Y = np.asarray(Y, dtype=np.float64)
    theta, _, rank_z, _ = np.linalg.lstsq(Z, X, rcond=None)
    fitted = Z @ theta
    beta, _, rank_f, _ = np.linalg.lstsq(fitted, Y, rcond=None)
    if rank_z != Z.shape[1] or rank_f != X.shape[1]:
        raise ValueError('identified full-rank case required')
    return theta, beta, fitted.T @ fitted, Z.T @ Z

def spectral_diagnostics(Z, theta_hat, alpha, eta):
    A = (Z @ theta_hat).T @ (Z @ theta_hat); B = Z.T @ Z
    ea = np.linalg.eigvalsh(A); eb = np.linalg.eigvalsh(B)
    gamma = float(np.max(np.abs(1.0 - alpha * ea)))
    kappa = float(np.max(np.abs(1.0 - eta * eb)))
    return {'gamma': gamma, 'kappa': kappa, 'Lambda': max(gamma, kappa), 'alpha_upper': float(2.0 / ea[-1]), 'eta_upper': float(2.0 / eb[-1]), 'cond_A': float(ea[-1] / ea[0]), 'cond_B': float(eb[-1] / eb[0])}

def run_coupled(Z, X, Y, alpha, eta, iterations, checkpoints=()):
    """Use zero initialization, unnormalized sums, constant steps, and old states in both updates."""
    Z = np.asarray(Z, dtype=np.float64); X = np.asarray(X, dtype=np.float64); Y = np.asarray(Y, dtype=np.float64)
    q, p = Z.shape[1], X.shape[1]
    theta = np.zeros((q, p)); beta = np.zeros(p)
    wanted = set(int(v) for v in checkpoints); trace = {}
    theta_hat, beta_hat, _, _ = exact_targets(Z, X, Y)
    nt = max(float(np.linalg.norm(theta_hat)), np.finfo(float).tiny); nb = max(float(np.linalg.norm(beta_hat)), np.finfo(float).tiny)
    def capture(t):
        te = float(np.linalg.norm(theta-theta_hat)/nt); be = float(np.linalg.norm(beta-beta_hat)/nb)
        trace[str(t)] = {'theta_rel_error': te, 'beta_rel_error': be, 'max_rel_error': max(te, be), 'theta_norm': float(np.linalg.norm(theta)), 'beta_norm': float(np.linalg.norm(beta))}
    if 0 in wanted: capture(0)
    status = 'completed'; completed = 0
    with np.errstate(over='ignore', invalid='ignore'):
        for t in range(iterations):
            old_theta = theta; old_beta = beta
            new_theta = old_theta - eta * (Z.T @ (Z @ old_theta - X))
            new_beta = old_beta - alpha * (old_theta.T @ (Z.T @ (Z @ old_theta @ old_beta - Y)))
            if not (np.isfinite(new_theta).all() and np.isfinite(new_beta).all()):
                status = 'nonfinite'; completed = t; break
            theta, beta = new_theta, new_beta; completed = t + 1
            if np.linalg.norm(theta) > 1e100 or np.linalg.norm(beta) > 1e100:
                status = 'threshold_diverged'; capture(completed); break
            if completed in wanted: capture(completed)
    if str(completed) not in trace: capture(completed)
    return {'status': status, 'iterations_completed': completed, 'trace': trace}
