"""Job-agnostic, finite-panel ARGOS-OC search rules.

This module has no FlexDC, V3 checkpoint, workload-name, or filesystem dependency.
The active checkpoint adapter may impose a narrower supported job count.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, replace

import numpy as np

from argos.oc_basic.core import distinct
from argos.search.candidates import Domain
from argos.types import Candidate


@dataclass(frozen=True)
class PanelRule:
    job_types: tuple[str, ...]
    panel_size: int
    required_passes: int
    tracking_limit: float = 0.30
    qos_limit: float = 0.10

    def __post_init__(self) -> None:
        if (
            not self.job_types
            or any(not name for name in self.job_types)
            or len(set(self.job_types)) != len(self.job_types)
        ):
            raise ValueError("Configured job types must be nonempty and unique")
        if not 1 <= self.required_passes <= self.panel_size:
            raise ValueError("Invalid finite-panel pass target")
        if self.tracking_limit <= 0 or self.qos_limit <= 0:
            raise ValueError("Feasibility limits must be positive")


@dataclass(frozen=True)
class PanelState:
    candidate_id: str
    status: str
    scenarios_evaluated: int
    passes: int
    failures: int
    remaining: int
    maximum_possible_passes: int
    complete_panel: bool
    early_rejected: bool
    g_target: float | None
    repair_count: int | None
    repair_sum: float | None
    critical_failure_seeds: tuple[int, ...]
    mean_objective_all: float | None
    signed_scenario_violations: tuple[tuple[int, float | None], ...]


def _pj(row: dict, rule: PanelRule) -> tuple[float, ...]:
    value = row.get("Pj")
    if isinstance(value, str):
        value = json.loads(value)
    if value is None or len(value) != len(rule.job_types):
        raise ValueError("Simulator Pj vector differs from configured job order")
    result = tuple(float(x) for x in value)
    if not np.isfinite(result).all():
        raise ValueError("Non-finite simulator Pj")
    return result


def signed_violation(row: dict, rule: PanelRule) -> float | None:
    """Return signed worst normalized violation; invalid evidence is not a pass."""
    evidence = row.get("evidence_valid")
    if isinstance(evidence, str):
        evidence = evidence.lower() == "true"
    if row.get("execution_status") != "COMPLETE" or not evidence:
        return None
    p90 = float(row["p90"])
    values = (p90 / rule.tracking_limit - 1, *[p / rule.qos_limit - 1 for p in _pj(row, rule)])
    if not np.isfinite(values).all():
        raise ValueError("Non-finite simulator feasibility metric")
    return float(max(values))


def panel_state(
    candidate_id: str, rows: Iterable[dict], seeds: Iterable[int], rule: PanelRule
) -> PanelState:
    panel = tuple(int(seed) for seed in seeds)
    if len(panel) != rule.panel_size or len(set(panel)) != len(panel):
        raise ValueError("Frozen arrival panel size or uniqueness changed")
    observed = list(rows)
    if any(r["candidate_id"] != candidate_id for r in observed):
        raise ValueError("Candidate identity crossed in panel")
    seen = [int(r["arrival_seed"]) for r in observed]
    if len(set(seen)) != len(seen) or any(seed not in panel for seed in seen):
        raise ValueError("Duplicate or unexpected arrival cell")
    scored = {int(r["arrival_seed"]): signed_violation(r, rule) for r in observed}
    passes = sum(g is not None and g <= 0 for g in scored.values())
    remaining = rule.panel_size - len(observed)
    failures = len(observed) - passes
    possible = passes + remaining
    complete = remaining == 0
    rejected = not complete and possible < rule.required_passes
    valid = sorted((g, seed) for seed, g in scored.items() if g is not None)
    all_valid = complete and len(valid) == rule.panel_size
    g_target = float(valid[rule.required_passes - 1][0]) if all_valid else None
    repairs = max(0, rule.required_passes - passes) if all_valid else None
    failing = [(g, seed) for g, seed in valid if g > 0]
    needed = failing[:repairs] if repairs is not None else failing
    critical = needed if repairs else failing
    if any(g is None for g in scored.values()):
        status = "INVALID_EVIDENCE_OR_EXECUTION"
    elif complete and passes >= rule.required_passes:
        status = "TARGET_MET_COMPLETE"
    elif complete:
        status = "FULL_PANEL_COMPLETE"
    elif rejected:
        status = "EARLY_REJECTED"
    else:
        status = "TARGET_POSSIBLE"
    objective = (
        float(np.mean([float(r["objective"]) for r in observed]))
        if all_valid and all(r.get("objective") is not None for r in observed)
        else None
    )
    return PanelState(
        candidate_id,
        status,
        len(observed),
        passes,
        failures,
        remaining,
        possible,
        complete,
        rejected,
        g_target,
        repairs,
        float(sum(g for g, _ in needed)) if all_valid else None,
        tuple(seed for _, seed in critical),
        objective,
        tuple((seed, scored[seed]) for seed in panel if seed in scored),
    )


def complete_rank(state: PanelState, rule: PanelRule) -> tuple:
    if not state.complete_panel or state.g_target is None:
        raise ValueError("Only valid complete panels can be ranked")
    if state.passes >= rule.required_passes:
        return (0, state.mean_objective_all, -state.passes, state.g_target, state.candidate_id)
    return (
        1,
        state.g_target,
        state.repair_sum,
        -state.passes,
        state.mean_objective_all,
        state.candidate_id,
    )


def select_final(states: Iterable[PanelState], rule: PanelRule) -> PanelState | None:
    eligible = [s for s in states if s.status == "TARGET_MET_COMPLETE" and s.complete_panel]
    return min(eligible, key=lambda s: complete_rank(s, rule)) if eligible else None


def anchor_rank(state: PanelState, rule: PanelRule) -> tuple:
    if state.complete_panel and state.g_target is not None:
        return complete_rank(state, rule)
    values = [g for _, g in state.signed_scenario_violations if g is not None]
    return (
        2,
        state.failures,
        float(np.mean([max(0.0, g) for g in values])) if values else float("inf"),
        -state.passes,
        state.candidate_id,
    )


def choose_anchors(
    candidates: dict[str, Candidate], states: Iterable[PanelState], domain: Domain, rule: PanelRule
) -> list[Candidate]:
    ranked = sorted(
        (s for s in states if s.scenarios_evaluated), key=lambda s: anchor_rank(s, rule)
    )
    if not ranked:
        raise ValueError("No measured candidate can anchor refinement")
    first = candidates[ranked[0].candidate_id]
    second = next(
        (
            candidates[s.candidate_id]
            for s in sorted(ranked[1:], key=lambda s: (-s.passes, anchor_rank(s, rule)))
            if domain.distance(first, candidates[s.candidate_id]) >= 0.08
        ),
        candidates[ranked[1].candidate_id] if len(ranked) > 1 else first,
    )
    return [first, second]


def critical_bottlenecks(rows: Iterable[dict], state: PanelState, rule: PanelRule) -> list[dict]:
    """Rank active constraint families by critical-scenario count and severity.

    Configured order is the final tie break. Every positive QoS violation is
    retained, including when tracking is the single worst violation.
    """
    observed = list(rows)
    critical = set(state.critical_failure_seeds)
    chosen = [r for r in observed if int(r["arrival_seed"]) in critical]
    if not chosen:
        chosen = [r for r in observed if (g := signed_violation(r, rule)) is not None and g > 0]
    result = []
    for order, name in enumerate(("tracking", *rule.job_types)):
        vals = []
        for row in chosen:
            if name == "tracking":
                value = float(row["p90"]) / rule.tracking_limit - 1
            else:
                value = _pj(row, rule)[order - 1] / rule.qos_limit - 1
            if value > 0:
                vals.append(value)
        if vals:
            result.append(
                {
                    "constraint": name,
                    "family": "tracking" if order == 0 else "qos",
                    "job_index": None if order == 0 else order - 1,
                    "count": len(vals),
                    "severity": float(sum(vals)),
                    "configured_order": order,
                }
            )
    return sorted(
        result, key=lambda item: (-item["count"], -item["severity"], item["configured_order"])
    )


def _donor(
    anchor: Candidate, rows: list[dict], receiver: int, domain: Domain, rule: PanelRule
) -> int | None:
    choices = [
        i
        for i in range(len(rule.job_types))
        if i != receiver and anchor.weights[i] > domain.lower[i] + 1e-5
    ]
    return (
        min(
            choices,
            key=lambda i: (float(np.mean([_pj(r, rule)[i] for r in rows])) if rows else 0.0, i),
        )
        if choices
        else None
    )


def weight_transfer(
    anchor: Candidate,
    domain: Domain,
    rule: PanelRule,
    receiver: int,
    donor: int,
    amount: float,
    candidate_id: str,
) -> Candidate | None:
    if len(anchor.weights) != len(rule.job_types) or receiver == donor or amount <= 0:
        raise ValueError("Invalid generic weight-transfer request")
    weights = list(anchor.weights)
    actual = min(
        amount, domain.upper[receiver] - weights[receiver], weights[donor] - domain.lower[donor]
    )
    if actual < 1e-5:
        return None
    weights[receiver] += actual
    weights[donor] -= actual
    candidate = replace(
        anchor,
        candidate_id=candidate_id,
        weights=tuple(weights),
        source="targeted_weight_transfer",
        prediction=None,
        provenance={
            "anchor": anchor.candidate_id,
            "receiver_job": rule.job_types[receiver],
            "donor_job": rule.job_types[donor],
            "receiver_index": receiver,
            "donor_index": donor,
            "weight_transfer": actual,
        },
    )
    domain.validate(candidate)
    return candidate


def axis_probe(
    anchor: Candidate, domain: Domain, axis: str, offset: float, candidate_id: str
) -> Candidate | None:
    z = domain.encode(anchor)
    index = 0 if axis == "P" else 1 if axis == "conditional_R" else None
    if index is None:
        raise ValueError("Unknown bid axis")
    value = z[index] + offset
    if not 0 <= value <= 1:
        return None
    pbar = domain.p_lower + value * (domain.p_upper - domain.p_lower) if index == 0 else anchor.Pbar
    conditional_r = value if index == 1 else z[1]
    reserve = domain.r_lower + conditional_r * (domain.r_max(pbar) - domain.r_lower)
    candidate = replace(
        anchor,
        candidate_id=candidate_id,
        Pbar=float(pbar),
        R=float(reserve),
        source="targeted_axis",
        prediction=None,
        provenance={"anchor": anchor.candidate_id, "axis": axis, "normalized_offset": offset},
    )
    domain.validate(candidate)
    return candidate


def proposal_pack(
    anchor: Candidate,
    rows: Iterable[dict],
    state: PanelState,
    domain: Domain,
    rule: PanelRule,
    batch: int,
    anchor_index: int,
    rng: np.random.Generator,
) -> list[Candidate]:
    """Bounded legal probes; no workload-name or V3-prediction veto."""
    observed = list(rows)
    bottlenecks = critical_bottlenecks(observed, state, rule)
    qos = [b for b in bottlenecks if b["family"] == "qos"][:2]
    prefix = f"b{batch:02d}-a{anchor_index}"
    scale = 1.0 + 0.15 * (batch % 7)
    proposals = []
    for info in qos:
        receiver = info["job_index"]
        donor = _donor(anchor, observed, receiver, domain, rule)
        if donor is None:
            continue
        for base_amount in (0.01, 0.02, 0.04):
            amount = base_amount * scale
            candidate = weight_transfer(
                anchor,
                domain,
                rule,
                receiver,
                donor,
                amount,
                f"{prefix}-weight-j{receiver}-{amount:.4f}",
            )
            if candidate is not None:
                proposals.append(
                    replace(
                        candidate,
                        provenance={
                            **candidate.provenance,
                            "critical_count": info["count"],
                            "critical_severity": info["severity"],
                        },
                    )
                )
        transfer = weight_transfer(
            anchor,
            domain,
            rule,
            receiver,
            donor,
            0.02 * scale,
            f"{prefix}-combined-weight-j{receiver}",
        )
        if transfer is not None:
            for axis, offset in (
                ("P", -0.01),
                ("P", 0.01),
                ("conditional_R", -0.02),
                ("conditional_R", 0.02),
            ):
                candidate = axis_probe(
                    transfer,
                    domain,
                    axis,
                    offset * scale,
                    f"{prefix}-combined-j{receiver}-{axis}-{offset * scale:+.4f}",
                )
                if candidate is not None:
                    proposals.append(
                        replace(
                            candidate,
                            source="targeted_combined",
                            provenance={
                                **candidate.provenance,
                                "anchor": anchor.candidate_id,
                                "weight_transfer": transfer.provenance,
                            },
                        )
                    )
    for axis, offsets in (
        ("P", (-0.04, -0.02, -0.01, 0.01, 0.02, 0.04)),
        ("conditional_R", (-0.04, -0.02, 0.02, 0.04)),
    ):
        for base in offsets:
            candidate = axis_probe(
                anchor, domain, axis, base * scale, f"{prefix}-{axis}-{base * scale:+.4f}"
            )
            if candidate is not None:
                proposals.append(candidate)
    for index in range(8):
        candidate = domain.local(anchor, rng, 0.035 * scale, f"{prefix}-local-{index}")
        proposals.append(
            replace(
                candidate,
                source="measured_local",
                prediction=None,
                provenance={"anchor": anchor.candidate_id, "radius": 0.035 * scale},
            )
        )
    return proposals


def next_batch(
    *,
    batch: int,
    candidates: dict[str, Candidate],
    rows_by_candidate: dict[str, list[dict]],
    states: list[PanelState],
    cloud: list[Candidate],
    domain: Domain,
    rule: PanelRule,
    rng: np.random.Generator,
) -> list[Candidate]:
    anchors = choose_anchors(candidates, states, domain, rule)
    selected = []
    existing = list(candidates.values())
    for anchor_index, anchor in enumerate(anchors):
        if anchor_index and anchor.candidate_id == anchors[0].candidate_id:
            continue
        state = next(s for s in states if s.candidate_id == anchor.candidate_id)
        pack = proposal_pack(
            anchor,
            rows_by_candidate.get(anchor.candidate_id, []),
            state,
            domain,
            rule,
            batch,
            anchor_index,
            rng,
        )
        sign = 1 if (batch + anchor_index) % 2 == 0 else -1
        classes = (
            ("targeted_weight_transfer", "targeted_combined", "measured_local"),
            ("P",),
            ("conditional_R",),
        )
        for group in classes:
            if group[0] in ("P", "conditional_R"):
                options = [
                    c
                    for c in pack
                    if c.source == "targeted_axis" and c.provenance.get("axis") in group
                ]
            else:
                options = [c for c in pack if c.source in group]
            options.sort(
                key=lambda c: (
                    0
                    if c.source
                    == ("targeted_weight_transfer" if batch % 2 == 0 else "targeted_combined")
                    else 1,
                    0 if float(c.provenance.get("normalized_offset", sign)) * sign > 0 else 1,
                    abs(abs(float(c.provenance.get("normalized_offset", 0.02))) - 0.02),
                    c.candidate_id,
                )
            )
            pick = next(
                (c for c in options if distinct(c, [*existing, *selected], domain, 0.005)), None
            )
            if pick is not None:
                selected.append(pick)
        own = [c for c in selected if c.provenance.get("anchor") == anchor.candidate_id]
        for candidate in pack:
            if len(own) >= 3:
                break
            if distinct(candidate, [*existing, *selected], domain, 0.005):
                selected.append(candidate)
                own.append(candidate)
    if len(selected) < 6:
        raise RuntimeError("Could not form six distinct measured-anchor proposals")
    selected = selected[:6]
    independents = sorted(
        (c for c in cloud if c.source == "independent"),
        key=lambda c: (predicted_violation(c, rule), c.prediction.objective),
    )
    for candidate in independents:
        if distinct(candidate, [*existing, *selected], domain, 0.04):
            selected.append(
                replace(
                    candidate,
                    candidate_id=f"b{batch:02d}-independent-{len(selected) - 6}",
                    provenance={
                        "cloud_id": candidate.candidate_id,
                        "protocol_version": "OC_GENERIC_1",
                    },
                )
            )
        if len(selected) == 8:
            break
    if len(selected) != 8:
        raise RuntimeError("Could not fill two independent exploration slots")
    return selected


def predicted_violation(candidate: Candidate, rule: PanelRule) -> float:
    prediction = candidate.prediction
    if prediction is None:
        return float("inf")
    if len(prediction.pj) != len(rule.job_types):
        raise ValueError("V3 prediction job dimension differs from configured jobs")
    return max(
        prediction.p90 / rule.tracking_limit - 1, *(p / rule.qos_limit - 1 for p in prediction.pj)
    )


def select_initial(cloud: list[Candidate], domain: Domain, rule: PanelRule) -> list[Candidate]:
    """Frozen 12 V3-guided and 3 independent legal initial geometries."""
    legal = [c for c in cloud if c.prediction is not None]
    for candidate in legal:
        domain.validate(candidate)
        predicted_violation(candidate, rule)
    guided = [c for c in legal if c.source != "independent"]
    independent = [c for c in legal if c.source == "independent"]
    if len(guided) < 12 or len(independent) < 3:
        raise ValueError("Candidate cloud cannot fill initial screen")
    safe = sorted(
        (c for c in guided if predicted_violation(c, rule) <= 0),
        key=lambda c: c.prediction.objective,
    )
    groups = [
        sorted(guided, key=lambda c: (predicted_violation(c, rule), c.prediction.objective)),
        sorted(guided, key=lambda c: (predicted_violation(c, rule), c.prediction.objective)),
        safe
        if safe
        else sorted(guided, key=lambda c: (predicted_violation(c, rule), c.prediction.objective)),
    ]
    selected = []
    for index in range(12):
        candidate = next(
            (c for c in groups[index % 3] if distinct(c, selected, domain, 0.018)), None
        )
        if candidate is None:
            raise ValueError("Insufficient diverse V3-guided initial candidates")
        selected.append(candidate)
    for candidate in sorted(
        independent, key=lambda c: (predicted_violation(c, rule), c.prediction.objective)
    ):
        if distinct(candidate, selected, domain, 0.025):
            selected.append(candidate)
        if len(selected) == 15:
            break
    if len(selected) != 15:
        raise ValueError("Insufficient independent initial candidates")
    return [
        replace(
            c,
            candidate_id=f"b01-screen-{i:02d}",
            provenance={
                **c.provenance,
                "cloud_id": c.candidate_id,
                "protocol_version": "OC_GENERIC_1",
            },
        )
        for i, c in enumerate(selected)
    ]


def serialize_state(state: PanelState) -> dict:
    return {
        **state.__dict__,
        "critical_failure_seeds": json.dumps(state.critical_failure_seeds),
        "signed_scenario_violations": json.dumps(state.signed_scenario_violations),
    }
