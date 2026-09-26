"""Pure, measured-first rules for the first ARGOS-OC experiment.

This module never starts FlexDC. A search-panel pass count is descriptive for
the ten frozen arrival tables, not an estimate of population reliability.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Iterable
from dataclasses import replace

import numpy as np

from argos.contracts import QOS_LIMIT, TRACKING_LIMIT
from argos.search.candidates import Domain
from argos.types import Candidate

SEARCH_TABLES = 10
ASSESSMENT_PAIRS = 30
SEARCH_TARGET = 8
HARD_CALL_CAP = 400
MAX_WORKERS = 10
INITIAL_CANDIDATES = 10
LATER_BATCH_CANDIDATES = 6
SEED_ROOT = 20260926
SEED_METHOD = "Python 3.12 random.Random(20260926).randrange(1, 2**32), sequential rejection"


def choose_seeds(excluded: Iterable[int], search_arrivals: Iterable[int]) -> dict:
    arrivals = [int(s) for s in search_arrivals]
    if len(arrivals) != SEARCH_TABLES or len(set(arrivals)) != SEARCH_TABLES:
        raise ValueError("Search panel must have exactly ten distinct seeds")
    used = {int(s) for s in excluded} | set(arrivals)
    rng = random.Random(SEED_ROOT)

    def next_seed() -> int:
        while True:
            seed = rng.randrange(1, 2**32)
            if seed not in used:
                used.add(seed)
                return seed

    runtime = next_seed()
    assessment = [{"arrival_seed": next_seed(), "runtime_seed": next_seed()} for _ in range(ASSESSMENT_PAIRS)]
    return {
        "selection_root": SEED_ROOT,
        "selection_method": SEED_METHOD,
        "search_arrival_seeds": arrivals,
        "search_runtime_seed": runtime,
        "assessment_pairs": assessment,
    }


def geometry(candidate: Candidate) -> tuple[float, ...]:
    return (candidate.Pbar, candidate.R, *candidate.weights)


def geometry_key(candidate: Candidate) -> str:
    return hashlib.sha256(
        json.dumps([format(float(v), ".17g") for v in geometry(candidate)], separators=(",", ":")).encode()
    ).hexdigest()


def result_status(row: dict) -> bool:
    if row.get("execution_status") != "COMPLETE" or not row.get("evidence_valid"):
        return False
    if row.get("p90") is None or len(row.get("Pj", [])) != 4:
        return False
    return float(row["p90"]) <= TRACKING_LIMIT and all(float(x) <= QOS_LIMIT for x in row["Pj"])


def candidate_aggregate(rows: list[dict]) -> dict:
    if len(rows) != SEARCH_TABLES or len({r["arrival_seed"] for r in rows}) != SEARCH_TABLES:
        raise ValueError("Incomplete or duplicate ten-table panel")
    if any(r.get("execution_status") != "COMPLETE" for r in rows):
        raise ValueError("Failed simulator execution cannot be ranked as infeasible")
    failures = []
    for r in rows:
        ratios = [float(r["p90"]) / TRACKING_LIMIT - 1] + [float(p) / QOS_LIMIT - 1 for p in r["Pj"]]
        row_failures = [max(0.0, v) for v in ratios]
        if not r.get("evidence_valid"):
            row_failures.append(1.0)  # evidence deficit is a failure, never a pass
        failures.append(row_failures)
    matrix = np.asarray([r + [0.0] * (6 - len(r)) for r in failures])
    passes = sum(result_status(r) for r in rows)
    objectives = [float(r["objective"]) for r in rows]
    return {
        "candidate_id": rows[0]["candidate_id"],
        "arrival_pass_count": passes,
        "search_panel_target_met": passes >= SEARCH_TARGET,
        "mean_objective_all_ten": float(np.mean(objectives)),
        "worst_normalized_violation": float(matrix.max()),
        "mean_total_normalized_violation": float(matrix.sum(axis=1).mean()),
        "worst_p90": max(float(r["p90"]) for r in rows),
        "worst_Pj": max(float(p) for r in rows for p in r["Pj"]),
        "minimum_normalized_margin": min(
            min(1 - float(r["p90"]) / TRACKING_LIMIT, *(1 - float(p) / QOS_LIMIT for p in r["Pj"]))
            for r in rows
        ),
    }


def measured_rank(aggregate: dict) -> tuple:
    if aggregate["search_panel_target_met"]:
        return (0, aggregate["mean_objective_all_ten"], -aggregate["arrival_pass_count"], -aggregate["minimum_normalized_margin"])
    return (
        1,
        -aggregate["arrival_pass_count"],
        aggregate["worst_normalized_violation"],
        aggregate["mean_total_normalized_violation"],
        aggregate["mean_objective_all_ten"],
    )


def select_final(aggregates: list[dict]) -> dict | None:
    eligible = [r for r in aggregates if r["search_panel_target_met"]]
    return min(eligible, key=measured_rank) if eligible else None


def choose_measured_anchors(candidates: dict[str, Candidate], aggregates: list[dict], domain: Domain) -> list[Candidate]:
    ranked = sorted(aggregates, key=measured_rank)
    if not ranked:
        raise ValueError("No measured anchor")
    first = candidates[ranked[0]["candidate_id"]]
    second = next(
        (candidates[r["candidate_id"]] for r in ranked[1:] if domain.distance(first, candidates[r["candidate_id"]]) >= 0.08),
        first,
    )
    return [first, second]


def distinct(candidate: Candidate, others: Iterable[Candidate], domain: Domain, distance: float = 0.025) -> bool:
    key = geometry_key(candidate)
    return all(key != geometry_key(other) and domain.distance(candidate, other) >= distance for other in others)


def next_batch(
    *,
    batch: int,
    candidates: dict[str, Candidate],
    aggregates: list[dict],
    cloud: list[Candidate],
    domain: Domain,
    rng: np.random.Generator,
) -> list[Candidate]:
    """Four measured-anchor local probes and two independent/diverse probes.

    V3 predictions do not veto measured-anchor candidates. The independent
    quota is 2/6 in every complete refinement batch.
    """
    if batch < 2:
        raise ValueError("Refinement starts after the initial measured round")
    anchors = choose_measured_anchors(candidates, aggregates, domain)
    radius = [0.18, 0.13, 0.09, 0.06, 0.04][min(batch - 2, 4)]
    selected: list[Candidate] = []
    existing = list(candidates.values())
    for i in range(4):
        anchor = anchors[i % 2]
        for attempt in range(200):
            proposal = domain.local(anchor, rng, radius, f"b{batch:02d}-measured-{i}-{attempt}")
            proposal = replace(proposal, source="measured_local", provenance={"anchor": anchor.candidate_id, "radius": radius})
            if distinct(proposal, [*existing, *selected], domain):
                selected.append(proposal)
                break
        else:
            raise RuntimeError("Could not form distinct measured-anchor probe")
    for candidate in cloud:
        if candidate.source == "independent" and distinct(candidate, [*existing, *selected], domain, 0.04):
            selected.append(replace(candidate, candidate_id=f"b{batch:02d}-independent-{len(selected)-4}", provenance={"cloud_id": candidate.candidate_id}))
        if len(selected) == LATER_BATCH_CANDIDATES:
            break
    while len(selected) < LATER_BATCH_CANDIDATES:
        candidate = domain.independent(rng, f"b{batch:02d}-independent-{len(selected)-4}")
        if distinct(candidate, [*existing, *selected], domain, 0.04):
            selected.append(candidate)
    return selected


def select_initial(cloud: list[Candidate], domain: Domain) -> list[Candidate]:
    legal = []
    seen = set()
    for candidate in cloud:
        domain.validate(candidate)
        key = geometry_key(candidate)
        if key not in seen:
            legal.append(candidate)
            seen.add(key)
    predicted = [c for c in legal if c.prediction is not None]
    independent = [c for c in predicted if c.source == "independent"]
    if len(predicted) < INITIAL_CANDIDATES or len(independent) < 2:
        raise ValueError("Initial V3/independent candidate cloud is too small")

    def violation(c: Candidate) -> float:
        m = c.prediction
        return max(0.0, m.p90 / TRACKING_LIMIT - 1, *(p / QOS_LIMIT - 1 for p in m.pj))

    def margin(c: Candidate) -> float:
        m = c.prediction
        return min(1 - m.p90 / TRACKING_LIMIT, *(1 - p / QOS_LIMIT for p in m.pj))

    groups = [
        sorted(predicted, key=lambda c: (violation(c) > 0, c.prediction.objective)),
        sorted(predicted, key=lambda c: (-margin(c), c.prediction.objective)),
        sorted(predicted, key=lambda c: (violation(c), c.prediction.objective)),
        sorted(predicted, key=lambda c: abs(c.prediction.p90 - TRACKING_LIMIT)),
        sorted(predicted, key=lambda c: abs(max(c.prediction.pj) - QOS_LIMIT)),
        sorted(predicted, key=lambda c: c.Pbar),
        sorted(predicted, key=lambda c: -c.Pbar),
        sorted(independent, key=lambda c: (violation(c), c.prediction.objective)),
        sorted(independent, key=lambda c: c.prediction.objective),
    ]
    selected: list[Candidate] = []
    for group in groups:
        candidate = next((c for c in group if distinct(c, selected, domain, 0.05)), None)
        if candidate is not None:
            selected.append(candidate)
    while len(selected) < INITIAL_CANDIDATES:
        candidate = max(
            (c for c in predicted if distinct(c, selected, domain, 0.05)),
            key=lambda c: min(domain.distance(c, s) for s in selected),
            default=None,
        )
        if candidate is None:
            raise RuntimeError("Candidate cloud lacks ten diverse points")
        selected.append(candidate)
    return [replace(c, candidate_id=f"b01-initial-{i:02d}", provenance={**c.provenance, "cloud_id": c.candidate_id}) for i, c in enumerate(selected[:INITIAL_CANDIDATES])]
