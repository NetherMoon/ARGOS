"""Phase 3 preparation, smoke, long trajectories, and independent assessment."""

from __future__ import annotations

import argparse
import configparser
import csv
import datetime as dt
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from argos.diagnostics.workload_seed_forensics import generate, load_generator, table_hash
from argos.experimental_sa.paper_consistent.domain import load_domain
from argos.experimental_sa.paper_consistent.feasibility import assess
from argos.experimental_sa.paper_consistent.objective import ObjectiveContract

from .engine import run_trajectory
from .evaluator import Phase3Evaluator
from .planning import (
    PHASE2B,
    accept_reporting_only_update,
    create_plan,
    freeze_code_and_plan_contract,
    verify_frozen_contract,
    verify_lineage,
)
from .reporting import build_final_outputs, build_zip
from .scenarios import (
    FixedArrivalScenarioPolicy,
    Scenario,
    VaryingArrivalScenarioPolicy,
    read_search_draws,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf8"))


def _write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf8")
    os.replace(temporary, path)


def _context(root: Path, experiment: Path, case_id: str):
    source = _read(root / PHASE2B)
    spec = source["specification"]
    case = next(x for x in spec["cases"] if x["case"] == case_id)
    _tables, Experiment, Jobs = load_generator(root)
    exp = Experiment(str(root / spec["experiment_path"]))
    exp._utilization = case["U"]
    jobs = Jobs(str(root / case["workload_path"]))
    domain = load_domain(root, "argos_v3_physical", jobs, exp)
    return source, spec, case, jobs, domain


def _settings(root: Path, domain) -> dict:
    config = configparser.ConfigParser()
    config.read(root / "configs/canonical_cost_source.ini")
    sa = config["simulated_annealing"]
    step = config["step_size"]
    return {
        "temperature": float(sa["temperature"]),
        "cooling_rate": float(sa["cooling_rate"]),
        "steps": (
            float(step["p_step"]) * domain.p_ratio_scale,
            float(step["r_step"]) * domain.r_ratio_scale,
            float(step["w_step"]),
        ),
        "smart_weight": sa.getboolean("smart_weight"),
    }


def run_named_trajectory(root: Path, experiment: Path, name: str, transitions: int = 400) -> dict:
    label, method = name.split("_", 1)
    case_id = {"A": "c005", "B": "c007"}[label]
    source, spec, case, jobs, domain = _context(root, experiment, case_id)
    seeds = _read(experiment / "seed_plan.json")
    schedule = seeds["arrival_schedule"][: transitions + 1]
    policy = (
        FixedArrivalScenarioPolicy(schedule[0], seeds["training_runtime_seed"], transitions + 1)
        if method == "fixed"
        else VaryingArrivalScenarioPolicy(schedule, seeds["training_runtime_seed"])
    )
    output = experiment / "optimization" / name
    evaluator = Phase3Evaluator(root, output, spec, case, source["expected_grid_hash"], method)
    draws = read_search_draws(experiment / "search_draw_schedule" / f"{label}.csv")[:transitions]
    settings = _settings(root, domain)
    result = run_trajectory(
        initial=(case["Pbar"], case["R"], *case["weights"]),
        domain=domain,
        evaluator=evaluator,
        contract=ObjectiveContract(root),
        job_names=list(jobs.all_jobs.values()),
        output=output,
        run_id=name,
        scenario_policy=policy,
        search_draws=draws,
        transitions=transitions,
        **settings,
    )
    _write(output / "result.json", result.to_dict())
    return result.to_dict()


def run_smoke(root: Path, experiment: Path) -> dict:
    marker = experiment / "smoke" / "smoke_result.json"
    if marker.exists():
        result = _read(marker)
        if result.get("status") == "PASSED":
            result = _repair_smoke_evidence(root, experiment, result)
            freeze_code_and_plan_contract(root, experiment)
            verify_frozen_contract(root, experiment)
            return result
        raise ValueError("Existing smoke did not pass")
    source, spec, case, jobs, domain = _context(root, experiment, "c007")
    seeds = _read(experiment / "seed_plan.json")["smoke"]
    draws = read_search_draws(experiment / "search_draw_schedule/smoke_B.csv")
    fixed_policy = FixedArrivalScenarioPolicy(
        seeds["arrival_schedule"][0], seeds["runtime_seed"], 6
    )
    varying_policy = VaryingArrivalScenarioPolicy(seeds["arrival_schedule"], seeds["runtime_seed"])
    settings = _settings(root, domain)
    results = {}
    for method, policy in [("fixed", fixed_policy), ("varying", varying_policy)]:
        output = experiment / "smoke" / method
        evaluator = Phase3Evaluator(root, output, spec, case, source["expected_grid_hash"], method)
        value = run_trajectory(
            initial=(case["Pbar"], case["R"], *case["weights"]),
            domain=domain,
            evaluator=evaluator,
            contract=ObjectiveContract(root),
            job_names=list(jobs.all_jobs.values()),
            output=output,
            run_id=f"smoke_B_{method}",
            scenario_policy=policy,
            search_draws=draws,
            transitions=5,
            **settings,
        )
        _write(output / "result.json", value.to_dict())
        if value.error or value.evaluations != 6:
            raise RuntimeError(f"{method} smoke failed: {value.error}")
        results[method] = value.to_dict()
    fixed_rows = [
        json.loads(x)
        for x in (experiment / "smoke/fixed/iterations.jsonl").read_text().splitlines()
    ]
    varying_rows = [
        json.loads(x)
        for x in (experiment / "smoke/varying/iterations.jsonl").read_text().splitlines()
    ]
    scientific = [
        "M_RSR",
        "p90",
        "Pj",
        "evidence_counts",
        "initial_job_table_hash",
        "grid_signal_hash",
        "target_trace_hash",
    ]
    parity = all(fixed_rows[0]["raw"][key] == varying_rows[0]["raw"][key] for key in scientific)
    fixed_hashes = {row["raw"]["initial_job_table_hash"] for row in fixed_rows}
    varying_hashes = {row["raw"]["initial_job_table_hash"] for row in varying_rows}
    grids = {row["raw"]["grid_signal_hash"] for row in fixed_rows + varying_rows}
    runtimes = {row["raw"]["runtime_seed"] for row in fixed_rows + varying_rows}
    summary = {
        "status": "PASSED"
        if parity
        and len(fixed_hashes) == 1
        and len(varying_hashes) == 6
        and len(grids) == 1
        and len(runtimes) == 1
        else "FAILED",
        "real_flexdc_calls": sum(x["simulator_calls"] for x in results.values()),
        "transitions_each": 5,
        "evaluations_each": 6,
        "iteration_0_scientific_parity": parity,
        "fixed_distinct_initial_hashes": len(fixed_hashes),
        "varying_distinct_initial_hashes": len(varying_hashes),
        "distinct_grid_hashes": len(grids),
        "distinct_runtime_seeds": len(runtimes),
        "runtime_seed": seeds["runtime_seed"],
        "fixed_hash": next(iter(fixed_hashes)),
        "varying_hashes": sorted(varying_hashes),
    }
    _write(marker, summary)
    if summary["status"] != "PASSED":
        raise RuntimeError("Real sequential Phase 3 smoke invariants failed")
    manifest = _read(experiment / "manifest.json")
    manifest["status"] = "READY_FOR_USER_RUN"
    manifest["smoke"] = summary
    manifest["smoke_completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    _write(experiment / "manifest.json", manifest)
    freeze_code_and_plan_contract(root, experiment)
    return summary


def _repair_smoke_evidence(root: Path, experiment: Path, summary: dict) -> dict:
    """Repair compact metadata only; never rerun a completed smoke simulator cell."""
    _source, spec, case, _jobs, _domain = _context(root, experiment, "c007")
    tables, Experiment, Jobs = load_generator(root)
    generated = {}
    total_rows = 0
    for method in ["fixed", "varying"]:
        trajectory = experiment / "smoke" / method
        rows = [
            json.loads(line) for line in (trajectory / "iterations.jsonl").read_text().splitlines()
        ]
        total_rows += len(rows)
        for row in rows:
            iteration = row["iteration"]
            raw_path = (
                trajectory
                / "fixed_initial_state/evaluations"
                / f"{iteration:06d}"
                / "raw_result.json"
                if method == "fixed"
                else trajectory
                / "initial_states"
                / f"{iteration:06d}"
                / "evaluations/000000/raw_result.json"
            )
            raw = _read(raw_path)
            seed = raw["arrival_seed"]
            if not raw.get("phase3_enriched"):
                if seed not in generated:
                    experiment_config = Experiment(str(root / spec["experiment_path"]))
                    experiment_config._utilization = case["U"]
                    jobs = Jobs(str(root / case["workload_path"]))
                    _trace, initial, prefill = generate(tables, experiment_config, jobs, seed)
                    if table_hash(initial) != raw["initial_job_table_hash"]:
                        raise ValueError("Smoke arrival regeneration hash mismatch")
                    generated[seed] = (initial, prefill)
                initial, prefill = generated[seed]
                summaries = []
                for job_id in range(len(case["weights"])):
                    all_mask = initial[1] == job_id
                    prefill_jobs = int((initial[1, :prefill] == job_id).sum())
                    later = initial[2, prefill:][initial[1, prefill:] == job_id]
                    summaries.append(
                        {
                            "job_type_id": job_id,
                            "total_jobs": int(all_mask.sum()),
                            "prefill_jobs": prefill_jobs,
                            "later_arrivals": len(later),
                            "min_later_arrival": None if len(later) == 0 else float(later.min()),
                            "max_later_arrival": None if len(later) == 0 else float(later.max()),
                            "mean_later_arrival": None if len(later) == 0 else float(later.mean()),
                        }
                    )
                raw["arrival_summary"] = summaries
                raw["simulator_policy_contract"] = "normal_v3_argos_aqa"
                raw["phase3_enriched"] = True
                _write(raw_path, raw)
            row["raw"] = raw
        temporary = trajectory / "iterations.jsonl.tmp"
        temporary.write_text(
            "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows),
            encoding="utf8",
        )
        os.replace(temporary, trajectory / "iterations.jsonl")
        items = {
            row["candidate_id"]: {
                "candidate_id": row["candidate_id"],
                "params": row["params"],
                "raw": row["raw"],
                "objective": row["objective"],
                "feasibility": row["feasibility"],
            }
            for row in rows
        }
        result_path = trajectory / "result.json"
        result = _read(result_path)
        for key in ["current", "best_scalar", "best_feasible", "best_violation"]:
            if result[key]:
                result[key] = items[result[key]["candidate_id"]]
        result["scientific_result"] = result["best_feasible"]
        result["simulator_calls"] = len(rows)
        _write(result_path, result)
        checkpoint_path = trajectory / "checkpoint.json"
        checkpoint = _read(checkpoint_path)
        for key in ["current", "best_scalar", "best_feasible", "best_violation"]:
            if checkpoint[key]:
                checkpoint[key] = items[checkpoint[key]["candidate_id"]]
        checkpoint["simulator_calls"] = len(rows)
        _write(checkpoint_path, checkpoint)
    if total_rows != 12:
        raise ValueError("Smoke evidence does not contain exactly 12 completed evaluations")
    summary["real_flexdc_calls"] = total_rows
    summary["metadata_repair"] = (
        "Call count and compact arrival summaries recovered from the 12 completed cells; "
        "no simulator rerun"
    )
    _write(experiment / "smoke/smoke_result.json", summary)
    manifest = _read(experiment / "manifest.json")
    manifest["smoke"] = summary
    _write(experiment / "manifest.json", manifest)
    return summary


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


def _selected(experiment: Path, case_label: str, method: str) -> dict:
    result = _read(experiment / "optimization" / f"{case_label}_{method}" / "result.json")
    if result["best_feasible"]:
        item = result["best_feasible"]
        selection = "best_feasible"
        successful = True
    else:
        item = result["best_violation"]
        selection = "best_violation_diagnostic"
        successful = False
    if item is None:
        raise ValueError(f"No assessable point for {case_label}_{method}")
    return {
        "candidate_source": f"{method}-SA",
        "selection": selection,
        "sa_success": successful,
        "params": item["params"],
        "optimization_candidate_id": item["candidate_id"],
    }


def build_assessment_plan(root: Path, experiment: Path) -> list[dict]:
    path = experiment / "assessment/run_plan.csv"
    if path.exists():
        with path.open(newline="", encoding="utf8") as stream:
            return list(csv.DictReader(stream))
    seeds = _read(experiment / "seed_plan.json")["assessment_seeds"]
    rows = []
    for label, case_id in [("A", "c005"), ("B", "c007")]:
        _source, _spec, case, _jobs, _domain = _context(root, experiment, case_id)
        candidates = [
            {
                "candidate_source": "starting",
                "selection": "frozen_starting_candidate",
                "sa_success": True,
                "params": [case["Pbar"], case["R"], *case["weights"]],
                "optimization_candidate_id": case["candidate_id"],
            },
            _selected(experiment, label, "fixed"),
            _selected(experiment, label, "varying"),
        ]
        for candidate in candidates:
            for seed in seeds:
                rows.append(
                    {
                        "cell_id": f"{label}_{candidate['candidate_source']}_{seed}",
                        "case_label": label,
                        "case": case_id,
                        "candidate_source": candidate["candidate_source"],
                        "selection": candidate["selection"],
                        "sa_success": candidate["sa_success"],
                        "params": json.dumps(candidate["params"], separators=(",", ":")),
                        "optimization_candidate_id": candidate["optimization_candidate_id"],
                        "seed": seed,
                    }
                )
    if len(rows) != 60 or len({x["cell_id"] for x in rows}) != 60:
        raise ValueError("Assessment plan must contain 60 unique calls")
    with path.open("x", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def assessment_worker(root: Path, experiment: Path, request_path: Path) -> None:
    request = _read(request_path)
    output = experiment / "assessment/cells" / request["cell_id"]
    result_path = output / "result.json"
    if result_path.exists():
        return
    source, spec, case, jobs, _domain = _context(root, experiment, request["case"])
    seed = int(request["seed"])
    evaluator = Phase3Evaluator(root, output, spec, case, source["expected_grid_hash"], "varying")
    scenario = Scenario(0, seed, seed)
    response = evaluator(json.loads(request["params"]), 0, scenario)
    raw = response["raw"]
    objective = ObjectiveContract(root).evaluate(raw["M_RSR"], raw["p90"], raw["Pj"]).to_dict()
    valid = assess(raw, list(jobs.all_jobs.values()), objective["Cfull"])
    result = {
        **request,
        "params": json.loads(request["params"]),
        "raw": raw,
        "objective": objective,
        "feasibility": valid,
    }
    output.mkdir(parents=True, exist_ok=True)
    _write(result_path, result)
    evaluator.finalize_iteration(0, scenario, True)


def run_long(root: Path, experiment: Path, max_parallel_sa: int, assessment_workers: int) -> None:
    verify_lineage(root)
    verify_frozen_contract(root, experiment)
    manifest = _read(experiment / "manifest.json")
    if manifest.get("status") not in {"READY_FOR_USER_RUN", "RUNNING", "COMPLETE"}:
        raise ValueError("Bounded real smoke has not passed")
    if manifest["status"] == "COMPLETE":
        print(experiment)
        return
    manifest["status"] = "RUNNING"
    _write(experiment / "manifest.json", manifest)
    names = ["A_fixed", "A_varying", "B_fixed", "B_varying"]
    commands = [
        [
            sys.executable,
            "-B",
            str(root / "scripts/run_phase3_sa_arrival_uncertainty.py"),
            "--experiment-dir",
            str(experiment),
            "--trajectory",
            name,
        ]
        for name in names
    ]
    with ThreadPoolExecutor(max_workers=max_parallel_sa) as pool:
        futures = {
            pool.submit(
                _run_subprocess, command, experiment / "optimization" / name / "trajectory.log"
            ): name
            for command, name in zip(commands, names, strict=True)
        }
        for future in as_completed(futures):
            code, log = future.result()
            if code:
                raise RuntimeError(f"Trajectory {futures[future]} failed; inspect {log}")
    results = [_read(experiment / "optimization" / name / "result.json") for name in names]
    if any(x["status"] == "EXECUTION_ERROR" for x in results):
        raise RuntimeError("At least one scientific trajectory aborted; assessment was not started")
    _validate_optimization_invariants(experiment)
    rows = build_assessment_plan(root, experiment)
    requests = experiment / "assessment/requests"
    requests.mkdir(exist_ok=True)
    tasks = []
    for row in rows:
        request = requests / f"{row['cell_id']}.json"
        if not request.exists():
            request.write_text(json.dumps(row, indent=2), encoding="utf8")
        result_path = experiment / "assessment/cells" / row["cell_id"] / "result.json"
        if not result_path.exists():
            command = [
                sys.executable,
                "-B",
                str(root / "scripts/run_phase3_sa_arrival_uncertainty.py"),
                "--experiment-dir",
                str(experiment),
                "--assessment-worker",
                str(request),
            ]
            tasks.append((command, row["cell_id"]))
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


def finalize_existing(root: Path, experiment: Path) -> None:
    """Reporting-only recovery after all scientific cells are complete."""
    verify_lineage(root)
    accept_reporting_only_update(root, experiment)
    verify_frozen_contract(root, experiment)
    _validate_optimization_invariants(experiment)
    result_paths = list((experiment / "assessment/cells").glob("*/result.json"))
    if len(result_paths) != 60:
        raise ValueError(f"Expected 60 completed assessment cells, found {len(result_paths)}")
    build_final_outputs(root, experiment)
    manifest = _read(experiment / "manifest.json")
    manifest["status"] = "COMPLETE"
    manifest["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest["reporting_recovery"] = (
        "Assessment case-label plot mapping corrected after all scientific calls completed; "
        "no simulator call was launched"
    )
    _write(experiment / "manifest.json", manifest)
    build_zip(experiment)
    print(experiment)
    print(experiment.with_suffix(".zip"))


def _validate_optimization_invariants(experiment: Path) -> None:
    seed_plan = _read(experiment / "seed_plan.json")
    scientific = [
        "M_RSR",
        "p90",
        "Pj",
        "evidence_counts",
        "initial_job_table_hash",
        "grid_signal_hash",
        "target_trace_hash",
    ]
    for case in ["A", "B"]:
        fixed = [
            json.loads(x)
            for x in (experiment / f"optimization/{case}_fixed/iterations.jsonl")
            .read_text()
            .splitlines()
        ]
        varying = [
            json.loads(x)
            for x in (experiment / f"optimization/{case}_varying/iterations.jsonl")
            .read_text()
            .splitlines()
        ]
        if len(fixed) != 401 or len(varying) != 401:
            raise ValueError("Optimization trajectory is not complete")
        if any(fixed[0]["raw"][key] != varying[0]["raw"][key] for key in scientific):
            raise ValueError(f"{case} iteration-zero pair mismatch")
        if len({x["raw"]["initial_job_table_hash"] for x in fixed}) != 1:
            raise ValueError(f"{case} fixed-arrival hash changed")
        if len({x["raw"]["initial_job_table_hash"] for x in varying}) != 401:
            raise ValueError(f"{case} varying arrivals did not produce 401 distinct tables")
        for rows in [fixed, varying]:
            if {x["raw"]["runtime_seed"] for x in rows} != {seed_plan["training_runtime_seed"]}:
                raise ValueError(f"{case} runtime seed changed")
            if len({x["raw"]["grid_signal_hash"] for x in rows}) != 1:
                raise ValueError(f"{case} grid hash changed")
        if [x["search_draw"] for x in fixed] != [x["search_draw"] for x in varying]:
            raise ValueError(f"{case} paired search draws differ")
        if [x["scenario"]["arrival_seed"] for x in varying] != seed_plan["arrival_schedule"]:
            raise ValueError(f"{case} varying schedule differs from frozen plan")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Phase 3 fixed-arrival versus arrival-uncertainty SA"
    )
    parser.add_argument("--experiment-dir", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--finalize-only", action="store_true")
    parser.add_argument("--trajectory", choices=["A_fixed", "A_varying", "B_fixed", "B_varying"])
    parser.add_argument("--assessment-worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--max-parallel-sa", type=int, default=4)
    parser.add_argument("--assessment-workers", type=int, default=10)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[4]
    if args.prepare_only:
        path = create_plan(root, args.experiment_dir)
        print(path)
        return
    if not args.experiment_dir:
        parser.error("--experiment-dir is required unless creating a new plan")
    experiment = args.experiment_dir.resolve()
    if args.smoke_only:
        print(json.dumps(run_smoke(root, experiment), indent=2))
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
