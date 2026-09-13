"""Canonical bid, prediction and simulator-evidence records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Metrics:
    mean_tracking: float
    p90: float
    pj: tuple[float, ...]
    objective: float


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    Pbar: float
    R: float
    weights: tuple[float, ...]
    source: str
    start_id: int | None = None
    iteration: int | None = None
    region_id: str | None = None
    prediction: Metrics | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Region:
    region_id: str
    representative: Candidate
    members: tuple[str, ...]
    center: tuple[float, ...]
    iterations: tuple[int, ...]


@dataclass(frozen=True)
class FlexDCObservation:
    candidate: Candidate
    seed: int
    phase: str
    batch: int
    valid: bool
    metrics: Metrics | None
    status: str
    runtime_seconds: float
    execution_id: str
    reported: dict[str, Any] = field(default_factory=dict)
    raw_paths: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    returncode: int | None = None
    worker: str = ""
    residuals: dict[str, Any] = field(default_factory=dict)


def candidate_from_dict(data: dict) -> Candidate:
    data = dict(data)
    data["weights"] = tuple(data["weights"])
    if data.get("prediction"):
        prediction = dict(data["prediction"])
        prediction["pj"] = tuple(prediction["pj"])
        data["prediction"] = Metrics(**prediction)
    return Candidate(**data)


def observation_from_dict(data: dict) -> FlexDCObservation:
    data = dict(data)
    data["candidate"] = candidate_from_dict(data["candidate"])
    if data.get("metrics"):
        metrics = dict(data["metrics"])
        metrics["pj"] = tuple(metrics["pj"])
        data["metrics"] = Metrics(**metrics)
    return FlexDCObservation(**data)
