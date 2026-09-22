"""Phase 3C provenance gates and immutable experiment-plan construction."""

from __future__ import annotations

import configparser
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

from argos.diagnostics.workload_seed_forensics import sha
from argos.experimental_sa.phase3.planning import (
    EXPECTED_CHECKPOINT,
    PHASE2B,
    PHASE2C,
    collect_prior_seeds,
)
from argos.experimental_sa.phase3.scenarios import UINT32_LIMIT, write_search_draws
from argos.experimental_sa.phase3b.planning import (
    PHASE3,
    _collect_seed_values,
    _hash,
    generate_replicate_search_draws,
    verify_phase3_provenance,
    verify_frozen_contract as verify_phase3b_contract,
)

PHASE3B = Path("runs/experiments/phase3b_sa_repeatability_20260920T013845_702021Z")
ROOT_SEED = 20260922
TRANSITIONS = 400
BLOCK_SIZE = 10
PANELS = 40
PANEL_SIZE = 3
NAIVE_EVALUATIONS = 401
SHARED_PANEL_EVALUATIONS = 440
NAIVE_CALLS_PER_TRAJECTORY = 401
SHARED_CALLS_PER_TRAJECTORY = 1320
OPTIMIZATION_RUNTIME_SEED = 3609882979
REPLICATES = (1, 2)
CASES = (("A", "c005"), ("B", "c007"))
METHODS = ("naive", "shared3")

PHASE3C_FILES = [
    "src/argos/experimental_sa/phase3c/__init__.py",
    "src/argos/experimental_sa/phase3c/engine.py",
    "src/argos/experimental_sa/phase3c/evaluator.py",
    "src/argos/experimental_sa/phase3c/planning.py",
    "src/argos/experimental_sa/phase3c/reporting.py",
    "src/argos/experimental_sa/phase3c/runner.py",
    "scripts/run_phase3c_shared_scenario_final.py",
    "tests/unit/test_phase3c_shared_scenario_final.py",
    "docs/PHASE3C_SHARED_SCENARIO_FINAL.md",
]
REUSED_FILES = [
    "src/argos/experimental_sa/phase3/engine.py",
    "src/argos/experimental_sa/phase3/evaluator.py",
    "src/argos/experimental_sa/phase3/scenarios.py",
    "src/argos/experimental_sa/phase3/runner.py",
    "src/argos/experimental_sa/paper_consistent/domain.py",
    "src/argos/experimental_sa/paper_consistent/evaluator.py",
    "src/argos/experimental_sa/paper_consistent/feasibility.py",
    "src/argos/experimental_sa/paper_consistent/objective.py",
    "scripts/run_experimental_sa.py",
]
FROZEN_PLAN_FILES = [
    "seed_plan.json",
    "search_seed_plan.csv",
    "naive_arrival_schedule.csv",
    "shared_panel_schedule.csv",
    "assessment_seed_panel.csv",
    "assessment_panel_A.csv",
    "assessment_panel_B.csv",
    "run_plan.csv",
    "optimization_call_plan.csv",
    "assessment_run_plan.csv",
    "provenance_links.json",
    "search_draw_schedule/replicate_1/A.csv",
    "search_draw_schedule/replicate_1/B.csv",
    "search_draw_schedule/replicate_2/A.csv",
    "search_draw_schedule/replicate_2/B.csv",
    "search_draw_schedule/smoke_A.csv",
]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf8"))


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("Cannot freeze an empty plan")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def verify_lineage(root: Path) -> dict:
    phase3 = verify_phase3_provenance(root)
    phase3b = root / PHASE3B
    manifest = _json(phase3b / "manifest.json")
    if manifest.get("status") != "COMPLETE":
        raise ValueError("Phase 3B is not complete")
    if manifest.get("repo_shas") != phase3["repo_shas"]:
        raise ValueError("Phase 3B repository lineage mismatch")
    verify_phase3b_contract(root, phase3b)
    if int(manifest.get("optimization_runtime_seed")) != OPTIMIZATION_RUNTIME_SEED:
        raise ValueError("Phase 3B optimization runtime seed mismatch")
    if len(list((phase3b / "assessment/cells").glob("*/result.json"))) != 280:
        raise ValueError("Phase 3B assessment evidence is incomplete")
    return {"phase3": phase3, "phase3b_manifest": manifest}


def _generate_seed_plan(prior: set[int]) -> dict:
    rng = np.random.default_rng(ROOT_SEED)
    used = set(int(x) for x in prior)

    def take(count: int) -> list[int]:
        result = []
        while len(result) < count:
            value = int(rng.integers(0, UINT32_LIMIT, dtype=np.uint32))
            if value not in used:
                used.add(value); result.append(value)
        return result

    search = take(2)
    naive = take(NAIVE_EVALUATIONS)
    shared = take(PANELS * PANEL_SIZE)
    assessment = take(20)
    smoke_search = take(1)[0]
    smoke_panel = take(6)
    plan = {
        "schema": 1,
        "generator": "numpy.random.Generator(PCG64)",
        "root_seed": ROOT_SEED,
        "selection_procedure": (
            "Draw uint32 values sequentially; reject prior scientific seeds and every earlier "
            "Phase 3C role. Allocate two search roots, 401 naive seeds, 120 shared-panel seeds, "
            "20 assessment seeds, then one smoke search root and six smoke-only panel seeds."
        ),
        "excluded_prior_seed_count": len(prior),
        "search_roots": {"replicate_1": search[0], "replicate_2": search[1]},
        "naive_arrival_seeds": naive,
        "shared_panel_seeds": [shared[i:i + 3] for i in range(0, len(shared), 3)],
        "assessment_seeds": assessment,
        "panel_A": assessment[:10],
        "panel_B": assessment[10:],
        "optimization_runtime_seed": OPTIMIZATION_RUNTIME_SEED,
        "smoke": {"search_root": smoke_search, "panel_seeds": [smoke_panel[:3], smoke_panel[3:]]},
    }
    validate_seed_plan(plan, prior)
    return plan


def validate_seed_plan(plan: dict, prior: set[int]) -> None:
    search = list(plan["search_roots"].values())
    naive = plan["naive_arrival_seeds"]
    shared = [x for panel in plan["shared_panel_seeds"] for x in panel]
    assessment = plan["assessment_seeds"]
    smoke = [plan["smoke"]["search_root"], *[x for p in plan["smoke"]["panel_seeds"] for x in p]]
    groups = [search, naive, shared, assessment, smoke]
    expected = [2, 401, 120, 20, 7]
    if [len(x) for x in groups] != expected or any(len(set(x)) != len(x) for x in groups):
        raise ValueError("Phase 3C seed group shape/uniqueness mismatch")
    unions = set()
    for group in groups:
        if set(group) & unions:
            raise ValueError("Phase 3C seed roles overlap")
        unions |= set(group)
    if unions & set(prior):
        raise ValueError("Phase 3C seed overlaps prior evidence")
    if plan["panel_A"] != assessment[:10] or plan["panel_B"] != assessment[10:]:
        raise ValueError("Assessment panel split changed")
    if int(plan["optimization_runtime_seed"]) != OPTIMIZATION_RUNTIME_SEED:
        raise ValueError("Optimization runtime seed changed")


def _prior_seeds(root: Path, lineage: dict) -> set[int]:
    prior = collect_prior_seeds(root)
    prior |= _collect_seed_values(lineage["phase3"]["phase3_seed_plan"])
    prior |= _collect_seed_values(_json(root / PHASE3B / "seed_plan.json"))
    prior |= _collect_seed_values(_json(root / PHASE3B / "training_arrival_schedule_reference.json"))
    return prior


def create_plan(root: Path, output: Path | None = None) -> Path:
    lineage = verify_lineage(root)
    spec = lineage["phase3"]["phase2b"]["specification"]
    seed_plan = _generate_seed_plan(_prior_seeds(root, lineage))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = (output or root / "runs/experiments" / f"phase3c_shared_scenario_final_{stamp}").resolve()
    output.mkdir(parents=True, exist_ok=False)
    _write_json(output / "seed_plan.json", seed_plan)

    _write_csv(output / "naive_arrival_schedule.csv", [
        {"evaluation": i, "arrival_seed": seed, "runtime_seed": OPTIMIZATION_RUNTIME_SEED}
        for i, seed in enumerate(seed_plan["naive_arrival_seeds"])
    ])
    shared_rows = []
    for panel_index, panel in enumerate(seed_plan["shared_panel_seeds"]):
        for slot, seed in enumerate(panel):
            shared_rows.append({
                "panel_index": panel_index,
                "block_start_transition": panel_index * BLOCK_SIZE + 1,
                "block_end_transition": (panel_index + 1) * BLOCK_SIZE,
                "slot": slot,
                "arrival_seed": seed,
                "runtime_seed": OPTIMIZATION_RUNTIME_SEED,
            })
    _write_csv(output / "shared_panel_schedule.csv", shared_rows)
    assessment_rows = [
        {
            "combined_index": i,
            "panel": "A" if i <= 10 else "B",
            "panel_index": i if i <= 10 else i - 10,
            "seed": seed,
            "arrival_seed": seed,
            "runtime_seed": seed,
            "role": "INDEPENDENT_FRESH_COUPLED",
        }
        for i, seed in enumerate(seed_plan["assessment_seeds"], 1)
    ]
    _write_csv(output / "assessment_seed_panel.csv", assessment_rows)
    _write_csv(output / "assessment_panel_A.csv", assessment_rows[:10])
    _write_csv(output / "assessment_panel_B.csv", assessment_rows[10:])

    search_rows = []
    for replicate in REPLICATES:
        draws = generate_replicate_search_draws(seed_plan["search_roots"][f"replicate_{replicate}"])
        for label, _case in CASES:
            path = output / "search_draw_schedule" / f"replicate_{replicate}" / f"{label}.csv"
            write_search_draws(path, draws[label])
            search_rows.append({
                "replicate": replicate,
                "case_label": label,
                "search_root_seed": seed_plan["search_roots"][f"replicate_{replicate}"],
                "schedule": str(path.relative_to(output)).replace("\\", "/"),
                "sha256": _hash(path),
                "matched_methods": "naive,shared3",
            })
    smoke_draws = generate_replicate_search_draws(seed_plan["smoke"]["search_root"])["A"][:4]
    write_search_draws(output / "search_draw_schedule/smoke_A.csv", smoke_draws)
    _write_csv(output / "search_seed_plan.csv", search_rows)

    run_rows = []
    for replicate in REPLICATES:
        for label, case in CASES:
            for method in METHODS:
                run_rows.append({
                    "trajectory": f"replicate_{replicate}/{case}_{method}",
                    "replicate": replicate,
                    "case_label": label,
                    "case": case,
                    "method": method,
                    "search_root_seed": seed_plan["search_roots"][f"replicate_{replicate}"],
                    "search_draw_schedule": f"search_draw_schedule/replicate_{replicate}/{label}.csv",
                    "transitions": TRANSITIONS,
                    "nominal_simulator_calls": NAIVE_CALLS_PER_TRAJECTORY if method == "naive" else SHARED_CALLS_PER_TRAJECTORY,
                    "runtime_seed": OPTIMIZATION_RUNTIME_SEED,
                })
    _write_csv(output / "run_plan.csv", run_rows)

    call_rows = []
    for run in run_rows:
        if run["method"] == "naive":
            for evaluation, seed in enumerate(seed_plan["naive_arrival_seeds"]):
                call_rows.append({**run, "logical_stage": "initial" if evaluation == 0 else "proposal",
                                  "transition": evaluation, "panel_index": "", "slot": 0,
                                  "arrival_seed": seed})
        else:
            for slot, seed in enumerate(seed_plan["shared_panel_seeds"][0]):
                call_rows.append({**run, "logical_stage": "initial", "transition": 0,
                                  "panel_index": 0, "slot": slot, "arrival_seed": seed})
            for transition in range(1, TRANSITIONS + 1):
                panel_index = (transition - 1) // BLOCK_SIZE
                if transition > 1 and (transition - 1) % BLOCK_SIZE == 0:
                    for slot, seed in enumerate(seed_plan["shared_panel_seeds"][panel_index]):
                        call_rows.append({**run, "logical_stage": "panel_switch_current",
                                          "transition": transition, "panel_index": panel_index,
                                          "slot": slot, "arrival_seed": seed})
                for slot, seed in enumerate(seed_plan["shared_panel_seeds"][panel_index]):
                    call_rows.append({**run, "logical_stage": "proposal", "transition": transition,
                                      "panel_index": panel_index, "slot": slot, "arrival_seed": seed})
    if len(call_rows) != 6884:
        raise AssertionError(f"Expected 6884 optimization calls, found {len(call_rows)}")
    _write_csv(output / "optimization_call_plan.csv", call_rows)

    roles = ["starting"] + [f"replicate_{r}_{m}" for r in REPLICATES for m in METHODS]
    assessment_plan = []
    for label, case in CASES:
        for role in roles:
            method = "starting" if role == "starting" else role.rsplit("_", 1)[1]
            replicate = 0 if role == "starting" else int(role.split("_")[1])
            for item in assessment_rows:
                assessment_plan.append({
                    "cell_id": f"{case}_{role}_{item['seed']}", "case_label": label,
                    "case": case, "candidate_role": role, "replicate": replicate,
                    "method": method, "panel": item["panel"], "panel_index": item["panel_index"],
                    "seed": item["seed"], "arrival_seed": item["seed"], "runtime_seed": item["seed"],
                })
    if len(assessment_plan) != 200:
        raise AssertionError("Expected 200 assessment cells")
    _write_csv(output / "assessment_run_plan.csv", assessment_plan)

    provenance = {
        "phase2b_manifest": str(PHASE2B).replace("\\", "/"),
        "phase2b_manifest_sha256": _hash(root / PHASE2B),
        "phase2c_manifest": str(PHASE2C).replace("\\", "/"),
        "phase2c_manifest_sha256": _hash(root / PHASE2C),
        "phase3_experiment": str(PHASE3).replace("\\", "/"),
        "phase3_manifest_sha256": _hash(root / PHASE3 / "manifest.json"),
        "phase3b_experiment": str(PHASE3B).replace("\\", "/"),
        "phase3b_manifest_sha256": _hash(root / PHASE3B / "manifest.json"),
    }
    _write_json(output / "provenance_links.json", provenance)

    config = configparser.ConfigParser(); config.read(root / "configs/canonical_cost_source.ini")
    manifest = {
        "schema": 1, "phase": "3C", "status": "PREPARED_PENDING_SMOKE",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "primary_factor": "candidate_comparison_scenario_sharing",
        "methods": {"naive": "one fresh arrival per candidate", "shared3": "shared three-arrival panel per ten-transition block"},
        "repo_shas": lineage["phase3"]["repo_shas"],
        "v3_checkpoint_sha256": EXPECTED_CHECKPOINT,
        "normal_import": "peacsim.aqa_runtimepolicy.AQARuntimePolicy",
        "optimization_runtime_seed": OPTIMIZATION_RUNTIME_SEED,
        "settings": {
            "temperature": float(config["simulated_annealing"]["temperature"]),
            "cooling_rate": float(config["simulated_annealing"]["cooling_rate"]),
            "transitions": TRANSITIONS, "smart_weight": True, "domain": "argos_v3_physical",
            "shared_panel_size": PANEL_SIZE, "shared_block_size": BLOCK_SIZE, "shared_panels": PANELS,
        },
        "call_budget": {"naive_optimization": 1604, "shared3_optimization": 5280,
                        "optimization": 6884, "assessment": 200,
                        "nominal_scientific_total": 7084, "smoke_excluded": 18},
        "assessment_semantics": "fresh coupled arrival_seed == runtime_seed; fixed grid",
        "interpretation_boundary": "final pre-ARGOS SA methodology experiment",
    }
    _write_json(output / "manifest.json", manifest)

    source_contract = {
        "repo_shas": lineage["phase3"]["repo_shas"],
        "v3_checkpoint_sha256": EXPECTED_CHECKPOINT,
        "simulator_policy_contract": "normal_v3_argos_aqa",
        "normal_import": "peacsim.aqa_runtimepolicy.AQARuntimePolicy",
        "normal_source": ".deps/FlexDC/src/peacsim/aqa_runtimepolicy.py",
        "normal_source_sha256": sha(root / ".deps/FlexDC/src/peacsim/aqa_runtimepolicy.py"),
        "grid_path": spec["grid_path"], "grid_sha256": sha(root / spec["grid_path"]),
        "expected_grid_hash": lineage["phase3"]["phase2b"]["expected_grid_hash"],
        "phase3_source_contract_sha256": _hash(root / PHASE3 / "source_contract.json"),
        "phase3b_source_contract_sha256": _hash(root / PHASE3B / "source_contract.json"),
    }
    _write_json(output / "source_contract.json", source_contract)
    for relative in ["optimization", "assessment/cells", "assessment/requests", "smoke", "plots"]:
        (output / relative).mkdir(parents=True, exist_ok=True)
    return output


def freeze_contract(root: Path, experiment: Path) -> None:
    contract = _json(experiment / "source_contract.json")
    contract["phase3c_files"] = {name: sha(root / name) for name in PHASE3C_FILES}
    contract["reused_scientific_files"] = {name: sha(root / name) for name in REUSED_FILES}
    contract["frozen_plan_files"] = {name: sha(experiment / name) for name in FROZEN_PLAN_FILES}
    _write_json(experiment / "source_contract.json", contract)


def verify_frozen_contract(root: Path, experiment: Path) -> None:
    verify_lineage(root)
    contract = _json(experiment / "source_contract.json")
    for group, base in [("phase3c_files", root), ("reused_scientific_files", root),
                        ("frozen_plan_files", experiment)]:
        if not contract.get(group):
            raise ValueError("Phase 3C contract is not frozen: " + group)
        for name, digest in contract[group].items():
            if sha(base / name) != digest:
                raise ValueError(f"Frozen Phase 3C contract changed: {name}")

