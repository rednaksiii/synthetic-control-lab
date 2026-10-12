"""Run a complete study from a spec: donor pool, fit, placebos, leave-one-out, SDID, decision rule."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd

from .data.panel import load_state_panel
from .data.prop99 import load_prop99
from .data.states import ADJACENCY
from .inference.placebo import (
    LeaveOneOutResult,
    PlaceboSpaceResult,
    PlaceboTimeResult,
    leave_one_out,
    placebo_in_space,
    placebo_spec_in_time,
)
from .model.synth import PanelData, SynthResult, SynthSpec, fit_synth
from .robustness.sdid import SDIDComparison, compare_estimators
from .spec import OUTCOME_ALIAS, StudySpec, load_spec, lock_status

log = logging.getLogger(__name__)

StageProgress = Callable[[str, int, int], None]


# --------------------------------------------------------------------------- data preparation


def load_dataset(spec: StudySpec) -> pd.DataFrame:
    if spec.dataset == "prop99":
        return load_prop99()
    if spec.dataset == "state_panel":
        return load_state_panel()
    path = Path(spec.dataset)
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def window(spec: StudySpec, df: pd.DataFrame) -> tuple[int, int]:
    years = df[spec.time]
    return int(spec.start if spec.start is not None else years.min()), int(spec.end if spec.end is not None else years.max())


def apply_transform(df: pd.DataFrame, spec: StudySpec, base_end: int | None = None) -> pd.DataFrame:
    """Add the transformed outcome column. The baseline window never extends past ``base_end``."""
    if spec.transform == "none":
        return df
    start, _ = window(spec, df)
    lo = spec.base_start if spec.base_start is not None else start
    hi = spec.base_end if spec.base_end is not None else spec.treatment_time - 1
    if base_end is not None:
        hi = min(hi, base_end)
    if hi >= spec.treatment_time:
        raise ValueError("The outcome baseline window must end before the first treated period")
    y = df[spec.outcome].astype(float)
    if spec.transform in ("log", "log_demeaned") and (y <= 0).any():
        raise ValueError(f"{spec.outcome} has non-positive values; cannot take logs")
    out = df.copy()
    if spec.transform == "log":
        out[spec.outcome_column] = np.log(y)
        return out
    in_base = df[spec.time].between(lo, hi)
    base_vals = np.log(y) if spec.transform == "log_demeaned" else y
    base = base_vals.where(in_base).groupby(df[spec.unit]).transform("mean")
    if spec.transform == "index":
        out[spec.outcome_column] = 100 * y / base
    else:
        out[spec.outcome_column] = 100 * (np.log(y) - base)
    return out


def select_donors(df: pd.DataFrame, spec: StudySpec) -> tuple[list[str], dict[str, str]]:
    """Apply the pre-registered donor rules; return (donors, {excluded unit: reason})."""
    units = sorted(df[spec.unit].astype(str).unique())
    if spec.treated not in units:
        raise KeyError(f"Treated unit {spec.treated!r} not in data")
    pool = [u for u in units if u != spec.treated] if spec.donor_pool == "all" else list(spec.donor_pool)
    excluded: dict[str, str] = {}
    if spec.donor_pool != "all":
        for u in units:
            if u != spec.treated and u not in pool:
                excluded[u] = "not in the specified donor pool"
    start, end = window(spec, df)
    by_unit = df.set_index([spec.unit, spec.time])

    def value(u: str, var: str, year: int) -> float:
        try:
            return float(by_unit.loc[(u, year), var])
        except KeyError:
            return float("nan")

    donors = []
    for u in pool:
        reason = None
        if u in spec.exclude:
            reason = f"excluded: {spec.exclude[u]}"
        elif spec.exclude_neighbors and u in ADJACENCY.get(spec.treated, ()):
            reason = f"borders {spec.treated} (spillover risk)"
        else:
            for r in spec.rules:
                v = value(u, r.variable, r.year)
                if np.isnan(v):
                    reason = f"rule: {r.variable} missing in {r.year}"
                elif (r.min is not None and v < r.min) or (r.max is not None and v > r.max):
                    bound = f"> {r.max}" if r.max is not None and v > r.max else f"< {r.min}"
                    reason = f"rule: {r.variable} = {v:.4g} in {r.year} ({bound}){' - ' + r.reason if r.reason else ''}"
                if reason:
                    break
        if reason is None:
            sub = df[(df[spec.unit] == u) & df[spec.time].between(start, end)]
            if sub[spec.outcome].notna().sum() < end - start + 1:
                reason = f"incomplete outcome data in {start}-{end}"
        if reason:
            excluded[u] = reason
        else:
            donors.append(u)
    return donors, excluded


def build_synth_spec(spec: StudySpec, donors: list[str]) -> SynthSpec:
    preds = tuple(replace(p, variable=spec.outcome_column) if p.variable == OUTCOME_ALIAS else p for p in spec.predictors)
    return SynthSpec(
        outcome=spec.outcome_column,
        treated=spec.treated,
        treatment_time=spec.treatment_time,
        donors=tuple(donors),
        predictors=preds,
        start=spec.start,
        end=spec.end,
        optimize_start=spec.optimize_start,
        optimize_end=spec.optimize_end,
        v_method=spec.v_method,  # type: ignore[arg-type]
        n_random_starts=spec.n_random_starts,
        tie_break=spec.tie_break,
    )


def drop_donors_without_predictors(data: PanelData, s: SynthSpec, excluded: dict[str, str]) -> SynthSpec:
    keep = []
    for d in s.donors:
        missing = []
        for p in s.predictors:
            w = data.wide(p.variable)
            cols = [t for t in p.years if t in w.columns]
            if d not in w.index or not cols or w.loc[d, cols].isna().all():
                missing.append(p.name)
        if missing:
            excluded[d] = f"no data for predictor(s) {', '.join(missing)}"
        else:
            keep.append(d)
    return replace(s, donors=tuple(keep))


# --------------------------------------------------------------------------- study


@dataclass
class StudyResult:
    spec: StudySpec
    synth_spec: SynthSpec
    fit: SynthResult
    excluded: dict[str, str]
    placebo_space: PlaceboSpaceResult | None
    placebo_times: list[PlaceboTimeResult]
    loo: LeaveOneOutResult | None
    sdid: SDIDComparison | None
    lock: dict
    decision: dict = field(default_factory=dict)
    published: list[dict] = field(default_factory=list)
    run_at: str = field(default_factory=lambda: dt.datetime.now().astimezone().isoformat(timespec="seconds"))


def analyze(spec: StudySpec, df: pd.DataFrame, lock: dict, *, n_jobs: int = 1, progress: StageProgress | None = None) -> StudyResult:
    def stage(name: str):
        return (lambda i, n, _u: progress(name, i, n)) if progress else None

    tdf = apply_transform(df, spec)
    data = PanelData(tdf, spec.unit, spec.time)
    donors, excluded = select_donors(tdf, spec)
    s = drop_donors_without_predictors(data, build_synth_spec(spec, donors), excluded)
    log.info("%s: %d donors, %d excluded", spec.name, len(s.donors), len(excluded))

    if progress:
        progress("fit", 0, 1)
    fit = fit_synth(data, s)

    pspace = None
    if spec.placebo_in_space:
        pspace = placebo_in_space(data, s, base=fit, n_jobs=n_jobs, progress=stage("placebo in space"))

    ptimes = []
    for i, fake in enumerate(spec.placebo_times):
        if progress:
            progress("placebo in time", i, len(spec.placebo_times))
        # Re-derive the outcome transform so its baseline never uses data from the fake post-period.
        pdata = PanelData(apply_transform(df, spec, base_end=fake - 1), spec.unit, spec.time)
        pspec, dropped = placebo_spec_in_time(pdata, s, fake)
        ptimes.append(PlaceboTimeResult(fake, spec.treatment_time, fit_synth(pdata, pspec), dropped))

    loo = leave_one_out(data, s, fit, progress=stage("leave-one-out")) if spec.leave_one_out else None

    sd = None
    if spec.sdid:
        if progress:
            progress("synthetic DiD", 0, 1)
        sd = compare_estimators(data, s)

    result = StudyResult(spec, s, fit, excluded, pspace, ptimes, loo, sd, lock)
    result.decision = evaluate_decision(result)
    result.published = check_published(result)
    return result


def run_study(spec_path: str | Path, *, n_jobs: int = 1, progress: StageProgress | None = None) -> StudyResult:
    spec = load_spec(spec_path)
    lock = {"state": "replication", "label": "REPLICATION (published specification)"} if spec.status == "replication" else lock_status(spec_path)
    if spec.status == "replication":
        lock |= {k: v for k, v in lock_status(spec_path).items() if k in ("sha256", "locked_at")}
    return analyze(spec, load_dataset(spec), lock, n_jobs=n_jobs, progress=progress)


# --------------------------------------------------------------------------- decision rule


def evaluate_decision(r: StudyResult) -> dict:
    d = r.spec.decision
    alpha = float(d.get("alpha", 0.10))
    filt = d.get("mspe_filter")
    min_effect = d.get("min_effect")
    effect = r.fit.mean_post_gap
    checks: list[dict] = []

    def add(name: str, passed: bool | None, value: float | str | None, threshold: str, role: str) -> None:
        checks.append({"check": name, "passed": passed, "value": value, "threshold": threshold, "role": role})

    if "max_pre_rmspe" in d:
        add("Pre-period fit (RMSPE)", r.fit.pre_rmspe <= d["max_pre_rmspe"], r.fit.pre_rmspe, f"<= {d['max_pre_rmspe']}", "fit")
    if min_effect is not None:
        add("Effect size |mean post gap|", abs(effect) >= min_effect, effect, f">= {min_effect} in absolute value", "size")
    p = None
    if r.placebo_space is not None:
        p = r.placebo_space.p_value(filt)
        label = "Placebo-in-space p-value (post/pre RMSPE ratio)" + (f", placebos with pre-MSPE <= {filt}x treated" if filt else "")
        add(label, p <= alpha, p, f"<= {alpha} (minimum attainable {1 / len(r.placebo_space.filtered_stats(filt)):.3f})", "significance")
    if r.placebo_times:
        limit = d.get("max_placebo_time_gap", 0.5 * min_effect if min_effect else None)
        for pt in r.placebo_times:
            g = float(pt.placebo_gap.mean())
            add(f"Placebo in time ({pt.fake_time}) |mean gap|", None if limit is None else abs(g) <= limit, g, f"<= {limit}" if limit else "n/a", "robustness")
    if r.loo is not None and d.get("require_loo_sign_stable", True):
        s = r.loo.summary()
        if s.get("n_refits"):
            add("Leave-one-out: no sign flips", s["sign_flips"] == 0, f"range {s['min_mean_post_gap']:.3g} to {s['max_mean_post_gap']:.3g}", "same sign as main estimate", "robustness")
    if r.sdid is not None and d.get("require_sdid_sign_agreement", True):
        tau = float(r.sdid.estimates.loc["sdid", "estimate"])
        add("Synthetic DiD agrees in sign", np.sign(tau) == np.sign(effect), tau, "same sign as main estimate", "robustness")

    failed = {c["role"] for c in checks if c["passed"] is False}
    direction = "reduction" if effect < 0 else "increase"
    if "fit" in failed:
        verdict = "INCONCLUSIVE: the pre-period fit fails the decision-rule threshold, so the synthetic unit is not a credible counterfactual."
    elif "significance" in failed:
        verdict = f"NO DETECTABLE EFFECT: the estimated gap ({effect:.3g}) is not unusual relative to the placebo distribution (p = {p:.3f})."
    elif "size" in failed:
        verdict = f"UNUSUAL BUT SMALL: the gap ({effect:.3g}) is below the decision-rule threshold for a meaningful effect."
    elif "robustness" in failed:
        bad = [c["check"] for c in checks if c["passed"] is False]
        verdict = f"FRAGILE: a meaningful {direction} ({effect:.3g}) that fails robustness check(s): {'; '.join(bad)}."
    else:
        verdict = f"MEANINGFUL EFFECT: a {direction} of {abs(effect):.3g} on average after treatment, passing every check in the decision rule."
    return {"verdict": verdict, "checks": checks, "alpha": alpha, "mspe_filter": filt}


# --------------------------------------------------------------------------- published-result check


def metric(r: StudyResult, name: str) -> float:
    if name == "mean_post_gap":
        return r.fit.mean_post_gap
    if name == "pre_rmspe":
        return r.fit.pre_rmspe
    if name.startswith("gap_"):
        return float(r.fit.gap.loc[int(name[4:])])
    if name in ("ratio_rank", "p_value_ratio") and r.placebo_space is not None:
        s = r.placebo_space.summary()
        return float(s["treated_ratio_rank"] if name == "ratio_rank" else s["p_value_ratio"])
    for m in ("sdid", "sc", "did"):
        if r.sdid is not None and name in (f"{m}_estimate", f"{m}_se"):
            return float(r.sdid.estimates.loc[m, "estimate" if name.endswith("estimate") else "se"])
    raise KeyError(f"Unknown or unavailable metric {name!r}")


def check_published(r: StudyResult) -> list[dict]:
    pub = r.spec.published
    rows: list[dict] = []
    if not pub:
        return rows
    if "weights" in pub:
        tol = float(pub["weights"].get("tolerance", 0.02))
        target = pub["weights"]["values"]
        for unit in sorted(set(target) | set(r.fit.top_weights(0.01).index)):
            ours = float(r.fit.weights.get(unit, 0.0))
            ref = float(target.get(unit, 0.0))
            rows.append({"item": f"weight: {unit}", "published": ref, "ours": ours, "tolerance": tol, "match": abs(ours - ref) <= tol})
    if "balance" in pub:
        tol = float(pub["balance"].get("tolerance_pct", 1.0))
        for pred, ref in pub["balance"]["values"].items():
            ours = float(r.fit.balance.loc[pred, "synthetic"]) if pred in r.fit.balance.index else float("nan")
            rows.append({"item": f"synthetic {pred}", "published": ref, "ours": ours, "tolerance": f"{tol}%", "match": abs(ours - ref) <= abs(ref) * tol / 100})
    for m in pub.get("metrics", []):
        try:
            ours = metric(r, m["name"])
        except KeyError:
            ours = float("nan")
        tol = float(m.get("tolerance", 0))
        rows.append({"item": m.get("label", m["name"]), "published": m["value"], "ours": ours, "tolerance": tol, "match": abs(ours - m["value"]) <= tol, "note": m.get("note", "")})
    return rows
