"""Canonical bid, prediction and simulator-evidence records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from argos.versions import OBSERVATION_SCHEMA, QOS_ESTIMATOR, QOS_PARITY_ATOL, QOS_PARITY_RTOL


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
class JobIdentity:
    index: int
    section: str
    descriptors: tuple[float, ...]


@dataclass(frozen=True)
class QoSEvidence:
    job: JobIdentity
    pj: float
    observation_count: int | None = None
    finished_count: int | None = None
    unfinished_count: int | None = None
    exceedance_count: int | None = None
    estimator_numerator: int | None = None
    estimator_denominator: int | None = None
    estimator: str = QOS_ESTIMATOR
    horizon_seconds: float = 3600.0
    threshold_sojourn_seconds: float | None = None
    threshold_exceeds_horizon: bool | None = None

    def __post_init__(self) -> None:
        n = self.observation_count
        counts = (self.finished_count, self.unfinished_count, self.exceedance_count)
        if n is None:
            if any(
                v is not None
                for v in (*counts, self.estimator_numerator, self.estimator_denominator)
            ):
                raise ValueError("Unknown sample size cannot have known estimator counts")
            return
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("Invalid QoS observation count")
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in counts):
            raise ValueError("Incomplete QoS count reconstruction")
        if self.finished_count + self.unfinished_count != n or self.exceedance_count > n:
            raise ValueError("Inconsistent QoS counts")
        m = self.exceedance_count
        numerator = max(m - 1, 0) if n >= 2 else m if n else None
        denominator = n - 1 if n >= 2 else 1 if n else None
        if (self.estimator_numerator, self.estimator_denominator) != (numerator, denominator):
            raise ValueError("Inconsistent QoS estimator numerator/denominator")
        expected = numerator / denominator if n else 0
        if abs(self.pj - expected) > QOS_PARITY_ATOL + QOS_PARITY_RTOL * abs(expected):
            raise ValueError("Reported QoS probability fails estimator parity")


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
    qos_evidence: tuple[QoSEvidence, ...] | None = None
    schema_version: int = OBSERVATION_SCHEMA

    @property
    def execution_status(self) -> str:
        """Normalize historical scientific labels without rewriting persisted history."""
        return "PARSED" if self.valid else self.status


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
    if data.get("qos_evidence") is not None:
        data["qos_evidence"] = evidence_from_dict(data["qos_evidence"])
    if "schema_version" not in data:
        data["schema_version"] = 1  # Historical files never acquire evidence implicitly.
    return FlexDCObservation(**data)


def evidence_from_dict(rows: list[dict]) -> tuple[QoSEvidence, ...]:
    result = []
    for row in rows:
        row = dict(row)
        job = dict(row["job"])
        job["descriptors"] = tuple(job["descriptors"])
        row["job"] = JobIdentity(**job)
        result.append(QoSEvidence(**row))
    return tuple(result)
