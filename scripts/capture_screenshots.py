"""Capture high-resolution screenshots of the dashboard into docs/screenshots/.

Starts the Streamlit app on a spare port, drives the installed Google Chrome headlessly with
Playwright, and opens each view through the dashboard's deep links (?study=...&tab=...).

    python scripts/capture_screenshots.py            # light theme
    python scripts/capture_screenshots.py --dark     # dark theme
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
PORT = 8599

# (file name, study, tab, crop after the n-th chart in the tab, or None for the whole tab)
SHOTS = [
    ("01_prop99_actual_vs_synthetic", "prop99", "Actual vs synthetic", None),
    ("02_prop99_placebo_in_space", "prop99", "Placebo in space", 0),
    ("03_prop99_weights_balance", "prop99", "Weights & balance", None),
    ("04_prop99_replication_check", "prop99", "Replication", None),
    ("05_kansas_actual_vs_synthetic", "kansas_2012", "Actual vs synthetic", None),
    ("06_kansas_placebo_in_space", "kansas_2012", "Placebo in space", 0),
    ("07_kansas_synthetic_did", "kansas_2012", "Synthetic DiD", 1),
    ("08_kansas_decision_checks", "kansas_2012", "Checks", None),
]

# Bottom edge (CSS px) of the active tab, or of its n-th Plotly chart.
BOTTOM_JS = """(n) => {
  const panel = [...document.querySelectorAll('[role="tabpanel"]')].find(p => p.offsetParent !== null);
  if (n === null) return panel.getBoundingClientRect().bottom;
  return panel.querySelectorAll('.js-plotly-plot')[n].getBoundingClientRect().bottom;
}"""


def wait_for_server(url: str, timeout: float = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url + "/_stcore/health", timeout=2)
            return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError("Streamlit did not start")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dark", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    base = f"http://localhost:{PORT}"
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "dashboard" / "app.py"), "--server.headless", "true", "--server.port", str(PORT)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_server(base)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            for name, study, tab, crop in SHOTS:
                page = browser.new_page(viewport={"width": 1440, "height": 3000}, device_scale_factor=2, color_scheme="dark" if a.dark else "light")
                page.goto(f"{base}/?{urllib.parse.urlencode({'study': study, 'tab': tab})}")
                page.wait_for_selector('[data-testid="stMainBlockContainer"]')
                page.wait_for_function("() => !document.querySelector('[data-testid=stStatusWidget]')", timeout=60_000)
                page.wait_for_timeout(3000)  # let Plotly finish drawing
                bottom = page.evaluate(BOTTOM_JS, crop)
                page.set_viewport_size({"width": 1440, "height": int(bottom) + 12})
                page.wait_for_timeout(1000)
                suffix = "_dark" if a.dark else ""
                path = OUT / f"{name}{suffix}.png"
                page.screenshot(path=str(path))
                print(path.relative_to(ROOT))
                page.close()
            browser.close()
    finally:
        server.terminate()


if __name__ == "__main__":
    main()
