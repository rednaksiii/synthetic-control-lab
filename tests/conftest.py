from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from synthpolicy.model.synth import PanelData


def make_panel(effect: float = -5.0, seed: int = 0, n_donors: int = 20, start: int = 1990, t0: int = 2005, end: int = 2012) -> tuple[pd.DataFrame, dict]:
    """Donors follow random walks with drift; the treated unit is an exact convex combination of
    three donors before ``t0`` and gets ``effect`` added from ``t0`` on."""
    rng = np.random.default_rng(seed)
    years = np.arange(start, end + 1)
    donors = {f"D{i:02d}": 100 + rng.normal(0, 10) + np.cumsum(rng.normal(0.5, 2.0, len(years))) for i in range(n_donors)}
    true_w = {"D00": 0.5, "D01": 0.3, "D02": 0.2}
    treated = sum(w * donors[d] for d, w in true_w.items()) + np.where(years >= t0, effect, 0.0)
    rows = [{"unit": u, "year": int(y), "y": float(v), "x": float(v) * 0.1 + rng.normal(0, 0.01)} for u, s in {"T": treated, **donors}.items() for y, v in zip(years, s)]
    return pd.DataFrame(rows), {"weights": true_w, "effect": effect, "t0": t0, "donors": sorted(donors)}


@pytest.fixture
def toy():
    df, truth = make_panel()
    return PanelData(df, "unit", "year"), truth
