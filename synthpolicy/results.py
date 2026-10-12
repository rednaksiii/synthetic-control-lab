"""Persist study results as Parquet + JSON (read by the dashboard) and write a Markdown report."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from .data._http import PROJECT_ROOT
from .pipeline import StudyResult

RESULTS_ROOT = PROJECT_ROOT / "results"


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if hasattr(x, "item"):
        x = x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def summary_dict(r: StudyResult) -> dict:
    s = r.spec
    out = {
        "name": s.name,
        "title": s.title,
        "status": s.status,
        "run_at": r.run_at,
        "lock": r.lock,
        "design": {
            "dataset": s.dataset,
            "treated": s.treated,
            "first_treated_period": s.treatment_time,
            "window": [int(r.fit.actual.index[0]), int(r.fit.actual.index[-1])],
            "outcome": s.outcome,
            "outcome_label": s.outcome_label,
            "transform": s.transform,
            "outcome_column": s.outcome_column,
            "v_method": s.v_method,
            "policy_note": s.policy_note,
            "n_donors": len(r.synth_spec.donors),
            "donors": list(r.synth_spec.donors),
            "excluded": r.excluded,
            "predictors": [p.name for p in r.synth_spec.predictors],
        },
        "fit": r.fit.summary(),
        "placebo_in_space": r.placebo_space.summary(tuple(s.mspe_filters)) if r.placebo_space else None,
        "placebo_in_time": [p.summary() for p in r.placebo_times],
        "leave_one_out": r.loo.summary() if r.loo else None,
        "sdid": r.sdid.summary() if r.sdid else None,
        "decision": r.decision,
        "published": r.published,
        "published_source": s.published.get("source", ""),
    }
    return _clean(out)


def frames(r: StudyResult) -> dict[str, pd.DataFrame]:
    """All tabular outputs of a study, keyed by the file stem they are saved under."""
    f = r.fit
    out = {
        "series": pd.DataFrame({"year": f.actual.index, "actual": f.actual.values, "synthetic": f.synthetic.values, "gap": f.gap.values}),
        "weights": f.weights.rename_axis("unit").reset_index(),
        "balance": f.balance.join(f.v).rename_axis("predictor").reset_index(),
        "donors": pd.DataFrame(
            [{"unit": u, "status": "donor", "reason": ""} for u in r.synth_spec.donors]
            + [{"unit": u, "status": "excluded", "reason": why} for u, why in sorted(r.excluded.items())]
        ),
    }
    if r.placebo_space:
        out["placebo_gaps"] = r.placebo_space.gaps.rename_axis("year").reset_index().melt(id_vars="year", var_name="unit", value_name="gap")
        out["placebo_stats"] = r.placebo_space.stats.reset_index()
    if r.placebo_times:
        out["placebo_time"] = pd.concat(
            pd.DataFrame({"fake_time": p.fake_time, "year": p.fit.actual.index, "actual": p.fit.actual.values, "synthetic": p.fit.synthetic.values, "gap": p.fit.gap.values})
            for p in r.placebo_times
        )
    if r.loo and r.loo.fits:
        out["loo"] = pd.concat(pd.DataFrame({"dropped": d, "year": x.synthetic.index, "synthetic": x.synthetic.values, "gap": x.gap.values}) for d, x in r.loo.fits.items())
        out["loo_stats"] = r.loo.stats.reset_index()
    if r.sdid:
        out["sdid_estimates"] = r.sdid.estimates.rename_axis("method").reset_index()
        out["sdid_paths"] = r.sdid.trajectories.rename_axis("year").reset_index()
        out["sdid_weights"] = r.sdid.omega.rename_axis("unit").reset_index()
        out["sdid_lambda"] = r.sdid.lam.rename_axis("year").reset_index()
    return out


def as_bundle(r: StudyResult) -> dict:
    """The same structure ``load_results`` returns, built in memory (used by the dashboard explorer)."""
    return {"summary": summary_dict(r), "report": markdown_report(summary_dict(r), r), **frames(r)}


def save_results(r: StudyResult, out_dir: Path | None = None) -> Path:
    out = out_dir or RESULTS_ROOT / r.spec.name
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.parquet"):
        old.unlink()
    for stem, df in frames(r).items():
        df.to_parquet(out / f"{stem}.parquet", index=False)
    summary = summary_dict(r)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    (out / "report.md").write_text(markdown_report(summary, r), encoding="utf-8")
    return out


def list_results(root: Path = RESULTS_ROOT) -> list[Path]:
    return sorted(p.parent for p in root.glob("*/summary.json")) if root.exists() else []


def load_results(path: Path) -> dict:
    out: dict = {"summary": json.loads((path / "summary.json").read_text())}
    report = path / "report.md"
    out["report"] = report.read_text(encoding="utf-8") if report.exists() else ""
    for f in path.glob("*.parquet"):
        out[f.stem] = pd.read_parquet(f)
    return out


# --------------------------------------------------------------------------- report


def _fmt(x, digits: int = 3) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, (int, float)):
        return f"{x:.{digits}g}" if abs(x) < 1e4 else f"{x:,.0f}"
    return str(x)


def _table(rows: list[dict], cols: list[str]) -> str:
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    return head + "".join("| " + " | ".join(_fmt(r.get(c)) for c in cols) + " |\n" for r in rows)


def markdown_report(s: dict, r: StudyResult) -> str:
    d, fit = s["design"], s["fit"]
    lines = [
        f"# {s['title']}",
        "",
        f"*Run {s['run_at']}. Status: **{s['lock']['label']}**.*",
        "",
        "## Verdict (decision rule in the spec)",
        "",
        f"> {s['decision']['verdict']}",
        "",
        _table(s["decision"]["checks"], ["check", "value", "threshold", "passed"]),
        "## Design",
        "",
        f"- Treated unit: **{d['treated']}**, first treated period **{d['first_treated_period']}**, window {d['window'][0]}-{d['window'][1]}",
        f"- Outcome: {d['outcome_label']} (`{d['outcome_column']}`, transform `{d['transform']}`)",
        f"- Donor pool: {d['n_donors']} units; {len(d['excluded'])} excluded",
        f"- Predictors: {', '.join(d['predictors'])}",
        f"- V selection: `{d['v_method']}`",
        "",
        "## Main estimate",
        "",
        f"- Pre-period RMSPE **{_fmt(fit['pre_rmspe'])}** (mean absolute error {_fmt(fit['pre_mape_pct'])}% of the treated level)",
        f"- Mean post-period gap **{_fmt(fit['mean_post_gap'])}**; gap in final year {_fmt(fit['last_gap'])}",
        f"- Post/pre RMSPE ratio {_fmt(fit['rmspe_ratio'])}",
        *[f"- **Warning:** {n}" for n in fit.get("notes", [])],
        "",
        "Donor weights:",
        "",
        _table([{"donor": k, "weight": v} for k, v in fit["weights"].items()], ["donor", "weight"]),
        "Predictor balance:",
        "",
        _table(r.fit.balance.join(r.fit.v).reset_index().rename(columns={"index": "predictor"}).to_dict("records"), ["predictor", "treated", "synthetic", "donor_mean", "v"]),
    ]
    if s["placebo_in_space"]:
        p = s["placebo_in_space"]
        lines += [
            "## Placebo in space",
            "",
            f"The treated unit ranks **{p['treated_ratio_rank']} of {p['n_units']}** by post/pre RMSPE ratio: p = {_fmt(p['p_value_ratio'])} "
            f"(smallest attainable {_fmt(p['min_attainable_p'])}). Using |mean post gap| instead: p = {_fmt(p['p_value_mean_gap'])}.",
            "",
            _table([{"filter": f"pre-MSPE <= {k}x treated", **v} for k, v in p["filtered"].items()], ["filter", "n_units", "p_value_ratio", "p_value_mean_gap"]),
        ]
    if s["placebo_in_time"]:
        lines += ["## Placebo in time", "", _table(s["placebo_in_time"], ["fake_time", "pre_rmspe", "mean_placebo_gap", "rmspe_ratio"])]
        for pt in s["placebo_in_time"]:
            if pt["dropped_predictors"]:
                lines += [f"- {pt['fake_time']}: dropped predictors without data: {', '.join(pt['dropped_predictors'])}", ""]
    if s["leave_one_out"] and s["leave_one_out"].get("n_refits"):
        lines += ["## Leave-one-out", "", _table(r.loo.stats.reset_index().to_dict("records"), ["dropped", "dropped_weight", "pre_rmspe", "mean_post_gap"])]
    if s["sdid"]:
        rows = [{"method": m, **v} for m, v in s["sdid"].items() if m in ("sdid", "sc", "did")]
        lines += [
            "## Robustness: synthetic difference-in-differences",
            "",
            "Average post-period effect; placebo standard errors (each control as pseudo-treated once).",
            "",
            _table(rows, ["method", "estimate", "se", "ci_low", "ci_high"]),
        ]
    if s["published"]:
        n_ok = sum(bool(x["match"]) for x in s["published"])
        lines += [
            "## Comparison with published results",
            "",
            f"{n_ok} of {len(s['published'])} items within tolerance. Source: {s['published_source']}",
            "",
            _table(s["published"], ["item", "published", "ours", "tolerance", "match"]),
        ]
    lines += [
        "## Excluded donors",
        "",
        _table([{"unit": k, "reason": v} for k, v in sorted(d["excluded"].items())], ["unit", "reason"]) if d["excluded"] else "None.\n",
        "## Caveats to address in the write-up",
        "",
        "- **Anticipation**: could agents have reacted before the first treated period?",
        "- **Spillovers**: could the policy have affected donor units (commuting, relocation, cross-border shopping)?",
        "- **Concurrent shocks**: did anything else hit the treated unit (or key donors) around the same time?",
        "- **Interpolation bias**: are the weighted donors similar to the treated unit, not just matched on average?",
        "- **Specification search**: every deviation from the locked spec must be reported as exploratory.",
        "",
    ]
    return "\n".join(lines)
