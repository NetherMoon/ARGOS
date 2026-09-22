"""Frozen scenario and paired-search schedules for Phase 3."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

UINT32_LIMIT = 2**32


@dataclass(frozen=True)
class Scenario:
    iteration: int
    arrival_seed: int
    runtime_seed: int


class FixedArrivalScenarioPolicy:
    name = "fixed"

    def __init__(self, arrival_seed: int, runtime_seed: int, evaluations: int):
        self.arrival_seed = _seed(arrival_seed)
        self.runtime_seed = _seed(runtime_seed)
        self.evaluations = evaluations

    def scenario_for_iteration(self, iteration: int) -> Scenario:
        _iteration(iteration, self.evaluations)
        return Scenario(iteration, self.arrival_seed, self.runtime_seed)


class VaryingArrivalScenarioPolicy:
    name = "varying"

    def __init__(self, arrival_schedule: list[int], runtime_seed: int):
        if not arrival_schedule:
            raise ValueError("Arrival schedule is empty")
        self.arrival_schedule = tuple(_seed(x) for x in arrival_schedule)
        if len(set(self.arrival_schedule)) != len(self.arrival_schedule):
            raise ValueError("Varying-arrival schedule must be unique")
        self.runtime_seed = _seed(runtime_seed)

    def scenario_for_iteration(self, iteration: int) -> Scenario:
        _iteration(iteration, len(self.arrival_schedule))
        return Scenario(iteration, self.arrival_schedule[iteration], self.runtime_seed)


def _seed(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise TypeError("Seed must be an integer")
    value = int(value)
    if not 0 <= value < UINT32_LIMIT:
        raise ValueError("Seed outside uint32")
    return value


def _iteration(iteration: int, evaluations: int) -> None:
    if not isinstance(iteration, int) or not 0 <= iteration < evaluations:
        raise IndexError("Iteration outside frozen schedule")


def generate_seed_plan(root_seed: int, excluded: set[int]) -> dict:
    """Generate all identities before any Phase 3 scientific outcome exists."""
    rng = np.random.default_rng(_seed(root_seed))
    used = {_seed(x) for x in excluded}

    def take(count: int) -> list[int]:
        result = []
        while len(result) < count:
            candidate = int(rng.integers(0, UINT32_LIMIT, dtype=np.uint32))
            if candidate not in used:
                used.add(candidate)
                result.append(candidate)
        return result

    arrival_schedule = take(401)
    assessment = take(10)
    runtime = take(1)[0]
    search = take(2)
    smoke_arrivals = take(6)
    smoke_runtime = take(1)[0]
    smoke_search = take(1)[0]
    plan = {
        "schema": 1,
        "generator": "numpy.random.Generator(PCG64)",
        "root_seed": _seed(root_seed),
        "rejection_rule": "draw uint32; reject prior-ledger and earlier Phase 3 role values",
        "excluded_prior_seed_count": len(set(excluded)),
        "arrival_schedule": arrival_schedule,
        "fixed_arrival_seed": arrival_schedule[0],
        "assessment_seeds": assessment,
        "training_runtime_seed": runtime,
        "search_seeds": {"A": search[0], "B": search[1]},
        "smoke": {
            "arrival_schedule": smoke_arrivals,
            "runtime_seed": smoke_runtime,
            "search_seed": smoke_search,
        },
    }
    validate_seed_plan(plan, excluded)
    return plan


def validate_seed_plan(plan: dict, excluded: set[int]) -> None:
    arrivals = [_seed(x) for x in plan["arrival_schedule"]]
    assessment = [_seed(x) for x in plan["assessment_seeds"]]
    runtime = _seed(plan["training_runtime_seed"])
    smoke = [_seed(x) for x in plan["smoke"]["arrival_schedule"]]
    smoke_runtime = _seed(plan["smoke"]["runtime_seed"])
    if len(arrivals) != 401 or len(set(arrivals)) != 401:
        raise ValueError("Expected 401 unique arrival seeds")
    if len(assessment) != 10 or len(set(assessment)) != 10:
        raise ValueError("Expected 10 unique assessment seeds")
    simulator_roles = set(arrivals) | set(assessment) | {runtime} | set(smoke) | {smoke_runtime}
    if len(simulator_roles) != 419:
        raise ValueError("Phase 3 simulator seed roles overlap")
    if simulator_roles & set(excluded):
        raise ValueError("Phase 3 simulator seed overlaps prior evidence")
    if plan["fixed_arrival_seed"] != arrivals[0]:
        raise ValueError("Fixed seed is not arrival_schedule[0]")


def generate_search_draws(search_seed: int, transitions: int, job_count: int) -> list[dict]:
    """Freeze exogenous proposal and Metropolis draws by transition."""
    rng = np.random.default_rng(_seed(search_seed))
    rows = []
    for transition in range(1, transitions + 1):
        rows.append(
            {
                "iteration": transition,
                "p_standard_normal": float(rng.normal()),
                "r_standard_normal": float(rng.normal()),
                "weight_standard_normals": [float(x) for x in rng.normal(size=job_count)],
                "metropolis_uniform": float(rng.random()),
            }
        )
    return rows


def write_search_draws(path: Path, draws: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "iteration",
                "p_standard_normal",
                "r_standard_normal",
                "weight_standard_normals",
                "metropolis_uniform",
            ],
        )
        writer.writeheader()
        for row in draws:
            item = dict(row)
            item["weight_standard_normals"] = json.dumps(item["weight_standard_normals"])
            writer.writerow(item)


def read_search_draws(path: Path) -> list[dict]:
    rows = []
    with path.open(newline="", encoding="utf8") as stream:
        for row in csv.DictReader(stream):
            rows.append(
                {
                    "iteration": int(row["iteration"]),
                    "p_standard_normal": float(row["p_standard_normal"]),
                    "r_standard_normal": float(row["r_standard_normal"]),
                    "weight_standard_normals": json.loads(row["weight_standard_normals"]),
                    "metropolis_uniform": float(row["metropolis_uniform"]),
                }
            )
    if [x["iteration"] for x in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("Search draw schedule is not contiguous")
    return rows


def scenario_dict(value: Scenario) -> dict:
    return asdict(value)
