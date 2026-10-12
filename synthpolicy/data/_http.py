"""Shared HTTP session, local cache layout, and Parquet caching helpers."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("synthpolicy.data")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
USER_AGENT = "synthpolicy/0.1 (synthetic-control policy research; python-requests)"


def cache_dir(*parts: str) -> Path:
    """Directory under the cache root (``$SYNTHPOLICY_CACHE`` or ``<project>/cache``), created on demand."""
    root = Path(os.environ.get("SYNTHPOLICY_CACHE", PROJECT_ROOT / "cache"))
    path = root.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        retry = Retry(total=4, backoff_factor=2.0, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=None)
        s.mount("https://", HTTPAdapter(max_retries=retry))
        _session = s
    return _session


def download(url: str, dest: Path, *, refresh: bool = False, timeout: int = 300, attempts: int = 4) -> Path:
    """Stream ``url`` to ``dest`` atomically; reuse an existing file unless ``refresh``.

    Transfers broken mid-stream (dropped connection, laptop sleep) are retried from scratch.
    """
    if dest.exists() and not refresh:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            return _download_once(url, dest, timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt == attempts:
                raise
            wait = 10 * attempt
            log.warning("Download of %s failed (%s); retry %d/%d in %ds", url, exc, attempt, attempts - 1, wait)
            time.sleep(wait)
    return dest


def _download_once(url: str, dest: Path, timeout: int) -> Path:
    log.info("Downloading %s", url)
    with session().get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        fd, tmp = tempfile.mkstemp(dir=dest.parent, suffix=".part")
        try:
            with os.fdopen(fd, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            os.replace(tmp, dest)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    return dest


def cached_frame(path: Path, build: Callable[[], pd.DataFrame], *, refresh: bool = False) -> pd.DataFrame:
    """Return the Parquet file at ``path``, building and writing it first if needed."""
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    df = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.part")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)
    return df


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def short_hash(*items: object) -> str:
    return hashlib.sha1("|".join(map(str, items)).encode()).hexdigest()[:10]
