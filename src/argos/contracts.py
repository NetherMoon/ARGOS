"""One scientific authority for numerical feasibility and measured ranking."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from argos.types import FlexDCObservation, Metrics

TRACKING_LIMIT = 0.30
QOS_LIMIT = 0.10


@dataclass(frozen=True)
class Costs:
    psi1: float
    psi2: float
    tracking_error_constraint: float
    beta: float
    rho: float
    qos_constraint: float

    def validate(self) -> None:
        if self.tracking_error_constraint != TRACKING_LIMIT or self.qos_constraint != QOS_LIMIT:
            raise ValueError(
                "Canonical constraint thresholds disagree with ARGOS behavioral contract"
            )
        if not np.isfinite(list(self.__dict__.values())).all():
            raise ValueError("Non-finite cost constants")

    def objective(self, monetary: float, p90: float, pj: tuple[float, ...]) -> float:
        values = [monetary, p90, *pj]
        if not pj or not np.isfinite(values).all() or p90 < 0 or min(pj) < 0 or max(pj) > 1:
            raise ValueError("Invalid raw objective inputs")
        tracking = self.psi1 * np.logaddexp(0.0, self.psi2 * (p90 - self.tracking_error_constraint))
        qos = self.beta * np.logaddexp(0.0, self.rho * (np.asarray(pj) - self.qos_constraint)).sum()
        return float(monetary + tracking + qos)


def validate_metrics(metrics: Metrics, job_count: int) -> None:
    if (
        len(metrics.pj) != job_count
        or not np.isfinite(
            [metrics.mean_tracking, metrics.p90, metrics.objective, *metrics.pj]
        ).all()
    ):
        raise ValueError("Incomplete or non-finite observation")
    if metrics.mean_tracking < 0 or metrics.p90 < 0 or min(metrics.pj) < 0 or max(metrics.pj) > 1:
        raise ValueError("Metrics outside physical domain")


def feasible(metrics: Metrics) -> bool:
    """Numerical feasibility only; simulator eligibility requires qualified()."""
    validate_metrics(metrics, len(metrics.pj))
    return metrics.p90 <= TRACKING_LIMIT and max(metrics.pj) <= QOS_LIMIT


def violations(metrics: Metrics) -> tuple[float, float]:
    validate_metrics(metrics, len(metrics.pj))
    v = np.maximum(
        0.0, np.array([metrics.p90 / TRACKING_LIMIT - 1, *[p / QOS_LIMIT - 1 for p in metrics.pj]])
    )
    return float(v.max()), float(v.sum())


def rank(metrics: Metrics) -> tuple:
    if feasible(metrics):
        return (0, metrics.objective, 0.0, 0.0)
    worst, total = violations(metrics)
    return (1, worst, total, metrics.objective)


def assessment(o: FlexDCObservation, minimum: int = 1) -> dict:
    numerical = feasible(o.metrics) if o.valid and o.metrics else None
    evidence = o.qos_evidence
    known = (
        o.valid
        and evidence is not None
        and o.metrics is not None
        and len(evidence) == len(o.metrics.pj)
        and all(
            e.job.index == i and e.pj == o.metrics.pj[i] and e.observation_count is not None
            for i, e in enumerate(evidence)
        )
    )
    sufficient = all(e.observation_count >= minimum for e in evidence) if known else None
    qualified_value = bool(o.valid and numerical and sufficient)
    worst, total = violations(o.metrics) if o.valid and o.metrics else (None, None)
    return {
        "tracking_pass": o.metrics.p90 <= TRACKING_LIMIT if o.valid and o.metrics else None,
        "qos_numerical_pass": max(o.metrics.pj) <= QOS_LIMIT if o.valid and o.metrics else None,
        "max_pj": max(o.metrics.pj) if o.valid and o.metrics else None,
        "worst_violation": worst,
        "total_violation": total,
        "per_job_evidence_counts": [e.observation_count for e in evidence]
        if evidence is not None
        else None,
        "ordered_job_sections": [e.job.section for e in evidence] if evidence is not None else None,
        "execution_valid": o.valid,
        "numerical_feasible": numerical,
        "evidence_status": "SUFFICIENT" if sufficient else "INSUFFICIENT" if known else "UNKNOWN",
        "evidence_sufficient": sufficient,
        "evidence_qualified_feasible": qualified_value,
        "min_qos_observations_per_type": minimum,
        "statistical_reliability_established": False,
    }


def qualified(o: FlexDCObservation, minimum: int = 1) -> bool:
    return assessment(o, minimum)["evidence_qualified_feasible"]


def observation_rank(o: FlexDCObservation, minimum: int = 1) -> tuple:
    if qualified(o, minimum):
        return (0, o.metrics.objective, 0, 0)
    if not o.valid or o.metrics is None:
        return (3, float("inf"), 0, 0)
    worst, total = violations(o.metrics)
    return (
        1 if assessment(o, minimum)["evidence_sufficient"] else 2,
        worst,
        total,
        o.metrics.objective,
    )
