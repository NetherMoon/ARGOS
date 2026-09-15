"""Explicit original-workload mechanisms: elites, scenario states, local probes."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from argos.contracts import observation_rank, qualified, rank, violations
from argos.types import Candidate


def geometry_key(c):
    return (c.Pbar, c.R, tuple(c.weights))


def groups(observations):
    result = {}
    for o in observations:
        if o.phase == "search":
            result.setdefault(geometry_key(o.candidate), []).append(o)
    return list(result.values())


def scenario_status(observations, minimum=1):
    if not observations:
        return "UNOBSERVED"
    if any(o.phase != "search" for o in observations):
        raise ValueError("Search racing cannot use confirmations")
    if any(not qualified(o, minimum) for o in observations):
        return "SCENARIO_FRAGILE" if len(observations) > 1 else "INFEASIBLE"
    return (
        "SEARCH_ROBUST_FEASIBLE"
        if len({o.seed for o in observations}) >= 2
        else "PROVISIONAL_FEASIBLE"
    )


def robust_rank(observations, minimum=1):
    state = scenario_status(observations, minimum)
    category = {
        "SEARCH_ROBUST_FEASIBLE": 0,
        "PROVISIONAL_FEASIBLE": 1,
        "SCENARIO_FRAGILE": 2,
        "INFEASIBLE": 3,
        "UNOBSERVED": 4,
    }[state]
    worst = max(
        (violations(o.metrics)[0] if o.valid and o.metrics else float("inf") for o in observations),
        default=float("inf"),
    )
    objective = (
        np.mean([o.metrics.objective for o in observations if o.valid and o.metrics])
        if any(o.valid and o.metrics for o in observations)
        else float("inf")
    )
    return (
        category,
        worst,
        float(objective),
        observations[0].candidate.candidate_id if observations else "",
    )


def protected_elites(selected, endpoints, domain, count=2, minimum_distance=0.02):
    """Retain the upstream selected endpoint verbatim in physical coordinates."""

    def endpoint_rank(c):
        safe = c.provenance.get(
            "v3_selection_safe", c.prediction.p90 <= 0.26 and max(c.prediction.pj) <= 0.09
        )
        return (
            (
                0,
                c.prediction.objective,
                -c.provenance.get("tracking_slack", 0),
                -c.provenance.get("qos_slack", 0),
                c.candidate_id,
            )
            if safe
            else (1, *rank(c.prediction), c.candidate_id)
        )

    candidates = sorted(endpoints, key=endpoint_rank)
    ordered = ([selected] if selected else []) + candidates
    chosen = []
    for c in ordered:
        if all(domain.distance(c, p) > minimum_distance for p in chosen):
            chosen.append(
                replace(
                    c,
                    source="protected_v3_elite",
                    provenance={
                        **c.provenance,
                        "v3_rank": len(chosen) + 1,
                        "original_candidate_id": c.candidate_id,
                        "original_source": c.source,
                        "original_selection": c is selected,
                    },
                )
            )
        if len(chosen) == count:
            break
    return chosen


@dataclass
class TrustRegion:
    center: Candidate
    radius: float = 0.06
    failures: int = 0
    successes: int = 0
    restarts: int = 0
    best_rank: tuple | None = None
    last_discrepancy: float | None = None

    def update(self, observation):
        actual = observation_rank(observation)
        if observation.candidate.prediction and observation.metrics:
            self.last_discrepancy = max(
                abs(observation.metrics.p90 - observation.candidate.prediction.p90) / 0.3,
                max(
                    abs(a - b) / 0.1
                    for a, b in zip(observation.metrics.pj, observation.candidate.prediction.pj)
                ),
            )
        if self.best_rank is None or actual < self.best_rank:
            self.best_rank = actual
            self.center = observation.candidate
            self.successes += 1
            self.failures = 0
            if self.successes >= 2:
                self.radius = min(0.12, self.radius * 1.5)
                self.successes = 0
        else:
            self.failures += 1
            self.successes = 0
            if self.failures >= 2:
                self.radius = max(0.0075, self.radius * 0.5)
                self.failures = 0

    def restart(self, center):
        self.center = center
        self.radius = 0.06
        self.failures = 0
        self.successes = 0
        self.best_rank = None
        self.restarts += 1


def targeted_probes(observation, domain, prefix, step=0.02, weight_step=0.01):
    """Paired P/R probes and transfers to measured bottlenecks; benefit is unassumed."""
    c = observation.candidate
    z = domain.encode(c)
    result = []
    if not observation.valid or observation.metrics is None:
        return result

    def make(pz, rz, w, kind, detail):
        p = domain.p_lower + pz * (domain.p_upper - domain.p_lower)
        r = domain.r_lower + rz * (domain.r_max(p) - domain.r_lower)
        new = Candidate(
            f"{prefix}-{len(result):03d}",
            float(p),
            float(r),
            tuple(w),
            kind,
            provenance={"anchor": c.candidate_id, **detail},
        )
        domain.validate(new)
        # P and R are rounded to integer watts by the plan wizard. Dynamic AQA
        # allocation depends on state, so only exact unchanged weights are skipped.
        if (round(p * 1e6), round(r * 1e6), tuple(w)) != (
            round(c.Pbar * 1e6),
            round(c.R * 1e6),
            tuple(c.weights),
        ):
            result.append(new)

    for axis in [0, 1]:
        for sign in [-1, 1]:
            new = z[:2].copy()
            new[axis] += sign * step
            if 0 <= new[axis] <= 1:
                make(
                    *new,
                    c.weights,
                    "tracking_direction",
                    {
                        "axis": "P" if axis == 0 else "conditional_R",
                        "signed_normalized_step": sign * step,
                    },
                )
    pj = np.asarray(observation.metrics.pj)
    receiver = int(np.argmax(pj))
    if pj[receiver] > 0.1:
        donors = sorted(
            [j for j in range(4) if j != receiver and pj[j] < 0.1], key=lambda j: (pj[j], j)
        )
        for donor in donors:
            amount = min(
                weight_step,
                domain.upper[receiver] - c.weights[receiver],
                c.weights[donor] - domain.lower[donor],
            )
            if amount > 1e-9:
                w = np.array(c.weights)
                w[receiver] += amount
                w[donor] -= amount
                make(
                    *z[:2],
                    w,
                    "qos_transfer",
                    {
                        "receiver": receiver,
                        "donor": donor,
                        "weight_transfer": float(amount),
                        "nominal_node_transfer_N1000": float(1000 * amount),
                        "effective_allocation": "Dynamic AQA; reported from simulator, not inferred from nominal weight",
                    },
                )
    return result
