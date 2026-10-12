from __future__ import annotations

import numpy as np

from synthpolicy.inference.placebo import leave_one_out, placebo_in_space, placebo_in_time, placebo_spec_in_time
from synthpolicy.model.synth import PanelData, Predictor, SynthSpec, fit_synth
from synthpolicy.robustness.sdid import did_estimate, noise_level, sc_estimate, synthdid_estimate
from tests.conftest import make_panel


def _spec(truth, **kw):
    return SynthSpec("y", "T", truth["t0"], tuple(truth["donors"]), v_method="outcomes", **kw)


def test_large_effect_ranks_first(toy):
    data, truth = toy
    df, truth = make_panel(effect=-40)
    data = PanelData(df, "unit", "year")
    res = placebo_in_space(data, _spec(truth))
    s = res.summary()
    assert s["treated_ratio_rank"] == 1
    assert np.isclose(res.p_value(), 1 / (len(truth["donors"]) + 1))
    # The treated unit is never a donor in any placebo fit.
    assert all("T" not in f.spec.donors for u, f in res.fits.items() if u != "T")
    assert set(res.gaps.columns) == {"T", *truth["donors"]}


def test_filtered_p_value_keeps_treated(toy):
    data, truth = toy
    res = placebo_in_space(data, _spec(truth))
    f = res.filtered_stats(2)
    assert "T" in f.index and (f.drop("T")["pre_mspe_multiple"] <= 2).all()
    assert 0 < res.p_value(2) <= 1


def test_placebo_in_time_shifts_and_clips_predictors(toy):
    data, truth = toy
    spec = SynthSpec("y", "T", 2005, tuple(truth["donors"]), (Predictor("y", 2000, 2004), Predictor("y", 1990), Predictor("x", 1995, 2004)))
    new, dropped = placebo_spec_in_time(data, spec, 2000)
    assert new.treatment_time == 2000 and new.end == 2004
    names = [p.name for p in new.predictors]
    assert names == ["y (1995-1999)", "x (1990-1999)"]  # 1990 shifted to 1985: no data, dropped
    assert dropped == ["y (1990)"]
    r = placebo_in_time(data, spec, 2000)
    assert r.fit.actual.index.max() == 2004  # real post-period data never used
    # With fewer donors than pre-periods the weights are identified, and nothing should happen
    # between the fake date and the real 2005 policy.
    df8, t8 = make_panel(n_donors=8)
    r = placebo_in_time(PanelData(df8, "unit", "year"), SynthSpec("y", "T", 2005, tuple(t8["donors"]), v_method="outcomes"), 2000)
    assert not r.fit.notes and abs(r.placebo_gap.mean()) < 0.5


def test_leave_one_out_drops_each_positive_weight_donor(toy):
    data, truth = toy
    spec = _spec(truth)
    base = fit_synth(data, spec)
    loo = leave_one_out(data, spec, base)
    assert set(loo.fits) == set(base.top_weights().index)
    for d, f in loo.fits.items():
        assert d not in f.spec.donors


def test_sdid_family_on_toy_panel():
    df, truth = make_panel(effect=-5)
    w = df.pivot(index="unit", columns="year", values="y")
    Y = w.loc[[*truth["donors"], "T"]].to_numpy()
    N0, T0 = len(truth["donors"]), truth["t0"] - 1990
    did = did_estimate(Y, N0, T0)
    manual = (Y[-1, T0:].mean() - Y[-1, :T0].mean()) - (Y[:N0, T0:].mean() - Y[:N0, :T0].mean())
    assert np.isclose(did.tau, manual)
    assert abs(sc_estimate(Y, N0, T0).tau - (-5)) < 0.5
    # SDID spreads weight over many donors (by design), so with random-walk donors it is close but not exact.
    assert abs(synthdid_estimate(Y, N0, T0).tau - (-5)) < 2.0
    assert noise_level(Y, N0, T0) > 0
