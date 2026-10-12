"""Least squares over the probability simplex.

Solves ``min ||A w - b||^2 + ridge * ||w||^2`` subject to ``w >= 0`` and ``sum(w) == 1``,
the inner problem of every synthetic control estimator.

A warm start comes from non-negative least squares with the sum-to-one constraint appended as a
heavily weighted row (fast, but only approximately optimal because the weighting makes NNLS
ill-conditioned). A primal active-set method then solves the problem exactly: it repeatedly
solves the equality-constrained problem on the current support, steps back to feasibility when a
weight would turn negative, and adds the donor with the most negative KKT multiplier until all
optimality conditions hold.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import nnls

_PENALTY = 1e3


def simplex_lstsq(A: np.ndarray, b: np.ndarray, ridge: float = 0.0) -> np.ndarray:
    A = np.atleast_2d(np.asarray(A, dtype=float))
    b = np.asarray(b, dtype=float).ravel()
    k, n = A.shape
    if b.shape[0] != k:
        raise ValueError(f"A has {k} rows but b has {b.shape[0]} entries")
    if n == 1:
        return np.ones(1)
    Q = A.T @ A
    if ridge > 0:
        Q = Q + ridge * np.eye(n)
    c = A.T @ b
    return _active_set(Q, c, _warm_start(A, b, ridge))


def _warm_start(A: np.ndarray, b: np.ndarray, ridge: float) -> np.ndarray:
    n = A.shape[1]
    if ridge > 0:
        A = np.vstack([A, np.sqrt(ridge) * np.eye(n)])
        b = np.concatenate([b, np.zeros(n)])
    big = _PENALTY * max(1.0, float(np.abs(A).max()), float(np.abs(b).max()))
    try:
        w, _ = nnls(np.vstack([A, np.full((1, n), big)]), np.append(b, big), maxiter=50 * n)
    except RuntimeError:
        w = np.zeros(n)
    if w.sum() <= 0:
        w = np.zeros(n)
        w[np.argmin(np.sum((A - b[:, None]) ** 2, axis=0))] = 1.0
    return w / w.sum()


def _eqp(Q: np.ndarray, c: np.ndarray, S: list[int]) -> tuple[np.ndarray, float]:
    """Minimise 0.5 x'Qx - c'x over sum(x) = 1 on support S; returns (x_S, nu)."""
    m = len(S)
    K = np.zeros((m + 1, m + 1))
    K[:m, :m] = Q[np.ix_(S, S)]
    K[:m, m] = K[m, :m] = 1.0
    rhs = np.append(c[S], 1.0)
    try:
        sol = np.linalg.solve(K, rhs)
        if not np.all(np.isfinite(sol)) or np.abs(K @ sol - rhs).max() > 1e-8 * max(1.0, np.abs(rhs).max()):
            raise np.linalg.LinAlgError
    except np.linalg.LinAlgError:  # singular when the support exceeds rank(A) + 1
        sol = np.linalg.lstsq(K, rhs, rcond=None)[0]
    return sol[:m], float(sol[m])


def _active_set(Q: np.ndarray, c: np.ndarray, w: np.ndarray, max_iter: int = 500) -> np.ndarray:
    n = w.size
    scale = max(1.0, float(np.abs(Q).max()), float(np.abs(c).max()))
    tol_kkt = 1e-11 * scale
    w = w.copy()
    S = [int(i) for i in np.flatnonzero(w > 0)]
    for _ in range(max_iter):
        xS, nu = _eqp(Q, c, S)
        if np.all(xS > 0):
            w = np.zeros(n)
            w[S] = xS
            mu = Q @ w - c + nu  # KKT multipliers of the w >= 0 constraints
            mu[S] = 0.0
            j = int(np.argmin(mu))
            if mu[j] >= -tol_kkt or j in S:
                break
            S.append(j)
        else:
            wS = w[S]
            down = (xS <= 0) & (wS - xS > 0)
            alpha = float(np.min(wS[down] / (wS[down] - xS[down]))) if down.any() else 0.0
            wS = wS + alpha * (xS - wS)
            keep = wS > 1e-14
            w = np.zeros(n)
            w[np.array(S)[keep]] = wS[keep]
            S = [s for s, k in zip(S, keep) if k]
            if not S:  # cannot happen for a convex problem, but never return garbage
                w[np.argmin(np.diag(Q) - 2 * c)] = 1.0
                break
    w = np.clip(w, 0.0, None)
    return w / w.sum()
