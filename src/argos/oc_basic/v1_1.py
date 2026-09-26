"""OC1.1 finite-panel search rules; no FlexDC code lives here."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, replace

import numpy as np

from argos.oc_basic.core import SEARCH_TABLES, SEARCH_TARGET, distinct
from argos.search.candidates import Domain
from argos.types import Candidate

PROTOCOL_VERSION = "OC1.1"
TRACKING_LIMIT = 0.30
QOS_LIMIT = 0.10
JOB_NAMES = ("ResNet", "GPT2", "Llama", "Bloom")
INITIAL_COUNT = 15
INITIAL_INDEPENDENT = 3
REFINEMENT_COUNT = 8
REFINEMENT_INDEPENDENT = 2
THIRD_FAILURE_CUTOFF = SEARCH_TABLES - SEARCH_TARGET + 1


@dataclass(frozen=True)
class CandidateState:
    candidate_id: str
    status: str
    scenarios_evaluated: int
    passes: int
    failures: int
    remaining: int
    maximum_possible_passes: int
    complete_panel: bool
    early_rejected: bool
    g8: float | None
    g9: float | None
    g10: float | None
    repair_count: int | None
    repair_sum: float | None
    critical_failure_seeds: tuple[int, ...]
    mean_objective_all_ten: float | None
    signed_scenario_violations: tuple[tuple[int, float | None], ...]


def signed_scenario_violation(row: dict) -> float | None:
    """A negative value is a valid passing margin; None denotes invalid evidence."""
    if row.get("execution_status") != "COMPLETE" or not row.get("evidence_valid"):
        return None
    pj = row.get("Pj")
    if isinstance(pj, str):
        pj = json.loads(pj)
    if row.get("p90") is None or pj is None or len(pj) != 4:
        return None
    values = [float(row["p90"]) / TRACKING_LIMIT - 1]
    values.extend(float(p) / QOS_LIMIT - 1 for p in pj)
    if not np.isfinite(values).all():
        return None
    return max(values)


def candidate_state(candidate_id: str, rows: Iterable[dict], seed_panel: Iterable[int]) -> CandidateState:
    panel = tuple(int(seed) for seed in seed_panel)
    if len(panel) != SEARCH_TABLES or len(set(panel)) != SEARCH_TABLES:
        raise ValueError("OC1.1 requires ten distinct frozen arrival seeds")
    observations = list(rows)
    if any(r["candidate_id"] != candidate_id for r in observations):
        raise ValueError("Candidate identity crossed in state reconstruction")
    if len(observations) != len({int(r["arrival_seed"]) for r in observations}):
        raise ValueError("Duplicate candidate/arrival execution")
    if any(int(r["arrival_seed"]) not in panel for r in observations):
        raise ValueError("Execution not in frozen arrival panel")
    scored = [(int(r["arrival_seed"]), signed_scenario_violation(r)) for r in observations]
    passes = sum(g is not None and g <= 0 for _, g in scored)
    failures = len(scored) - passes
    remaining = SEARCH_TABLES - len(scored)
    if remaining < 0:
        raise ValueError("Candidate exceeded frozen scenario panel")
    complete = remaining == 0
    rejected = failures >= THIRD_FAILURE_CUTOFF and not complete
    if any(r.get("execution_status") != "COMPLETE" for r in observations):
        status = "EXECUTION_ERROR"
    elif complete and passes >= SEARCH_TARGET:
        status = "TARGET_MET_COMPLETE"
    elif complete:
        status = "FULL_PANEL_COMPLETE"
    elif rejected:
        status = "EARLY_REJECTED_3_FAILURES"
    elif passes + remaining >= SEARCH_TARGET:
        status = "TARGET_POSSIBLE"
    else:
        status = "ACTIVE"
    valid = sorted((g, seed) for seed, g in scored if g is not None)
    g8 = valid[7][0] if complete and len(valid) == SEARCH_TABLES else None
    g9 = valid[8][0] if complete and len(valid) == SEARCH_TABLES else None
    g10 = valid[9][0] if complete and len(valid) == SEARCH_TABLES else None
    repair_count = max(0, SEARCH_TARGET - passes) if complete else None
    needed = [(g, seed) for g, seed in valid if g > 0][:repair_count] if repair_count is not None else []
    repair_sum = sum(g for g, _ in needed) if complete and len(valid) == SEARCH_TABLES else None
    objective = (
        float(np.mean([float(r["objective"]) for r in observations]))
        if complete and all(r.get("objective") is not None for r in observations) else None
    )
    return CandidateState(
        candidate_id, status, len(scored), passes, failures, remaining,
        passes + remaining, complete, rejected, g8, g9, g10,
        repair_count, repair_sum, tuple(seed for _, seed in needed), objective,
        tuple((seed, next((g for s, g in scored if s == seed), None)) for seed in panel if seed in {s for s, _ in scored}),
    )


def complete_rank(state: CandidateState) -> tuple:
    if not state.complete_panel or state.g8 is None:
        raise ValueError("Exact g8 ranking requires a complete valid panel")
    if state.passes >= SEARCH_TARGET:
        return (0, state.mean_objective_all_ten, -state.passes, state.g8)
    return (1, state.g8, state.repair_sum, -state.passes, state.mean_objective_all_ten)


def anchor_rank(state: CandidateState) -> tuple:
    if state.complete_panel and state.g8 is not None:
        return complete_rank(state)
    valid = [g for _, g in state.signed_scenario_violations if g is not None]
    positive = [max(0.0, g) for g in valid]
    # A partial panel is never declared eligible; this only orders probe centers.
    return (2, state.failures, np.mean(positive) if positive else float("inf"), -state.passes, state.candidate_id)


def select_final(states: Iterable[CandidateState]) -> CandidateState | None:
    eligible = [s for s in states if s.complete_panel and s.status == "TARGET_MET_COMPLETE"]
    return min(eligible, key=complete_rank) if eligible else None


def seed_order_from_v1(seed_rows: Iterable[dict]) -> tuple[int, ...]:
    """Hard measured seeds first; v1 evidence freezes this before OC1.1 calls."""
    rows = list(seed_rows)
    if len(rows) != SEARCH_TABLES:
        raise ValueError("Historical seed difficulty must cover all ten tables")
    ordered = sorted(rows, key=lambda r: (
        int(r["passed_candidate_count"]), -float(r["minimum_signed_g"]), int(r["arrival_seed"]),
    ))
    seeds = tuple(int(r["arrival_seed"]) for r in ordered)
    if len(set(seeds)) != SEARCH_TABLES:
        raise ValueError("Historical seed order has duplicates")
    return seeds


def predicted_violation(candidate: Candidate) -> float:
    p = candidate.prediction
    if p is None:
        return float("inf")
    return max(p.p90 / TRACKING_LIMIT - 1, *(x / QOS_LIMIT - 1 for x in p.pj))


def predicted_margin(candidate: Candidate) -> float:
    return -predicted_violation(candidate)


def select_initial(cloud: list[Candidate], domain: Domain) -> list[Candidate]:
    """Twelve V3-guided safety starts plus three diverse independents."""
    legal = [c for c in cloud if c.prediction is not None]
    for c in legal:
        domain.validate(c)
    guided = [c for c in legal if c.source != "independent"]
    independent = [c for c in legal if c.source == "independent"]
    if len(guided) < INITIAL_COUNT - INITIAL_INDEPENDENT or len(independent) < INITIAL_INDEPENDENT:
        raise ValueError("V3 candidate cloud cannot fill OC1.1 initial screen")
    selected: list[Candidate] = []
    groups = [
        sorted(guided, key=lambda c: (-predicted_margin(c), c.prediction.objective)),
        sorted(guided, key=lambda c: (predicted_violation(c), c.prediction.objective)),
        sorted((c for c in guided if predicted_violation(c) <= 0), key=lambda c: c.prediction.objective),
    ]
    for i in range(INITIAL_COUNT - INITIAL_INDEPENDENT):
        group = groups[i % len(groups)]
        point = next((c for c in group if distinct(c, selected, domain, 0.018)), None)
        if point is None:
            raise RuntimeError("Insufficient diverse V3-guided initial candidates")
        selected.append(point)
    for c in sorted(independent, key=lambda c: (predicted_violation(c), c.prediction.objective)):
        if distinct(c, selected, domain, 0.025):
            selected.append(c)
        if len(selected) == INITIAL_COUNT:
            break
    if len(selected) != INITIAL_COUNT:
        raise RuntimeError("Insufficient diverse independent initial candidates")
    return [replace(c, candidate_id=f"b01-screen-{i:02d}",
                    provenance={**c.provenance, "cloud_id": c.candidate_id, "protocol_version": PROTOCOL_VERSION})
            for i, c in enumerate(selected)]


def choose_anchors(candidates: dict[str, Candidate], states: Iterable[CandidateState], domain: Domain) -> list[Candidate]:
    ranked = sorted((s for s in states if s.scenarios_evaluated), key=anchor_rank)
    if not ranked:
        raise ValueError("No measured candidate can anchor refinement")
    first = candidates[ranked[0].candidate_id]
    second = next((candidates[s.candidate_id] for s in sorted(ranked[1:], key=lambda s: (-s.passes, anchor_rank(s)))
                   if domain.distance(first, candidates[s.candidate_id]) >= 0.08), first)
    return [first, second]


def axis_probe(anchor: Candidate, domain: Domain, axis: str, offset: float, candidate_id: str) -> Candidate | None:
    z = domain.encode(anchor)
    if axis == "P":
        new = z[0] + offset
        if not 0 <= new <= 1:
            return None
        pbar = domain.p_lower + new * (domain.p_upper - domain.p_lower)
        reserve = domain.r_lower + z[1] * (domain.r_max(pbar) - domain.r_lower)
    elif axis == "conditional_R":
        new = z[1] + offset
        if not 0 <= new <= 1:
            return None
        pbar = anchor.Pbar
        reserve = domain.r_lower + new * (domain.r_max(pbar) - domain.r_lower)
    else:
        raise ValueError("Unknown OC1.1 axis")
    c = replace(anchor, candidate_id=candidate_id, Pbar=float(pbar), R=float(reserve),
                source="targeted_axis", prediction=None,
                provenance={"anchor": anchor.candidate_id, "axis": axis, "normalized_offset": offset})
    domain.validate(c)
    return c


def weight_transfer(anchor: Candidate, domain: Domain, receiver: int, donor: int, amount: float,
                    candidate_id: str) -> Candidate | None:
    if receiver == donor or amount <= 0:
        raise ValueError("Weight transfer needs distinct jobs and positive amount")
    weights = list(anchor.weights)
    actual = min(amount, domain.upper[receiver] - weights[receiver], weights[donor] - domain.lower[donor])
    if actual < 1e-5:
        return None
    weights[receiver] += actual
    weights[donor] -= actual
    c = replace(anchor, candidate_id=candidate_id, weights=tuple(weights), source="targeted_weight_transfer",
                prediction=None, provenance={"anchor": anchor.candidate_id, "receiver": JOB_NAMES[receiver],
                                             "donor": JOB_NAMES[donor], "weight_transfer": actual})
    domain.validate(c)
    return c


def critical_bottleneck(rows: Iterable[dict], state: CandidateState) -> tuple[str, int]:
    critical = set(state.critical_failure_seeds)
    chosen = [r for r in rows if int(r["arrival_seed"]) in critical]
    if not chosen:
        chosen = list(rows)
    if not chosen:
        return "tracking", 0
    counts = {name: 0 for name in ("tracking", *JOB_NAMES)}
    for r in chosen:
        pj = r["Pj"] if isinstance(r["Pj"], list) else json.loads(r["Pj"])
        ratios = [float(r["p90"]) / TRACKING_LIMIT - 1, *(float(p) / QOS_LIMIT - 1 for p in pj)]
        counts[("tracking", *JOB_NAMES)[int(np.argmax(ratios))]] += 1
    name = max(counts, key=lambda n: (counts[n], n == "Bloom"))
    # Choose a donor with the lowest measured mean QoS risk among other types.
    donors = [i for i in range(4) if JOB_NAMES[i] != name]
    donor = min(donors, key=lambda i: np.mean([
        float((r["Pj"] if isinstance(r["Pj"], list) else json.loads(r["Pj"]))[i]) for r in chosen
    ])) if donors else 0
    return name, donor


def proposal_pack(anchor: Candidate, rows: Iterable[dict], state: CandidateState,
                  domain: Domain, batch: int, anchor_index: int, rng: np.random.Generator) -> list[Candidate]:
    """Small legal measured-evidence probe pack; no surrogate veto."""
    bottleneck, donor = critical_bottleneck(rows, state)
    prefix = f"b{batch:02d}-a{anchor_index}"
    proposals: list[Candidate] = []
    if bottleneck in JOB_NAMES:
        receiver = JOB_NAMES.index(bottleneck)
        for amount in (0.01, 0.02, 0.04):
            c = weight_transfer(anchor, domain, receiver, donor, amount,
                                f"{prefix}-weight-{amount:.2f}")
            if c is not None:
                proposals.append(c)
    for axis, offsets in (("P", (-0.04, -0.02, -0.01, 0.01, 0.02, 0.04)),
                          ("conditional_R", (-0.04, -0.02, 0.02, 0.04))):
        for offset in offsets:
            c = axis_probe(anchor, domain, axis, offset, f"{prefix}-{axis}-{offset:+.2f}")
            if c is not None:
                proposals.append(c)
    if bottleneck == "Bloom":
        transfer = weight_transfer(anchor, domain, 3, donor, 0.02, f"{prefix}-combined-weight")
        if transfer is not None:
            for axis, offset in (("P", -0.01), ("P", 0.01), ("conditional_R", -0.02), ("conditional_R", 0.02)):
                c = axis_probe(transfer, domain, axis, offset, f"{prefix}-combined-{axis}-{offset:+.2f}")
                if c is not None:
                    proposals.append(replace(c, source="targeted_combined",
                                             provenance={**c.provenance, "anchor": anchor.candidate_id,
                                                         "weight_transfer": transfer.provenance}))
    for i in range(2):
        c = domain.local(anchor, rng, 0.035, f"{prefix}-local-{i}")
        proposals.append(replace(c, source="measured_local", prediction=None,
                                 provenance={"anchor": anchor.candidate_id, "radius": 0.035}))
    return proposals


def next_batch(*, batch: int, candidates: dict[str, Candidate], rows_by_candidate: dict[str, list[dict]],
               states: list[CandidateState], cloud: list[Candidate], domain: Domain,
               rng: np.random.Generator) -> list[Candidate]:
    anchors = choose_anchors(candidates, states, domain)
    measured: list[Candidate] = []
    existing = list(candidates.values())
    # Reserve a weight/combined, Pbar, and conditional-reserve slot for each
    # distinct measured anchor. The sign cycles by batch; a single probe pack
    # must not consume all three slots with the first three weight transfers.
    for anchor_index, anchor in enumerate(anchors):
        state = next(s for s in states if s.candidate_id == anchor.candidate_id)
        pack = proposal_pack(anchor, rows_by_candidate.get(anchor.candidate_id, []),
                             state, domain, batch, anchor_index, rng)
        quota = 3 if anchor_index == 0 else 3 if anchor.candidate_id != anchors[0].candidate_id else 0
        if quota == 0:
            continue
        preferred_sign = 1 if (batch + anchor_index) % 2 == 0 else -1
        classes = (
            ("targeted_weight_transfer", "targeted_combined", "measured_local"),
            ("P",),
            ("conditional_R",),
        )
        for search_class in classes:
            if search_class[0] in ("P", "conditional_R"):
                options = [c for c in pack if c.source == "targeted_axis" and c.provenance.get("axis") in search_class]
            else:
                options = [c for c in pack if c.source in search_class]
            options.sort(key=lambda c: (
                0 if c.source == ("targeted_weight_transfer" if batch % 2 == 0 else "targeted_combined") else 1,
                0 if float(c.provenance.get("normalized_offset", preferred_sign)) * preferred_sign > 0 else 1,
                abs(abs(float(c.provenance.get("normalized_offset", 0.02))) - 0.02),
                c.candidate_id,
            ))
            picked = next((c for c in options if distinct(c, [*existing, *measured], domain, 0.005)), None)
            if picked is not None:
                measured.append(picked)
        if len([x for x in measured if x.provenance.get("anchor") == anchor.candidate_id]) < quota:
            for c in pack:
                if len([x for x in measured if x.provenance.get("anchor") == anchor.candidate_id]) >= quota:
                    break
                if distinct(c, [*existing, *measured], domain, 0.005):
                    measured.append(c)
    if len(measured) < REFINEMENT_COUNT - REFINEMENT_INDEPENDENT:
        raise RuntimeError("Could not form six distinct measured-anchor probes")
    selected = measured[:REFINEMENT_COUNT - REFINEMENT_INDEPENDENT]
    for c in sorted((x for x in cloud if x.source == "independent"),
                    key=lambda x: (predicted_violation(x), x.prediction.objective)):
        if distinct(c, [*existing, *selected], domain, 0.04):
            selected.append(replace(c, candidate_id=f"b{batch:02d}-independent-{len(selected)-6}",
                                    provenance={"cloud_id": c.candidate_id, "protocol_version": PROTOCOL_VERSION}))
        if len(selected) == REFINEMENT_COUNT:
            break
    if len(selected) != REFINEMENT_COUNT:
        raise RuntimeError("Could not fill independent exploration quota")
    return selected


def serialize_state(state: CandidateState) -> dict:
    data = dict(state.__dict__)
    data["critical_failure_seeds"] = json.dumps(state.critical_failure_seeds)
    data["signed_scenario_violations"] = json.dumps(state.signed_scenario_violations)
    return data
