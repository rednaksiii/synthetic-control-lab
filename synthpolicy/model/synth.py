"""Classic synthetic control (Abadie & Gardeazabal 2003; Abadie, Diamond & Hainmueller 2010).

The treated unit's counterfactual is a convex combination of donor units. Donor weights W are
chosen so the synthetic unit reproduces the treated unit's pre-treatment *predictors* (outcome
lags and covariates), with predictor importance V chosen so that the resulting synthetic unit
tracks the treated unit's pre-treatment *outcome path* as closely as possible:

    W*(V) = argmin_W (X1 - X0 W)' V (X1 - X0 W)    s.t. W >= 0, sum(W) = 1
    V*    = argmin_V  mean over pre-period years of (Z1 - Z0 W*(V))^2

Everything is fitted on pre-treatment data only. Post-treatment outcomes are never seen by the
optimiser; they are used only to compute the gap afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .simplex import simplex_lstsq

VMethod = Literal["nested", "equal", "regression", "outcomes"]


@dataclass(frozen=True)
class Predictor:
    """One row of the predictor matrix: ``variable`` averaged over the years ``start..end``."""

    variable: str
    start: int
    end: int | None = None
    label: str | None = None

    @property
    def last(self) -> int:
        return self.start if self.end is None else self.end

    @property
    def years(self) -> range:
        return range(self.start, self.last + 1)

    @property
    def name(self) -> str:
        if self.label:
            return self.label
        if self.last == self.start:
            return f"{self.variable} ({self.start})"
        return f"{self.variable} ({self.start}-{self.last})"

    def shifted(self, offset: int) -> Predictor:
        return replace(self, start=self.start + offset, end=None if self.end is None else self.end + offset, label=None)

    def clipped(self, lo: int, hi: int) -> Predictor | None:
        start, last = max(self.start, lo), min(self.last, hi)
        if start > last:
            return None
        return replace(self, start=start, end=None if start == last else last, label=None)


@dataclass(frozen=True)
class SynthSpec:
    """Everything that defines one synthetic control fit."""

    outcome: str
    treated: str
    treatment_time: int
    """First period in which the policy is in effect (or could have been anticipated)."""
    donors: tuple[str, ...]
    predictors: tuple[Predictor, ...] = ()
    """Empty means: use the outcome in every pre-treatment period."""
    start: int | None = None
    end: int | None = None
    optimize_start: int | None = None
    optimize_end: int | None = None
    """Window of pre-treatment periods over which V is chosen (default: whole pre-period)."""
    v_method: VMethod = "nested"
    n_random_starts: int = 4
    seed: int = 0
    tie_break: float = 0.0
    """Weight on standardised pre-period outcome fit inside the W problem (0 = classic ADH).
    When several W match the predictors equally well (the treated unit lies inside the donors'
    convex hull) a small value such as 1e-4 picks the one that best tracks the pre-period
    outcome path. It is not neutral: the V search can exploit it, so it defines a (slightly)
    different estimator and must be chosen before seeing results."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "donors", tuple(self.donors))
        object.__setattr__(self, "predictors", tuple(self.predictors))
        if self.treated in self.donors:
            raise ValueError(f"Treated unit {self.treated!r} is also in the donor pool")
        if len(set(self.donors)) != len(self.donors):
            raise ValueError("Donor pool contains duplicates")
        if not self.donors:
            raise ValueError("Donor pool is empty")


class PanelData:
    """Long panel with cached wide (unit x period) views of each variable."""

    def __init__(self, df: pd.DataFrame, unit: str, time: str):
        missing = {unit, time} - set(df.columns)
        if missing:
            raise KeyError(f"Panel is missing columns {sorted(missing)}")
        if df.duplicated([unit, time]).any():
            raise ValueError(f"Panel has duplicate ({unit}, {time}) rows")
        self.df = df
        self.unit = unit
        self.time = time
        self._wide: dict[str, pd.DataFrame] = {}

    @property
    def units(self) -> list[str]:
        return sorted(self.df[self.unit].astype(str).unique())

    @property
    def times(self) -> list[int]:
        return sorted(int(t) for t in self.df[self.time].unique())

    @property
    def variables(self) -> list[str]:
        return [c for c in self.df.columns if c not in (self.unit, self.time)]

    def wide(self, variable: str) -> pd.DataFrame:
        if variable not in self._wide:
            if variable not in self.df.columns:
                raise KeyError(f"Variable {variable!r} is not in the panel")
            w = self.df.pivot(index=self.unit, columns=self.time, values=variable)
            w.index = w.index.astype(str)
            w.columns = [int(c) for c in w.columns]
            self._wide[variable] = w.astype(float)
        return self._wide[variable]

    def complete_units(self, variable: str, start: int, end: int) -> list[str]:
        """Units with a non-missing ``variable`` in every period of ``start..end``."""
        w = self.wide(variable)
        cols = [t for t in w.columns if start <= t <= end]
        expected = end - start + 1
        ok = w[cols].notna().sum(axis=1) == expected
        return sorted(ok[ok].index)


@dataclass
class SynthResult:
    spec: SynthSpec
    weights: pd.Series
    v: pd.Series
    balance: pd.DataFrame
    actual: pd.Series
    synthetic: pd.Series
    loss_v: float
    loss_w: float
    notes: list[str] = field(default_factory=list)

    @property
    def gap(self) -> pd.Series:
        return (self.actual - self.synthetic).rename("gap")

    @property
    def pre_index(self) -> pd.Index:
        return self.actual.index[self.actual.index < self.spec.treatment_time]

    @property
    def post_index(self) -> pd.Index:
        return self.actual.index[self.actual.index >= self.spec.treatment_time]

    @property
    def pre_rmspe(self) -> float:
        return _rmspe(self.gap.loc[self.pre_index])

    @property
    def post_rmspe(self) -> float:
        return _rmspe(self.gap.loc[self.post_index])

    @property
    def rmspe_ratio(self) -> float:
        return self.post_rmspe / self.pre_rmspe if self.pre_rmspe > 0 else np.inf

    @property
    def mean_post_gap(self) -> float:
        return float(self.gap.loc[self.post_index].mean())

    @property
    def pre_mape(self) -> float:
        """Mean absolute pre-period error as a percentage of the treated unit's level."""
        a = self.actual.loc[self.pre_index]
        return float((self.gap.loc[self.pre_index].abs() / a.abs()).mean() * 100)

    def top_weights(self, threshold: float = 1e-3) -> pd.Series:
        return self.weights[self.weights > threshold].sort_values(ascending=False)

    def summary(self) -> dict:
        return {
            "treated": self.spec.treated,
            "outcome": self.spec.outcome,
            "treatment_time": self.spec.treatment_time,
            "n_donors": len(self.spec.donors),
            "pre_rmspe": self.pre_rmspe,
            "post_rmspe": self.post_rmspe,
            "rmspe_ratio": self.rmspe_ratio,
            "pre_mape_pct": self.pre_mape,
            "mean_post_gap": self.mean_post_gap,
            "last_gap": float(self.gap.iloc[-1]),
            "weights": {k: float(v) for k, v in self.top_weights().items()},
            "v": {k: float(v) for k, v in self.v.items()},
            "loss_v": self.loss_v,
            "notes": list(self.notes),
        }


def _rmspe(x: pd.Series) -> float:
    return float(np.sqrt(np.mean(np.square(x.to_numpy(dtype=float))))) if len(x) else float("nan")


def resolve_predictors(data: PanelData, spec: SynthSpec, pre_times: list[int]) -> tuple[Predictor, ...]:
    if spec.v_method == "outcomes" or not spec.predictors:
        return tuple(Predictor(spec.outcome, t) for t in pre_times)
    late = [p.name for p in spec.predictors if p.last >= spec.treatment_time]
    if late:
        raise ValueError(f"Predictors use post-treatment periods (>= {spec.treatment_time}): {late}")
    return spec.predictors


def predictor_matrix(data: PanelData, predictors: tuple[Predictor, ...], units: list[str]) -> pd.DataFrame:
    """Predictors x units matrix of window means (missing years are skipped, as in Synth)."""
    rows = {}
    for p in predictors:
        w = data.wide(p.variable)
        cols = [t for t in p.years if t in w.columns]
        rows[p.name] = w.loc[units, cols].mean(axis=1, skipna=True) if cols else pd.Series(np.nan, index=units)
    X = pd.DataFrame(rows).T
    if X.isna().any().any():
        bad = [(r, c) for r in X.index for c in X.columns if pd.isna(X.loc[r, c])]
        raise ValueError(f"Predictors have no data for some units (predictor, unit): {bad[:10]}")
    return X


def fit_synth(data: PanelData, spec: SynthSpec) -> SynthResult:
    times = [t for t in data.times if (spec.start is None or t >= spec.start) and (spec.end is None or t <= spec.end)]
    pre_times = [t for t in times if t < spec.treatment_time]
    if len(pre_times) < 2:
        raise ValueError(f"Need at least two pre-treatment periods, found {pre_times}")
    if not any(t >= spec.treatment_time for t in times):
        raise ValueError("No post-treatment periods in the window")

    units = [spec.treated, *spec.donors]
    Y = data.wide(spec.outcome).reindex(index=units, columns=times)
    if Y.isna().any().any():
        bad = Y.index[Y.isna().any(axis=1)].tolist()
        raise ValueError(f"Outcome {spec.outcome!r} is missing for {bad} within {times[0]}-{times[-1]}")

    opt_lo = spec.optimize_start if spec.optimize_start is not None else pre_times[0]
    opt_hi = spec.optimize_end if spec.optimize_end is not None else pre_times[-1]
    opt_times = [t for t in pre_times if opt_lo <= t <= opt_hi]
    if not opt_times:
        raise ValueError("Optimisation window contains no pre-treatment periods")

    predictors = resolve_predictors(data, spec, pre_times)
    X = predictor_matrix(data, predictors, units)
    sd = X.std(axis=1, ddof=1).replace(0.0, 1.0)
    Xs = X.div(sd, axis=0).to_numpy()
    X1, X0 = Xs[:, 0], Xs[:, 1:]
    Z = Y[opt_times].to_numpy().T  # periods x units
    Z1, Z0 = Z[:, 0], Z[:, 1:]
    z_scale = float(Z.std()) or 1.0
    zt = np.sqrt(spec.tie_break / len(opt_times)) / z_scale

    def solve_w(v: np.ndarray) -> np.ndarray:
        sv = np.sqrt(v)
        A = np.vstack([X0 * sv[:, None], zt * Z0])
        b = np.concatenate([X1 * sv, zt * Z1])
        return simplex_lstsq(A, b)

    def loss_v(v: np.ndarray) -> float:
        r = Z1 - Z0 @ solve_w(v)
        return float(r @ r / r.size)

    k = len(predictors)
    notes: list[str] = []
    if k == 1 or spec.v_method in ("equal", "outcomes"):
        v = np.full(k, 1.0 / k)
    elif spec.v_method == "regression":
        v = _regression_v(Xs, Z)
        if v is None:
            notes.append("Regression-based V was singular; fell back to equal V.")
            v = np.full(k, 1.0 / k)
    elif spec.v_method == "nested":
        v = _optimize_v(loss_v, Xs, Z, k, spec.n_random_starts, spec.seed)
    else:
        raise ValueError(f"Unknown v_method {spec.v_method!r}")

    w = solve_w(v)
    weights = pd.Series(w, index=list(spec.donors), name="weight")
    synthetic = pd.Series(Y.iloc[1:].to_numpy().T @ w, index=times, name="synthetic")
    actual = pd.Series(Y.iloc[0].to_numpy(), index=times, name="actual")
    balance = pd.DataFrame(
        {"treated": X.iloc[:, 0], "synthetic": X.iloc[:, 1:].to_numpy() @ w, "donor_mean": X.iloc[:, 1:].mean(axis=1)}
    )
    resid = X1 - X0 @ w
    loss_w = float(resid @ (v * resid))
    if loss_w < 1e-10 and spec.tie_break == 0 and len(spec.donors) > k + 1:
        notes.append(
            "The predictors are matched exactly, so the donor weights may not be unique (the treated unit "
            "lies inside the donors' convex hull); weights are then solver-dependent. Consider tie_break."
        )
    return SynthResult(
        spec=spec,
        weights=weights,
        v=pd.Series(v, index=[p.name for p in predictors], name="v"),
        balance=balance,
        actual=actual,
        synthetic=synthetic,
        loss_v=loss_v(v),
        loss_w=loss_w,
        notes=notes,
    )


def _regression_v(Xs: np.ndarray, Z: np.ndarray) -> np.ndarray | None:
    """Synth's regression-based starting V: regress pre-period outcomes on predictors across units."""
    design = np.column_stack([np.ones(Xs.shape[1]), Xs.T])
    if np.linalg.matrix_rank(design) < design.shape[1]:
        return None
    beta, *_ = np.linalg.lstsq(design, Z.T, rcond=None)
    d = np.sum(beta[1:] ** 2, axis=1)
    return d / d.sum() if d.sum() > 0 else None


def _optimize_v(loss_v, Xs: np.ndarray, Z: np.ndarray, k: int, n_random: int, seed: int) -> np.ndarray:
    """Nelder-Mead over V from several starts (equal, regression-based, random), keeping the best."""

    def objective(theta: np.ndarray) -> float:
        a = np.abs(theta)
        s = a.sum()
        return np.inf if s <= 0 else loss_v(a / s)

    rng = np.random.default_rng(seed)
    starts = [np.full(k, 1.0 / k)]
    reg = _regression_v(Xs, Z)
    if reg is not None:
        starts.append(reg)
    starts += list(rng.dirichlet(np.ones(k), size=n_random))

    opts = {"maxiter": 400 * k, "maxfev": 600 * k, "xatol": 1e-7, "fatol": 1e-10, "adaptive": True}
    best_x, best_f = starts[0], objective(starts[0])
    for x0 in starts:
        res = minimize(objective, x0, method="Nelder-Mead", options=opts)
        # A restart from the optimum lets the simplex escape premature collapse.
        res = minimize(objective, np.abs(res.x), method="Nelder-Mead", options=opts)
        if res.fun < best_f:
            best_x, best_f = res.x, res.fun
    v = np.abs(best_x)
    return v / v.sum()
