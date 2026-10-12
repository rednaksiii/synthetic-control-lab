"""Synthetic difference-in-differences (Arkhangelsky, Athey, Hirshberg, Imbens & Wager 2021).

A port of the reference R implementation (github.com/synth-inference/synthdid), including its
Frank-Wolfe solver, weight sparsification and placebo standard errors, so that results can be
checked against the published California Proposition 99 numbers:

    SDID -15.6 (8.4)    SC -19.6 (9.9)    DiD -27.3 (17.7)      [Table 1 of the paper]

SDID re-weights both units (omega, like synthetic control but with an intercept, so the
synthetic unit only has to run *parallel* to the treated one) and pre-treatment periods
(lambda, emphasising pre-periods that resemble the post-period). It is more forgiving than
classic SC when the pre-period fit is imperfect.

The panel matrix ``Y`` is units x periods with the N0 control units first and the T0
pre-treatment periods first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from ..model.synth import PanelData, SynthSpec

Method = Literal["sdid", "sc", "did"]


@dataclass(frozen=True)
class SDIDOptions:
    zeta_omega: float
    zeta_lambda: float
    omega_intercept: bool
    lambda_intercept: bool
    update_omega: bool
    update_lambda: bool
    min_decrease: float
    max_iter: int
    max_iter_pre_sparsify: int
    sparsify: bool


@dataclass
class SDIDFit:
    tau: float
    omega: np.ndarray
    lam: np.ndarray
    Y: np.ndarray
    N0: int
    T0: int
    opts: SDIDOptions
    method: str

    def trajectories(self) -> tuple[np.ndarray, np.ndarray]:
        """(treated mean path, synthetic path shifted by the method's intercept)."""
        treated = self.Y[self.N0 :].mean(axis=0)
        control = self.omega @ self.Y[: self.N0]
        shift = float(self.lam @ (treated[: self.T0] - control[: self.T0])) if self.lam.sum() > 0 else 0.0
        return treated, control + shift


def noise_level(Y: np.ndarray, N0: int, T0: int) -> float:
    return float(np.diff(Y[:N0, :T0], axis=1).std(ddof=1))


def collapsed_form(Y: np.ndarray, N0: int, T0: int) -> np.ndarray:
    top = np.column_stack([Y[:N0, :T0], Y[:N0, T0:].mean(axis=1)])
    bottom = np.append(Y[N0:, :T0].mean(axis=0), Y[N0:, T0:].mean())
    return np.vstack([top, bottom])


def _fw_step(A: np.ndarray, x: np.ndarray, b: np.ndarray, eta: float) -> np.ndarray:
    Ax = A @ x
    half_grad = (Ax - b) @ A + eta * x
    i = int(np.argmin(half_grad))
    d_x = -x.copy()
    d_x[i] = 1 - x[i]
    if np.all(d_x == 0):
        return x
    d_err = A[:, i] - Ax
    step = -(d_err @ (Ax - b) + eta * (x @ d_x)) / (d_err @ d_err + eta * (d_x @ d_x))
    return x + min(1.0, max(0.0, step)) * d_x


def _sc_weight_fw(
    Y: np.ndarray, zeta: float, intercept: bool, init: np.ndarray | None, min_decrease: float, max_iter: int
) -> np.ndarray:
    """min_x  zeta^2 ||x||^2 + ||Y[:, :-1] x - Y[:, -1]||^2 / rows   over the simplex (Frank-Wolfe)."""
    rows, cols = Y.shape
    T0 = cols - 1
    x = np.full(T0, 1.0 / T0) if init is None else init.astype(float).copy()
    if intercept:
        Y = Y - Y.mean(axis=0)
    A, b = Y[:, :T0], Y[:, T0]
    eta = rows * zeta**2
    vals: list[float] = []
    t = 0
    while t < max_iter and (t < 2 or vals[-2] - vals[-1] > min_decrease**2):
        t += 1
        x = _fw_step(A, x, b, eta)
        err = Y @ np.append(x, -1.0)
        vals.append(zeta**2 * (x @ x) + (err @ err) / rows)
    return x


def _sparsify(v: np.ndarray) -> np.ndarray:
    v = v.copy()
    v[v <= v.max() / 4] = 0
    return v / v.sum()


def synthdid_estimate(
    Y: np.ndarray,
    N0: int,
    T0: int,
    *,
    omega: np.ndarray | None = None,
    lam: np.ndarray | None = None,
    update_omega: bool | None = None,
    update_lambda: bool | None = None,
    eta_omega: float | None = None,
    eta_lambda: float = 1e-6,
    zeta_omega: float | None = None,
    zeta_lambda: float | None = None,
    omega_intercept: bool = True,
    lambda_intercept: bool = True,
    min_decrease: float | None = None,
    max_iter: int = 10_000,
    max_iter_pre_sparsify: int = 100,
    sparsify: bool = True,
    method: str = "sdid",
) -> SDIDFit:
    Y = np.asarray(Y, dtype=float)
    N, T = Y.shape
    if not (0 < N0 < N and 0 < T0 < T):
        raise ValueError("Need at least one control, one treated unit, one pre and one post period")
    N1, T1 = N - N0, T - T0
    sigma = noise_level(Y, N0, T0)
    if eta_omega is None:
        eta_omega = (N1 * T1) ** 0.25
    opts = SDIDOptions(
        zeta_omega=eta_omega * sigma if zeta_omega is None else zeta_omega,
        zeta_lambda=eta_lambda * sigma if zeta_lambda is None else zeta_lambda,
        omega_intercept=omega_intercept,
        lambda_intercept=lambda_intercept,
        update_omega=omega is None if update_omega is None else update_omega,
        update_lambda=lam is None if update_lambda is None else update_lambda,
        min_decrease=1e-5 * sigma if min_decrease is None else min_decrease,
        max_iter=max_iter,
        max_iter_pre_sparsify=max_iter_pre_sparsify,
        sparsify=sparsify,
    )
    return _estimate(Y, N0, T0, omega, lam, opts, method)


def _estimate(
    Y: np.ndarray, N0: int, T0: int, omega: np.ndarray | None, lam: np.ndarray | None, o: SDIDOptions, method: str
) -> SDIDFit:
    N, T = Y.shape
    Yc = collapsed_form(Y, N0, T0)

    def solve(M: np.ndarray, zeta: float, intercept: bool, init: np.ndarray | None) -> np.ndarray:
        x = _sc_weight_fw(M, zeta, intercept, init, o.min_decrease, o.max_iter_pre_sparsify)
        if o.sparsify:
            x = _sc_weight_fw(M, zeta, intercept, _sparsify(x), o.min_decrease, o.max_iter)
        return x

    if o.update_lambda:
        lam = solve(Yc[:N0, :], o.zeta_lambda, o.lambda_intercept, lam)
    if o.update_omega:
        omega = solve(Yc[:, :T0].T, o.zeta_omega, o.omega_intercept, omega)
    assert omega is not None and lam is not None
    tau = float(np.append(-omega, np.full(N - N0, 1 / (N - N0))) @ Y @ np.append(-lam, np.full(T - T0, 1 / (T - T0))))
    return SDIDFit(tau, np.asarray(omega, float), np.asarray(lam, float), Y, N0, T0, o, method)


def sc_estimate(Y: np.ndarray, N0: int, T0: int, **kw) -> SDIDFit:
    """Outcome-only synthetic control as defined in the synthdid package (no intercept, no time weights)."""
    kw.setdefault("eta_omega", 1e-6)
    return synthdid_estimate(Y, N0, T0, lam=np.zeros(T0), omega_intercept=False, method="sc", **kw)


def did_estimate(Y: np.ndarray, N0: int, T0: int, **kw) -> SDIDFit:
    return synthdid_estimate(Y, N0, T0, omega=np.full(N0, 1 / N0), lam=np.full(T0, 1 / T0), method="did", **kw)


def placebo_se(fit: SDIDFit, replications: int | None = None, seed: int = 0) -> float:
    """Placebo standard error (Algorithm 4): re-assign treatment to controls and re-estimate.

    With one treated unit there are only N0 distinct placebos, so by default each control is
    used once (exact and deterministic). Pass ``replications`` to sample random permutations as
    the R package does; the paper's Prop 99 SEs (8.4 / 9.9 / 17.7) are one such random draw of
    200, while the exhaustive values are 9.4 / 10.6 / 17.3.
    """
    N1 = fit.Y.shape[0] - fit.N0
    if fit.N0 <= N1:
        raise ValueError("Need more controls than treated units for placebo standard errors")
    n0 = fit.N0 - N1
    if replications is None and N1 == 1:
        orders = [np.append(np.delete(np.arange(fit.N0), j), j) for j in range(fit.N0)]
    else:
        rng = np.random.default_rng(seed)
        orders = [rng.permutation(fit.N0) for _ in range(replications or 200)]
    taus = np.empty(len(orders))
    for r, ind in enumerate(orders):
        om = fit.omega[ind[:n0]]
        om = om / om.sum() if om.sum() > 0 else np.full(n0, 1 / n0)
        taus[r] = _estimate(fit.Y[ind], n0, fit.T0, om, fit.lam, fit.opts, fit.method).tau
    return float(taus.std(ddof=0))


# --------------------------------------------------------------------------- panel wrapper


@dataclass
class SDIDComparison:
    estimates: pd.DataFrame
    """Rows sdid / sc / did; columns estimate, se, ci_low, ci_high."""
    omega: pd.DataFrame
    """Unit weights per method (columns)."""
    lam: pd.Series
    """SDID time weights over pre-treatment periods."""
    trajectories: pd.DataFrame
    """Columns: treated, and one synthetic path per method."""

    def summary(self) -> dict:
        return {
            m: {k: float(v) for k, v in row.items()} for m, row in self.estimates.iterrows()
        } | {"sdid_top_unit_weights": {k: float(v) for k, v in self.omega["sdid"].nlargest(8).items() if v > 1e-3}}


def panel_matrix(data: PanelData, spec: SynthSpec) -> tuple[np.ndarray, list[str], list[int], int, int]:
    times = [t for t in data.times if (spec.start is None or t >= spec.start) and (spec.end is None or t <= spec.end)]
    units = [*spec.donors, spec.treated]
    Y = data.wide(spec.outcome).reindex(index=units, columns=times)
    if Y.isna().any().any():
        raise ValueError(f"Outcome has missing values for {Y.index[Y.isna().any(axis=1)].tolist()}")
    T0 = sum(t < spec.treatment_time for t in times)
    return Y.to_numpy(), units, times, len(spec.donors), T0


def compare_estimators(
    data: PanelData, spec: SynthSpec, *, replications: int | None = None, seed: int = 0, methods: tuple[Method, ...] = ("sdid", "sc", "did")
) -> SDIDComparison:
    Y, units, times, N0, T0 = panel_matrix(data, spec)
    estimators = {"sdid": synthdid_estimate, "sc": sc_estimate, "did": did_estimate}
    rows, omegas, paths = {}, {}, {}
    sdid_fit = None
    for m in methods:
        fit = estimators[m](Y, N0, T0)
        se = placebo_se(fit, replications, seed) if replications != 0 else float("nan")
        rows[m] = {"estimate": fit.tau, "se": se, "ci_low": fit.tau - 1.96 * se, "ci_high": fit.tau + 1.96 * se}
        omegas[m] = pd.Series(fit.omega, index=units[:N0])
        treated, synth = fit.trajectories()
        paths["treated"] = treated
        paths[m] = synth
        if m == "sdid":
            sdid_fit = fit
    lam = pd.Series(sdid_fit.lam if sdid_fit is not None else np.nan, index=times[:T0], name="lambda")
    return SDIDComparison(
        estimates=pd.DataFrame(rows).T,
        omega=pd.DataFrame(omegas),
        lam=lam,
        trajectories=pd.DataFrame(paths, index=times),
    )

