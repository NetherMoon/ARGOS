"""Normalized legal geometry with bounded-simplex projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from argos.types import Candidate


@dataclass(frozen=True)
class Domain:
    p_lower: float
    p_upper: float
    pr_upper: float
    r_lower: float
    r_over_p: float
    lower: tuple[float, ...]
    upper: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.lower or len(self.lower) != len(self.upper):
            raise ValueError("Weight domain dimensions invalid")
        if not np.isfinite(
            [
                self.p_lower,
                self.p_upper,
                self.pr_upper,
                self.r_lower,
                self.r_over_p,
                *self.lower,
                *self.upper,
            ]
        ).all():
            raise ValueError("Non-finite domain")
        if (
            self.p_lower <= 0
            or self.p_upper <= self.p_lower
            or self.r_lower < 0
            or self.r_over_p <= 0
        ):
            raise ValueError("Invalid bid domain")
        if (
            any(lo < 0 or hi > 1 or hi < lo for lo, hi in zip(self.lower, self.upper))
            or sum(self.lower) > 1 + 1e-12
            or sum(self.upper) < 1 - 1e-12
        ):
            raise ValueError("Infeasible bounded simplex")
        if min(self.r_max(self.p_lower), self.r_max(self.p_upper)) < self.r_lower - 1e-12:
            raise ValueError("Negative reserve interval in bid domain")

    def r_max(self, pbar: float) -> float:
        return min(self.r_over_p * pbar, self.pr_upper - pbar)

    def validate(self, candidate: Candidate) -> None:
        p, r, w = candidate.Pbar, candidate.R, np.asarray(candidate.weights)
        if len(w) != len(self.lower) or not np.isfinite([p, r, *w]).all():
            raise ValueError("Non-finite or wrong-size candidate")
        eps = 1e-6  # accommodates upstream float32 parameterization, never repairs data
        if (
            not self.p_lower - eps <= p <= self.p_upper + eps
            or not self.r_lower - eps <= r <= self.r_max(p) + eps
        ):
            raise ValueError("Illegal Pbar/R")
        if (
            abs(w.sum() - 1) > eps
            or np.any(w < np.array(self.lower) - eps)
            or np.any(w > np.array(self.upper) + eps)
        ):
            raise ValueError("Illegal weights")

    def encode(self, candidate: Candidate) -> np.ndarray:
        self.validate(candidate)
        span = np.asarray(self.upper) - self.lower
        weights = np.divide(
            np.asarray(candidate.weights) - self.lower,
            span,
            out=np.zeros_like(span),
            where=span > 0,
        )
        return np.r_[
            (candidate.Pbar - self.p_lower) / (self.p_upper - self.p_lower),
            (
                (candidate.R - self.r_lower) / (self.r_max(candidate.Pbar) - self.r_lower)
                if self.r_max(candidate.Pbar) - self.r_lower > 1e-12
                else 0.0
            ),
            weights,
        ]

    def distance(self, a: Candidate, b: Candidate) -> float:
        diff = self.encode(a) - self.encode(b)
        # Equal aggregate contributions from Pbar, conditional reserve, and weight block.
        return float(np.sqrt((diff[0] ** 2 + diff[1] ** 2 + np.mean(diff[2:] ** 2)) / 3))

    def project(self, weights: np.ndarray) -> tuple[float, ...]:
        weights = np.asarray(weights, dtype=float)
        if len(weights) != len(self.lower) or not np.isfinite(weights).all():
            raise ValueError("Invalid projection input")
        lo, hi = np.asarray(self.lower), np.asarray(self.upper)
        left, right = float(np.min(weights - hi) - 1), float(np.max(weights - lo) + 1)
        for _ in range(80):
            mid = (left + right) / 2
            if np.clip(weights - mid, lo, hi).sum() > 1:
                left = mid
            else:
                right = mid
        result = np.clip(weights - (left + right) / 2, lo, hi)
        if abs(result.sum() - 1) > 1e-10:
            raise ValueError("Simplex projection failed")
        return tuple(result.tolist())

    def independent(self, rng: np.random.Generator, candidate_id: str) -> Candidate:
        p = float(rng.uniform(self.p_lower, self.p_upper))
        r = interval_sample(rng, self.r_lower, self.r_max(p))
        # Sequential conditional allocation samples feasible weights directly.
        order = rng.permutation(len(self.lower))
        w = np.zeros(len(order))
        remaining = 1.0
        for k, j in enumerate(order):
            rest = order[k + 1 :]
            low = max(self.lower[j], remaining - sum(self.upper[t] for t in rest))
            high = min(self.upper[j], remaining - sum(self.lower[t] for t in rest))
            w[j] = interval_sample(rng, low, high)
            remaining -= w[j]
        candidate = Candidate(candidate_id, p, r, tuple(w.tolist()), "independent")
        self.validate(candidate)
        return candidate

    def local(
        self, anchor: Candidate, rng: np.random.Generator, radius: float, candidate_id: str
    ) -> Candidate:
        if not np.isfinite(radius) or radius < 0:
            raise ValueError("Invalid local radius")
        z = self.encode(anchor)
        # Truncated intervals are a defined direct transform, not post-hoc clipping.
        pz = float(rng.uniform(max(0, z[0] - radius), min(1, z[0] + radius)))
        rz = float(rng.uniform(max(0, z[1] - radius), min(1, z[1] + radius)))
        p = self.p_lower + pz * (self.p_upper - self.p_lower)
        r = self.r_lower + rz * (self.r_max(p) - self.r_lower)
        w = self.project(
            np.asarray(anchor.weights)
            + rng.normal(0, radius, len(self.lower)) * (np.asarray(self.upper) - self.lower)
        )
        candidate = Candidate(
            candidate_id,
            p,
            r,
            w,
            "local",
            region_id=anchor.region_id,
            provenance={"anchor": anchor.candidate_id, "radius": radius},
        )
        self.validate(candidate)
        return candidate


def interval_sample(rng: np.random.Generator, low: float, high: float, tolerance=1e-12) -> float:
    """Only roundoff-width intervals collapse; genuinely empty intervals are errors."""
    if not np.isfinite([low, high]).all() or high < low - tolerance:
        raise ValueError("Invalid conditional sampling interval")
    return float((low + high) / 2) if high - low <= tolerance else float(rng.uniform(low, high))


class RadiusPolicy(Protocol):
    def radius(self, *, batch: int, observations: tuple) -> float: ...


@dataclass(frozen=True)
class FixedRadius:
    value: float

    def radius(self, *, batch: int, observations: tuple) -> float:
        return self.value
