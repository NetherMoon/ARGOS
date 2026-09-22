"""Resumable shared three-scenario panel simulated annealing."""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from argos.contracts import QOS_LIMIT, TRACKING_LIMIT
from argos.experimental_sa.paper_consistent.feasibility import assess


@dataclass(frozen=True)
class Shared3Result:
    status: str
    scientific_result: dict | None
    current: dict | None
    best_scalar: dict | None
    best_panel_feasible: dict | None
    best_violation: dict | None
    transitions_completed: int
    panel_evaluations: int
    simulator_calls: int
    performed_calls_this_invocation: int
    error: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf8")
    os.replace(temporary, path)


def _better(candidate: dict, incumbent: dict | None) -> bool:
    return incumbent is None or candidate["panel_mean_Cfull"] < incumbent["panel_mean_Cfull"]


def _rank_violation(item: dict) -> tuple[float, float, float]:
    values = []
    for observation in item["scenario_observations"]:
        raw = observation["raw"]
        values.extend([raw["p90"] / TRACKING_LIMIT - 1])
        values.extend(np.asarray(raw["Pj"], dtype=float) / QOS_LIMIT - 1)
    excess = np.maximum(0.0, np.asarray(values, dtype=float))
    return float(excess.max()), float(excess.sum()), float(item["panel_mean_Cfull"])


def aggregate_panel(
    *,
    params,
    candidate_id: str,
    evaluation_id: int,
    panel_index: int,
    panel_seeds: list[int],
    raw_results: list[dict],
    contract,
    job_names: list[str],
) -> dict:
    if len(panel_seeds) != 3 or len(raw_results) != 3:
        raise ValueError("S3 requires exactly three scenario observations")
    observations = []
    for seed, raw in zip(panel_seeds, raw_results, strict=True):
        if int(raw["arrival_seed"]) != int(seed):
            raise ValueError("Shared-panel result has the wrong arrival seed")
        objective = contract.evaluate(raw["M_RSR"], raw["p90"], raw["Pj"]).to_dict()
        feasibility = assess(raw, job_names, objective["Cfull"])
        observations.append(
            {
                "arrival_seed": int(seed),
                "runtime_seed": int(raw["runtime_seed"]),
                "raw": raw,
                "objective": objective,
                "feasibility": feasibility,
            }
        )
    all_valid = all(x["feasibility"]["valid"] for x in observations)
    pass_count = sum(bool(x["feasibility"]["feasible"]) for x in observations)
    all_feasible = all_valid and pass_count == 3
    objective_keys = list(observations[0]["objective"])
    panel_objective = {}
    for key in objective_keys:
        values = [x["objective"][key] for x in observations]
        if isinstance(values[0], (list, tuple)):
            panel_objective[key] = np.mean(np.asarray(values, dtype=float), axis=0).tolist()
        elif isinstance(values[0], (int, float)):
            panel_objective[key] = float(np.mean(values))
    mean_pj = np.mean([x["raw"]["Pj"] for x in observations], axis=0).tolist()
    return {
        "candidate_id": candidate_id,
        "panel_evaluation_id": int(evaluation_id),
        "params": [float(x) for x in params],
        "panel_index": int(panel_index),
        "panel_seeds": [int(x) for x in panel_seeds],
        "scenario_observations": observations,
        "panel_mean_Cfull": float(np.mean([x["objective"]["Cfull"] for x in observations])),
        "panel_mean_p90": float(np.mean([x["raw"]["p90"] for x in observations])),
        "panel_mean_Pj": mean_pj,
        "panel_pass_count": int(pass_count),
        "panel_all_valid": bool(all_valid),
        "panel_all_feasible": bool(all_feasible),
        "objective": panel_objective,
        "feasibility": {
            "valid": bool(all_valid),
            "feasible": bool(all_feasible),
            "reason": "PANEL_FEASIBLE" if all_feasible else "PANEL_NOT_ALL_FEASIBLE",
            "evidence_valid_count": sum(bool(x["feasibility"]["valid"]) for x in observations),
        },
    }


def _update_best(item, best, feasible, violation):
    if not item["panel_all_valid"]:
        return best, feasible, violation
    if _better(item, best):
        best = item
    if item["panel_all_feasible"]:
        if _better(item, feasible):
            feasible = item
    elif violation is None or _rank_violation(item) < _rank_violation(violation):
        violation = item
    return best, feasible, violation


def _checkpoint(path, run_id, next_transition, temperature, current, current_panel_index,
                best, feasible, violation, panel_evaluations, simulator_calls, error):
    _atomic_json(
        path,
        {
            "schema": 1,
            "run_id": run_id,
            "next_transition": int(next_transition),
            "temperature": float(temperature),
            "current": current,
            "current_panel_index": int(current_panel_index),
            "current_panel_seeds": current["panel_seeds"] if current else None,
            "cached_current_panel_observation": current,
            "current_panel_mean_Cfull": current["panel_mean_Cfull"] if current else None,
            "current_panel_pass_count": current["panel_pass_count"] if current else None,
            "best_scalar": best,
            "best_panel_feasible": feasible,
            "best_violation": violation,
            "search_draw_position": int(next_transition),
            "panel_evaluations": int(panel_evaluations),
            "simulator_calls": int(simulator_calls),
            "error": error,
        },
    )


def run_shared3_trajectory(
    *,
    initial,
    domain,
    evaluator,
    contract,
    job_names,
    output: Path,
    run_id: str,
    panel_schedule: list[list[int]],
    runtime_seed: int,
    search_draws: list[dict],
    transitions: int = 400,
    block_size: int = 10,
    temperature: float = 1000.0,
    cooling_rate: float = 0.95,
    steps=(1.0, 1.0, 0.02),
    smart_weight: bool = True,
) -> Shared3Result:
    if transitions != len(search_draws):
        raise ValueError("Search schedule length must equal transitions")
    expected_panels = math.ceil(transitions / block_size)
    if len(panel_schedule) != expected_panels or any(len(x) != 3 for x in panel_schedule):
        raise ValueError("S3 panel schedule shape mismatch")
    if len({seed for panel in panel_schedule for seed in panel}) != expected_panels * 3:
        raise ValueError("S3 panel seeds must be unique")
    if not math.isfinite(temperature) or temperature <= 0 or not 0 < cooling_rate <= 1:
        raise ValueError("Invalid SA temperature schedule")
    domain.validate(initial)
    output.mkdir(parents=True, exist_ok=True)
    record_path = output / "iterations.jsonl"
    checkpoint_path = output / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else None
    performed_this_invocation = 0
    if checkpoint:
        next_transition = int(checkpoint["next_transition"])
        current = checkpoint["current"]
        current_panel_index = int(checkpoint["current_panel_index"])
        best = checkpoint["best_scalar"]
        feasible = checkpoint["best_panel_feasible"]
        violation = checkpoint["best_violation"]
        temperature = float(checkpoint["temperature"])
        panel_evaluations = int(checkpoint["panel_evaluations"])
        simulator_calls = int(checkpoint["simulator_calls"])
        error = checkpoint.get("error")
        lines = record_path.read_text(encoding="utf8").splitlines()
        if len(lines) != next_transition:
            raise ValueError("S3 checkpoint/trajectory mismatch")
        def restore_aggregate(item):
            if item is None or "qos_terms" in item.get("objective", {}):
                return item
            return aggregate_panel(
                params=item["params"], candidate_id=item["candidate_id"],
                evaluation_id=item["panel_evaluation_id"], panel_index=item["panel_index"],
                panel_seeds=item["panel_seeds"],
                raw_results=[x["raw"] for x in item["scenario_observations"]],
                contract=contract, job_names=job_names,
            )
        current = restore_aggregate(current)
        best = restore_aggregate(best)
        feasible = restore_aggregate(feasible)
        violation = restore_aggregate(violation)
    else:
        if record_path.exists():
            raise ValueError("S3 trajectory exists without checkpoint")
        record_path.touch()
        next_transition = 0
        current = best = feasible = violation = None
        current_panel_index = 0
        panel_evaluations = simulator_calls = 0
        error = None

    def evaluate(params, candidate_id, evaluation_id, panel_index):
        nonlocal performed_this_invocation
        response = evaluator.evaluate_panel(
            params=params,
            evaluation_id=evaluation_id,
            panel_index=panel_index,
            panel_seeds=panel_schedule[panel_index],
            runtime_seed=runtime_seed,
        )
        performed_this_invocation += int(response.get("performed_calls", 0))
        return aggregate_panel(
            params=params,
            candidate_id=candidate_id,
            evaluation_id=evaluation_id,
            panel_index=panel_index,
            panel_seeds=panel_schedule[panel_index],
            raw_results=response["raw_results"],
            contract=contract,
            job_names=job_names,
        )

    if next_transition == 0:
        current = evaluate(tuple(initial), f"{run_id}:0", 0, 0)
        panel_evaluations = 1
        simulator_calls = 3
        best, feasible, violation = _update_best(current, best, feasible, violation)
        row = {
            "run_id": run_id,
            "transition": 0,
            "kind": "INITIAL_CURRENT",
            "candidate_id": current["candidate_id"],
            "params": current["params"],
            "panel_index": 0,
            "panel_seeds": current["panel_seeds"],
            "panel_evaluation": current,
            "search_draw": None,
            "accepted": True,
            "temperature": temperature,
            "current_state_id": current["candidate_id"],
        }
        with record_path.open("a", encoding="utf8") as log:
            log.write(json.dumps(row, allow_nan=False) + "\n")
            log.flush(); os.fsync(log.fileno())
        next_transition = 1
        _checkpoint(checkpoint_path, run_id, next_transition, temperature, current, 0,
                    best, feasible, violation, panel_evaluations, simulator_calls, error)

    with record_path.open("a", encoding="utf8") as log:
        for transition in range(next_transition, transitions + 1):
            target_panel = (transition - 1) // block_size
            if target_panel != current_panel_index:
                boundary_evaluation_id = transition + target_panel - 1
                reevaluated = evaluate(
                    current["params"], current["candidate_id"], boundary_evaluation_id, target_panel
                )
                panel_evaluations += 1
                simulator_calls += 3
                current = reevaluated
                current_panel_index = target_panel
                best, feasible, violation = _update_best(current, best, feasible, violation)
                event = {
                    "kind": "PANEL_SWITCH_CURRENT_REEVALUATION",
                    "transition_before": transition,
                    "panel_index": target_panel,
                    "panel_seeds": panel_schedule[target_panel],
                    "current": current,
                }
                event_path = output / "panel_events" / f"panel_{target_panel:03d}.json"
                if event_path.exists():
                    if json.loads(event_path.read_text()) != event:
                        raise ValueError("Existing panel-switch event conflicts with resume")
                else:
                    _atomic_json(event_path, event)
                _checkpoint(checkpoint_path, run_id, transition, temperature, current,
                            current_panel_index, best, feasible, violation,
                            panel_evaluations, simulator_calls, error)

            draw = search_draws[transition - 1]
            if int(draw["iteration"]) != transition:
                raise ValueError("Search draw position mismatch")
            scale = 0.5 ** int(transition - 1 >= 200) * 0.5 ** int(transition - 1 >= 300)
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
            candidate_id = f"{run_id}:{transition}"
            proposal_evaluation_id = transition + target_panel
            proposal = evaluate(params, candidate_id, proposal_evaluation_id, target_panel)
            panel_evaluations += 1
            simulator_calls += 3
            if not proposal["panel_all_valid"]:
                error = "Panel evaluation lacks required evidence"
                _checkpoint(checkpoint_path, run_id, transition, temperature, current,
                            current_panel_index, best, feasible, violation,
                            panel_evaluations, simulator_calls, error)
                break
            best, feasible, violation = _update_best(proposal, best, feasible, violation)
            delta = proposal["panel_mean_Cfull"] - current["panel_mean_Cfull"]
            probability = 1.0 if delta <= 0 else math.exp(-delta / temperature)
            accepted = delta < 0 or draw["metropolis_uniform"] < probability
            parent_id = current["candidate_id"]
            if accepted:
                current = proposal
            row = {
                "run_id": run_id,
                "transition": transition,
                "kind": "PROPOSAL",
                "candidate_id": candidate_id,
                "parent_current_state_id": parent_id,
                "params": [float(v) for v in params],
                "panel_index": target_panel,
                "panel_seeds": panel_schedule[target_panel],
                "panel_evaluation": proposal,
                "search_draw": draw,
                "accepted": bool(accepted),
                "acceptance_probability": float(probability),
                "acceptance_draw": float(draw["metropolis_uniform"]),
                "temperature": float(temperature),
                "current_state_id": current["candidate_id"],
                "best_scalar_state_id": best["candidate_id"] if best else None,
                "best_panel_feasible_state_id": feasible["candidate_id"] if feasible else None,
                "best_violation_state_id": violation["candidate_id"] if violation else None,
            }
            log.write(json.dumps(row, allow_nan=False) + "\n")
            log.flush(); os.fsync(log.fileno())
            temperature = max(temperature * cooling_rate, float(np.finfo(float).tiny))
            _checkpoint(checkpoint_path, run_id, transition + 1, temperature, current,
                        current_panel_index, best, feasible, violation,
                        panel_evaluations, simulator_calls, error)

    status = (
        "EXECUTION_ERROR" if error else
        "PANEL_FEASIBLE_CANDIDATE_FOUND" if feasible else
        "NO_PANEL_FEASIBLE_CANDIDATE_FOUND"
    )
    return Shared3Result(
        status=status,
        scientific_result=feasible,
        current=current,
        best_scalar=best,
        best_panel_feasible=feasible,
        best_violation=violation,
        transitions_completed=min(transitions, int(json.loads(checkpoint_path.read_text())["next_transition"]) - 1),
        panel_evaluations=panel_evaluations,
        simulator_calls=simulator_calls,
        performed_calls_this_invocation=performed_this_invocation,
        error=error,
    )
