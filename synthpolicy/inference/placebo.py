"""Placebo-based inference for synthetic control.

* Placebo in space: re-run the method pretending each donor was treated. If the real treated
  unit's post/pre RMSPE ratio does not stand out from the placebo ratios, the "effect" is
  indistinguishable from noise (Abadie, Diamond & Hainmueller 2010, 2015).
* Placebo in time: pretend the policy started earlier, using only data from before the real
  policy. A large "effect" where none can exist means the method is picking up something else.
* Leave-one-out: drop each donor with positive weight in turn. A result that hinges on a single
  donor deserves scepticism.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from ..model.synth import PanelData, Predictor, SynthResult, SynthSpec, fit_synth

Progress = Callable[[int, int, str], None]


# --------------------------------------------------------------------------- placebo in space


@dataclass
class PlaceboSpaceResult:
    treated: str
    treatment_time: int
    fits: dict[str, SynthResult]

    @property
    def gaps(self) -> pd.DataFrame:
        """Periods x units matrix of gaps (actual minus synthetic)."""
        return pd.DataFrame({u: f.gap for u, f in self.fits.items()})

    @property
    def stats(self) -> pd.DataFrame:
        t = self.fits[self.treated]
        rows = []
        for u, f in self.fits.items():
            rows.append(
                {
                    "unit": u,
                    "is_treated": u == self.treated,
                    "pre_rmspe": f.pre_rmspe,
                    "post_rmspe": f.post_rmspe,
                    "rmspe_ratio": f.rmspe_ratio,
                    "mean_post_gap": f.mean_post_gap,
                    "pre_mspe_multiple": (f.pre_rmspe / t.pre_rmspe) ** 2 if t.pre_rmspe > 0 else np.inf,
                }
            )
        df = pd.DataFrame(rows).set_index("unit")
        df["ratio_rank"] = df["rmspe_ratio"].rank(ascending=False, method="min").astype(int)
        return df.sort_values("ratio_rank")

    def filtered_stats(self, max_pre_mspe_multiple: float | None = None) -> pd.DataFrame:
        """Drop placebos whose pre-period MSPE exceeds ``multiple`` x the treated unit's (ADH 2010)."""
        s = self.stats
        if max_pre_mspe_multiple is not None:
            s = s[(s["pre_mspe_multiple"] <= max_pre_mspe_multiple) | s["is_treated"]]
        return s

    def p_value(self, max_pre_mspe_multiple: float | None = None, statistic: str = "rmspe_ratio") -> float:
        """Share of units (treated included) whose statistic is at least as extreme as the treated unit's.

        ``rmspe_ratio`` is one-sided by construction; ``mean_post_gap`` is compared in absolute value.
        """
        s = self.filtered_stats(max_pre_mspe_multiple)
        x = s[statistic].abs() if statistic == "mean_post_gap" else s[statistic]
        return float((x >= x.loc[self.treated] - 1e-12).sum() / len(x))

    def summary(self, multiples: tuple[float, ...] = (20, 5, 2)) -> dict:
        s = self.stats
        out = {
            "n_units": len(s),
            "treated_ratio_rank": int(s.loc[self.treated, "ratio_rank"]),
            "p_value_ratio": self.p_value(),
            "p_value_mean_gap": self.p_value(statistic="mean_post_gap"),
            "min_attainable_p": 1 / len(s),
            "filtered": {},
        }
        for m in multiples:
            fs = self.filtered_stats(m)
            out["filtered"][str(m)] = {
                "n_units": len(fs),
                "p_value_ratio": self.p_value(m),
                "p_value_mean_gap": self.p_value(m, "mean_post_gap"),
            }
        return out


def _placebo_spec(spec: SynthSpec, unit: str) -> SynthSpec:
    if unit == spec.treated:
        return spec
    # The real treated unit is never a donor for a placebo: it is contaminated by the policy.
    return replace(spec, treated=unit, donors=tuple(d for d in spec.donors if d != unit))


def _fit_one(args: tuple[PanelData, SynthSpec]) -> SynthResult:
    return fit_synth(*args)


def placebo_in_space(
    data: PanelData,
    spec: SynthSpec,
    *,
    base: SynthResult | None = None,
    n_jobs: int = 1,
    progress: Progress | None = None,
) -> PlaceboSpaceResult:
    units = [spec.treated, *spec.donors]
    specs = {u: _placebo_spec(spec, u) for u in units}
    fits: dict[str, SynthResult] = {}
    if base is not None:
        fits[spec.treated] = base
    todo = [u for u in units if u not in fits]
    if n_jobs > 1:
        with ProcessPoolExecutor(max_workers=n_jobs) as pool:
            for i, (u, res) in enumerate(zip(todo, pool.map(_fit_one, [(data, specs[u]) for u in todo]))):
                fits[u] = res
                if progress:
                    progress(i + 1, len(todo), u)
    else:
        for i, u in enumerate(todo):
            fits[u] = fit_synth(data, specs[u])
            if progress:
                progress(i + 1, len(todo), u)
    return PlaceboSpaceResult(spec.treated, spec.treatment_time, {u: fits[u] for u in units})


# --------------------------------------------------------------------------- placebo in time


@dataclass
class PlaceboTimeResult:
    fake_time: int
    real_time: int
    fit: SynthResult
    dropped_predictors: list[str] = field(default_factory=list)

    @property
    def placebo_gap(self) -> pd.Series:
        g = self.fit.gap
        return g[(g.index >= self.fake_time) & (g.index < self.real_time)]

    def summary(self) -> dict:
        return {
            "fake_time": self.fake_time,
            "pre_rmspe": self.fit.pre_rmspe,
            "placebo_post_rmspe": self.fit.post_rmspe,
            "rmspe_ratio": self.fit.rmspe_ratio,
            "mean_placebo_gap": float(self.placebo_gap.mean()),
            "weights": {k: float(v) for k, v in self.fit.top_weights().items()},
            "dropped_predictors": self.dropped_predictors,
        }


def placebo_spec_in_time(
    data: PanelData, spec: SynthSpec, fake_time: int, shift_predictors: bool = True
) -> tuple[SynthSpec, list[str]]:
    """Spec for a fake treatment date; uses only data from before the real treatment date.

    Predictor windows are shifted back by the same offset as the treatment date (so "the 3
    years before treatment" stays "the 3 years before treatment"), then clipped to the new
    pre-period. Predictors with no data left for some unit are dropped and reported.
    """
    if fake_time >= spec.treatment_time:
        raise ValueError("Placebo date must precede the real treatment date")
    first = spec.start if spec.start is not None else data.times[0]
    offset = fake_time - spec.treatment_time
    units = [spec.treated, *spec.donors]
    kept: list[Predictor] = []
    dropped: list[str] = []
    for p in spec.predictors:
        q = p.shifted(offset) if shift_predictors else p
        q = q.clipped(first, fake_time - 1)
        if q is None:
            dropped.append(p.name)
            continue
        w = data.wide(q.variable)
        cols = [t for t in q.years if t in w.columns]
        if not cols or w.loc[units, cols].notna().any(axis=1).sum() < len(units):
            dropped.append(p.name)
            continue
        kept.append(q)
    if spec.predictors and not kept:
        dropped.append("(all predictors dropped: falling back to pre-period outcomes)")
    new = replace(
        spec,
        treatment_time=fake_time,
        end=spec.treatment_time - 1,
        predictors=tuple(kept),
        optimize_start=None,
        optimize_end=None,
    )
    return new, dropped


def placebo_in_time(data: PanelData, spec: SynthSpec, fake_time: int, shift_predictors: bool = True) -> PlaceboTimeResult:
    new, dropped = placebo_spec_in_time(data, spec, fake_time, shift_predictors)
    return PlaceboTimeResult(fake_time, spec.treatment_time, fit_synth(data, new), dropped)


# --------------------------------------------------------------------------- leave-one-out


@dataclass
class LeaveOneOutResult:
    base: SynthResult
    fits: dict[str, SynthResult]

    @property
    def synthetics(self) -> pd.DataFrame:
        return pd.DataFrame({f"without {d}": f.synthetic for d, f in self.fits.items()})

    @property
    def stats(self) -> pd.DataFrame:
        rows = [
            {
                "dropped": d,
                "dropped_weight": float(self.base.weights[d]),
                "pre_rmspe": f.pre_rmspe,
                "mean_post_gap": f.mean_post_gap,
                "last_gap": float(f.gap.iloc[-1]),
            }
            for d, f in self.fits.items()
        ]
        return pd.DataFrame(rows).set_index("dropped") if rows else pd.DataFrame()

    def summary(self) -> dict:
        s = self.stats
        base = self.base.mean_post_gap
        if s.empty:
            return {"n_refits": 0}
        return {
            "n_refits": len(s),
            "base_mean_post_gap": base,
            "min_mean_post_gap": float(s["mean_post_gap"].min()),
            "max_mean_post_gap": float(s["mean_post_gap"].max()),
            "sign_flips": int((np.sign(s["mean_post_gap"]) != np.sign(base)).sum()),
            "most_influential": str((s["mean_post_gap"] - base).abs().idxmax()),
        }


def leave_one_out(
    data: PanelData, spec: SynthSpec, base: SynthResult, *, min_weight: float = 1e-3, progress: Progress | None = None
) -> LeaveOneOutResult:
    drop = [d for d in base.top_weights(min_weight).index if len(spec.donors) > 1]
    fits = {}
    for i, d in enumerate(drop):
        fits[d] = fit_synth(data, replace(spec, donors=tuple(x for x in spec.donors if x != d)))
        if progress:
            progress(i + 1, len(drop), d)
    return LeaveOneOutResult(base, fits)
