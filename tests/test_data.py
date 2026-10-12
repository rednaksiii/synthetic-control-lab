"""Parsers and reference tables, tested offline on small fixtures in each source's real format."""

from __future__ import annotations

import pandas as pd

from synthpolicy.data import acs, bea, laus, qcew
from synthpolicy.data.states import ADJACENCY, neighbors, states_table, to_abbr

BEA_CSV = '''GeoFIPS,GeoName,Region,TableName,LineCode,IndustryClassification,Description,Unit,2011,2012
 "00000","United States", ,SAGDP1,1,"...","Real GDP (millions of chained 2017 dollars) 1/","Millions of chained 2017 dollars",17052410.0,17442759.0
 "20000","Kansas",4,SAGDP1,1,"...","Real GDP (millions of chained 2017 dollars) 1/","Millions of chained 2017 dollars",147836.8,150077.1
 "20000","Kansas",4,SAGDP1,3,"...","Current-dollar GDP (millions of current dollars) ","Millions of current dollars",136747.1,(D)
 "91000","New England",1,SAGDP1,1,"...","Real GDP","Millions",1.0,2.0
"Note: See the included footnote file."
"U.S. Bureau of Economic Analysis"
'''


def test_parse_bea_csv():
    df = bea.parse_bea_csv(BEA_CSV)
    assert set(df["state_fips"]) == {"20"}
    real = df[df["line_code"] == 1].set_index("year")["value"]
    assert real.loc[2012] == 150077.1
    assert df[(df["line_code"] == 3) & (df["year"] == 2012)]["value"].isna().all()


def test_qcew_tidy_and_wide():
    raw = pd.DataFrame(
        {
            "area_fips": ["20000", "20000", "20000", "20001", "US000"],
            "own_code": ["0", "5", "5", "5", "0"],
            "industry_code": ["10", "10", "722", "10", "10"],
            "agglvl_code": ["50", "51", "55", "71", "10"],
            "year": ["2015"] * 5,
            "disclosure_code": ["", "", "N", "", ""],
            "annual_avg_estabs_count": ["86786", "81779", "0", "5", "1"],
            "annual_avg_emplvl": ["1367329", "1124352", "0", "10", "1"],
            "total_annual_wages": ["1", "2", "0", "3", "4"],
            "avg_annual_pay": ["43878", "44729", "0", "1", "1"],
        }
    )
    t = qcew.tidy_qcew(raw)
    assert len(t) == 3 and set(t["state_fips"]) == {"20"}
    assert t.loc[t["industry_code"] == "722", "emp"].isna().all()  # suppressed -> NaN, not 0
    w = qcew.qcew_wide(t)
    assert w.loc[0, "qcew_private_10_emp"] == 1124352 and w.loc[0, "qcew_all_10_estabs"] == 86786


def test_laus_series_ids_and_annual_average():
    sid = laus.series_id("20", "06")
    assert sid == "LAUST200000000000006" and len(sid) == 20
    assert laus.parse_series_id(sid) == ("20", "06")
    body = {"Results": {"series": [{"seriesID": sid, "data": [{"year": "2012", "period": f"M{m:02d}", "value": str(100 + m)} for m in range(1, 13)]
                                    + [{"year": "2013", "period": "M01", "value": "1"}]}]}}
    annual = laus.annual_averages(laus.parse_response(body))
    assert len(annual) == 1  # incomplete 2013 dropped
    assert annual.iloc[0]["value"] == 106.5


def test_acs_parse_drops_sentinels():
    rows = [["NAME", "B25064_001E", "state"], ["Kansas", "800", "20"], ["Puerto Rico", "400", "72"], ["Alaska", "-666666666", "02"]]
    df = acs.parse_response(rows, {"B25064_001E": "acs_median_gross_rent"}, 2015)
    assert list(df["state_fips"]) == ["20", "02"]
    assert df.loc[df["state_fips"] == "02", "acs_median_gross_rent"].isna().all()


def test_states_and_borders():
    st = states_table()
    assert len(st) == 51 and st["fips"].is_unique
    assert neighbors("Kansas") == {"MO", "NE", "OK", "CO"}
    assert neighbors("TN") == {"AL", "AR", "GA", "KY", "MS", "MO", "NC", "VA"}
    assert neighbors("AK") == frozenset() and neighbors("HI") == frozenset()
    assert all(a in ADJACENCY[b] for a, ns in ADJACENCY.items() for b in ns)
    assert to_abbr("20") == "KS" and to_abbr("california") == "CA"
