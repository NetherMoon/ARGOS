"""Phase 3C preparation, shared-panel smoke, optimization, and assessment."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from argos.experimental_sa.paper_consistent.feasibility import assess
from argos.experimental_sa.paper_consistent.objective import ObjectiveContract
from argos.experimental_sa.phase3.engine import run_trajectory
from argos.experimental_sa.phase3.evaluator import Phase3Evaluator
from argos.experimental_sa.phase3.runner import _context, _settings
from argos.experimental_sa.phase3.scenarios import (
    Scenario,
    VaryingArrivalScenarioPolicy,
    read_search_draws,
)

from .engine import run_shared3_trajectory
from .evaluator import SharedPanelEvaluator
from .planning import (
    BLOCK_SIZE,
    CASES,
    METHODS,
    OPTIMIZATION_RUNTIME_SEED,
    REPLICATES,
    SHARED_CALLS_PER_TRAJECTORY,
    TRANSITIONS,
    create_plan,
    freeze_contract,
    verify_frozen_contract,
)
from .reporting import build_final_outputs


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf8"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf8")
    os.replace(temporary, path)


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf8") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _parts(name: str) -> tuple[int, str, str]:
    replicate_name, trajectory = name.replace("\\", "/").split("/", 1)
    replicate = int(replicate_name.rsplit("_", 1)[1])
    case, method = trajectory.rsplit("_", 1)
    if replicate not in REPLICATES or case not in {x[1] for x in CASES} or method not in METHODS:
        raise ValueError("Unknown Phase 3C trajectory")
    return replicate, case, method


def run_named_trajectory(root: Path, experiment: Path, name: str) -> dict:
    replicate, case_id, method = _parts(name)
    label = next(label for label, case in CASES if case == case_id)
    source, spec, case, jobs, domain = _context(root, experiment, case_id)
    seed_plan = _read(experiment / "seed_plan.json")
    draws = read_search_draws(
        experiment / f"search_draw_schedule/replicate_{replicate}/{label}.csv"
    )
    output = experiment / "optimization" / f"replicate_{replicate}" / f"{case_id}_{method}"
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if method == "naive":
        evaluator = Phase3Evaluator(
            root, output, spec, case, source["expected_grid_hash"], "varying"
        )
        policy = VaryingArrivalScenarioPolicy(
            seed_plan["naive_arrival_seeds"], OPTIMIZATION_RUNTIME_SEED
        )
        result_obj = run_trajectory(
            initial=(case["Pbar"], case["R"], *case["weights"]),
            domain=domain,
            evaluator=evaluator,
            contract=ObjectiveContract(root),
            job_names=list(jobs.all_jobs.values()),
            output=output,
            run_id=f"replicate_{replicate}_{case_id}_naive",
            scenario_policy=policy,
            search_draws=draws,
            transitions=TRANSITIONS,
            **_settings(root, domain),
        )
        result = result_obj.to_dict()
    else:
        evaluator = SharedPanelEvaluator(root, output, spec, case, source["expected_grid_hash"])
        result_obj = run_shared3_trajectory(
            initial=(case["Pbar"], case["R"], *case["weights"]),
            domain=domain,
            evaluator=evaluator,
            contract=ObjectiveContract(root),
            job_names=list(jobs.all_jobs.values()),
            output=output,
            run_id=f"replicate_{replicate}_{case_id}_shared3",
            panel_schedule=seed_plan["shared_panel_seeds"],
            runtime_seed=OPTIMIZATION_RUNTIME_SEED,
            search_draws=draws,
            transitions=TRANSITIONS,
            block_size=BLOCK_SIZE,
            **_settings(root, domain),
        )
        result = result_obj.to_dict()
    _write(output / "result.json", result)
    metadata_path = output / "trajectory_metadata.json"
    previous = _read(metadata_path) if metadata_path.exists() else {}
    metadata = {
        "trajectory": name,
        "method": method,
        "invocations": int(previous.get("invocations", 0)) + 1,
        "wall_clock_seconds_accumulated": float(previous.get("wall_clock_seconds_accumulated", 0.0))
        + (time.perf_counter() - started),
        "last_completed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": result["status"],
    }
    _write(metadata_path, metadata)
    return result


def run_smoke(root: Path, experiment: Path) -> dict:
    verify_frozen_contract(root, experiment)
    marker = experiment / "smoke/smoke_result.json"
    if marker.exists():
        value = _read(marker)
        if value.get("status") != "PASSED":
            raise ValueError("Existing smoke did not pass")
        return value
    source, spec, case, jobs, domain = _context(root, experiment, "c005")
    plan = _read(experiment / "seed_plan.json")
    draws = read_search_draws(experiment / "search_draw_schedule/smoke_A.csv")
    output = experiment / "smoke/shared3"
    evaluator = SharedPanelEvaluator(root, output, spec, case, source["expected_grid_hash"])
    common = dict(
        initial=(case["Pbar"], case["R"], *case["weights"]),
        domain=domain,
        evaluator=evaluator,
        contract=ObjectiveContract(root),
        job_names=list(jobs.all_jobs.values()),
        output=output,
        run_id="phase3c_real_smoke",
        runtime_seed=OPTIMIZATION_RUNTIME_SEED,
        block_size=2,
        **_settings(root, domain),
    )
    run_shared3_trajectory(
        panel_schedule=plan["smoke"]["panel_seeds"][:1],
        search_draws=draws[:2],
        transitions=2,
        **common,
    )
    result = run_shared3_trajectory(
        panel_schedule=plan["smoke"]["panel_seeds"], search_draws=draws, transitions=4, **common
    )
    rows = [json.loads(x) for x in (output / "iterations.jsonl").read_text().splitlines()]
    events = list((output / "panel_events").glob("*.json"))
    observations = [row["panel_evaluation"] for row in rows]
    observations += [_read(path)["current"] for path in events]
    scenario_rows = [x for panel in observations for x in panel["scenario_observations"]]
    accepted = [bool(x["accepted"]) for x in rows[1:]]
    summary = {
        "status": "PASSED",
        "real_flexdc_calls": result.simulator_calls,
        "performed_calls_across_resumed_invocations": 18,
        "transitions": 4,
        "blocks": 2,
        "panel_switches": len(events),
        "panel_evaluations": result.panel_evaluations,
        "scenario_observations_per_panel": sorted(
            {len(x["scenario_observations"]) for x in observations}
        ),
        "distinct_arrival_hashes": len({x["raw"]["initial_job_table_hash"] for x in scenario_rows}),
        "distinct_grid_hashes": len({x["raw"]["grid_signal_hash"] for x in scenario_rows}),
        "runtime_seeds": sorted({int(x["raw"]["runtime_seed"]) for x in scenario_rows}),
        "acceptance_decisions_recorded": len(accepted),
        "accepted_count": sum(accepted),
        "rejected_count": len(accepted) - sum(accepted),
        "resume_test": "first two transitions completed, then resumed at panel boundary through transition four",
        "panel_feasible_observations": sum(bool(x["panel_all_feasible"]) for x in observations),
    }
    if not (
        result.simulator_calls == 18
        and result.panel_evaluations == 6
        and len(events) == 1
        and summary["scenario_observations_per_panel"] == [3]
        and summary["distinct_arrival_hashes"] == 6
        and summary["distinct_grid_hashes"] == 1
        and summary["runtime_seeds"] == [OPTIMIZATION_RUNTIME_SEED]
    ):
        summary["status"] = "FAILED"
        _write(marker, summary)
        raise RuntimeError("Phase 3C real S3 smoke invariants failed")
    _write(marker, summary)
    manifest = _read(experiment / "manifest.json")
    manifest["status"] = "READY_FOR_USER_RUN"
    manifest["smoke"] = summary
    manifest["smoke_completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    _write(experiment / "manifest.json", manifest)
    return summary


def validate_optimization(root: Path, experiment: Path) -> None:
    plan = _read(experiment / "seed_plan.json")
    for replicate in REPLICATES:
        for label, case in CASES:
            paths = {
                m: experiment / f"optimization/replicate_{replicate}/{case}_{m}" for m in METHODS
            }
            naive = [
                json.loads(x)
                for x in (paths["naive"] / "iterations.jsonl").read_text().splitlines()
            ]
            shared = [
                json.loads(x)
                for x in (paths["shared3"] / "iterations.jsonl").read_text().splitlines()
            ]
            if len(naive) != 401 or len(shared) != 401:
                raise ValueError("Incomplete Phase 3C trajectory")
            if [x["search_draw"] for x in naive[1:]] != [x["search_draw"] for x in shared[1:]]:
                raise ValueError("Matched N/S3 search draws differ")
            if [int(x["scenario"]["arrival_seed"]) for x in naive] != plan["naive_arrival_seeds"]:
                raise ValueError("Naive arrival schedule changed")
            if len({x["raw"]["initial_job_table_hash"] for x in naive}) != 401:
                raise ValueError("Naive trajectory lacks 401 arrival hashes")
            shared_observations = [x["panel_evaluation"] for x in shared]
            event_paths = sorted((paths["shared3"] / "panel_events").glob("*.json"))
            shared_observations += [_read(x)["current"] for x in event_paths]
            if len(event_paths) != 39 or len(shared_observations) != 440:
                raise ValueError("S3 panel/current reevaluation count changed")
            if any(len(x["scenario_observations"]) != 3 for x in shared_observations):
                raise ValueError("S3 panel does not have exactly three observations")
            hashes = {
                y["raw"]["initial_job_table_hash"]
                for x in shared_observations
                for y in x["scenario_observations"]
            }
            if len(hashes) != 120:
                raise ValueError("S3 does not contain 120 distinct arrival hashes")
            for row in shared:
                expected = plan["shared_panel_seeds"][int(row["panel_index"])]
                if (
                    row["panel_seeds"] != expected
                    or row["panel_evaluation"]["panel_seeds"] != expected
                ):
                    raise ValueError("S3 candidate comparison used the wrong shared panel")
            for method, path in paths.items():
                result = _read(path / "result.json")
                expected_calls = 401 if method == "naive" else SHARED_CALLS_PER_TRAJECTORY
                if (
                    result["status"] == "EXECUTION_ERROR"
                    or int(result["simulator_calls"]) != expected_calls
                ):
                    raise ValueError("Phase 3C trajectory result/call count mismatch")
            grids = {x["raw"]["grid_signal_hash"] for x in naive}
            grids |= {
                y["raw"]["grid_signal_hash"]
                for x in shared_observations
                for y in x["scenario_observations"]
            }
            runtimes = {int(x["raw"]["runtime_seed"]) for x in naive}
            runtimes |= {
                int(y["raw"]["runtime_seed"])
                for x in shared_observations
                for y in x["scenario_observations"]
            }
            if len(grids) != 1 or runtimes != {OPTIMIZATION_RUNTIME_SEED}:
                raise ValueError("Optimization fixed grid/runtime contract changed")


def _selected_from_result(path: Path, method: str) -> tuple[dict, str, bool]:
    result = _read(path)
    key = "best_feasible" if method == "naive" else "best_panel_feasible"
    if result.get(key):
        return result[key], key, True
    if not result.get("best_violation"):
        raise ValueError("Trajectory has no assessable diagnostic candidate")
    return result["best_violation"], "diagnostic_best_violation", False


def build_selected_candidates(root: Path, experiment: Path) -> list[dict]:
    rows = []
    for label, case_id in CASES:
        _source, _spec, case, _jobs, _domain = _context(root, experiment, case_id)
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
                "source_path": "Phase2B frozen starting candidate",
            }
        )
        for replicate in REPLICATES:
            for method in METHODS:
                path = (
                    experiment
                    / f"optimization/replicate_{replicate}/{case_id}_{method}/result.json"
                )
                item, selection, success = _selected_from_result(path, method)
                rows.append(
                    {
                        "case_label": label,
                        "case": case_id,
                        "candidate_role": f"replicate_{replicate}_{method}",
                        "replicate": replicate,
                        "method": method,
                        "selection": selection,
                        "sa_success": success,
                        "optimization_candidate_id": item["candidate_id"],
                        "Pbar": item["params"][0],
                        "R": item["params"][1],
                        "weights": json.dumps(item["params"][2:], separators=(",", ":")),
                        "optimization_objective": item.get(
                            "panel_mean_Cfull", item["objective"]["Cfull"]
                        ),
                        "source_path": str(path).replace("\\", "/"),
                    }
                )
    if len(rows) != 10:
        raise ValueError("Expected five assessed roles per workload")
    path = experiment / "selected_candidates.csv"
    if path.exists():
        if _read_csv(path) != [{k: str(v) for k, v in x.items()} for x in rows]:
            raise ValueError("Selected candidates changed on resume")
    else:
        _write_csv(path, rows)
    return rows


def build_assessment_requests(experiment: Path, candidates: list[dict]) -> list[dict]:
    candidate_map = {(x["case"], x["candidate_role"]): x for x in candidates}
    requests = []
    for row in _read_csv(experiment / "assessment_run_plan.csv"):
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
    if len(requests) != 200:
        raise ValueError("Assessment request count changed")
    return requests


def assessment_worker(root: Path, experiment: Path, request_path: Path) -> None:
    request = _read(request_path)
    output = experiment / "assessment/cells" / request["cell_id"]
    result_path = output / "result.json"
    if result_path.exists():
        if _read(result_path)["cell_id"] != request["cell_id"]:
            raise ValueError("Existing assessment result conflicts with request")
        return
    source, spec, case, jobs, _domain = _context(root, experiment, request["case"])
    seed = int(request["seed"])
    evaluator = Phase3Evaluator(root, output, spec, case, source["expected_grid_hash"], "varying")
    response = evaluator(json.loads(request["params"]), 0, Scenario(0, seed, seed))
    raw = response["raw"]
    objective = ObjectiveContract(root).evaluate(raw["M_RSR"], raw["p90"], raw["Pj"]).to_dict()
    result = {
        **request,
        "params": json.loads(request["params"]),
        "raw": raw,
        "objective": objective,
        "feasibility": assess(raw, list(jobs.all_jobs.values()), objective["Cfull"]),
    }
    _write(result_path, result)
    evaluator.finalize_iteration(0, Scenario(0, seed, seed), True)


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


def run_long(root: Path, experiment: Path, max_parallel_sa: int, assessment_workers: int) -> None:
    verify_frozen_contract(root, experiment)
    manifest = _read(experiment / "manifest.json")
    if manifest.get("status") not in {"READY_FOR_USER_RUN", "RUNNING", "COMPLETE"}:
        raise ValueError("Phase 3C smoke has not passed")
    if manifest["status"] == "COMPLETE":
        print(experiment)
        print(experiment.with_suffix(".zip"))
        return
    manifest["status"] = "RUNNING"
    _write(experiment / "manifest.json", manifest)
    names = [
        f"replicate_{r}/{case}_{method}"
        for r in REPLICATES
        for _label, case in CASES
        for method in METHODS
    ]
    commands = [
        [
            sys.executable,
            "-B",
            str(root / "scripts/run_phase3c_shared_scenario_final.py"),
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
            rep, trajectory = name.split("/", 1)
            log = experiment / "optimization" / rep / trajectory / "trajectory.log"
            futures[pool.submit(_run_subprocess, command, log)] = name
        for future in as_completed(futures):
            code, log = future.result()
            if code:
                raise RuntimeError(f"Trajectory {futures[future]} failed; inspect {log}")
    validate_optimization(root, experiment)
    candidates = build_selected_candidates(root, experiment)
    requests = build_assessment_requests(experiment, candidates)
    tasks = []
    for request in requests:
        path = experiment / "assessment/requests" / f"{request['cell_id']}.json"
        if path.exists() and _read(path) != request:
            raise ValueError("Assessment request changed on resume")
        if not path.exists():
            _write(path, request)
        if not (experiment / "assessment/cells" / request["cell_id"] / "result.json").exists():
            tasks.append(
                (
                    [
                        sys.executable,
                        "-B",
                        str(root / "scripts/run_phase3c_shared_scenario_final.py"),
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
                _run_subprocess, command, experiment / "assessment/cells" / cell / "assessment.log"
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


def validate_prepared(root: Path, experiment: Path) -> None:
    verify_frozen_contract(root, experiment)
    calls = _read_csv(experiment / "optimization_call_plan.csv")
    assessment = _read_csv(experiment / "assessment_run_plan.csv")
    result = {
        "status": _read(experiment / "manifest.json")["status"],
        "optimization_calls": len(calls),
        "naive_calls": sum(x["method"] == "naive" for x in calls),
        "shared3_calls": sum(x["method"] == "shared3" for x in calls),
        "assessment_cells": len(assessment),
    }
    if (
        result["optimization_calls"],
        result["naive_calls"],
        result["shared3_calls"],
        result["assessment_cells"],
    ) != (6884, 1604, 5280, 200):
        raise ValueError("Frozen Phase 3C call budget mismatch")
    print(json.dumps(result, indent=2))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Phase 3C naive versus shared three-scenario SA")
    parser.add_argument("--experiment-dir", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--trajectory", help=argparse.SUPPRESS)
    parser.add_argument("--assessment-worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--max-parallel-sa", type=int, default=4)
    parser.add_argument("--assessment-workers", type=int, default=10)
    parser.add_argument(
        "--acknowledge-shelved-execution",
        action="store_true",
        help="Explicitly acknowledge that Phase 3C is shelved for the current research direction",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[4]
    if args.prepare_only:
        path = create_plan(root, args.experiment_dir)
        freeze_contract(root, path)
        print(path)
        return
    if not args.experiment_dir:
        parser.error("--experiment-dir is required unless --prepare-only")
    experiment = args.experiment_dir.resolve()
    if args.smoke_only:
        print(json.dumps(run_smoke(root, experiment), indent=2))
    elif args.validate_only:
        validate_prepared(root, experiment)
    elif args.trajectory:
        result = run_named_trajectory(root, experiment, args.trajectory)
        print(result["status"])
        if result.get("error"):
            raise SystemExit(1)
    elif args.assessment_worker:
        assessment_worker(root, experiment, args.assessment_worker.resolve())
    else:
        if not args.acknowledge_shelved_execution:
            parser.error("Phase 3C is shelved; use the fixed-job-table ARGOS workflow")
        if not 1 <= args.max_parallel_sa <= 4:
            parser.error("--max-parallel-sa must be in [1,4]")
        if not 1 <= args.assessment_workers <= 10:
            parser.error("--assessment-workers must be in [1,10]")
        run_long(root, experiment, args.max_parallel_sa, args.assessment_workers)
