"""Phase 3B orchestration: two new matched SA replicates and one fresh panel."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from argos.experimental_sa.paper_consistent.feasibility import assess
from argos.experimental_sa.paper_consistent.objective import ObjectiveContract
from argos.experimental_sa.phase3.engine import run_trajectory
from argos.experimental_sa.phase3.evaluator import Phase3Evaluator
from argos.experimental_sa.phase3.runner import _context, _settings
from argos.experimental_sa.phase3.scenarios import (
    FixedArrivalScenarioPolicy,
    Scenario,
    VaryingArrivalScenarioPolicy,
    read_search_draws,
)

from .planning import (
    CASES,
    EVALUATIONS,
    METHODS,
    PHASE3,
    REPLICATES,
    TRANSITIONS,
    create_plan,
    verify_frozen_contract,
)
from .reporting import build_final_outputs, build_zip


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf8"))


def _write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf8")
    os.replace(temporary, path)


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf8") as stream:
        return list(csv.DictReader(stream))


def _write_csv_atomic(path: Path, rows: list[dict]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _trajectory_parts(value: str) -> tuple[int, str, str]:
    replicate_name, trajectory = value.replace("\\", "/").split("/", 1)
    if replicate_name not in {"replicate_2", "replicate_3"}:
        raise ValueError("Only Replicates 2 and 3 are new Phase 3B trajectories")
    label, method = trajectory.split("_", 1)
    if label not in {"A", "B"} or method not in METHODS:
        raise ValueError("Unknown Phase 3B trajectory")
    return int(replicate_name.rsplit("_", 1)[1]), label, method


def run_named_trajectory(root: Path, experiment: Path, name: str) -> dict:
    replicate, label, method = _trajectory_parts(name)
    case_id = dict(CASES)[label]
    source, spec, case, jobs, domain = _context(root, experiment, case_id)
    reference = _read(experiment / "training_arrival_schedule_reference.json")
    schedule = [int(x) for x in reference["arrival_schedule"]]
    runtime_seed = int(reference["optimization_runtime_seed"])
    policy = (
        FixedArrivalScenarioPolicy(schedule[0], runtime_seed, EVALUATIONS)
        if method == "fixed"
        else VaryingArrivalScenarioPolicy(schedule, runtime_seed)
    )
    output = experiment / "optimization" / f"replicate_{replicate}" / f"{label}_{method}"
    evaluator = Phase3Evaluator(root, output, spec, case, source["expected_grid_hash"], method)
    draws = read_search_draws(
        experiment / "search_draw_schedule" / f"replicate_{replicate}" / f"{label}.csv"
    )
    settings = _settings(root, domain)
    result = run_trajectory(
        initial=(case["Pbar"], case["R"], *case["weights"]),
        domain=domain,
        evaluator=evaluator,
        contract=ObjectiveContract(root),
        job_names=list(jobs.all_jobs.values()),
        output=output,
        run_id=f"replicate_{replicate}_{label}_{method}",
        scenario_policy=policy,
        search_draws=draws,
        transitions=TRANSITIONS,
        **settings,
    )
    _write(output / "result.json", result.to_dict())
    return result.to_dict()


def _run_subprocess(command: list[str], log_path: Path) -> tuple[int, str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf8") as log:
        result = subprocess.run(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    return result.returncode, str(log_path)


def _load_iterations(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line]


def validate_optimization_invariants(root: Path, experiment: Path) -> None:
    reference = _read(experiment / "training_arrival_schedule_reference.json")
    schedule = [int(x) for x in reference["arrival_schedule"]]
    runtime_seed = int(reference["optimization_runtime_seed"])
    scientific = [
        "M_RSR",
        "p90",
        "Pj",
        "evidence_counts",
        "initial_job_table_hash",
        "grid_signal_hash",
        "target_trace_hash",
    ]
    all_draw_schedules = []
    for replicate in REPLICATES:
        for label, _case_id in CASES:
            fixed_path = experiment / "optimization" / f"replicate_{replicate}" / f"{label}_fixed"
            varying_path = experiment / "optimization" / f"replicate_{replicate}" / f"{label}_varying"
            fixed = _load_iterations(fixed_path / "iterations.jsonl")
            varying = _load_iterations(varying_path / "iterations.jsonl")
            if len(fixed) != EVALUATIONS or len(varying) != EVALUATIONS:
                raise ValueError("Incomplete Phase 3B optimization trajectory")
            if [x["iteration"] for x in fixed] != list(range(EVALUATIONS)):
                raise ValueError("Fixed trajectory iteration sequence changed")
            if [x["iteration"] for x in varying] != list(range(EVALUATIONS)):
                raise ValueError("Varying trajectory iteration sequence changed")
            if any(fixed[0]["raw"][key] != varying[0]["raw"][key] for key in scientific):
                raise ValueError(f"Replicate {replicate} {label} iteration-zero mismatch")
            if [x["search_draw"] for x in fixed] != [x["search_draw"] for x in varying]:
                raise ValueError("Matched fixed/varying search draws differ")
            planned_draws = read_search_draws(
                experiment / "search_draw_schedule" / f"replicate_{replicate}" / f"{label}.csv"
            )
            if [x["search_draw"] for x in fixed[1:]] != planned_draws:
                raise ValueError("Trajectory search draws differ from frozen schedule")
            all_draw_schedules.append(json.dumps(planned_draws, sort_keys=True))
            if [x["scenario"]["arrival_seed"] for x in varying] != schedule:
                raise ValueError("Varying trajectory did not reuse the Phase 3 schedule")
            if {x["scenario"]["arrival_seed"] for x in fixed} != {schedule[0]}:
                raise ValueError("Fixed trajectory did not reuse Phase 3 schedule[0]")
            if len({x["raw"]["initial_job_table_hash"] for x in fixed}) != 1:
                raise ValueError("Fixed trajectory initial jobs changed")
            if len({x["raw"]["initial_job_table_hash"] for x in varying}) != EVALUATIONS:
                raise ValueError("Varying trajectory lacks 401 distinct initial tables")
            for rows in [fixed, varying]:
                if {x["raw"]["runtime_seed"] for x in rows} != {runtime_seed}:
                    raise ValueError("Optimization runtime seed changed")
                if len({x["raw"]["grid_signal_hash"] for x in rows}) != 1:
                    raise ValueError("Grid hash changed within a trajectory")
                if any(x.get("retry_records") for x in rows):
                    retries = [y for x in rows for y in x.get("retry_records", [])]
                    if any(not item.get("same_scientific_identity", False) for item in retries):
                        raise ValueError("A retry changed scientific identity")
            for result_path in [fixed_path / "result.json", varying_path / "result.json"]:
                result = _read(result_path)
                if result["status"] == "EXECUTION_ERROR" or result["evaluations"] != EVALUATIONS:
                    raise ValueError("New Phase 3B trajectory did not complete")
    if len(set(all_draw_schedules)) != len(all_draw_schedules):
        raise ValueError("Replicate/case search schedules are not distinct")


def _candidate_from_result(result_path: Path, role: str, replicate: int, label: str, method: str) -> dict:
    result = _read(result_path)
    if result.get("best_feasible") is not None:
        item = result["best_feasible"]
        selection = "best_feasible"
        success = True
    else:
        item = result.get("best_violation")
        selection = "diagnostic_best_violation"
        success = False
    if item is None:
        raise ValueError("Trajectory has no predeclared assessable candidate: " + str(result_path))
    return {
        "case_label": label,
        "case": dict(CASES)[label],
        "candidate_role": role,
        "replicate": replicate,
        "method": method,
        "selection": selection,
        "sa_success": success,
        "optimization_candidate_id": item["candidate_id"],
        "Pbar": item["params"][0],
        "R": item["params"][1],
        "weights": json.dumps(item["params"][2:], separators=(",", ":")),
        "optimization_objective": item["objective"]["Cfull"],
        "source_path": str(result_path).replace("\\", "/"),
    }


def build_all_selected_candidates(root: Path, experiment: Path) -> list[dict]:
    rows = []
    phase3 = root / PHASE3
    phase3_selected = _read_csv(phase3 / "selected_candidates.csv")
    for label, case_id in CASES:
        source, _spec, case, _jobs, _domain = _context(root, experiment, case_id)
        rows.append(
            {
                "case_label": label,
                "case": case_id,
                "candidate_role": "starting",
                "replicate": 0,
                "method": "starting",
                "selection": "frozen_starting_candidate",
                "sa_success": True,
                "optimization_candidate_id": case["candidate_id"],
                "Pbar": case["Pbar"],
                "R": case["R"],
                "weights": json.dumps(case["weights"], separators=(",", ":")),
                "optimization_objective": "",
                "source_path": str(PHASE3).replace("\\", "/"),
            }
        )
        for method in METHODS:
            trajectory = f"{label}_{method}"
            saved = next(x for x in phase3_selected if x["trajectory"] == trajectory)
            rows.append(
                {
                    "case_label": label,
                    "case": case_id,
                    "candidate_role": f"replicate_1_{method}",
                    "replicate": 1,
                    "method": method,
                    "selection": saved["selection"],
                    "sa_success": saved["sa_success"].lower() == "true",
                    "optimization_candidate_id": saved["candidate_id"],
                    "Pbar": float(saved["Pbar"]),
                    "R": float(saved["R"]),
                    "weights": json.dumps(json.loads(saved["weights"]), separators=(",", ":")),
                    "optimization_objective": float(saved["optimization_objective"]),
                    "source_path": str(PHASE3 / "optimization" / trajectory / "result.json").replace("\\", "/"),
                }
            )
        for replicate in REPLICATES:
            for method in METHODS:
                result_path = experiment / "optimization" / f"replicate_{replicate}" / f"{label}_{method}" / "result.json"
                rows.append(
                    _candidate_from_result(
                        result_path,
                        f"replicate_{replicate}_{method}",
                        replicate,
                        label,
                        method,
                    )
                )
    if len(rows) != 14 or len({(x["case"], x["candidate_role"]) for x in rows}) != 14:
        raise ValueError("Expected seven unique candidate sources per workload")
    path = experiment / "all_selected_candidates.csv"
    if path.exists():
        existing = _read_csv(path)
        normalized = [{k: str(v) for k, v in row.items()} for row in rows]
        if existing != normalized:
            raise ValueError("Selected-candidate artifact changed on resume")
    else:
        _write_csv_atomic(path, rows)
    return rows


def build_assessment_requests(root: Path, experiment: Path, candidates: list[dict]) -> list[dict]:
    plan = _read_csv(experiment / "assessment_run_plan.csv")
    candidate_map = {(x["case"], x["candidate_role"]): x for x in candidates}
    requests = []
    for row in plan:
        candidate = candidate_map[(row["case"], row["candidate_role"])]
        requests.append(
            {
                **row,
                "selection": candidate["selection"],
                "sa_success": candidate["sa_success"],
                "params": json.dumps(
                    [candidate["Pbar"], candidate["R"], *json.loads(candidate["weights"])],
                    separators=(",", ":"),
                ),
                "optimization_candidate_id": candidate["optimization_candidate_id"],
            }
        )
    if len(requests) != 280:
        raise ValueError("Assessment request plan must contain 280 calls")
    return requests


def assessment_worker(root: Path, experiment: Path, request_path: Path) -> None:
    request = _read(request_path)
    output = experiment / "assessment" / "cells" / request["cell_id"]
    result_path = output / "result.json"
    if result_path.exists():
        existing = _read(result_path)
        if existing["cell_id"] != request["cell_id"] or int(existing["seed"]) != int(request["seed"]):
            raise ValueError("Existing assessment result conflicts with frozen request")
        return
    source, spec, case, jobs, _domain = _context(root, experiment, request["case"])
    seed = int(request["seed"])
    evaluator = Phase3Evaluator(root, output, spec, case, source["expected_grid_hash"], "varying")
    scenario = Scenario(0, seed, seed)
    response = evaluator(json.loads(request["params"]), 0, scenario)
    raw = response["raw"]
    objective = ObjectiveContract(root).evaluate(raw["M_RSR"], raw["p90"], raw["Pj"]).to_dict()
    feasibility = assess(raw, list(jobs.all_jobs.values()), objective["Cfull"])
    result = {
        **request,
        "params": json.loads(request["params"]),
        "raw": raw,
        "objective": objective,
        "feasibility": feasibility,
    }
    output.mkdir(parents=True, exist_ok=True)
    _write(result_path, result)
    evaluator.finalize_iteration(0, scenario, True)


def run_long(root: Path, experiment: Path, max_parallel_sa: int, assessment_workers: int) -> None:
    verify_frozen_contract(root, experiment)
    manifest = _read(experiment / "manifest.json")
    if manifest.get("status") not in {"READY_FOR_USER_RUN", "RUNNING", "COMPLETE"}:
        raise ValueError("Phase 3B experiment is not ready")
    if manifest["status"] == "COMPLETE":
        print(experiment)
        print(experiment.with_suffix(".zip"))
        return
    manifest["status"] = "RUNNING"
    _write(experiment / "manifest.json", manifest)
    names = [
        f"replicate_{replicate}/{label}_{method}"
        for replicate in REPLICATES
        for label, _case in CASES
        for method in METHODS
    ]
    commands = [
        [
            sys.executable,
            "-B",
            str(root / "scripts/run_phase3b_sa_repeatability.py"),
            "--experiment-dir",
            str(experiment),
            "--trajectory",
            name,
        ]
        for name in names
    ]
    with ThreadPoolExecutor(max_workers=max_parallel_sa) as pool:
        futures = {}
        for command, name in zip(commands, names, strict=True):
            replicate_name, trajectory = name.split("/", 1)
            log = experiment / "optimization" / replicate_name / trajectory / "trajectory.log"
            futures[pool.submit(_run_subprocess, command, log)] = name
        for future in as_completed(futures):
            code, log = future.result()
            if code:
                raise RuntimeError(f"Trajectory {futures[future]} failed; inspect {log}")
    validate_optimization_invariants(root, experiment)
    candidates = build_all_selected_candidates(root, experiment)
    requests = build_assessment_requests(root, experiment, candidates)
    tasks = []
    request_dir = experiment / "assessment" / "requests"
    for request in requests:
        path = request_dir / f"{request['cell_id']}.json"
        if path.exists():
            if _read(path) != request:
                raise ValueError("Frozen assessment request changed on resume")
        else:
            _write(path, request)
        result_path = experiment / "assessment" / "cells" / request["cell_id"] / "result.json"
        if not result_path.exists():
            tasks.append(
                (
                    [
                        sys.executable,
                        "-B",
                        str(root / "scripts/run_phase3b_sa_repeatability.py"),
                        "--experiment-dir",
                        str(experiment),
                        "--assessment-worker",
                        str(path),
                    ],
                    request["cell_id"],
                )
            )
    with ThreadPoolExecutor(max_workers=assessment_workers) as pool:
        futures = {
            pool.submit(
                _run_subprocess,
                command,
                experiment / "assessment" / "cells" / cell / "assessment.log",
            ): cell
            for command, cell in tasks
        }
        for future in as_completed(futures):
            code, log = future.result()
            if code:
                raise RuntimeError(f"Assessment {futures[future]} failed; inspect {log}")
    build_final_outputs(root, experiment)
    manifest = _read(experiment / "manifest.json")
    manifest["status"] = "COMPLETE"
    manifest["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    _write(experiment / "manifest.json", manifest)
    build_final_outputs(root, experiment, rebuild_zip=True)
    print(experiment)
    print(experiment.with_suffix(".zip"))


def finalize_existing(root: Path, experiment: Path) -> None:
    verify_frozen_contract(root, experiment)
    validate_optimization_invariants(root, experiment)
    build_all_selected_candidates(root, experiment)
    results = list((experiment / "assessment" / "cells").glob("*/result.json"))
    if len(results) != 280:
        raise ValueError(f"Expected 280 completed assessment cells, found {len(results)}")
    build_final_outputs(root, experiment)
    manifest = _read(experiment / "manifest.json")
    manifest["status"] = "COMPLETE"
    manifest["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    _write(experiment / "manifest.json", manifest)
    build_zip(experiment)


def validate_prepared(root: Path, experiment: Path) -> None:
    verify_frozen_contract(root, experiment)
    plan = _read_csv(experiment / "optimization_run_plan.csv")
    assessment = _read_csv(experiment / "assessment_run_plan.csv")
    if len(plan) != 3208 or len(assessment) != 280:
        raise ValueError("Frozen call budget mismatch")
    if len([x for x in assessment if x["candidate_role"] == "starting"]) != 40:
        raise ValueError("Starting candidate is not planned exactly once per seed/workload")
    print(json.dumps({"status": "READY_FOR_USER_RUN", "optimization_cells": 3208, "assessment_cells": 280, "real_smoke_calls": 0}, indent=2))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Phase 3B repeatability of fixed-arrival versus varying-arrival SA"
    )
    parser.add_argument("--experiment-dir", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--finalize-only", action="store_true")
    parser.add_argument("--trajectory", help=argparse.SUPPRESS)
    parser.add_argument("--assessment-worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--max-parallel-sa", type=int, default=4)
    parser.add_argument("--assessment-workers", type=int, default=10)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[4]
    if args.prepare_only:
        print(create_plan(root, args.experiment_dir))
        return
    if not args.experiment_dir:
        parser.error("--experiment-dir is required unless creating a new plan")
    experiment = args.experiment_dir.resolve()
    if args.validate_only:
        validate_prepared(root, experiment)
    elif args.finalize_only:
        finalize_existing(root, experiment)
    elif args.trajectory:
        result = run_named_trajectory(root, experiment, args.trajectory)
        print(result["status"])
        if result["error"]:
            raise SystemExit(1)
    elif args.assessment_worker:
        assessment_worker(root, experiment, args.assessment_worker.resolve())
    else:
        if not 1 <= args.max_parallel_sa <= 4:
            parser.error("--max-parallel-sa must be in [1,4]")
        if not 1 <= args.assessment_workers <= 10:
            parser.error("--assessment-workers must be in [1,10]")
        run_long(root, experiment, args.max_parallel_sa, args.assessment_workers)

