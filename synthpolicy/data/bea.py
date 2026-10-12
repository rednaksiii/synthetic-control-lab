"""BEA regional accounts: state GDP (SAGDP) and personal income / population (SAINC).

Uses BEA's bulk zip files, which need no API key and contain every state and year:
  https://apps.bea.gov/regional/zip/SAGDP.zip   (GDP by state, 1997 onward, NAICS basis)
  https://apps.bea.gov/regional/zip/SAINC.zip   (personal income and population, 1929 onward)
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from ._http import cache_dir, cached_frame, download, short_hash
from .states import FIPS_TO_ABBR

ZIP_URL = "https://apps.bea.gov/regional/zip/{name}.zip"

# column name -> (zip, table, line code, description)
DEFAULT_SERIES: dict[str, tuple[str, str, int, str]] = {
    "bea_real_gdp": ("SAGDP", "SAGDP1", 1, "Real GDP, millions of chained dollars"),
    "bea_gdp": ("SAGDP", "SAGDP1", 3, "Nominal GDP, millions of current dollars"),
    "bea_gdp_mining": ("SAGDP", "SAGDP2", 6, "GDP in mining, quarrying, and oil and gas extraction, millions of current dollars"),
    "bea_personal_income": ("SAINC", "SAINC1", 1, "Personal income, millions of current dollars"),
    "bea_population": ("SAINC", "SAINC1", 2, "Population (persons)"),
    "bea_pc_personal_income": ("SAINC", "SAINC1", 3, "Per capita personal income, current dollars"),
}


def bea_zip(name: str, refresh: bool = False) -> Path:
    return download(ZIP_URL.format(name=name), cache_dir("raw", "bea") / f"{name}.zip", refresh=refresh)


def parse_bea_csv(raw: bytes | str) -> pd.DataFrame:
    """Parse one BEA regional ``*__ALL_AREAS_*.csv`` file into tidy state-level rows.

    Returns columns state_fips, year, table, line_code, description, unit, value. Suppressed or
    unavailable cells such as ``(D)`` and ``(NA)`` become NaN; regions and the US total are dropped.
    """
    text = raw.decode("latin-1") if isinstance(raw, bytes) else raw
    df = pd.read_csv(io.StringIO(text), skipinitialspace=True, dtype=str)
    df = df[pd.to_numeric(df["LineCode"], errors="coerce").notna()].copy()
    df["GeoFIPS"] = df["GeoFIPS"].str.strip().str.strip('"').str.strip()
    df = df[df["GeoFIPS"].str.fullmatch(r"\d{2}000") & df["GeoFIPS"].str[:2].isin(FIPS_TO_ABBR)]
    year_cols = [c for c in df.columns if re.fullmatch(r"\d{4}", c)]
    long = df.melt(
        id_vars=["GeoFIPS", "TableName", "LineCode", "Description", "Unit"],
        value_vars=year_cols,
        var_name="year",
        value_name="value",
    )
    long["value"] = pd.to_numeric(long["value"].str.strip(), errors="coerce")
    return pd.DataFrame(
        {
            "state_fips": long["GeoFIPS"].str[:2].to_numpy(),
            "year": long["year"].astype(int).to_numpy(),
            "table": long["TableName"].str.strip().to_numpy(),
            "line_code": long["LineCode"].astype(float).astype(int).to_numpy(),
            "description": long["Description"].str.strip().to_numpy(),
            "unit": long["Unit"].str.strip().to_numpy(),
            "value": long["value"].to_numpy(dtype=float),
        }
    )


def read_bea_table(zip_path: Path, table: str) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if re.fullmatch(rf"{table}__ALL_AREAS_\d{{4}}_\d{{4}}\.csv", n)]
        if not names:
            raise FileNotFoundError(f"No all-areas file for {table} in {zip_path.name}")
        return parse_bea_csv(zf.read(names[0]))


def fetch_bea(series: dict[str, tuple[str, str, int, str]] | None = None, refresh: bool = False) -> pd.DataFrame:
    """Wide state-by-year frame (state_fips, year, one column per requested series)."""
    series = series or DEFAULT_SERIES
    key = short_hash(sorted((k, v[:3]) for k, v in series.items()))
    path = cache_dir("bea") / f"bea_{key}.parquet"

    def build() -> pd.DataFrame:
        frames = []
        tables: dict[tuple[str, str], pd.DataFrame] = {}
        for col, (zname, table, line, _) in series.items():
            if (zname, table) not in tables:
                tables[(zname, table)] = read_bea_table(bea_zip(zname, refresh), table)
            t = tables[(zname, table)]
            s = t[t["line_code"] == line][["state_fips", "year", "value"]].rename(columns={"value": col})
            if s.empty:
                raise ValueError(f"{table} has no line {line}")
            frames.append(s.set_index(["state_fips", "year"]))
        return pd.concat(frames, axis=1).reset_index()

    return cached_frame(path, build, refresh=refresh)


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if {"bea_real_gdp", "bea_population"} <= set(out.columns):
        out["bea_real_gdp_pc"] = out["bea_real_gdp"] * 1e6 / out["bea_population"]
        out["ln_bea_real_gdp_pc"] = np.log(out["bea_real_gdp_pc"])
    if "bea_real_gdp" in out.columns:
        out["ln_bea_real_gdp"] = np.log(out["bea_real_gdp"])
    if {"bea_gdp_mining", "bea_gdp"} <= set(out.columns):
        out["bea_mining_share"] = out["bea_gdp_mining"] / out["bea_gdp"]
    if "bea_pc_personal_income" in out.columns:
        out["ln_bea_pc_personal_income"] = np.log(out["bea_pc_personal_income"])
    return out
