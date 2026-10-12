"""BLS Local Area Unemployment Statistics (LAUS): state annual averages via the BLS Public Data API.

Without a key the API allows 25 requests/day, 25 series and 10 years per request. Set
``BLS_API_KEY`` (free registration at https://data.bls.gov/registrationEngine/) to get 500
requests/day, 50 series and 20 years per request. Every response is cached on disk, so an
interrupted fetch resumes where it stopped and re-runs cost nothing.

Annual averages are means of the 12 not-seasonally-adjusted monthly values (as BLS computes
them); the unemployment rate is derived from annual-average unemployment and labour force.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os

import numpy as np
import pandas as pd

from ._http import cache_dir, cached_frame, session, short_hash
from .states import FIPS_TO_ABBR

log = logging.getLogger(__name__)

API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
MEASURES = {"03": "unemployment_rate", "04": "unemployment", "05": "employment", "06": "labor_force"}
FIRST_YEAR = 1976


class BLSQuotaError(RuntimeError):
    pass


def series_id(state_fips: str, measure: str, seasonal: str = "U") -> str:
    """e.g. ``LAUST200000000000006`` = Kansas labour force, not seasonally adjusted."""
    return f"LA{seasonal}ST{state_fips}{'0' * 11}{measure}"


def parse_series_id(sid: str) -> tuple[str, str]:
    return sid[5:7], sid[-2:]


def _post(series: list[str], start: int, end: int, key: str | None, refresh: bool) -> dict:
    path = cache_dir("raw", "laus") / f"{short_hash(sorted(series), start, end, bool(key))}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    payload: dict = {"seriesid": series, "startyear": str(start), "endyear": str(end)}
    if key:
        payload |= {"registrationkey": key, "annualaverage": True}
    r = session().post(API_URL, json=payload, timeout=120)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "REQUEST_SUCCEEDED":
        msg = " ".join(body.get("message", [])) or body.get("status", "unknown error")
        if "threshold" in msg.lower() or "daily" in msg.lower():
            raise BLSQuotaError(f"BLS API daily limit reached: {msg}. Set BLS_API_KEY or resume tomorrow (progress is cached).")
        raise RuntimeError(f"BLS API error: {msg}")
    path.write_text(json.dumps(body))
    return body


def parse_response(body: dict) -> pd.DataFrame:
    """Monthly (and M13 annual) observations as state_fips, measure, year, period, value."""
    rows = []
    for s in body["Results"]["series"]:
        fips, measure = parse_series_id(s["seriesID"])
        for obs in s["data"]:
            v = pd.to_numeric(obs["value"], errors="coerce")
            rows.append((fips, measure, int(obs["year"]), obs["period"], v))
    return pd.DataFrame(rows, columns=["state_fips", "measure", "year", "period", "value"])


def annual_averages(monthly: pd.DataFrame) -> pd.DataFrame:
    """M13 where published, else the mean of a complete set of 12 monthly values."""
    m13 = monthly[monthly["period"] == "M13"].set_index(["state_fips", "measure", "year"])["value"]
    months = monthly[monthly["period"].str.fullmatch(r"M(0[1-9]|1[0-2])")]
    g = months.groupby(["state_fips", "measure", "year"])["value"]
    mean = g.mean()[g.count() == 12]
    out = mean.combine_first(m13) if len(m13) else mean
    return out.rename("value").reset_index()


def fetch_laus(
    start: int = 1990,
    end: int | None = None,
    measures: tuple[str, ...] = ("04", "06"),
    *,
    api_key: str | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """Wide state-by-year frame with columns ``laus_<measure>`` and ``laus_unemployment_rate``."""
    end = end or dt.date.today().year - 1
    start = max(start, FIRST_YEAR)
    key = api_key or os.environ.get("BLS_API_KEY")
    max_series, max_years = (50, 20) if key else (25, 10)
    all_series = [series_id(f, m) for f in sorted(FIPS_TO_ABBR) for m in measures]
    path = cache_dir("laus") / f"laus_{short_hash(start, end, measures)}.parquet"

    def build() -> pd.DataFrame:
        chunks = []
        year_chunks = [(y, min(y + max_years - 1, end)) for y in range(start, end + 1, max_years)]
        n_requests = len(year_chunks) * -(-len(all_series) // max_series)
        log.info("LAUS: %d API requests (%s key)", n_requests, "with" if key else "no")
        for i in range(0, len(all_series), max_series):
            batch = all_series[i : i + max_series]
            for y0, y1 in year_chunks:
                chunks.append(parse_response(_post(batch, y0, y1, key, refresh)))
        annual = annual_averages(pd.concat(chunks, ignore_index=True))
        annual["measure"] = "laus_" + annual["measure"].map(MEASURES)
        wide = annual.pivot(index=["state_fips", "year"], columns="measure", values="value").reset_index()
        wide.columns.name = None
        if {"laus_unemployment", "laus_labor_force"} <= set(wide.columns):
            wide["laus_unemployment_rate"] = 100 * wide["laus_unemployment"] / wide["laus_labor_force"]
        return wide

    return cached_frame(path, build, refresh=refresh)


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ("laus_employment", "laus_labor_force"):
        if col in out.columns:
            out[f"ln_{col}"] = np.log(out[col])
    return out
