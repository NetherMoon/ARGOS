"""One-time deterministic seed allocation; scientific seeds are frozen before simulation."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from argos.fixed_table.protocol import EPISODE_PLAN, ROOT, SEED_PLAN, WORKLOADS
from argos.provenance import sha256

ROOT_SEED = 20260922
SOURCES = (
    "configs/campaigns/seed_ledger_v1.json",
    "configs/vnext/seed_ledger.json",
    "configs/diagnostics/w2_characterization_new_seed_panel.csv",
    "configs/diagnostics/w2_seed_historical_outcomes.csv",
    "runs/experiments/phase3_sa_arrival_uncertainty_20260919T192854_241405Z/seed_plan.json",
    "runs/experiments/phase3b_sa_repeatability_20260920T013845_702021Z/seed_plan.json",
    "runs/experiments/phase3c_shared_scenario_final_20260921T030010_482207Z/seed_plan.json",
)


def integers(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from integers(child)
    elif isinstance(value, list):
        for child in value:
            yield from integers(child)
    elif isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 2**32:
        yield value


def select(root: Path = ROOT) -> tuple[dict, list[dict]]:
    excluded = {20, 21, 22}
    receipts = {}
    for name in SOURCES:
        path = root / name
        if not path.exists():
            if name.startswith("configs/"):
                raise FileNotFoundError(path)
            continue
        receipts[name] = sha256(path)
        if path.suffix == ".json":
            excluded.update(integers(json.loads(path.read_text(encoding="utf8"))))
        else:
            with path.open(newline="", encoding="utf8") as stream:
                for row in csv.DictReader(stream):
                    for key, value in row.items():
                        if "seed" in key.lower() and value and value.isdecimal():
                            excluded.add(int(value))
    rng = random.Random(ROOT_SEED)
    used = set(excluded)

    def fresh():
        while True:
            value = rng.randrange(1, 2**32)
            if value not in used:
                used.add(value)
                return value

    seeds = {
        "schema": 1,
        "selection_method": "Python 3.12 random.Random(20260922).randrange(1,2**32), sequential rejection against all listed prior integers and selected values",
        "root_seed": ROOT_SEED,
        "excluded_source_sha256": receipts,
        "excluded_count": len(excluded),
        "arrival_seeds": [fresh() for _ in range(3)],
        "search_runtime_seed": fresh(),
        "final_runtime_seeds": [fresh() for _ in range(3)],
        "controller_seeds": {name: fresh() for name in WORKLOADS},
        "controller_randomness": "One candidate seed per workload reused across all three arrival-table episodes; V3 bank and each batch draw use this seed",
    }
    rows = [
        {
            "workload": name,
            "server_count": 1000,
            "utilization": 0.6,
            "arrival_seed": arrival_seed,
            "search_runtime_seed": seeds["search_runtime_seed"],
            "episode_path": f"{name}/arrival_{arrival_seed}",
            "max_search_calls": 32,
            "max_final_checks": 3,
        }
        for name in WORKLOADS
        for arrival_seed in seeds["arrival_seeds"]
    ]
    if (
        len(rows) != 6
        or len(
            {
                *seeds["arrival_seeds"],
                seeds["search_runtime_seed"],
                *seeds["final_runtime_seeds"],
                *seeds["controller_seeds"].values(),
            }
        )
        != 9
    ):
        raise ValueError("Seed allocation collision")
    return seeds, rows


def freeze(root: Path = ROOT) -> tuple[dict, list[dict]]:
    seeds, rows = select(root)
    seed_path, plan_path = root / SEED_PLAN, root / EPISODE_PLAN
    if seed_path.exists() or plan_path.exists():
        raise FileExistsError("Fixed-table plan already frozen")
    seed_path.write_text(json.dumps(seeds, indent=2) + "\n", encoding="utf8")
    with plan_path.open("x", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return seeds, rows
