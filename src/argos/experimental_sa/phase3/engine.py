"""Resumable sequential SA with frozen scenario and search-draw schedules."""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from argos.contracts import QOS_LIMIT, TRACKING_LIMIT
from argos.experimental_sa.paper_consistent.feasibility import assess

from .scenarios import scenario_dict


@dataclass(frozen=True)
class Phase3Result:
    status: str
    scientific_result: dict | None
    current: dict | None
    best_scalar: dict | None
    best_feasible: dict | None
    best_violation: dict | None
    evaluations: int
    simulator_calls: int
    error: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf8")
    os.replace(temporary, path)


def _rank_violation(item: dict) -> tuple[float, float, float]:
    values = np.maximum(
        0,
        np.r_[
            item["raw"]["p90"] / TRACKING_LIMIT - 1,
            np.asarray(item["raw"]["Pj"]) / QOS_LIMIT - 1,
        ],
    )
    return float(values.max()), float(values.sum()), item["objective"]["Cfull"]


def _better(candidate: dict, incumbent: dict | None) -> bool:
    return incumbent is None or candidate["objective"]["Cfull"] < incumbent["objective"]["Cfull"]


def run_trajectory(
    *,
    initial,
    domain,
    evaluator,
    contract,
    job_names,
    output: Path,
    run_id: str,
    scenario_policy,
    search_draws: list[dict],
    transitions: int,
    temperature: float,
    cooling_rate: float,
    steps,
    smart_weight: bool = True,
    max_infrastructure_retries: int = 2,
) -> Phase3Result:
    if transitions < 0 or len(search_draws) != transitions:
        raise ValueError("Search schedule length must equal transitions")
    if not math.isfinite(temperature) or temperature <= 0 or not 0 < cooling_rate <= 1:
        raise ValueError("Invalid SA temperature schedule")
    domain.validate(initial)
    output.mkdir(parents=True, exist_ok=True)
    record_path = output / "iterations.jsonl"
    checkpoint_path = output / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else None
    if checkpoint:
        next_iteration = int(checkpoint["next_iteration"])
        current = checkpoint["current"]
        best = checkpoint["best_scalar"]
        feasible = checkpoint["best_feasible"]
        violation = checkpoint["best_violation"]
        temperature = float(checkpoint["temperature"])
        simulator_calls = int(checkpoint["simulator_calls"])
        error = checkpoint.get("error")
        if error:
            return _result(
                current, best, feasible, violation, next_iteration, simulator_calls, error
            )
        lines = record_path.read_text(encoding="utf8").splitlines()
        if len(lines) != next_iteration or (
            lines and json.loads(lines[-1])["iteration"] != next_iteration - 1
        ):
            raise ValueError("Checkpoint/trajectory mismatch")
    else:
        if record_path.exists():
            raise ValueError("Trajectory exists without a valid checkpoint")
        next_iteration = 0
        current = best = feasible = violation = None
        simulator_calls = 0
        error = None
        record_path.touch()

    with record_path.open("a", encoding="utf8") as log:
        for iteration in range(next_iteration, transitions + 1):
            scenario = scenario_policy.scenario_for_iteration(iteration)
            parent = current
            if iteration == 0:
                params = tuple(initial)
                draw = None
            else:
                draw = search_draws[iteration - 1]
                if draw["iteration"] != iteration:
                    raise ValueError("Search draw position mismatch")
                scale = 0.5 ** int(iteration - 1 >= 200) * 0.5 ** int(iteration - 1 >= 300)
                x = np.asarray(current["params"], dtype=float).copy()
                x[0] += draw["p_standard_normal"] * steps[0] * scale
                x[1] += draw["r_standard_normal"] * steps[1] * scale
                if smart_weight:
                    terms = np.asarray(current["objective"]["qos_terms"], dtype=float)
                    maximum = float(terms.max())
                    if maximum > 0:
                        x[2:] *= 1 + steps[2] * scale * terms / maximum
                else:
                    x[2:] += np.asarray(draw["weight_standard_normals"]) * steps[2] * scale
                params = domain.project(x)
            candidate_id = f"{run_id}:{iteration}"
            retry_records = []
            raw = None
            performed_calls = 0
            for attempt in range(max_infrastructure_retries + 1):
                try:
                    response = evaluator(params, iteration, scenario)
                    raw = response["raw"]
                    performed_calls += int(response.get("simulator_call_performed", True))
                    retry_records.extend(response.get("retry_records", []))
                    break
                except Exception as exc:  # noqa: BLE001 - exact candidate/scenario retry only
                    retry_records.append(
                        {
                            "attempt": attempt + 1,
                            "kind": "INFRASTRUCTURE_FAILURE",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    if attempt == max_infrastructure_retries:
                        error = retry_records[-1]["error"]
            simulator_calls += performed_calls
            obj = None
            validity = assess({"status": "ERROR", "error": error}, job_names, 0)
            if raw is not None:
                try:
                    obj = contract.evaluate(raw["M_RSR"], raw["p90"], raw["Pj"]).to_dict()
                    validity = assess(raw, job_names, obj["Cfull"])
                except Exception as exc:  # noqa: BLE001 - stable scientific-invalid record
                    error = f"{type(exc).__name__}: {exc}"
                    validity = assess({"status": "INVALID", "error": error}, job_names, 0)
            item = {
                "candidate_id": candidate_id,
                "params": list(params),
                "raw": raw,
                "objective": obj,
                "feasibility": validity,
            }
            accepted = False
            probability = 0.0
            acceptance_draw = None if iteration == 0 else draw["metropolis_uniform"]
            if validity["valid"]:
                if _better(item, best):
                    best = item
                if validity["feasible"] and _better(item, feasible):
                    feasible = item
                if not validity["feasible"] and (
                    violation is None or _rank_violation(item) < _rank_violation(violation)
                ):
                    violation = item
                delta = 0.0 if current is None else obj["Cfull"] - current["objective"]["Cfull"]
                probability = 1.0 if delta <= 0 else math.exp(-delta / temperature)
                accepted = current is None or delta < 0 or acceptance_draw < probability
                if accepted:
                    current = item
            else:
                error = error or validity["reason"]
            row = {
                "run_id": run_id,
                "iteration": iteration,
                "candidate_id": candidate_id,
                "parent_current_state_id": parent["candidate_id"] if parent else None,
                "params": list(params),
                "scenario": scenario_dict(scenario),
                "search_draw": draw,
                "raw": raw,
                "objective": obj,
                "feasibility": validity,
                "accepted": accepted,
                "acceptance_probability": probability,
                "acceptance_draw": acceptance_draw,
                "temperature": temperature,
                "current_state_id": current["candidate_id"] if current else None,
                "best_scalar_state_id": best["candidate_id"] if best else None,
                "best_feasible_state_id": feasible["candidate_id"] if feasible else None,
                "best_violation_state_id": violation["candidate_id"] if violation else None,
                "retry_records": retry_records,
            }
            log.write(json.dumps(row, allow_nan=False) + "\n")
            log.flush()
            os.fsync(log.fileno())
            if iteration > 0:
                temperature = max(temperature * cooling_rate, float(np.finfo(float).tiny))
            checkpoint = {
                "schema": 1,
                "run_id": run_id,
                "next_iteration": iteration + 1,
                "temperature": temperature,
                "current": current,
                "best_scalar": best,
                "best_feasible": feasible,
                "best_violation": violation,
                "simulator_calls": simulator_calls,
                "error": error,
            }
            _atomic_json(checkpoint_path, checkpoint)
            evaluator.finalize_iteration(iteration, scenario, validity["valid"])
            if error:
                break
    return _result(
        current,
        best,
        feasible,
        violation,
        int(checkpoint["next_iteration"]),
        simulator_calls,
        error,
    )


def _result(current, best, feasible, violation, evaluations, simulator_calls, error):
    status = (
        "EXECUTION_ERROR"
        if error
        else "FEASIBLE_CANDIDATE_FOUND"
        if feasible
        else "NO_FEASIBLE_CANDIDATE_FOUND"
    )
    return Phase3Result(
        status,
        feasible,
        current,
        best,
        feasible,
        violation,
        evaluations,
        simulator_calls,
        error,
    )
