"""Experimental paper-consistent SA derived from pinned FlexDC simulated_annealing.py.
Retains Gaussian P/R proposals, optional QoS-directed weights, Metropolis acceptance,
geometric cooling, and the original iteration-200/300 step reductions. See the diff.
"""

import json
import math
from dataclasses import asdict, dataclass

import numpy as np

from argos.contracts import QOS_LIMIT, TRACKING_LIMIT

from .feasibility import assess
from .rng import search_rng, state


@dataclass(frozen=True)
class SAResult:
    status: str
    scientific_result: dict | None
    current: dict | None
    best_scalar: dict | None
    best_feasible: dict | None
    best_violation: dict | None
    evaluations: int
    error: str | None

    def to_dict(self):
        return asdict(self)


def optimize(
    initial,
    domain,
    evaluator,
    contract,
    job_names,
    record_path,
    *,
    run_id,
    search_seed,
    arrival_seed,
    runtime_seed,
    iterations,
    temperature,
    cooling_rate,
    steps,
    smart_weight=True,
):
    if (
        iterations < 0
        or not isinstance(iterations, int)
        or not math.isfinite(temperature)
        or temperature <= 0
        or not 0 < cooling_rate <= 1
        or len(steps) != 3
        or not np.isfinite(steps).all()
        or min(steps) < 0
    ):
        raise ValueError("Invalid SA settings")
    domain.validate(initial)
    rng = search_rng(search_seed)
    current = best = feasible = violation = None
    error = None
    count = 0

    def rank(v):
        vals = np.maximum(
            0, np.r_[v["raw"]["p90"] / TRACKING_LIMIT - 1, np.array(v["raw"]["Pj"]) / QOS_LIMIT - 1]
        )
        return (float(vals.max()), float(vals.sum()), v["objective"]["Cfull"])

    # Exclusive create prevents silently overwriting a previous trajectory.
    with record_path.open("x", encoding="utf8") as log:
        for iteration in range(iterations + 1):
            parent = current
            before = state(rng)
            accept_draw = None
            if iteration == 0:
                params = tuple(initial)
            else:
                scale = 0.5 ** int(iteration - 1 >= 200) * 0.5 ** int(iteration - 1 >= 300)
                x = np.array(current["params"])
                x[0] += rng.normal(0, steps[0] * scale)
                x[1] += rng.normal(0, steps[1] * scale)
                if smart_weight:
                    terms = np.array(current["objective"]["qos_terms"])
                    x[2:] *= 1 + steps[2] * scale * terms / max(terms)
                else:
                    x[2:] += rng.normal(0, steps[2] * scale, len(job_names))
                params = domain.project(x)
            candidate_id = f"{run_id}:{iteration}"
            search_before_call = state(rng)
            try:
                raw = evaluator(params, iteration, runtime_seed)
                if state(rng) != search_before_call:
                    raise RuntimeError("Simulator mutated search RNG")
                obj = contract.evaluate(raw["M_RSR"], raw["p90"], raw["Pj"]).to_dict()
                validity = assess(raw, job_names, obj["Cfull"])
            except Exception as exc:  # noqa: BLE001 - record execution failure in stable result schema
                raw = {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}
                obj = None
                validity = assess(raw, job_names, 0)
            accepted = False
            probability = 0.0
            item = {
                "candidate_id": candidate_id,
                "params": list(params),
                "raw": raw,
                "objective": obj,
                "feasibility": validity,
            }
            if validity["valid"]:
                if best is None or obj["Cfull"] < best["objective"]["Cfull"]:
                    best = item
                if validity["feasible"] and (
                    feasible is None or obj["Cfull"] < feasible["objective"]["Cfull"]
                ):
                    feasible = item
                if not validity["feasible"] and (violation is None or rank(item) < rank(violation)):
                    violation = item
                delta = 0 if current is None else obj["Cfull"] - current["objective"]["Cfull"]
                probability = 1.0 if delta <= 0 else math.exp(-delta / temperature)
                if current is None or delta < 0:
                    accepted = True
                else:
                    accept_draw = float(rng.random())
                    accepted = accept_draw < probability
                if accepted:
                    current = item
            else:
                error = raw.get("error", validity["reason"])
                raw = {
                    "status": "INVALID",
                    "error": error,
                    "invalid_payload_repr": repr(raw)[:4096],
                }
                obj = None
            row = {
                "run_id": run_id,
                "iteration": iteration,
                "candidate_id": candidate_id,
                "parent_current_state_id": parent["candidate_id"] if parent else None,
                "Pbar": params[0],
                "R": params[1],
                "weights": list(params[2:]),
                "search_seed": search_seed,
                "arrival_seed": arrival_seed,
                "runtime_seed": runtime_seed,
                "search_rng_before": before,
                "search_rng_after": state(rng),
                "raw": raw,
                "objective": obj,
                "feasibility": validity,
                "accepted": accepted,
                "acceptance_probability": probability,
                "acceptance_draw": accept_draw,
                "temperature": temperature,
                "current_objective_before": parent["objective"]["Cfull"] if parent else None,
                "current_objective_after": current["objective"]["Cfull"] if current else None,
                "best_objective": best["objective"]["Cfull"] if best else None,
                "best_feasible_objective": feasible["objective"]["Cfull"] if feasible else None,
                "current_state_id": current["candidate_id"] if current else None,
                "best_feasible_state_id": feasible["candidate_id"] if feasible else None,
            }
            log.write(json.dumps(row, allow_nan=False) + "\n")
            log.flush()
            count += 1
            if error:
                break
            if iteration > 0:
                temperature *= cooling_rate
            if temperature <= 0:
                temperature = float(np.finfo(float).tiny)
    status = (
        "EXECUTION_ERROR"
        if error
        else "FEASIBLE_CANDIDATE_FOUND"
        if feasible
        else "NO_FEASIBLE_CANDIDATE_FOUND"
    )
    return SAResult(status, feasible, current, best, feasible, violation, count, error)
