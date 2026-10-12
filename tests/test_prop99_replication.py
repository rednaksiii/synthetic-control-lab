"""The validation test: reproduce ADH (2010) and Arkhangelsky et al. (2021) on Proposition 99.

Downloads the pinned, checksummed dataset on first run (cached afterwards).
"""

from __future__ import annotations

import pytest

from synthpolicy.data._http import PROJECT_ROOT
from synthpolicy.inference.placebo import placebo_in_space
from synthpolicy.model.synth import PanelData
from synthpolicy.pipeline import build_synth_spec, load_dataset, select_donors
from synthpolicy.robustness.sdid import did_estimate, panel_matrix, sc_estimate, synthdid_estimate
from synthpolicy.model.synth import fit_synth
from synthpolicy.spec import load_spec

ADH_WEIGHTS = {"Colorado": 0.164, "Connecticut": 0.069, "Montana": 0.199, "Nevada": 0.234, "Utah": 0.334}


@pytest.fixture(scope="module")
def prop99():
    spec = load_spec(PROJECT_ROOT / "specs" / "prop99.toml")
    try:
        df = load_dataset(spec)
    except OSError as exc:  # no network on first run
        pytest.skip(f"Prop 99 data unavailable: {exc}")
    data = PanelData(df, spec.unit, spec.time)
    donors, _ = select_donors(df, spec)
    s = build_synth_spec(spec, donors)
    return data, s, fit_synth(data, s)


def test_donor_pool_is_the_papers(prop99):
    _, s, _ = prop99
    assert len(s.donors) == 38


def test_adh_weights_and_effect(prop99):
    _, _, r = prop99
    for state, w in ADH_WEIGHTS.items():
        assert abs(r.weights[state] - w) < 0.02, state
    assert r.weights.drop(list(ADH_WEIGHTS)).max() < 0.01
    assert abs(r.gap.loc[2000] - (-26)) < 2
    assert -21.5 < r.mean_post_gap < -18
    assert r.pre_rmspe < 2.0


def test_adh_predictor_balance(prop99):
    _, _, r = prop99
    table1 = {"lnincome (1980-1988)": 9.86, "retprice (1980-1988)": 89.41, "beer (1984-1988)": 24.20, "cigsale (1988)": 91.62, "cigsale (1980)": 120.43, "cigsale (1975)": 126.99}
    for k, v in table1.items():
        assert abs(r.balance.loc[k, "synthetic"] - v) / v < 0.01, k


def test_california_ranks_first_among_39(prop99):
    data, s, r = prop99
    res = placebo_in_space(data, s, base=r, n_jobs=4)
    assert res.summary()["treated_ratio_rank"] == 1
    assert res.p_value() == pytest.approx(1 / 39)


def test_synthdid_table1(prop99):
    data, s, _ = prop99
    Y, _, _, N0, T0 = panel_matrix(data, s)
    assert synthdid_estimate(Y, N0, T0).tau == pytest.approx(-15.60, abs=0.01)
    assert sc_estimate(Y, N0, T0).tau == pytest.approx(-19.62, abs=0.01)
    assert did_estimate(Y, N0, T0).tau == pytest.approx(-27.35, abs=0.01)
