"""Study specifications (TOML) and the pre-registration lock.

A study spec is the machine-readable half of a pre-registration: the treated unit, the first
treated period, the outcome, the donor-pool rules, the predictors, the inference plan, and the
decision rule for what counts as a meaningful effect. ``PREREGISTRATION.md`` is the human-readable
half and explains each choice.

Locking a spec records its SHA-256 and a timestamp in ``<spec>.lock.json``. Every run reports
whether the spec it used matches the lock, so results from a spec edited after locking (i.e.
after the analyst could have seen results) are labelled exploratory rather than confirmatory.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model.synth import Predictor

OUTCOME_ALIAS = "@outcome"
TRANSFORMS = ("none", "log", "index", "log_demeaned")


@dataclass(frozen=True)
class DonorRule:
    """Keep a donor only if ``variable`` in ``year`` lies within [min, max]."""

    variable: str
    year: int
    min: float | None = None
    max: float | None = None
    reason: str = ""


@dataclass(frozen=True)
class StudySpec:
    path: Path | None
    name: str
    title: str
    status: str
    dataset: str
    unit: str
    time: str
    start: int | None
    end: int | None
    treated: str
    treatment_time: int
    policy_note: str
    outcome: str
    outcome_label: str
    transform: str
    base_start: int | None
    base_end: int | None
    donor_pool: list[str] | str
    exclude: dict[str, str]
    exclude_neighbors: bool
    rules: list[DonorRule]
    predictors: list[Predictor]
    v_method: str
    optimize_start: int | None
    optimize_end: int | None
    n_random_starts: int
    tie_break: float
    placebo_in_space: bool
    mspe_filters: list[float]
    placebo_times: list[int]
    leave_one_out: bool
    sdid: bool
    decision: dict[str, Any]
    published: dict[str, Any]
    raw: dict[str, Any] = field(repr=False)

    @property
    def outcome_column(self) -> str:
        return self.outcome if self.transform == "none" else f"{self.outcome}__{self.transform}"


def _predictor(d: dict) -> Predictor:
    return Predictor(d["variable"], int(d["start"]), int(d["end"]) if "end" in d else None, d.get("label"))


def load_spec(path: str | Path) -> StudySpec:
    path = Path(path)
    return spec_from_dict(tomllib.loads(path.read_text(encoding="utf-8")), path)


def spec_from_dict(raw: dict[str, Any], path: Path | None = None) -> StudySpec:
    """Build a spec from the parsed TOML structure (also used for ad-hoc exploratory specs)."""
    study, data, treat, out = raw["study"], raw["data"], raw["treatment"], raw["outcome"]
    donors = raw.get("donors", {})
    model = raw.get("model", {})
    inf = raw.get("inference", {})
    transform = out.get("transform", "none")
    if transform not in TRANSFORMS:
        raise ValueError(f"Unknown transform {transform!r}; choose from {TRANSFORMS}")
    return StudySpec(
        path=path,
        name=study["name"],
        title=study.get("title", study["name"]),
        status=study.get("status", "confirmatory"),
        dataset=data["source"],
        unit=data.get("unit", "state"),
        time=data.get("time", "year"),
        start=data.get("start"),
        end=data.get("end"),
        treated=treat["unit"],
        treatment_time=int(treat["first_treated_period"]),
        policy_note=treat.get("note", ""),
        outcome=out["variable"],
        outcome_label=out.get("label", out["variable"]),
        transform=transform,
        base_start=out.get("base_start"),
        base_end=out.get("base_end"),
        donor_pool=donors.get("pool", "all"),
        exclude=dict(donors.get("exclude", {})),
        exclude_neighbors=bool(donors.get("exclude_neighbors", False)),
        rules=[DonorRule(**r) for r in donors.get("rules", [])],
        predictors=[_predictor(p) for p in raw.get("predictors", [])],
        v_method=model.get("v_method", "nested"),
        optimize_start=model.get("optimize_start"),
        optimize_end=model.get("optimize_end"),
        n_random_starts=int(model.get("n_random_starts", 4)),
        tie_break=float(model.get("tie_break", 0.0)),
        placebo_in_space=bool(inf.get("placebo_in_space", True)),
        mspe_filters=[float(x) for x in inf.get("mspe_filters", [20, 5, 2])],
        placebo_times=[int(x) for x in inf.get("placebo_in_time", [])],
        leave_one_out=bool(inf.get("leave_one_out", True)),
        sdid=bool(raw.get("robustness", {}).get("sdid", True)),
        decision=dict(raw.get("decision", {})),
        published=dict(raw.get("published", {})),
        raw=raw,
    )


# --------------------------------------------------------------------------- pre-registration lock


def _lock_path(spec_path: Path) -> Path:
    return spec_path.with_suffix(".lock.json")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def lock_spec(spec_path: str | Path, note: str = "") -> dict:
    spec_path = Path(spec_path)
    load_spec(spec_path)  # refuse to lock a spec that does not parse
    lock_file = _lock_path(spec_path)
    if lock_file.exists():
        raise FileExistsError(f"{lock_file.name} already exists; a locked spec must not be re-locked")
    record = {
        "spec": spec_path.name,
        "sha256": file_sha256(spec_path),
        "locked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "note": note,
    }
    lock_file.write_text(json.dumps(record, indent=2) + "\n")
    return record


def lock_status(spec_path: str | Path) -> dict:
    spec_path = Path(spec_path)
    lock_file = _lock_path(spec_path)
    current = file_sha256(spec_path)
    if not lock_file.exists():
        return {"state": "unlocked", "sha256": current, "label": "EXPLORATORY (spec not pre-registered)"}
    record = json.loads(lock_file.read_text())
    if record["sha256"] != current:
        return {
            "state": "modified",
            "sha256": current,
            "locked_sha256": record["sha256"],
            "locked_at": record["locked_at"],
            "label": "EXPLORATORY (spec changed after it was locked)",
        }
    return {"state": "locked", "sha256": current, "locked_at": record["locked_at"], "label": "CONFIRMATORY (matches locked spec)"}
