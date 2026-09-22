"""Frozen Phase 3B plan construction and provenance verification."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

from argos.diagnostics.workload_seed_forensics import sha
from argos.experimental_sa.phase3.planning import (
    EXPECTED_CHECKPOINT,
    EXPECTED_SHAS,
    PHASE2B,
    PHASE2C,
    collect_prior_seeds,
    verify_frozen_contract as verify_phase3_contract,
    verify_lineage,
)
from argos.experimental_sa.phase3.scenarios import UINT32_LIMIT, write_search_draws

PHASE3 = Path("runs/experiments/phase3_sa_arrival_uncertainty_20260919T192854_241405Z")
PHASE3_ARRIVAL_SCHEDULE_SHA256 = "464225850c667f6566da4719661d91e9f96cd0c007c6a8b012e7bad1430db349"
PHASE3B_ROOT_SEED = 20260921
TRANSITIONS = 400
EVALUATIONS = 401
REPLICATES = (2, 3)
CASES = (("A", "c005"), ("B", "c007"))
METHODS = ("fixed", "varying")

PHASE3B_CODE_FILES = [
    "src/argos/experimental_sa/phase3b/__init__.py",
    "src/argos/experimental_sa/phase3b/planning.py",
    "src/argos/experimental_sa/phase3b/runner.py",
    "src/argos/experimental_sa/phase3b/reporting.py",
    "scripts/run_phase3b_sa_repeatability.py",
    "tests/unit/test_phase3b_sa_repeatability.py",
    "docs/PHASE3B_SA_REPEATABILITY.md",
]
REUSED_SCIENTIFIC_FILES = [
    "src/argos/experimental_sa/phase3/engine.py",
    "src/argos/experimental_sa/phase3/evaluator.py",
    "src/argos/experimental_sa/phase3/scenarios.py",
    "src/argos/experimental_sa/paper_consistent/domain.py",
    "src/argos/experimental_sa/paper_consistent/evaluator.py",
    "src/argos/experimental_sa/paper_consistent/feasibility.py",
    "src/argos/experimental_sa/paper_consistent/objective.py",
    "scripts/run_experimental_sa.py",
]
FROZEN_PLAN_FILES = [
    "seed_plan.json",
    "search_seed_plan.csv",
    "replicate_plan.csv",
    "optimization_run_plan.csv",
    "training_arrival_schedule_reference.json",
    "assessment_seed_panel.csv",
    "assessment_panel_A.csv",
    "assessment_panel_B.csv",
    "assessment_run_plan.csv",
    "provenance_links.json",
    "search_draw_schedule/replicate_2/A.csv",
    "search_draw_schedule/replicate_2/B.csv",
    "search_draw_schedule/replicate_3/A.csv",
    "search_draw_schedule/replicate_3/B.csv",
]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf8"))


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf8")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_seed_values(value, key: str = "") -> set[int]:
    result: set[int] = set()
    if isinstance(value, dict):
        for name, child in value.items():
            result |= _collect_seed_values(child, name.lower())
    elif isinstance(value, list):
        for child in value:
            result |= _collect_seed_values(child, key)
    elif (
        "seed" in key
        and isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value < UINT32_LIMIT
    ):
        result.add(int(value))
    return result


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf8") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("Cannot write an empty frozen plan")
    with path.open("x", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _phase3_selected_consistent(phase3: Path) -> bool:
    rows = _read_csv(phase3 / "selected_candidates.csv")
    if len(rows) != 4:
        return False
    for row in rows:
        result = _json(phase3 / "optimization" / row["trajectory"] / "result.json")
        item = result["best_feasible"] or result["best_violation"]
        if item is None or item["candidate_id"] != row["candidate_id"]:
            return False
        if [float(row["Pbar"]), float(row["R"]), *json.loads(row["weights"])] != item["params"]:
            return False
    return True


def verify_phase3_provenance(root: Path) -> dict:
    shas, phase2b, phase2c = verify_lineage(root)
    phase3 = root / PHASE3
    manifest = _json(phase3 / "manifest.json")
    if manifest.get("status") != "COMPLETE":
        raise ValueError("Phase 3 is not complete")
    if manifest.get("repo_shas") != shas:
        raise ValueError("Phase 3 repository lineage mismatch")
    if manifest.get("primary_factor") != "workload_arrival_policy":
        raise ValueError("Unexpected Phase 3 primary factor")
    verify_phase3_contract(root, phase3)
    contract = _json(phase3 / "source_contract.json")
    if contract.get("simulator_policy_contract") != "normal_v3_argos_aqa":
        raise ValueError("Phase 3 did not use the normal AQA contract")
    if contract.get("normal_import") != "peacsim.aqa_runtimepolicy.AQARuntimePolicy":
        raise ValueError("Phase 3 normal AQA import mismatch")
    if contract.get("v3_checkpoint_sha256") != EXPECTED_CHECKPOINT:
        raise ValueError("Phase 3 V3 checkpoint mismatch")
    if _hash(phase3 / "arrival_schedule.csv") != PHASE3_ARRIVAL_SCHEDULE_SHA256:
        raise ValueError("Phase 3 arrival schedule hash mismatch")
    seed_plan = _json(phase3 / "seed_plan.json")
    schedule_rows = _read_csv(phase3 / "arrival_schedule.csv")
    schedule = [int(row["arrival_seed"]) for row in schedule_rows]
    if schedule != seed_plan["arrival_schedule"] or len(schedule) != EVALUATIONS:
        raise ValueError("Phase 3 arrival schedule contents mismatch")
    if len(set(schedule)) != EVALUATIONS:
        raise ValueError("Phase 3 varying-arrival schedule is not unique")
    if seed_plan["fixed_arrival_seed"] != schedule[0]:
        raise ValueError("Phase 3 fixed arrival seed mismatch")
    if int(seed_plan["training_runtime_seed"]) != 3609882979:
        raise ValueError("Phase 3 optimization runtime seed mismatch")
    if not _phase3_selected_consistent(phase3):
        raise ValueError("Phase 3 selected-candidate artifacts disagree")
    for trajectory in ["A_fixed", "A_varying", "B_fixed", "B_varying"]:
        iteration_path = phase3 / "optimization" / trajectory / "iterations.jsonl"
        if sum(1 for line in iteration_path.open(encoding="utf8") if line.strip()) != EVALUATIONS:
            raise ValueError("Incomplete Phase 3 trajectory: " + trajectory)
    return {
        "repo_shas": shas,
        "phase2b": phase2b,
        "phase2c": phase2c,
        "phase3_manifest": manifest,
        "phase3_contract": contract,
        "phase3_seed_plan": seed_plan,
        "arrival_schedule": schedule,
    }


def _draw_rows(rng: np.random.Generator, transitions: int = TRANSITIONS) -> list[dict]:
    rows = []
    for transition in range(1, transitions + 1):
        rows.append(
            {
                "iteration": transition,
                "p_standard_normal": float(rng.normal()),
                "r_standard_normal": float(rng.normal()),
                "weight_standard_normals": [float(x) for x in rng.normal(size=4)],
                "metropolis_uniform": float(rng.random()),
            }
        )
    return rows


def generate_replicate_search_draws(root_seed: int) -> dict[str, list[dict]]:
    """Generate independent A/B schedules from one frozen replicate root stream."""
    rng = np.random.default_rng(int(root_seed))
    return {"A": _draw_rows(rng), "B": _draw_rows(rng)}


def _generate_seed_plan(prior: set[int]) -> dict:
    rng = np.random.default_rng(PHASE3B_ROOT_SEED)
    used = set(int(x) for x in prior)

    def take(count: int) -> list[int]:
        values = []
        while len(values) < count:
            candidate = int(rng.integers(0, UINT32_LIMIT, dtype=np.uint32))
            if candidate not in used:
                used.add(candidate)
                values.append(candidate)
        return values

    search_roots = take(2)
    assessment = take(20)
    plan = {
        "schema": 1,
        "generator": "numpy.random.Generator(PCG64)",
        "root_seed": PHASE3B_ROOT_SEED,
        "selection_procedure": (
            "Draw uint32 values sequentially; reject every prior scientific seed and every "
            "earlier Phase 3B role value. The first two accepted values are replicate search "
            "roots; the next twenty form the assessment panel."
        ),
        "excluded_prior_seed_count": len(prior),
        "replicate_search_root_seeds": {
            "replicate_2": search_roots[0],
            "replicate_3": search_roots[1],
        },
        "assessment_seeds": assessment,
        "panel_A": assessment[:10],
        "panel_B": assessment[10:],
    }
    validate_seed_plan(plan, prior)
    return plan


def validate_seed_plan(plan: dict, prior: set[int]) -> None:
    roots = [int(x) for x in plan["replicate_search_root_seeds"].values()]
    assessment = [int(x) for x in plan["assessment_seeds"]]
    if len(roots) != 2 or len(set(roots)) != 2:
        raise ValueError("Expected two distinct search root seeds")
    if len(assessment) != 20 or len(set(assessment)) != 20:
        raise ValueError("Expected twenty unique assessment seeds")
    if plan["panel_A"] != assessment[:10] or plan["panel_B"] != assessment[10:]:
        raise ValueError("Assessment panel split changed")
    if (set(roots) | set(assessment)) & set(prior):
        raise ValueError("Phase 3B seed overlaps prior evidence")


def create_plan(root: Path, output: Path | None = None) -> Path:
    provenance = verify_phase3_provenance(root)
    phase3 = root / PHASE3
    prior = collect_prior_seeds(root) | _collect_seed_values(provenance["phase3_seed_plan"])
    seed_plan = _generate_seed_plan(prior)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = (output or root / "runs/experiments" / f"phase3b_sa_repeatability_{stamp}").resolve()
    output.mkdir(parents=True, exist_ok=False)
    _write_json(output / "seed_plan.json", seed_plan)

    schedule = provenance["arrival_schedule"]
    training_reference = {
        "phase3_experiment": str(PHASE3).replace("\\", "/"),
        "phase3_arrival_schedule_path": str(PHASE3 / "arrival_schedule.csv").replace("\\", "/"),
        "phase3_arrival_schedule_sha256": PHASE3_ARRIVAL_SCHEDULE_SHA256,
        "entry_count": len(schedule),
        "fixed_arrival_seed": schedule[0],
        "optimization_runtime_seed": provenance["phase3_seed_plan"]["training_runtime_seed"],
        "arrival_schedule": schedule,
    }
    _write_json(output / "training_arrival_schedule_reference.json", training_reference)

    search_rows = []
    schedule_hashes: dict[str, dict[str, str]] = {}
    for replicate in REPLICATES:
        replicate_name = f"replicate_{replicate}"
        root_seed = seed_plan["replicate_search_root_seeds"][replicate_name]
        draws = generate_replicate_search_draws(root_seed)
        schedule_hashes[replicate_name] = {}
        for label, _case_id in CASES:
            path = output / "search_draw_schedule" / replicate_name / f"{label}.csv"
            write_search_draws(path, draws[label])
            schedule_hashes[replicate_name][label] = _hash(path)
            search_rows.append(
                {
                    "replicate": replicate,
                    "case_label": label,
                    "search_root_seed": root_seed,
                    "derivation": "single PCG64 stream; A draws first, then B draws",
                    "search_draw_schedule": str(path.relative_to(output)).replace("\\", "/"),
                    "search_draw_schedule_sha256": schedule_hashes[replicate_name][label],
                }
            )
    _write_csv(output / "search_seed_plan.csv", search_rows)

    panel_rows = [
        {
            "combined_index": index,
            "panel": "A" if index <= 10 else "B",
            "panel_index": index if index <= 10 else index - 10,
            "seed": seed,
            "arrival_seed": seed,
            "runtime_seed": seed,
            "role": "INDEPENDENT_FRESH_COUPLED",
        }
        for index, seed in enumerate(seed_plan["assessment_seeds"], 1)
    ]
    _write_csv(output / "assessment_seed_panel.csv", panel_rows)
    _write_csv(output / "assessment_panel_A.csv", [x for x in panel_rows if x["panel"] == "A"])
    _write_csv(output / "assessment_panel_B.csv", [x for x in panel_rows if x["panel"] == "B"])

    phase3_search = provenance["phase3_seed_plan"]["search_seeds"]
    replicate_rows = []
    for replicate in (1, 2, 3):
        for label, case_id in CASES:
            for method in METHODS:
                if replicate == 1:
                    search_seed = phase3_search[label]
                    search_root = ""
                    schedule_path = str(PHASE3 / "search_draw_schedule" / f"{label}.csv").replace("\\", "/")
                    schedule_hash = _hash(root / schedule_path)
                    source = "historical_phase3_reused"
                else:
                    replicate_name = f"replicate_{replicate}"
                    search_seed = ""
                    search_root = seed_plan["replicate_search_root_seeds"][replicate_name]
                    schedule_path = f"search_draw_schedule/{replicate_name}/{label}.csv"
                    schedule_hash = schedule_hashes[replicate_name][label]
                    source = "new_phase3b"
                replicate_rows.append(
                    {
                        "replicate": replicate,
                        "case_label": label,
                        "case": case_id,
                        "method": method,
                        "source": source,
                        "search_seed_phase3": search_seed,
                        "search_root_seed_phase3b": search_root,
                        "search_draw_schedule": schedule_path,
                        "search_draw_schedule_sha256": schedule_hash,
                        "transitions": TRANSITIONS,
                        "nominal_evaluations": EVALUATIONS,
                        "runtime_seed": training_reference["optimization_runtime_seed"],
                        "arrival_policy": "phase3_schedule[0] repeated" if method == "fixed" else "phase3_schedule[i]",
                    }
                )
    _write_csv(output / "replicate_plan.csv", replicate_rows)

    optimization_cells = []
    for replicate in REPLICATES:
        for label, case_id in CASES:
            for method in METHODS:
                for iteration, arrival_seed in enumerate(schedule):
                    optimization_cells.append(
                        {
                            "replicate": replicate,
                            "case_label": label,
                            "case": case_id,
                            "method": method,
                            "trajectory": f"replicate_{replicate}/{label}_{method}",
                            "iteration": iteration,
                            "arrival_seed": schedule[0] if method == "fixed" else arrival_seed,
                            "runtime_seed": training_reference["optimization_runtime_seed"],
                            "search_draw_iteration": 0 if iteration == 0 else iteration,
                        }
                    )
    if len(optimization_cells) != 3208:
        raise AssertionError("Phase 3B optimization plan is not 3208 cells")
    _write_csv(output / "optimization_run_plan.csv", optimization_cells)

    candidate_roles = ["starting"] + [
        f"replicate_{replicate}_{method}"
        for replicate in (1, 2, 3)
        for method in METHODS
    ]
    assessment_cells = []
    for label, case_id in CASES:
        for role in candidate_roles:
            replicate = 0 if role == "starting" else int(role.split("_")[1])
            method = "starting" if role == "starting" else role.rsplit("_", 1)[1]
            for item in panel_rows:
                assessment_cells.append(
                    {
                        "cell_id": f"{label}_{role}_{item['seed']}",
                        "case_label": label,
                        "case": case_id,
                        "candidate_role": role,
                        "replicate": replicate,
                        "method": method,
                        "panel": item["panel"],
                        "panel_index": item["panel_index"],
                        "seed": item["seed"],
                        "arrival_seed": item["seed"],
                        "runtime_seed": item["seed"],
                    }
                )
    if len(assessment_cells) != 280 or len({x["cell_id"] for x in assessment_cells}) != 280:
        raise AssertionError("Phase 3B assessment plan is not 280 unique cells")
    _write_csv(output / "assessment_run_plan.csv", assessment_cells)

    provenance_links = {
        "phase2b_manifest": str(PHASE2B).replace("\\", "/"),
        "phase2b_manifest_sha256": _hash(root / PHASE2B),
        "phase2c_manifest": str(PHASE2C).replace("\\", "/"),
        "phase2c_manifest_sha256": _hash(root / PHASE2C),
        "phase3_experiment": str(PHASE3).replace("\\", "/"),
        "phase3_manifest_sha256": _hash(phase3 / "manifest.json"),
        "phase3_source_contract_sha256": _hash(phase3 / "source_contract.json"),
        "phase3_seed_plan_sha256": _hash(phase3 / "seed_plan.json"),
        "phase3_selected_candidates_sha256": _hash(phase3 / "selected_candidates.csv"),
        "phase3_arrival_schedule_sha256": PHASE3_ARRIVAL_SCHEDULE_SHA256,
    }
    _write_json(output / "provenance_links.json", provenance_links)

    for relative in ["optimization/replicate_2", "optimization/replicate_3", "assessment/cells", "assessment/requests", "plots"]:
        (output / relative).mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema": 1,
        "phase": "3B",
        "status": "READY_FOR_USER_RUN",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase3b_primary_factor": "sa_search_replicate",
        "replicate_1_source": str(PHASE3).replace("\\", "/"),
        "new_replicates": [2, 3],
        "matched_within_replicate": [
            "starting candidate",
            "search root and per-iteration draws",
            "training arrival schedule",
            "optimization runtime seed",
            "temperature schedule",
            "transition count",
            "domain",
            "grid",
            "objective and feasibility contracts",
        ],
        "only_changed_between_replicates": "SA search root/draw schedule",
        "repo_shas": provenance["repo_shas"],
        "simulator_policy_contract": "normal_v3_argos_aqa",
        "normal_import": "peacsim.aqa_runtimepolicy.AQARuntimePolicy",
        "v3_checkpoint_sha256": EXPECTED_CHECKPOINT,
        "settings": provenance["phase3_manifest"]["settings"],
        "training_arrival_schedule_sha256": PHASE3_ARRIVAL_SCHEDULE_SHA256,
        "optimization_runtime_seed": training_reference["optimization_runtime_seed"],
        "call_budget": {
            "new_optimization": 3208,
            "new_assessment": 280,
            "nominal_new_scientific_total": 3488,
            "replicate_1_optimization_reused": 1604,
            "setup_smoke_calls": 0,
        },
        "assessment_semantics": "fresh coupled arrival_seed == runtime_seed; fixed grid",
        "proposed_8_of_10_scenario_criterion": "diagnostic_only_not_official",
        "average_metric_feasible_definition": "mean p90 <= 0.30 and every mean Pj <= 0.10",
        "interpretation_limit": (
            "Repeatability across SA search trajectories under one fixed training-arrival "
            "schedule and one fixed optimization runtime seed."
        ),
    }
    _write_json(output / "manifest.json", manifest)

    contract = {
        "repo_shas": provenance["repo_shas"],
        "v3_checkpoint_sha256": EXPECTED_CHECKPOINT,
        "simulator_policy_contract": "normal_v3_argos_aqa",
        "normal_import": "peacsim.aqa_runtimepolicy.AQARuntimePolicy",
        "normal_source": ".deps/FlexDC/src/peacsim/aqa_runtimepolicy.py",
        "normal_source_sha256": sha(root / ".deps/FlexDC/src/peacsim/aqa_runtimepolicy.py"),
        "grid_path": provenance["phase3_contract"]["grid_path"],
        "grid_sha256": provenance["phase3_contract"]["grid_sha256"],
        "expected_grid_hash": provenance["phase3_contract"]["expected_grid_hash"],
        "phase3_arrival_schedule_sha256": PHASE3_ARRIVAL_SCHEDULE_SHA256,
        "phase3_source_contract_sha256": _hash(phase3 / "source_contract.json"),
        "phase3b_files": {name: sha(root / name) for name in PHASE3B_CODE_FILES},
        "reused_scientific_files": {name: sha(root / name) for name in REUSED_SCIENTIFIC_FILES},
        "frozen_plan_files": {name: sha(output / name) for name in FROZEN_PLAN_FILES},
    }
    _write_json(output / "source_contract.json", contract)
    return output


def verify_frozen_contract(root: Path, experiment: Path) -> None:
    verify_phase3_provenance(root)
    contract = _json(experiment / "source_contract.json")
    if contract.get("repo_shas") != EXPECTED_SHAS:
        raise ValueError("Phase 3B repository lineage mismatch")
    for group in ["phase3b_files", "reused_scientific_files"]:
        for name, digest in contract[group].items():
            if sha(root / name) != digest:
                raise ValueError(f"Frozen Phase 3B source changed: {name}")
    for name, digest in contract["frozen_plan_files"].items():
        if sha(experiment / name) != digest:
            raise ValueError(f"Frozen Phase 3B plan changed: {name}")
    reference = _json(experiment / "training_arrival_schedule_reference.json")
    if reference["phase3_arrival_schedule_sha256"] != PHASE3_ARRIVAL_SCHEDULE_SHA256:
        raise ValueError("Phase 3B schedule reference changed")

