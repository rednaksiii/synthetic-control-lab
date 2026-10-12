from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from scipy.optimize import minimize

from synthpolicy.model.simplex import simplex_lstsq
from synthpolicy.model.synth import PanelData, Predictor, SynthSpec, fit_synth
from tests.conftest import make_panel


def _reference(A, b, ridge=0.0):
    n = A.shape[1]
    f = lambda w: np.sum((A @ w - b) ** 2) + ridge * w @ w  # noqa: E731
    res = minimize(f, np.full(n, 1 / n), method="SLSQP", bounds=[(0, 1)] * n, constraints={"type": "eq", "fun": lambda w: w.sum() - 1}, options={"ftol": 1e-14, "maxiter": 1000})
    x = np.clip(res.x, 0, None)
    x /= x.sum()  # SLSQP may violate the constraints slightly; compare feasible points only
    return x, f(x)


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("shape", [(7, 38), (20, 10), (3, 3)])
def test_simplex_matches_reference(seed, shape):
    rng = np.random.default_rng(seed)
    A = rng.normal(size=shape) * rng.uniform(0.1, 100)
    b = rng.normal(size=shape[0]) * np.abs(A).mean()
    w = simplex_lstsq(A, b)
    assert w.min() >= 0 and abs(w.sum() - 1) < 1e-12
    _, ref_loss = _reference(A, b)
    assert np.sum((A @ w - b) ** 2) <= ref_loss * (1 + 1e-10) + 1e-9
    # KKT: equal gradient on the support, no improving direction off it.
    g = A.T @ (A @ w - b)
    on = w > 0
    scale = np.abs(A.T @ A).max()
    assert np.ptp(g[on]) < 1e-9 * scale
    assert (~on).sum() == 0 or g[~on].min() >= g[on].mean() - 1e-9 * scale


def test_simplex_ridge_and_trivial_cases():
    rng = np.random.default_rng(1)
    A, b = rng.normal(size=(5, 6)), rng.normal(size=5)
    w = simplex_lstsq(A, b, ridge=0.5)
    _, ref_loss = _reference(A, b, ridge=0.5)
    assert np.sum((A @ w - b) ** 2) + 0.5 * w @ w <= ref_loss * (1 + 1e-6)
    assert simplex_lstsq(A[:, :1], b).tolist() == [1.0]
    # Exact convex combination is recovered.
    target = A @ np.array([0.2, 0.8, 0, 0, 0, 0])
    assert np.allclose(simplex_lstsq(A, target)[:2], [0.2, 0.8], atol=1e-6)


@pytest.mark.parametrize("v_method", ["outcomes", "nested", "equal", "regression"])
def test_recovers_known_effect(toy, v_method):
    data, truth = toy
    preds = (Predictor("y", 1990, 1995), Predictor("y", 1996, 2000), Predictor("y", 2001, 2004), Predictor("x", 1990, 2004))
    spec = SynthSpec("y", "T", truth["t0"], tuple(truth["donors"]), preds, v_method=v_method, tie_break=1e-4)
    r = fit_synth(data, spec)
    assert abs(r.weights.sum() - 1) < 1e-9 and r.weights.min() >= 0
    if v_method in ("outcomes", "nested"):
        assert r.pre_rmspe < 0.05
        assert abs(r.mean_post_gap - truth["effect"]) < 0.1
        for d, w in truth["weights"].items():
            assert abs(r.weights[d] - w) < 0.02


def test_no_peeking_at_post_period():
    """Weights and V must not depend on post-treatment outcomes in any way."""
    df, truth = make_panel(effect=-5)
    spec = SynthSpec("y", "T", truth["t0"], tuple(truth["donors"]), (Predictor("y", 1990, 1997), Predictor("y", 1998, 2004), Predictor("x", 1990, 2004)))
    a = fit_synth(PanelData(df, "unit", "year"), spec)
    scrambled = df.copy()
    post = scrambled["year"] >= truth["t0"]
    scrambled.loc[post, "y"] = np.random.default_rng(9).normal(0, 1000, post.sum())
    b = fit_synth(PanelData(scrambled, "unit", "year"), spec)
    assert np.allclose(a.weights, b.weights) and np.allclose(a.v, b.v)
    assert np.allclose(a.gap.loc[: truth["t0"] - 1], b.gap.loc[: truth["t0"] - 1])


def test_rejects_post_period_predictors_and_bad_specs(toy):
    data, truth = toy
    donors = tuple(truth["donors"])
    with pytest.raises(ValueError, match="post-treatment"):
        fit_synth(data, SynthSpec("y", "T", 2005, donors, (Predictor("y", 2000, 2006),)))
    with pytest.raises(ValueError, match="also in the donor pool"):
        SynthSpec("y", "T", 2005, ("T", *donors))
    with pytest.raises(ValueError, match="missing"):
        df = data.df.copy()
        df.loc[(df.unit == "D03") & (df.year == 1999), "y"] = np.nan
        fit_synth(PanelData(df, "unit", "year"), SynthSpec("y", "T", 2005, donors))


def test_optimize_window_and_spec_window(toy):
    data, truth = toy
    spec = SynthSpec("y", "T", truth["t0"], tuple(truth["donors"]), start=1995, end=2010)
    r = fit_synth(data, spec)
    assert r.actual.index[0] == 1995 and r.actual.index[-1] == 2010
    r2 = fit_synth(data, replace(spec, optimize_start=2000))
    assert r2.pre_rmspe < 0.1


def test_flags_non_unique_weights(toy):
    """Inside the convex hull, classic ADH weights are not identified; the fit must say so."""
    data, truth = toy
    preds = (Predictor("y", 1990, 1995), Predictor("y", 1996, 2004), Predictor("x", 1990, 2004))
    r = fit_synth(data, SynthSpec("y", "T", truth["t0"], tuple(truth["donors"]), preds))
    assert any("may not be unique" in n for n in r.notes)
    r = fit_synth(data, SynthSpec("y", "T", truth["t0"], tuple(truth["donors"]), preds, tie_break=1e-4))
    assert not r.notes and r.pre_rmspe < 0.05
