"""Transparent trade-off interleaving and greedy diverse representatives."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from argos.contracts import feasible, rank
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


def promising(candidates: list[Candidate], count: int) -> list[Candidate]:
    selected = []
    for iteration in sorted({c.iteration for c in candidates}):
        group = [c for c in candidates if c.iteration == iteration]
        good = [c for c in group if feasible(c.prediction)]
        if good:
            orders = [
                sorted(good, key=lambda c: (c.prediction.objective, c.candidate_id)),
                sorted(
                    good, key=lambda c: (c.prediction.p90, c.prediction.objective, c.candidate_id)
                ),
                sorted(
                    good,
                    key=lambda c: (max(c.prediction.pj), c.prediction.objective, c.candidate_id),
                ),
            ]
        else:
            orders = [sorted(group, key=lambda c: (rank(c.prediction), c.candidate_id))]
        seen = set()
        retained = []
        for row in zip(*orders):
            for c in row:
                if c.candidate_id not in seen and len(retained) < count:
                    retained.append(c)
                    seen.add(c.candidate_id)
        selected.extend(retained)
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
