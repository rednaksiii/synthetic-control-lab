"""BLS Quarterly Census of Employment and Wages (QCEW): state annual averages.

Two public sources, both keyless:
  * 2014 onward: the QCEW open-data API, one small CSV per year and industry
    https://data.bls.gov/cew/data/api/{year}/a/industry/{industry}.csv
  * 1990-2013: the annual "singlefile" zip (~30-60 MB per year), from which only state-level
    rows are kept. The zip is deleted after extraction unless ``keep_raw=True``.

Ownership codes: 0 total covered, 1 federal, 2 state government, 3 local government, 5 private.
Industry codes are NAICS-based: "10" is all industries; e.g. "722" food services and drinking places.
"""

from __future__ import annotations

import logging
import zipfile
from io import StringIO

import numpy as np
import pandas as pd

from ._http import cache_dir, cached_frame, download, session
from .states import FIPS_TO_ABBR

log = logging.getLogger(__name__)

API_URL = "https://data.bls.gov/cew/data/api/{year}/a/industry/{industry}.csv"
ZIP_URL = "https://data.bls.gov/cew/data/files/{year}/csv/{year}_annual_singlefile.zip"
API_FIRST_YEAR = 2014
FIRST_YEAR = 1990

OWNERSHIP = {"0": "all", "1": "federal", "2": "stategov", "3": "localgov", "5": "private"}
MEASURES = {"estabs": "establishments", "emp": "employment", "total_wages": "total wages ($)", "avg_pay": "average annual pay ($)"}
_STATE_AREAS = {f"{f}000" for f in FIPS_TO_ABBR}
_COLUMNS = ["state_fips", "year", "own_code", "industry_code", "estabs", "emp", "total_wages", "avg_pay", "disclosure_code"]


def tidy_qcew(raw: pd.DataFrame) -> pd.DataFrame:
    """Keep state-level annual rows and standardise column names (works for API and zip files)."""
    df = raw.rename(columns=lambda c: "annual_avg_estabs" if c.startswith("annual_avg_estabs") else c)
    df = df[df["area_fips"].astype(str).isin(_STATE_AREAS)]
    out = pd.DataFrame(
        {
            "state_fips": df["area_fips"].astype(str).str[:2].to_numpy(),
            "year": pd.to_numeric(df["year"]).astype(int).to_numpy(),
            "own_code": df["own_code"].astype(str).to_numpy(),
            "industry_code": df["industry_code"].astype(str).to_numpy(),
            "estabs": pd.to_numeric(df["annual_avg_estabs"], errors="coerce").to_numpy(dtype=float),
            "emp": pd.to_numeric(df["annual_avg_emplvl"], errors="coerce").to_numpy(dtype=float),
            "total_wages": pd.to_numeric(df["total_annual_wages"], errors="coerce").to_numpy(dtype=float),
            "avg_pay": pd.to_numeric(df["avg_annual_pay"], errors="coerce").to_numpy(dtype=float),
            "disclosure_code": df["disclosure_code"].fillna("").astype(str).str.strip().to_numpy(),
        }
    )
    # Suppressed cells are published as zeros with disclosure code "N".
    out.loc[out["disclosure_code"] == "N", ["estabs", "emp", "total_wages", "avg_pay"]] = np.nan
    return out[_COLUMNS]


_DTYPES = {"area_fips": str, "own_code": str, "industry_code": str, "agglvl_code": str, "disclosure_code": str, "qtr": str}


def _from_api(year: int, industry: str) -> pd.DataFrame:
    url = API_URL.format(year=year, industry=industry)
    r = session().get(url, timeout=120)
    if r.status_code == 404:
        log.warning("QCEW API has no data for %s industry %s", year, industry)
        return pd.DataFrame(columns=_COLUMNS)
    r.raise_for_status()
    return tidy_qcew(pd.read_csv(StringIO(r.text), dtype=_DTYPES))


def _from_zip(year: int, refresh: bool, keep_raw: bool) -> pd.DataFrame:
    zpath = download(ZIP_URL.format(year=year), cache_dir("raw", "qcew") / f"{year}_annual_singlefile.zip", refresh=refresh)
    parts = []
    with zipfile.ZipFile(zpath) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".csv"))
        with zf.open(name) as fh:
            for chunk in pd.read_csv(fh, dtype=_DTYPES, chunksize=500_000, low_memory=False):
                chunk = chunk[chunk["area_fips"].isin(_STATE_AREAS)]
                if len(chunk):
                    parts.append(tidy_qcew(chunk))
    if not keep_raw:
        zpath.unlink(missing_ok=True)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=_COLUMNS)


def fetch_qcew(
    years: range | list[int],
    industries: tuple[str, ...] = ("10",),
    ownerships: tuple[str, ...] = ("0", "5"),
    *,
    refresh: bool = False,
    keep_raw: bool = False,
) -> pd.DataFrame:
    """Tidy state-level QCEW annual averages for the requested years, industries and ownerships."""
    frames = []
    for year in years:
        if year < FIRST_YEAR:
            log.warning("QCEW NAICS-based data start in %d; skipping %d", FIRST_YEAR, year)
            continue
        if year >= API_FIRST_YEAR:
            for ind in industries:
                path = cache_dir("qcew") / f"state_{year}_ind{ind}.parquet"
                frames.append(cached_frame(path, lambda y=year, i=ind: _from_api(y, i), refresh=refresh))
        else:
            path = cache_dir("qcew") / f"state_{year}_all.parquet"
            df = cached_frame(path, lambda y=year: _from_zip(y, refresh, keep_raw), refresh=refresh)
            frames.append(df[df["industry_code"].isin(industries)])
    if not frames:
        return pd.DataFrame(columns=_COLUMNS)
    out = pd.concat(frames, ignore_index=True)
    return out[out["own_code"].isin(ownerships) & out["industry_code"].isin(industries)].reset_index(drop=True)


def qcew_wide(tidy: pd.DataFrame) -> pd.DataFrame:
    """One column per (ownership, industry, measure), e.g. ``qcew_private_10_emp``."""
    if tidy.empty:
        return pd.DataFrame(columns=["state_fips", "year"])
    t = tidy.copy()
    t["key"] = "qcew_" + t["own_code"].map(OWNERSHIP).fillna("own" + t["own_code"]) + "_" + t["industry_code"]
    t = t.drop_duplicates(["state_fips", "year", "key"])
    wide = t.pivot(index=["state_fips", "year"], columns="key", values=list(MEASURES))
    wide.columns = [f"{key}_{measure}" for measure, key in wide.columns]
    return wide.reset_index()


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in [c for c in df.columns if c.startswith("qcew_") and c.endswith(("_emp", "_estabs"))]:
        out[f"ln_{col}"] = np.log(out[col].where(out[col] > 0))
    return out
