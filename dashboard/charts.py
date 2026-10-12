"""Plotly figures for the dashboard.

Colour roles (validated with the dataviz palette checker, light and dark):
  treated / actual  -> categorical slot 1 (blue)
  synthetic         -> categorical slot 2 (orange)
  placebos, LOO     -> de-emphasis gray (context, never identity)
Text always uses ink tokens, never a series colour.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go


@dataclass(frozen=True)
class Theme:
    surface: str
    ink: str
    ink2: str
    muted: str
    grid: str
    axis: str
    treated: str
    synthetic: str
    context: str


LIGHT = Theme("#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#2a78d6", "#eb6834", "#c9c8c0")
DARK = Theme("#1a1a19", "#ffffff", "#c3c2b7", "#898781", "#2c2c2a", "#383835", "#3987e5", "#d95926", "#4d4c48")

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def _layout(fig: go.Figure, t: Theme, *, title: str = "", y_title: str = "", x_title: str = "", height: int = 420, legend: bool = True) -> go.Figure:
    fig.update_layout(
        title={"text": title, "font": {"size": 15, "color": t.ink}, "x": 0, "xanchor": "left"} if title else None,
        paper_bgcolor=t.surface,
        plot_bgcolor=t.surface,
        font={"family": FONT, "color": t.ink2, "size": 12},
        height=height,
        margin={"l": 60, "r": 120, "t": 56 if title else 24, "b": 48},
        showlegend=legend,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "font": {"color": t.ink2}},
        hoverlabel={"bgcolor": t.surface, "bordercolor": t.axis, "font": {"color": t.ink, "family": FONT}},
    )
    axis = {"gridcolor": t.grid, "gridwidth": 1, "linecolor": t.axis, "zerolinecolor": t.axis, "tickfont": {"color": t.muted}, "title": {"font": {"color": t.ink2}}}
    fig.update_xaxes(**axis, title_text=x_title, showgrid=False, showline=True, ticks="outside", tickcolor=t.axis, automargin=True)
    fig.update_yaxes(**axis, title_text=y_title, showgrid=True, zeroline=False, automargin=True)
    return fig


def _policy_line(fig: go.Figure, t: Theme, x: float, label: str) -> None:
    fig.add_vline(x=x - 0.5, line={"color": t.muted, "width": 1})
    fig.add_annotation(x=x - 0.5, y=1, yref="paper", text=label, showarrow=False, xanchor="left", yanchor="top", xshift=4, font={"color": t.ink2, "size": 11})


def _years(fig: go.Figure, years) -> None:
    fig.update_xaxes(range=[float(min(years)) - 0.5, float(max(years)) + 0.5])


def _end_label(fig: go.Figure, t: Theme, x: float, y: float, text: str) -> None:
    fig.add_annotation(x=x, y=y, text=text, showarrow=False, xanchor="left", xshift=8, font={"color": t.ink2, "size": 11})


def actual_vs_synthetic(series: pd.DataFrame, t0: int, treated: str, y_title: str, t: Theme) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=series["year"], y=series["actual"], name=treated, mode="lines", line={"color": t.treated, "width": 2}, hovertemplate="%{y:.3~f}")
    fig.add_scatter(x=series["year"], y=series["synthetic"], name=f"Synthetic {treated}", mode="lines", line={"color": t.synthetic, "width": 2}, hovertemplate="%{y:.3~f}")
    last = series.iloc[-1]
    _end_label(fig, t, last["year"], last["actual"], treated)
    _end_label(fig, t, last["year"], last["synthetic"], f"Synthetic {treated}")
    _policy_line(fig, t, t0, "Policy")
    _layout(fig, t, y_title=y_title)
    _years(fig, series["year"])
    fig.update_layout(hovermode="x unified")
    return fig


def gap(series: pd.DataFrame, t0: int, y_title: str, t: Theme) -> go.Figure:
    fig = go.Figure()
    fig.add_hline(y=0, line={"color": t.axis, "width": 1})
    fig.add_scatter(x=series["year"], y=series["gap"], name="Gap", mode="lines", line={"color": t.treated, "width": 2}, hovertemplate="%{x}: %{y:.3~f}<extra>gap</extra>")
    _policy_line(fig, t, t0, "Policy")
    _layout(fig, t, y_title=y_title, legend=False, height=320)
    _years(fig, series["year"])
    return fig


def weights(w: pd.DataFrame, t: Theme, threshold: float = 1e-3) -> go.Figure:
    w = w[w["weight"] > threshold].sort_values("weight")
    fig = go.Figure(
        go.Bar(
            x=w["weight"], y=w["unit"], orientation="h", marker={"color": t.treated, "cornerradius": 4},
            text=[f"{v:.3f}" for v in w["weight"]], textposition="outside", textfont={"color": t.ink2}, cliponaxis=False,
            hovertemplate="%{y}: %{x:.3f}<extra></extra>",
        )
    )
    _layout(fig, t, x_title="Weight in the synthetic unit", legend=False, height=max(220, 40 + 34 * len(w)))
    fig.update_layout(bargap=0.45, margin={"r": 60})
    fig.update_xaxes(range=[0, max(0.05, float(w["weight"].max()) * 1.18)], showgrid=True)
    fig.update_yaxes(showgrid=False)
    return fig


def placebo_spaghetti(gaps: pd.DataFrame, treated: str, t0: int, keep: set[str], y_title: str, t: Theme) -> go.Figure:
    fig = go.Figure()
    fig.add_hline(y=0, line={"color": t.axis, "width": 1})
    first = True
    for unit, g in gaps.groupby("unit"):
        if unit == treated or unit not in keep:
            continue
        fig.add_scatter(
            x=g["year"], y=g["gap"], mode="lines", line={"color": t.context, "width": 1}, name="Placebo (donor treated as if)",
            legendgroup="placebo", showlegend=first, hovertemplate=f"{unit}<br>%{{x}}: %{{y:.3~f}}<extra></extra>",
        )
        first = False
    g = gaps[gaps["unit"] == treated]
    fig.add_scatter(x=g["year"], y=g["gap"], mode="lines", line={"color": t.treated, "width": 2.5}, name=treated, hovertemplate=f"{treated}<br>%{{x}}: %{{y:.3~f}}<extra></extra>")
    _end_label(fig, t, g["year"].iloc[-1], g["gap"].iloc[-1], treated)
    _policy_line(fig, t, t0, "Policy")
    _layout(fig, t, y_title=y_title, height=460)
    _years(fig, gaps["year"])
    return fig


def ratio_ranks(stats: pd.DataFrame, treated: str, t: Theme) -> go.Figure:
    s = stats.sort_values("rmspe_ratio")
    colors = [t.treated if u == treated else t.context for u in s["unit"]]
    fig = go.Figure(
        go.Bar(
            x=s["rmspe_ratio"], y=s["unit"], orientation="h", marker={"color": colors, "cornerradius": 4},
            hovertemplate="%{y}: ratio %{x:.2f}<extra></extra>",
        )
    )
    _layout(fig, t, x_title="Post-period RMSPE / pre-period RMSPE", legend=False, height=max(320, 18 * len(s) + 80))
    fig.update_layout(bargap=0.3, margin={"r": 40})
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(showgrid=False, tickfont={"size": 10})
    return fig


def placebo_in_time(pt: pd.DataFrame, fake: int, real: int, treated: str, y_title: str, t: Theme) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=pt["year"], y=pt["actual"], name=treated, mode="lines", line={"color": t.treated, "width": 2}, hovertemplate="%{y:.3~f}")
    fig.add_scatter(x=pt["year"], y=pt["synthetic"], name=f"Synthetic {treated} (fitted before {fake})", mode="lines", line={"color": t.synthetic, "width": 2}, hovertemplate="%{y:.3~f}")
    _policy_line(fig, t, fake, f"Fake policy {fake}")
    fig.add_vline(x=real - 0.5, line={"color": t.muted, "width": 1})
    _layout(fig, t, y_title=y_title)
    _years(fig, pt["year"])
    fig.update_layout(hovermode="x unified")
    return fig


def leave_one_out(series: pd.DataFrame, loo: pd.DataFrame, t0: int, treated: str, y_title: str, t: Theme) -> go.Figure:
    fig = go.Figure()
    first = True
    for d, g in loo.groupby("dropped"):
        fig.add_scatter(
            x=g["year"], y=g["synthetic"], mode="lines", line={"color": t.context, "width": 1}, name="Synthetic, one donor dropped",
            legendgroup="loo", showlegend=first, hovertemplate=f"without {d}<br>%{{x}}: %{{y:.3~f}}<extra></extra>",
        )
        first = False
    fig.add_scatter(x=series["year"], y=series["synthetic"], name=f"Synthetic {treated}", mode="lines", line={"color": t.synthetic, "width": 2}, hovertemplate="%{y:.3~f}<extra>synthetic</extra>")
    fig.add_scatter(x=series["year"], y=series["actual"], name=treated, mode="lines", line={"color": t.treated, "width": 2}, hovertemplate="%{y:.3~f}<extra>actual</extra>")
    _policy_line(fig, t, t0, "Policy")
    _layout(fig, t, y_title=y_title)
    _years(fig, series["year"])
    return fig


def estimates(rows: pd.DataFrame, t: Theme, x_title: str) -> go.Figure:
    """Dot + 95% interval per estimator (one hue: the rows are labelled on the axis)."""
    rows = rows.iloc[::-1]
    has_ci = rows["ci_low"].notna()
    fig = go.Figure()
    fig.add_vline(x=0, line={"color": t.axis, "width": 1})
    fig.add_scatter(
        x=rows["estimate"], y=rows["label"], mode="markers",
        marker={"color": t.treated, "size": 11, "line": {"color": t.surface, "width": 2}},
        error_x={"type": "data", "symmetric": False, "array": (rows["ci_high"] - rows["estimate"]).where(has_ci, 0), "arrayminus": (rows["estimate"] - rows["ci_low"]).where(has_ci, 0), "color": t.treated, "thickness": 2, "width": 0},
        text=[f"{e:.2f}" for e in rows["estimate"]], textposition="top center", textfont={"color": t.ink2},
        customdata=rows[["ci_low", "ci_high"]].to_numpy(),
        hovertemplate="%{y}: %{x:.2f}<br>95% CI %{customdata[0]:.2f} to %{customdata[1]:.2f}<extra></extra>",
    )
    fig.update_traces(mode="markers+text")
    _layout(fig, t, x_title=x_title, legend=False, height=80 + 60 * len(rows))
    fig.update_yaxes(showgrid=False)
    fig.update_xaxes(showgrid=True)
    return fig
