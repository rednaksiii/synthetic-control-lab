"""Command line: ``python -m synthpolicy {fetch,run,lock,status,dashboard}``."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time

from .data._http import PROJECT_ROOT


def _fetch(a: argparse.Namespace) -> None:
    from .data.panel import build_state_panel, panel_metadata, panel_path

    panel = build_state_panel(
        a.start,
        a.end,
        sources=tuple(a.sources.split(",")),
        qcew_industries=tuple(a.industries.split(",")),
        refresh=a.refresh,
        strict=a.strict,
    )
    meta = panel_metadata()
    print(f"Panel: {panel.shape[0]} rows x {panel.shape[1]} columns -> {panel_path()}")
    for name, info in meta["sources"].items():
        print(f"  {name:5s} {info['status']}" + (f": {info['reason']}" if info["status"] != "ok" else f" ({len(info['columns'])} columns)"))


def _run(a: argparse.Namespace) -> None:
    from .pipeline import run_study
    from .results import save_results

    last = {"stage": None}

    def progress(stage: str, i: int, n: int) -> None:
        if stage != last["stage"]:
            print(f"  {stage}...", flush=True)
            last["stage"] = stage

    t = time.perf_counter()
    r = run_study(a.spec, n_jobs=a.jobs, progress=progress)
    out = save_results(r)
    print(f"\n{r.lock['label']}\n{r.decision['verdict']}")
    if r.published:
        n_ok = sum(x["match"] for x in r.published)
        print(f"Published-result check: {n_ok}/{len(r.published)} items within tolerance")
    print(f"Results -> {out}  ({time.perf_counter() - t:.0f}s)")


def _lock(a: argparse.Namespace) -> None:
    from .spec import lock_spec

    print(json.dumps(lock_spec(a.spec, a.note), indent=2))


def _status(a: argparse.Namespace) -> None:
    from .spec import lock_status

    print(json.dumps(lock_status(a.spec), indent=2))


def _dashboard(a: argparse.Namespace) -> None:
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(PROJECT_ROOT / "dashboard" / "app.py")], check=False)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="synthpolicy", description=__doc__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download sources and build the state-by-year panel")
    f.add_argument("--start", type=int, default=1990)
    f.add_argument("--end", type=int, default=None)
    f.add_argument("--sources", default="qcew,laus,bea,acs")
    f.add_argument("--industries", default="10", help="comma-separated QCEW NAICS codes, e.g. 10,722")
    f.add_argument("--refresh", action="store_true", help="ignore the cache and re-download")
    f.add_argument("--strict", action="store_true", help="fail if any source fails")
    f.set_defaults(func=_fetch)

    r = sub.add_parser("run", help="run a full study from a spec file")
    r.add_argument("spec")
    r.add_argument("--jobs", type=int, default=1, help="parallel processes for placebo fits")
    r.set_defaults(func=_run)

    lk = sub.add_parser("lock", help="pre-register a spec (records its hash; cannot be undone)")
    lk.add_argument("spec")
    lk.add_argument("--note", default="")
    lk.set_defaults(func=_lock)

    st = sub.add_parser("status", help="show whether a spec matches its lock")
    st.add_argument("spec")
    st.set_defaults(func=_status)

    sub.add_parser("dashboard", help="launch the Streamlit dashboard").set_defaults(func=_dashboard)

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    a.func(a)
