"""Assemble a clean state-by-year panel from QCEW, LAUS, BEA and ACS, cached as Parquet.

The panel has one row per (state, year) for the 50 states and DC, keyed by ``state`` (two-letter
abbreviation) and ``year``, with ``state_fips`` and ``state_name`` alongside. A source that
cannot be fetched (e.g. no Census key) is skipped with a warning unless ``strict=True``; the
outcome is recorded in a JSON sidecar next to the Parquet file.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

import pandas as pd

from . import acs, bea, laus, qcew
from ._http import cache_dir
from .states import states_table

log = logging.getLogger(__name__)

SOURCES = ("qcew", "laus", "bea", "acs")


def panel_path() -> Path:
    return cache_dir("panel") / "state_panel.parquet"


def build_state_panel(
    start: int = 1990,
    end: int | None = None,
    *,
    sources: tuple[str, ...] = SOURCES,
    qcew_industries: tuple[str, ...] = ("10",),
    qcew_ownerships: tuple[str, ...] = ("0", "5"),
    laus_measures: tuple[str, ...] = ("04", "06"),
    refresh: bool = False,
    strict: bool = False,
) -> pd.DataFrame:
    end = end or dt.date.today().year - 1
    years = range(start, end + 1)
    st = states_table().rename(columns={"fips": "state_fips", "abbr": "state", "name": "state_name"})
    panel = st.merge(pd.DataFrame({"year": list(years)}), how="cross")

    fetchers = {
        "qcew": lambda: qcew.add_derived(qcew.qcew_wide(qcew.fetch_qcew(years, qcew_industries, qcew_ownerships, refresh=refresh))),
        "laus": lambda: laus.add_derived(laus.fetch_laus(start, end, laus_measures, refresh=refresh)),
        "bea": lambda: bea.add_derived(bea.fetch_bea(refresh=refresh)),
        "acs": lambda: acs.add_derived(acs.fetch_acs(years, refresh=refresh)),
    }
    meta: dict = {"built": dt.datetime.now().isoformat(timespec="seconds"), "start": start, "end": end, "sources": {}}
    for name in sources:
        try:
            df = fetchers[name]()
        except Exception as exc:  # noqa: BLE001 - one failing source should not sink the panel
            if strict:
                raise
            log.warning("Skipping %s: %s", name, exc)
            meta["sources"][name] = {"status": "skipped", "reason": str(exc)}
            continue
        df = df[df["year"].between(start, end)]
        cols = [c for c in df.columns if c not in ("state_fips", "year")]
        panel = panel.merge(df, on=["state_fips", "year"], how="left")
        meta["sources"][name] = {"status": "ok", "columns": cols}
        log.info("%s: %d columns", name, len(cols))

    panel = panel.sort_values(["state", "year"]).reset_index(drop=True)
    meta["coverage"] = {
        c: [int(panel.loc[panel[c].notna(), "year"].min()), int(panel.loc[panel[c].notna(), "year"].max())]
        for c in panel.columns
        if c not in ("state", "state_fips", "state_name", "year") and panel[c].notna().any()
    }
    path = panel_path()
    panel.to_parquet(path, index=False)
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    return panel


def load_state_panel() -> pd.DataFrame:
    path = panel_path()
    if not path.exists():
        raise FileNotFoundError(f"No state panel at {path}. Build it first: python -m synthpolicy fetch")
    return pd.read_parquet(path)


def panel_metadata() -> dict:
    p = panel_path().with_suffix(".meta.json")
    return json.loads(p.read_text()) if p.exists() else {}
