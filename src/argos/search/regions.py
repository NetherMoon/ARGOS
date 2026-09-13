"""Transparent trade-off interleaving and greedy diverse representatives."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from argos.contracts import feasible, rank, violations
from argos.search.candidates import Domain
from argos.types import Candidate, Metrics, Region


def from_snapshot(row: dict, final_iteration: int) -> Candidate:
    iteration = int(row["Iteration"])
    start = int(row["Start_Index"])
    prediction = Metrics(
        float(row["Predicted_Mean_Tracking"]),
        float(row["Predicted_P90_Tracking"]),
        tuple(row["Predicted_QoS_Probabilities"]),
        float(row["Predicted_Full_Objective"]),
    )
    return Candidate(
        f"v3-{iteration:04d}-{start:04d}",
        float(row["Pbar_kw_per_server"]),
        float(row["R_kw_per_server"]),
        tuple(row["weights"]),
        "V3 endpoint" if iteration == final_iteration else "V3 snapshot",
        start,
        iteration,
        prediction=prediction,
    )


def tradeoff_select(
    candidates: list[Candidate], count: int, domain: Domain | None = None
) -> list[Candidate]:
    """Stable round-robin quotas; infeasible and geometric coverage remain explicit."""
    if not candidates or count <= 0:
        return []
    tie = lambda c: (c.prediction.objective, c.candidate_id)
    good = [c for c in candidates if feasible(c.prediction)]
    bad = [c for c in candidates if not feasible(c.prediction)]
    violation_key = lambda c: (*violations(c.prediction), *tie(c))
    orders = [
        sorted(good, key=tie),
        sorted(candidates, key=lambda c: (c.prediction.p90, *tie(c))),
        sorted(candidates, key=lambda c: (max(c.prediction.pj), *tie(c))),
        sorted(candidates, key=violation_key),
        sorted(bad, key=violation_key),
    ]
    # The sixth quota is farthest from the retained set, in the legal geometry.
    selected, seen = [], set()
    cursors = [0] * len(orders)
    while len(selected) < min(count, len(candidates)):
        before = len(selected)
        for i, order in enumerate(orders):
            while cursors[i] < len(order) and order[cursors[i]].candidate_id in seen:
                cursors[i] += 1
            if cursors[i] < len(order) and len(selected) < count:
                c = order[cursors[i]]
                selected.append(c)
                seen.add(c.candidate_id)
        remaining = [c for c in candidates if c.candidate_id not in seen]
        if remaining and len(selected) < count:
            c = (
                min(
                    remaining,
                    key=lambda c: (-min(domain.distance(c, s) for s in selected), c.candidate_id),
                )
                if domain and selected
                else min(remaining, key=lambda c: c.candidate_id)
            )
            selected.append(c)
            seen.add(c.candidate_id)
        if before == len(selected):
            break
    return selected


def promising(
    candidates: list[Candidate], count: int, domain: Domain | None = None
) -> list[Candidate]:
    selected = []
    for iteration in sorted(
        {c.iteration for c in candidates}, key=lambda i: -1 if i is None else i
    ):
        selected.extend(
            tradeoff_select([c for c in candidates if c.iteration == iteration], count, domain)
        )
    return selected


def extract_regions(
    pool: list[Candidate], domain: Domain, max_regions: int, distance: float, dedupe: float
) -> tuple[list[Candidate], list[Region]]:
    # Round-robin snapshot-ranked pool order preserves both temporal and margin coverage.
    groups = {i: [c for c in pool if c.iteration == i] for i in sorted({c.iteration for c in pool})}
    ordered = [min(pool, key=lambda c: (rank(c.prediction), c.candidate_id))] if pool else []
    for index in range(max((len(g) for g in groups.values()), default=0)):
        for group in groups.values():
            if index < len(group):
                ordered.append(group[index])
    unique = []
    for c in ordered:
        domain.validate(c)
        if all(domain.distance(c, other) > dedupe for other in unique):
            unique.append(c)
    representatives = []
    for c in unique:
        if all(domain.distance(c, r) >= distance for r in representatives):
            representatives.append(c)
        if len(representatives) == max_regions:
            break
    regions = []
    assignments = {
        c.candidate_id: int(np.argmin([domain.distance(c, r) for r in representatives]))
        for c in unique
    }
    for i, representative in enumerate(representatives):
        name = f"region-{i + 1:02d}"
        members = [c for c in unique if assignments[c.candidate_id] == i]
        regions.append(
            Region(
                name,
                replace(representative, region_id=name),
                tuple(c.candidate_id for c in members),
                tuple(domain.encode(representative)),
                tuple(sorted({c.iteration for c in members})),
            )
        )
    assigned = [
        replace(c, region_id=regions[assignments[c.candidate_id]].region_id) for c in unique
    ]
    return assigned, regions
