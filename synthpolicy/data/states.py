"""Reference table of the 50 states + DC: FIPS codes, abbreviations, names, land borders."""

from __future__ import annotations

import pandas as pd

# (fips, abbreviation, name)
_STATES: list[tuple[str, str, str]] = [
    ("01", "AL", "Alabama"), ("02", "AK", "Alaska"), ("04", "AZ", "Arizona"),
    ("05", "AR", "Arkansas"), ("06", "CA", "California"), ("08", "CO", "Colorado"),
    ("09", "CT", "Connecticut"), ("10", "DE", "Delaware"), ("11", "DC", "District of Columbia"),
    ("12", "FL", "Florida"), ("13", "GA", "Georgia"), ("15", "HI", "Hawaii"),
    ("16", "ID", "Idaho"), ("17", "IL", "Illinois"), ("18", "IN", "Indiana"),
    ("19", "IA", "Iowa"), ("20", "KS", "Kansas"), ("21", "KY", "Kentucky"),
    ("22", "LA", "Louisiana"), ("23", "ME", "Maine"), ("24", "MD", "Maryland"),
    ("25", "MA", "Massachusetts"), ("26", "MI", "Michigan"), ("27", "MN", "Minnesota"),
    ("28", "MS", "Mississippi"), ("29", "MO", "Missouri"), ("30", "MT", "Montana"),
    ("31", "NE", "Nebraska"), ("32", "NV", "Nevada"), ("33", "NH", "New Hampshire"),
    ("34", "NJ", "New Jersey"), ("35", "NM", "New Mexico"), ("36", "NY", "New York"),
    ("37", "NC", "North Carolina"), ("38", "ND", "North Dakota"), ("39", "OH", "Ohio"),
    ("40", "OK", "Oklahoma"), ("41", "OR", "Oregon"), ("42", "PA", "Pennsylvania"),
    ("44", "RI", "Rhode Island"), ("45", "SC", "South Carolina"), ("46", "SD", "South Dakota"),
    ("47", "TN", "Tennessee"), ("48", "TX", "Texas"), ("49", "UT", "Utah"),
    ("50", "VT", "Vermont"), ("51", "VA", "Virginia"), ("53", "WA", "Washington"),
    ("54", "WV", "West Virginia"), ("55", "WI", "Wisconsin"), ("56", "WY", "Wyoming"),
]

# Shared land borders. Point contacts (Four Corners) and water-only boundaries are excluded.
_BORDERS: dict[str, tuple[str, ...]] = {
    "AL": ("FL", "GA", "MS", "TN"),
    "AZ": ("CA", "NV", "NM", "UT"),
    "AR": ("LA", "MO", "MS", "OK", "TN", "TX"),
    "CA": ("NV", "OR"),
    "CO": ("KS", "NE", "NM", "OK", "UT", "WY"),
    "CT": ("MA", "NY", "RI"),
    "DE": ("MD", "NJ", "PA"),
    "DC": ("MD", "VA"),
    "FL": ("GA",),
    "GA": ("NC", "SC", "TN"),
    "ID": ("MT", "NV", "OR", "UT", "WA", "WY"),
    "IL": ("IN", "IA", "KY", "MO", "WI"),
    "IN": ("KY", "MI", "OH"),
    "IA": ("MN", "MO", "NE", "SD", "WI"),
    "KS": ("MO", "NE", "OK"),
    "KY": ("MO", "OH", "TN", "VA", "WV"),
    "LA": ("MS", "TX"),
    "ME": ("NH",),
    "MD": ("PA", "VA", "WV"),
    "MA": ("NH", "NY", "RI", "VT"),
    "MI": ("OH", "WI"),
    "MN": ("ND", "SD", "WI"),
    "MS": ("TN",),
    "MO": ("NE", "OK", "TN"),
    "MT": ("ND", "SD", "WY"),
    "NE": ("SD", "WY"),
    "NV": ("OR", "UT"),
    "NH": ("VT",),
    "NJ": ("NY", "PA"),
    "NM": ("OK", "TX"),
    "NY": ("PA", "VT"),
    "NC": ("SC", "TN", "VA"),
    "ND": ("SD",),
    "OH": ("PA", "WV"),
    "OK": ("TX",),
    "OR": ("WA",),
    "PA": ("WV",),
    "SD": ("WY",),
    "TN": ("VA",),
    "UT": ("WY",),
    "VA": ("WV",),
}


def states_table() -> pd.DataFrame:
    """DataFrame with columns fips, abbr, name for the 50 states and DC."""
    return pd.DataFrame(_STATES, columns=["fips", "abbr", "name"])


FIPS_TO_ABBR = {f: a for f, a, _ in _STATES}
FIPS_TO_NAME = {f: n for f, _, n in _STATES}
ABBR_TO_FIPS = {a: f for f, a, _ in _STATES}
ABBR_TO_NAME = {a: n for _, a, n in _STATES}
NAME_TO_ABBR = {n: a for _, a, n in _STATES}


def _build_adjacency() -> dict[str, frozenset[str]]:
    adj: dict[str, set[str]] = {a: set() for _, a, _ in _STATES}
    for a, neighbors in _BORDERS.items():
        for b in neighbors:
            adj[a].add(b)
            adj[b].add(a)
    return {k: frozenset(v) for k, v in adj.items()}


ADJACENCY = _build_adjacency()


def to_abbr(state: str) -> str:
    """Normalise a FIPS code, abbreviation or full name to a two-letter abbreviation."""
    s = state.strip()
    if s.upper() in ABBR_TO_NAME:
        return s.upper()
    if s.zfill(2) in FIPS_TO_ABBR and s.isdigit():
        return FIPS_TO_ABBR[s.zfill(2)]
    for name, abbr in NAME_TO_ABBR.items():
        if name.lower() == s.lower():
            return abbr
    raise KeyError(f"Unknown state: {state!r}")


def neighbors(state: str) -> frozenset[str]:
    """Abbreviations of the states sharing a land border with ``state``."""
    return ADJACENCY[to_abbr(state)]
