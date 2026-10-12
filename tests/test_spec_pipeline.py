from __future__ import annotations

import numpy as np
import pytest

from synthpolicy.pipeline import analyze, apply_transform, select_donors
from synthpolicy.spec import load_spec, lock_spec, lock_status, spec_from_dict
from tests.conftest import make_panel

SPEC = """
[study]
name = "toy"

[data]
source = "toy.csv"
unit = "unit"
time = "year"

[treatment]
unit = "T"
first_treated_period = 2005

[outcome]
variable = "y"
transform = "log_demeaned"

[donors]
exclude = { D05 = "test exclusion" }

[[donors.rules]]
variable = "x"
year = 2000
max = 1e9

[[predictors]]
variable = "@outcome"
start = 1990
end = 2004

[model]
v_method = "outcomes"

[inference]
placebo_in_time = [2000]

[decision]
min_effect = 1.0
"""


def test_lock_lifecycle(tmp_path):
    p = tmp_path / "toy.toml"
    p.write_text(SPEC)
    assert lock_status(p)["state"] == "unlocked"
    lock_spec(p, "test")
    assert lock_status(p)["state"] == "locked"
    with pytest.raises(FileExistsError):
        lock_spec(p)
    p.write_text(SPEC.replace("min_effect = 1.0", "min_effect = 0.1"))
    st = lock_status(p)
    assert st["state"] == "modified" and "EXPLORATORY" in st["label"]


def test_transform_uses_only_baseline_years(tmp_path):
    p = tmp_path / "toy.toml"
    p.write_text(SPEC)
    spec = load_spec(p)
    df, _ = make_panel()
    out = apply_transform(df, spec)
    col = spec.outcome_column
    base = out[(out["year"] < 2005)].groupby("unit")[col].mean()
    assert np.allclose(base, 0, atol=1e-9)
    changed = df.copy()
    changed.loc[changed["year"] >= 2005, "y"] *= 3
    assert np.allclose(apply_transform(changed, spec).loc[df["year"] < 2005, col], out.loc[df["year"] < 2005, col])


def test_analyze_end_to_end(tmp_path):
    p = tmp_path / "toy.toml"
    p.write_text(SPEC)
    spec = load_spec(p)
    df, truth = make_panel(effect=-10)
    donors, excluded = select_donors(df, spec)
    assert "D05" not in donors and excluded["D05"].startswith("excluded")
    r = analyze(spec, df, lock_status(p))
    assert r.fit.mean_post_gap < -5  # log points
    assert r.placebo_space.summary()["treated_ratio_rank"] == 1
    assert {c["check"].split(" (")[0] for c in r.decision["checks"]} >= {"Effect size |mean post gap|", "Placebo in time"}
    assert r.decision["verdict"].startswith(("MEANINGFUL", "FRAGILE"))


def test_spec_from_dict_validates_transform():
    with pytest.raises(ValueError, match="transform"):
        spec_from_dict({"study": {"name": "x"}, "data": {"source": "x"}, "treatment": {"unit": "T", "first_treated_period": 2000}, "outcome": {"variable": "y", "transform": "sqrt"}})
