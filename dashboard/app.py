"""Synthetic control dashboard.  Run:  streamlit run dashboard/app.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import charts  # noqa: E402

from synthpolicy.data.panel import load_state_panel  # noqa: E402
from synthpolicy.data.prop99 import load_prop99  # noqa: E402
from synthpolicy.pipeline import analyze  # noqa: E402
from synthpolicy.results import as_bundle, list_results, load_results  # noqa: E402
from synthpolicy.spec import spec_from_dict  # noqa: E402

st.set_page_config(page_title="Synthetic Control Lab", page_icon=":material/insights:", layout="wide")
st.markdown("<style>.block-container {padding-top: 2.5rem;}</style>", unsafe_allow_html=True)


def theme() -> charts.Theme:
    try:
        return charts.DARK if st.context.theme.type == "dark" else charts.LIGHT
    except AttributeError:
        return charts.LIGHT


def plot(fig) -> None:
    st.plotly_chart(fig, theme=None, config={"displaylogo": False})


def full_height(df: pd.DataFrame) -> int:
    """Pixel height that shows every row of a dataframe without an inner scrollbar."""
    return 38 + 35 * len(df)


def table(df: pd.DataFrame, label: str = "Table view") -> None:
    with st.expander(label):
        st.dataframe(df, hide_index=True)


def fmt(x, digits: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{digits}g}"


@st.cache_data(show_spinner=False)
def cached_results(path: str, mtime: float) -> dict:
    return load_results(Path(path))


@st.cache_data(show_spinner="Loading data...")
def dataset(name: str) -> pd.DataFrame:
    return load_prop99() if name == "prop99" else load_state_panel()


# --------------------------------------------------------------------------- rendering


def status_banner(s: dict) -> None:
    lock = s["lock"]
    state = lock.get("state")
    detail = f" Locked {lock['locked_at']}." if lock.get("locked_at") else ""
    if state == "locked":
        st.success(f"**{lock['label']}**.{detail}", icon=":material/lock:")
    elif state == "replication":
        st.info(f"**{lock['label']}**: every design choice comes from the original paper.", icon=":material/library_books:")
    else:
        st.warning(f"**{lock['label']}**. Results here are not evidence; pre-register and lock a spec first.", icon=":material/science:")


def render(b: dict) -> None:
    t = theme()
    s = b["summary"]
    d, fit = s["design"], s["fit"]
    treated, t0, outcome_label = d["treated"], d["first_treated_period"], d["outcome_label"]
    ylab = outcome_label.split(", ")[0]  # short axis title; the full definition is in the caption

    st.header(s["title"])
    status_banner(s)
    with st.container(border=True):
        rule = "default rule, not pre-registered" if s["lock"].get("state") in ("unlocked", "modified", "exploratory") else "decision rule in the spec"
        st.markdown(f"**Verdict ({rule}):** {s['decision']['verdict']}")

    for note in fit.get("notes", []):
        st.warning(note, icon=":material/warning:")

    pis = s.get("placebo_in_space")
    sd = s.get("sdid")
    c = st.columns(4)
    c[0].metric("Mean post-period gap", fmt(fit["mean_post_gap"]), help="Average of actual minus synthetic from the first treated period on.")
    c[1].metric("Pre-period RMSPE", fmt(fit["pre_rmspe"]), help="How closely the synthetic unit tracked the treated unit before the policy. Smaller is better.")
    if pis:
        c[2].metric("Placebo p-value", fmt(pis["p_value_ratio"]), help=f"Rank {pis['treated_ratio_rank']} of {pis['n_units']} on the post/pre RMSPE ratio.")
    if sd:
        c[3].metric("Synthetic DiD estimate", fmt(sd["sdid"]["estimate"]), help=f"Placebo SE {fmt(sd['sdid']['se'])}.")

    st.caption(f"Outcome: {outcome_label}")

    names = ["Actual vs synthetic", "Weights & balance", "Placebo in space", "Placebo in time", "Leave-one-out", "Synthetic DiD", "Checks", "Design & donors"]
    if s.get("published"):
        names.insert(6, "Replication")
    # Deep links: ?study=<name>&tab=<tab name> opens a study on a given tab.
    wanted = st.query_params.get("tab")
    tabs = dict(zip(names, st.tabs(names, default=wanted if wanted in names else None)))

    series = b["series"]
    with tabs["Actual vs synthetic"]:
        plot(charts.actual_vs_synthetic(series, t0, treated, ylab, t))
        st.caption("Gap (actual minus synthetic)")
        plot(charts.gap(series, t0, ylab, t))
        table(series)

    with tabs["Weights & balance"]:
        left, right = st.columns([2, 3])
        with left:
            st.subheader("Donor weights")
            plot(charts.weights(b["weights"], t))
            table(b["weights"].sort_values("weight", ascending=False))
        with right:
            st.subheader("Predictor balance")
            st.caption("Pre-period predictor values for the treated unit, its synthetic twin, and the plain donor average. `v` is each predictor's importance.")
            st.dataframe(b["balance"], hide_index=True)

    with tabs["Placebo in space"]:
        if "placebo_stats" not in b:
            st.info("Not run for this study.")
        else:
            stats = b["placebo_stats"]
            choice = st.radio("Show placebos whose pre-period MSPE is at most", ["all", "20x", "5x", "2x"], horizontal=True, help="ADH (2010) drop placebos that fit their own pre-period badly, since their large post-period gaps say nothing.")
            mult = None if choice == "all" else float(choice[:-1])
            keep = set(stats["unit"] if mult is None else stats.loc[stats["pre_mspe_multiple"] <= mult, "unit"])
            sub = stats[stats["unit"].isin(keep | {treated})]
            rank = int((sub["rmspe_ratio"] >= float(sub.loc[sub["unit"] == treated, "rmspe_ratio"].iloc[0]) - 1e-12).sum())
            st.markdown(f"**{treated}** ranks **{rank} of {len(sub)}** on the post/pre RMSPE ratio: p = **{rank / len(sub):.3f}** (smallest attainable {1 / len(sub):.3f}).")
            plot(charts.placebo_spaghetti(b["placebo_gaps"], treated, t0, keep, f"Gap: {ylab}", t))
            plot(charts.ratio_ranks(sub, treated, t))
            table(sub)

    with tabs["Placebo in time"]:
        if "placebo_time" not in b:
            st.info("Not run for this study.")
        for pt in s.get("placebo_in_time", []):
            fake = pt["fake_time"]
            st.subheader(f"Fake policy date {fake}")
            st.caption(f"Fitted on data before {fake} only; nothing should happen between {fake} and the real policy in {t0}.")
            cc = st.columns(3)
            cc[0].metric("Mean placebo gap", fmt(pt["mean_placebo_gap"]))
            cc[1].metric("Pre-period RMSPE", fmt(pt["pre_rmspe"]))
            cc[2].metric("Real mean post gap", fmt(fit["mean_post_gap"]))
            if pt["dropped_predictors"]:
                st.caption("Predictors dropped (no data before the fake date): " + ", ".join(pt["dropped_predictors"]))
            g = b["placebo_time"][b["placebo_time"]["fake_time"] == fake]
            plot(charts.placebo_in_time(g, fake, t0, treated, ylab, t))
            table(g)

    with tabs["Leave-one-out"]:
        if "loo" not in b:
            st.info("Not run for this study.")
        else:
            plot(charts.leave_one_out(series, b["loo"], t0, treated, ylab, t))
            st.dataframe(b["loo_stats"], hide_index=True)

    with tabs["Synthetic DiD"]:
        if "sdid_estimates" not in b:
            st.info("Not run for this study.")
        else:
            est = b["sdid_estimates"].copy()
            labels = {"sdid": "Synthetic DiD", "sc": "SC (synthdid, outcomes only)", "did": "Difference-in-differences"}
            est["label"] = est["method"].map(labels)
            main = pd.DataFrame([{"method": "classic", "label": "Classic SC (this study)", "estimate": fit["mean_post_gap"], "se": None, "ci_low": None, "ci_high": None}])
            rows = pd.concat([main, est], ignore_index=True)
            st.caption("Average post-period effect with 95% placebo intervals (each control as pseudo-treated once). The classic SC row has no interval: its inference is the placebo rank.")
            plot(charts.estimates(rows, t, f"Effect on {ylab}"))
            table(rows[["label", "estimate", "se", "ci_low", "ci_high"]])
            paths = b["sdid_paths"].rename(columns={"treated": "actual", "sdid": "synthetic"})
            st.caption("SDID synthetic unit, shifted by its intercept: SDID only needs the two paths to be parallel before the policy.")
            plot(charts.actual_vs_synthetic(paths, t0, treated, ylab, t))
            cl, cr = st.columns(2)
            cl.markdown("**SDID unit weights**")
            cl.dataframe(b["sdid_weights"].sort_values("sdid", ascending=False).head(12), hide_index=True)
            cr.markdown("**SDID time weights (pre-period)**")
            cr.dataframe(b["sdid_lambda"][b["sdid_lambda"]["lambda"] > 1e-4], hide_index=True)

    if "Replication" in tabs:
        with tabs["Replication"]:
            pub = pd.DataFrame(s["published"])
            n_ok = int(pub["match"].sum())
            st.markdown(f"**{n_ok} of {len(pub)}** published values reproduced within tolerance. Source: {s.get('published_source', '')}")
            pub["result"] = pub["match"].map({True: "✓ within tolerance", False: "✗ outside tolerance"})
            pub["tolerance"] = pub["tolerance"].map(lambda v: v if isinstance(v, str) else f"±{v:g}")
            if "note" in pub:
                pub["note"] = pub["note"].fillna("")
            pub = pub.drop(columns=["match"])
            st.dataframe(pub, hide_index=True, height=full_height(pub))

    with tabs["Checks"]:
        st.markdown(f"**Verdict:** {s['decision']['verdict']}")
        ch = pd.DataFrame(s["decision"]["checks"])
        if not ch.empty:
            ch["result"] = ch["passed"].map({True: "✓ pass", False: "✗ fail"}).fillna("not evaluated")
            ch["value"] = ch["value"].map(lambda v: v if isinstance(v, str) else fmt(v, 4))
            st.dataframe(ch.drop(columns=["passed"]), hide_index=True)

    with tabs["Design & donors"]:
        st.markdown(
            f"- **Treated:** {treated}, first treated period **{t0}**, window {d['window'][0]}–{d['window'][1]}\n"
            f"- **Outcome:** {outcome_label} (`{d['outcome_column']}`)\n- **V selection:** `{d['v_method']}`\n"
            f"- **Predictors:** {', '.join(d['predictors'])}\n- **Policy:** {d.get('policy_note') or 'n/a'}"
        )
        if s["lock"].get("sha256"):
            st.caption(f"Spec SHA-256 {s['lock']['sha256']}")
        st.dataframe(b["donors"], hide_index=True)
        if b.get("report"):
            st.download_button("Download report (Markdown)", b["report"], file_name=f"{s['name']}_report.md", mime="text/markdown")


# --------------------------------------------------------------------------- explorer


def explorer() -> dict | None:
    st.sidebar.warning("Exploratory mode: nothing here is pre-registered. Use it to learn the method and draft specs, not to find results.", icon=":material/science:")
    source = st.sidebar.selectbox("Dataset", ["prop99", "state_panel"], format_func={"prop99": "Prop 99 smoking data (1970-2000)", "state_panel": "State panel (QCEW, LAUS, BEA)"}.get)
    try:
        df = dataset(source)
    except FileNotFoundError as exc:
        st.error(str(exc))
        return None
    numeric = [c for c in df.columns if c not in ("state", "state_fips", "state_name", "year") and pd.api.types.is_numeric_dtype(df[c])]
    units = sorted(df["state"].astype(str).unique())
    years = sorted(df["year"].unique())
    default_outcome = "cigsale" if source == "prop99" else "qcew_private_10_emp"
    with st.sidebar.form("explore"):
        outcome = st.selectbox("Outcome", numeric, index=numeric.index(default_outcome) if default_outcome in numeric else 0)
        treated = st.selectbox("Treated unit", units, index=units.index("California") if "California" in units else 0)
        t0 = st.number_input("First treated year", min_value=int(years[2]), max_value=int(years[-1]), value=1989 if source == "prop99" else 2012)
        start, end = st.slider("Window", int(years[0]), int(years[-1]), (int(years[0]), int(years[-1])))
        transform = st.selectbox("Outcome transform", ["none", "log", "index", "log_demeaned"], index=0 if source == "prop99" else 3, help="index and log_demeaned use each unit's own pre-period mean as the base.")
        method = st.radio("Predictors", ["outcomes", "nested"], format_func={"outcomes": "Every pre-period outcome, equal V (fast)", "nested": "Four sub-period outcome means, nested V (slower)"}.get)
        neighbors = st.checkbox("Exclude bordering states", value=source == "state_panel", disabled=source == "prop99")
        exclude = st.multiselect("Exclude units", [u for u in units if u != treated])
        fake = st.number_input("Placebo-in-time year (0 = skip)", min_value=0, max_value=int(years[-1]), value=0)
        go = st.form_submit_button("Run analysis", type="primary")

    raw = {
        "study": {"name": "explore", "title": f"Exploratory: {treated}, {outcome}, from {t0}", "status": "exploratory"},
        "data": {"source": source, "unit": "state", "time": "year", "start": start, "end": end},
        "treatment": {"unit": treated, "first_treated_period": int(t0)},
        "outcome": {"variable": outcome, "label": outcome + ("" if transform == "none" else f" ({transform})"), "transform": transform},
        "donors": {"pool": "all", "exclude": {u: "excluded in explorer" for u in exclude}, "exclude_neighbors": bool(neighbors)},
        "model": {"v_method": "outcomes" if method == "outcomes" else "nested"},
        "inference": {"placebo_in_space": True, "placebo_in_time": [int(fake)] if fake else [], "leave_one_out": True},
        "robustness": {"sdid": True},
        "decision": {"alpha": 0.10},
    }
    if method == "nested":
        pre = list(range(start, int(t0)))
        cuts = [pre[i * len(pre) // 4 : (i + 1) * len(pre) // 4] for i in range(4)]
        raw["predictors"] = [{"variable": "@outcome", "start": c[0], "end": c[-1]} for c in cuts if c]
    key = json.dumps(raw, sort_keys=True)
    if go:
        bar = st.progress(0.0, text="Fitting...")

        def progress(stage: str, i: int, n: int) -> None:
            bar.progress(min(1.0, i / max(n, 1)), text=f"{stage} ({i}/{n})")

        try:
            spec = spec_from_dict(raw)
            frame = df[df["year"].between(start, end)]
            result = analyze(spec, frame, {"state": "exploratory", "label": "EXPLORATORY (ad-hoc, not pre-registered)"}, progress=progress)
            st.session_state["explore_result"] = (key, as_bundle(result))
        except Exception as exc:  # noqa: BLE001 - surface any modelling error to the user
            st.error(f"Analysis failed: {exc}")
        bar.empty()
    saved = st.session_state.get("explore_result")
    if saved is None:
        st.title("Explore")
        st.markdown("Choose a treated unit, outcome and date in the sidebar, then run. Each run fits the synthetic control, re-runs it for every donor (placebo in space), and runs leave-one-out and synthetic DiD.")
        return None
    if saved[0] != key:
        st.caption("Settings changed since the last run; showing the previous run.")
    return saved[1]


def main() -> None:
    st.sidebar.title("Synthetic Control Lab")
    mode = st.sidebar.radio("Mode", ["Saved studies", "Explore"], label_visibility="collapsed")
    if mode == "Explore":
        bundle = explorer()
        if bundle:
            render(bundle)
        return
    paths = list_results()
    if not paths:
        st.title("No saved studies")
        st.markdown("Run one first:\n\n```\npython -m synthpolicy run specs/prop99.toml\n```")
        return
    names = [p.name for p in paths]
    wanted = st.query_params.get("study")
    path = st.sidebar.selectbox("Study", paths, index=names.index(wanted) if wanted in names else 0, format_func=lambda p: p.name)
    render(cached_results(str(path), (path / "summary.json").stat().st_mtime))


main()
