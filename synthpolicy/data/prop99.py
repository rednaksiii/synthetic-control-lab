"""California Proposition 99 data (Abadie, Diamond & Hainmueller 2010), used to validate the code.

39 states (California plus the 38-state donor pool used in the paper), 1970-2000:
  cigsale     per-capita cigarette sales (packs)
  lnincome    log per-capita personal income
  beer        per-capita beer consumption (gallons)
  age15to24   percent of population aged 15-24 (converted from a share to a percent)
  retprice    average retail cigarette price (cents per pack)
"""

from __future__ import annotations

import logging

import pandas as pd

from ._http import cache_dir, download, sha256

log = logging.getLogger(__name__)

# Pinned to a specific commit so the replication input can never change underneath us.
URL = (
    "https://raw.githubusercontent.com/OscarEngelbrektson/SyntheticControlMethods/"
    "739a36fbf7e9438ad2bc2b0aa4ae937d9355b417/examples/datasets/smoking_data.csv"
)
SHA256 = "d1b537fc9b69bee16ddee19b92869fd1632afa17f3b0744ae72ba2506da7b582"


def load_prop99(refresh: bool = False) -> pd.DataFrame:
    path = download(URL, cache_dir("raw", "prop99") / "smoking_data.csv", refresh=refresh)
    digest = sha256(path)
    if digest != SHA256:
        raise ValueError(f"Prop 99 data checksum mismatch ({digest}); delete {path} and retry")
    df = pd.read_csv(path)
    df["state"] = df["state"].astype(str)
    df["year"] = df["year"].astype(int)
    df["age15to24"] = df["age15to24"] * 100
    if df.shape != (1209, 7) or df["state"].nunique() != 39:
        raise ValueError(f"Unexpected Prop 99 data shape {df.shape}")
    return df.sort_values(["state", "year"]).reset_index(drop=True)
