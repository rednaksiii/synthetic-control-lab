"""Census American Community Survey (ACS) state estimates via the Census Data API.

The API now requires a free key: request one at https://api.census.gov/data/key_signup.html
and set ``CENSUS_API_KEY``.

ACS 1-year estimates exist from 2005 (no standard 1-year release for 2020); 5-year estimates
from 2009 (labelled by their final year). Note that 5-year estimates overlap, so consecutive
years are not independent: prefer 1-year estimates for state-level synthetic control.
"""

from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

from ._http import cache_dir, cached_frame, session, short_hash
from .states import FIPS_TO_ABBR

log = logging.getLogger(__name__)

API_URL = "https://api.census.gov/data/{year}/acs/{dataset}"
FIRST_YEAR = {"acs1": 2005, "acs5": 2009}
MISSING_YEARS = {"acs1": {2020}, "acs5": set()}

DEFAULT_VARIABLES = {
    "B01003_001E": "acs_population",
    "B19013_001E": "acs_median_household_income",
    "B25064_001E": "acs_median_gross_rent",
    "B25077_001E": "acs_median_home_value",
    "B25003_001E": "acs_occupied_units",
    "B25003_003E": "acs_renter_occupied_units",
}


class MissingKeyError(RuntimeError):
    pass


def parse_response(rows: list[list[str]], variables: dict[str, str], year: int) -> pd.DataFrame:
    header, *data = rows
    df = pd.DataFrame(data, columns=header)
    out = pd.DataFrame({"state_fips": df["state"].str.zfill(2), "year": year})
    for code, name in variables.items():
        v = pd.to_numeric(df[code], errors="coerce")
        out[name] = v.where(v >= 0)  # negative values are Census annotation sentinels (e.g. -666666666)
    return out[out["state_fips"].isin(FIPS_TO_ABBR)].reset_index(drop=True)


def _fetch_year(year: int, dataset: str, variables: dict[str, str], key: str) -> pd.DataFrame:
    params = {"get": ",".join(["NAME", *variables]), "for": "state:*", "key": key}
    r = session().get(API_URL.format(year=year, dataset=dataset), params=params, timeout=120)
    if r.status_code == 404:
        log.warning("ACS %s has no release for %d", dataset, year)
        return pd.DataFrame(columns=["state_fips", "year", *variables.values()])
    if "missing_key" in r.url or "invalid_key" in r.url:
        raise MissingKeyError("Census API rejected the key in CENSUS_API_KEY")
    r.raise_for_status()
    return parse_response(r.json(), variables, year)


def fetch_acs(
    years: range | list[int],
    dataset: str = "acs1",
    variables: dict[str, str] | None = None,
    *,
    api_key: str | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    variables = variables or DEFAULT_VARIABLES
    key = api_key or os.environ.get("CENSUS_API_KEY")
    if not key:
        raise MissingKeyError(
            "The Census API requires a key. Get one free at https://api.census.gov/data/key_signup.html "
            "and set the CENSUS_API_KEY environment variable."
        )
    frames = []
    for year in years:
        if year < FIRST_YEAR[dataset] or year in MISSING_YEARS[dataset]:
            continue
        path = cache_dir("acs") / f"{dataset}_{year}_{short_hash(sorted(variables.items()))}.parquet"
        frames.append(cached_frame(path, lambda y=year: _fetch_year(y, dataset, variables, key), refresh=refresh))
    if not frames:
        return pd.DataFrame(columns=["state_fips", "year", *variables.values()])
    return pd.concat(frames, ignore_index=True)


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if {"acs_renter_occupied_units", "acs_occupied_units"} <= set(out.columns):
        out["acs_renter_share"] = out["acs_renter_occupied_units"] / out["acs_occupied_units"]
    for col in ("acs_median_gross_rent", "acs_median_home_value", "acs_median_household_income"):
        if col in out.columns:
            out[f"ln_{col}"] = np.log(out[col])
    return out
