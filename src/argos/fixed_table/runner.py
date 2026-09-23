"""Six independent fixed-job-table ARGOS searches and post-selection runtime checks."""

from __future__ import annotations

import argparse
import json
import shutil
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from argos.campaign.candidate_bank import get_bank, setup
from argos.campaign.identity import digest, immutable_json, verify_files
from argos.campaign.runner import campaign_lock
from argos.contracts import assessment, observation_rank, qualified
from argos.experimental_sa.paper_consistent.evaluator import prepare
from argos.fixed_table.protocol import (
    EPISODE_PLAN,
    GRID_TRACE_HASH,
    ROOT,
    SEED_PLAN,
    SOURCE_SPEC,
    WORKLOADS,
    config_for,
    load_plan,
    verify_environment,
)
from argos.fixed_table.simulator import FixedTableSimulator
from argos.provenance import git, read_json, sha256, write_json
from argos.search.regions import from_snapshot
from argos.types import candidate_from_dict, observation_from_dict
from argos.vnext.controller import NextController
from argos.vnext.device import V3Adapter
from argos.vnext.mechanisms import protected_elites

SOURCE_FILES = (
    "src/argos/fixed_table/__init__.py",
    "src/argos/fixed_table/protocol.py",
    "src/argos/fixed_table/planning.py",
    "src/argos/fixed_table/simulator.py",
    "src/argos/fixed_table/runner.py",
    "scripts/run_argos_fixed_job_table.py",
    "scripts/run_experimental_sa.py",
    "src/argos/config.py",
    "src/argos/contracts.py",
    "src/argos/types.py",
    "src/argos/search/candidates.py",
    "src/argos/search/regions.py",
    "src/argos/vnext/controller.py",
    "src/argos/vnext/mechanisms.py",
    "src/argos/vnext/correction.py",
    "src/argos/campaign/candidate_bank.py",
    "src/argos/experimental_sa/paper_consistent/evaluator.py",
    "src/argos/experimental_sa/paper_consistent/objective.py",
    "src/argos/experimental_sa/paper_consistent/feasibility.py",
    "src/argos/diagnostics/seed_factorization_worker.py",
    "src/argos/diagnostics/workload_seed_forensics.py",
    "src/argos/simulator/evidence.py",
    "src/argos/simulator/configuration.py",
    "src/argos/surrogate/v3_adapter.py",
    SEED_PLAN,
    EPISODE_PLAN,
    SOURCE_SPEC,
    "configs/canonical_cost_source.ini",
    "configs/v3_context_contract.json",
    "artifact_manifest.json",
)


def source_hashes(root: Path, seed_plan: str = SEED_PLAN, episode_plan: str = EPISODE_PLAN) -> dict:
    files = dict.fromkeys((*SOURCE_FILES, seed_plan, episode_plan))
    return {name: sha256(root / name) for name in files}


def new_experiment(
    root: Path,
    directory: Path,
    workers: int,
    seed_plan: str = SEED_PLAN,
    episode_plan: str = EPISODE_PLAN,
) -> dict:
    evidence = verify_environment(root, seed_plan, episode_plan)
    seeds, rows = load_plan(root, seed_plan, episode_plan)
    if directory.exists():
        manifest = read_json(directory / "manifest.json")
        if (
            manifest["source_hashes"] != source_hashes(root, seed_plan, episode_plan)
            or manifest.get("plan_paths") != {"seed_plan": seed_plan, "episode_plan": episode_plan}
            or manifest["seed_plan_sha256"] != sha256(root / seed_plan)
            or manifest["episode_plan_sha256"] != sha256(root / episode_plan)
            or manifest["checkpoint_sha256"] != evidence["checkpoint_sha256"]
            or manifest["artifact_manifest_sha256"] != evidence["artifact_manifest_sha256"]
            or manifest["dependency_shas"] != evidence["dependencies"]
            or manifest["repo_head"] != git(root, "rev-parse", "HEAD")
        ):
            raise ValueError("Fixed-table experiment source or plan changed on recovery")
        verify_files(directory, manifest["frozen_files"])
        return manifest
    directory.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(root / seed_plan, directory / "seed_plan.json")
    shutil.copyfile(root / episode_plan, directory / "episode_plan.csv")
    manifest = {
        "schema": 1,
        "mode": "ARGOS_FIXED_JOB_TABLE_SINGLE_SEARCH_RUNTIME_SEED",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "repo_head": git(root, "rev-parse", "HEAD"),
        "dependency_shas": evidence["dependencies"],
        "checkpoint_sha256": evidence["checkpoint_sha256"],
        "artifact_manifest_sha256": evidence["artifact_manifest_sha256"],
        "source_hashes": source_hashes(root, seed_plan, episode_plan),
        "plan_paths": {"seed_plan": seed_plan, "episode_plan": episode_plan},
        "seed_plan_sha256": sha256(root / seed_plan),
        "episode_plan_sha256": sha256(root / episode_plan),
        "frozen_files": {
            "seed_plan.json": sha256(directory / "seed_plan.json"),
            "episode_plan.csv": sha256(directory / "episode_plan.csv"),
        },
        "specification": evidence["spec"],
        "v3_contexts": evidence["v3_contexts"],
        "grid_trace_hash": GRID_TRACE_HASH,
        "budget": {
            "episodes": len(rows),
            "search_per_episode": 32,
            "final_checks_per_feasible_episode": 3,
            "max_search": 192,
            "max_final_checks": 18,
            "max_total": 210,
            "global_worker_limit": 10,
        },
        "v3": {
            "starts": 512,
            "iterations": 1500,
            "snapshot_every": 50,
            "bank_policy": "one immutable bank per workload context; separate search state per arrival table",
        },
        "seed_plan": seeds,
        "search_selection": "lowest measured canonical objective among valid evidence-qualified search observations",
        "final_checks": "three runtime-only seeds after frozen selection; excluded from search selection",
    }
    write_json(directory / "manifest.json", manifest)
    return manifest


def bank_for(
    root: Path,
    directory: Path,
    workload: str,
    seeds: dict,
    manifest: dict,
    adapter,
    workers: int,
    config_override=None,
):
    config = config_override or config_for(workload, seeds, workers)
    values = setup(adapter, root, config)
    _, _, _, _, domain, predictor = values
    identity = {
        "mode": "fixed_table_v3_bank_v1",
        "workload": workload,
        "workload_sha256": manifest["specification"]["files"][
            f".deps/FlexDC/configs/workload/{workload}.ini"
        ],
        "experiment_sha256": manifest["specification"]["files"][
            manifest["specification"]["experiment_path"]
        ],
        "cluster_sha256": manifest["specification"]["files"][
            manifest["specification"]["cluster_path"]
        ],
        "checkpoint": manifest["checkpoint_sha256"],
        "v3_context": manifest["v3_contexts"][workload],
        "candidate_seed": config.candidate_seed,
        "starts": config.starts,
        "iterations": config.iterations,
        "snapshot_every": config.snapshot_every,
        "weight_policy": config.weight_policy,
        "weight_bounds": list(config.weight_bounds(4)),
        "v3_sources": {
            name: manifest["source_hashes"][name]
            for name in (
                "src/argos/surrogate/v3_adapter.py",
                "src/argos/campaign/candidate_bank.py",
                "configs/v3_context_contract.json",
            )
        },
        "device": adapter.device_metadata,
    }
    # The historical N1000/U0.6 identity remains byte-for-byte compatible.
    # Other contexts need U in the key; N is already captured by experiment SHA.
    if (config.server_count, config.utilization) != (1000, 0.6):
        identity["mode"] = "fixed_table_v3_bank_v2"
        identity["server_count"] = config.server_count
        identity["utilization"] = config.utilization
    case = {"bank_id": digest(identity), "bank_identity": identity}
    bank, metadata, reused = get_bank(directory, case, adapter, config, values)
    bank_path = directory / "cache/v3_banks" / case["bank_id"] / metadata["completed_attempt"]
    frame = pd.read_csv(bank_path / "endpoints.csv")
    for column in ("weights", "Predicted_QoS_Probabilities"):
        frame[column] = frame[column].map(json.loads)
    frame["Iteration"] = config.iterations
    from dataclasses import replace

    endpoints = [
        replace(
            from_snapshot(row, config.iterations),
            provenance={
                "v3_selection_safe": bool(row["Safety_Both_Pass"]),
                "tracking_slack": float(row["Safety_Tracking_Slack"]),
                "qos_slack": float(row["Safety_QoS_Slack"]),
            },
        )
        for row in frame.to_dict("records")
    ]
    elites = protected_elites(bank[1], endpoints, domain)
    return config, domain, predictor, bank[0], elites, metadata, reused, case["bank_id"]


def episode_result(
    root: Path, directory: Path, row: dict, manifest: dict, bank_data, workers: int
) -> dict:
    workload, arrival_seed = row["workload"], int(row["arrival_seed"])
    config, domain, predictor, regions, elites, bank_meta, reused, bank_id = bank_data
    episode = directory / row["episode_path"]
    spec = manifest["specification"]
    case = spec["cases"][workload]
    started = time.perf_counter()
    if (episode / "fixed_context.json").exists():
        context = read_json(episode / "fixed_context.json")
        if (
            context["arrival_seed"] != arrival_seed
            or context["case"] != case
            or context["spec"] != spec
        ):
            raise ValueError("Episode fixed-table context changed")
    else:
        if episode.exists():
            raise RuntimeError("Incomplete initial table preparation requires review")
        context, _, _ = prepare(root, episode, spec, case, arrival_seed, GRID_TRACE_HASH)
    simulator = FixedTableSimulator(root, episode, config, context, workers)
    search_started = time.perf_counter()
    state = NextController(
        episode,
        config,
        domain,
        regions,
        simulator,
        predictor,
        elites,
        [],
        "ERT",
        fixed_table_single_seed=True,
    ).run()
    search_seconds = time.perf_counter() - search_started
    observations = [observation_from_dict(o) for o in state["observations"]]
    search = [o for o in observations if o.phase == "search"]
    valid_good = sorted(
        [o for o in search if qualified(o)],
        key=lambda o: (o.metrics.objective, o.candidate.candidate_id),
    )
    selected = candidate_from_dict(state["incumbent"]) if state["incumbent"] else None
    if selected and (not valid_good or selected != valid_good[0].candidate):
        raise ValueError("Controller selected a nonminimal feasible search bid")
    if not selected and valid_good:
        raise ValueError("Controller omitted a measured feasible bid")
    diagnostic = min(search, key=observation_rank) if search else None
    first_good = next((o for o in search if qualified(o)), None)
    initial_good = any(
        qualified(o) and o.batch == 1 and o.candidate.source != "independent" for o in search
    )
    initial_independent_good = any(
        qualified(o) and o.batch == 1 and o.candidate.source == "independent" for o in search
    )
    if state["phase"] == "ERROR":
        raise RuntimeError(f"Fixed-table search stopped on invalid evidence: {episode}")
    frozen = {
        "workload": workload,
        "arrival_seed": arrival_seed,
        "initial_job_table_hash": context["initial_job_table_hash"],
        "search_runtime_seed": config.search_seed,
        "status": "SEARCH_OBSERVED_FEASIBLE"
        if selected
        else "NO_FEASIBLE_BID_FOUND_WITHIN_SEARCH_BUDGET",
        "candidate": asdict(selected) if selected else None,
        "search_observation_id": valid_good[0].execution_id if selected else None,
        "best_violation_diagnostic": asdict(diagnostic) if not selected and diagnostic else None,
    }
    immutable_json(episode / "selection.json", frozen)
    checks = []
    check_started = time.perf_counter()
    if selected:
        with ThreadPoolExecutor(max_workers=min(3, workers)) as pool:
            futures = [
                pool.submit(simulator.evaluate_batch, [selected], seed, "confirmation", index)
                for index, seed in enumerate(config.confirmation_seeds, 1)
            ]
            checks = [future.result()[0] for future in futures]
        target = valid_good[0].reported["raw"]["target_trace_hash"]
        if any(o.valid and o.reported["raw"]["target_trace_hash"] != target for o in checks):
            raise ValueError("Selected bid power-target trace changed across runtime seeds")
    check_seconds = time.perf_counter() - check_started
    if any(not o.valid for o in checks):
        raise RuntimeError(f"Fixed-table runtime check has invalid evidence: {episode}")
    result = {
        "workload": workload,
        "server_count": int(row["server_count"]),
        "utilization": float(row["utilization"]),
        "arrival_seed": arrival_seed,
        "initial_job_table_hash": context["initial_job_table_hash"],
        "initial_file_sha256": context["initial_file_sha256"],
        "grid_signal_hash": GRID_TRACE_HASH,
        "search_runtime_seed": config.search_seed,
        "search_status": frozen["status"],
        "search_calls": simulator.search_attempts(),
        "search_observations": len(search),
        "qualified_candidates_total": len(valid_good),
        "first_feasible_call_number": search.index(first_good) + 1 if first_good else None,
        "first_feasible_candidate_id": first_good.candidate.candidate_id if first_good else None,
        "first_feasible_candidate_source": first_good.candidate.source if first_good else None,
        "initial_v3_guided_feasible": initial_good,
        "hybrid_contribution": (
            "INITIAL_V3_GUIDED_FEASIBLE"
            if initial_good
            else "INITIAL_INDEPENDENT_PROBE_FEASIBLE"
            if initial_independent_good
            else "ARGOS_REFINEMENT_FOUND_FEASIBILITY"
            if selected
            else "NO_FEASIBLE_WITHIN_32_CALLS"
        ),
        "selected_candidate_source": selected.source if selected else None,
        "selected_candidate_id": selected.candidate_id if selected else None,
        "Pbar": selected.Pbar if selected else None,
        "R": selected.R if selected else None,
        "weights": list(selected.weights) if selected else None,
        "search_p90": valid_good[0].metrics.p90 if selected else None,
        "search_Pj_by_job": dict(zip((j.section for j in simulator.jobs), valid_good[0].metrics.pj))
        if selected
        else None,
        "search_objective": valid_good[0].metrics.objective if selected else None,
        "search_objective_components": valid_good[0].reported["objective_components"]
        if selected
        else None,
        "runtime_checks_executed": len(checks),
        "runtime_checks_passed": sum(qualified(o) for o in checks),
        "runtime_check_failure_reasons": [assessment(o) for o in checks if not qualified(o)],
        "runtime_check_status": f"RUNTIME_CHECKS_{sum(qualified(o) for o in checks)}_OF_3_PASS"
        if selected
        else "RUNTIME_CHECKS_NOT_RUN",
        "v3_bank_id": bank_id,
        "v3_bank_generated_or_reused": "REUSED" if reused else "GENERATED",
        "v3_bank_seconds": bank_meta["wall_seconds"],
        "search_seconds": search_seconds,
        "runtime_check_seconds": check_seconds,
        "episode_seconds": time.perf_counter() - started,
        "best_violation_candidate_id": diagnostic.candidate.candidate_id if diagnostic else None,
        "best_violation": assessment(diagnostic)["worst_violation"] if diagnostic else None,
    }
    return result


def collect(directory: Path, rows: list[dict]) -> list[dict]:
    summaries, search_rows, selected_rows, check_rows = [], [], [], []
    for row in rows:
        episode = directory / row["episode_path"]
        if not (episode / "result.json").exists():
            continue
        result = read_json(episode / "result.json")
        summaries.append(result)
        selection = read_json(episode / "selection.json")
        selected_rows.append(
            {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in selection.items()}
        )
        state = read_json(episode / "vnext_state.json")
        for raw in state["observations"]:
            o = observation_from_dict(raw)
            item = {
                "workload": row["workload"],
                "arrival_seed": int(row["arrival_seed"]),
                "table_hash": result["initial_job_table_hash"],
                "runtime_seed": o.seed,
                "candidate_id": o.candidate.candidate_id,
                "candidate_source": o.candidate.source,
                "candidate_provenance": json.dumps(o.candidate.provenance),
                "Pbar": o.candidate.Pbar,
                "R": o.candidate.R,
                "weights": json.dumps(o.candidate.weights),
                "valid": o.valid,
                "status": o.status,
                "error": o.error,
                "p90": o.metrics.p90 if o.metrics else None,
                "Pj": json.dumps(o.metrics.pj) if o.metrics else None,
                "objective": o.metrics.objective if o.metrics else None,
                "objective_components": json.dumps(o.reported.get("objective_components")),
                "evidence_counts": json.dumps(assessment(o)["per_job_evidence_counts"]),
                "qualified_pass": qualified(o),
                "execution_id": o.execution_id,
                "grid_hash": o.reported.get("raw", {}).get("grid_signal_hash"),
                "target_hash": o.reported.get("raw", {}).get("target_trace_hash"),
            }
            search_rows.append(item)
        for index, seed in enumerate(
            read_json(directory / "seed_plan.json")["final_runtime_seeds"], 1
        ):
            cell = episode / "evaluations" / f"{32 + index:06d}" / "observation.json"
            if cell.exists():
                o = observation_from_dict(read_json(cell))
                check_rows.append(
                    {
                        "workload": row["workload"],
                        "arrival_seed": int(row["arrival_seed"]),
                        "runtime_seed": seed,
                        "candidate_id": o.candidate.candidate_id,
                        "p90": o.metrics.p90 if o.metrics else None,
                        "Pj": json.dumps(o.metrics.pj) if o.metrics else None,
                        "objective": o.metrics.objective if o.metrics else None,
                        "evidence_counts": json.dumps(assessment(o)["per_job_evidence_counts"]),
                        "qualified_pass": qualified(o),
                        "valid": o.valid,
                        "error": o.error,
                        "target_hash": o.reported.get("raw", {}).get("target_trace_hash"),
                    }
                )
    for name, data in (
        ("summary.csv", summaries),
        ("search_results.csv", search_rows),
        ("selected_candidates.csv", selected_rows),
        ("runtime_checks.csv", check_rows),
    ):
        if data:
            pd.DataFrame(data).to_csv(directory / name, index=False)
    lines = [
        "# Fixed-job-table ARGOS experiment",
        "",
        "Each arrival seed defines an independent optimization. All candidate evaluations within it reuse one initial job table and one search runtime seed. Final runtime checks occur after bid selection.",
        "",
        "| Workload | Arrival seed | Search result | Search calls | Search p90 | Search Bloom Pj | Search objective | Final runtime checks | Selected source |",
        "|---|---:|---|---:|---:|---:|---:|---|---|",
    ]

    def show(value):
        return "—" if value is None else f"{value:.6g}"

    for result in summaries:
        bloom = (result.get("search_Pj_by_job") or {}).get("Bloom.infer.4")
        lines.append(
            f"| {result['workload']} | {result['arrival_seed']} | {result['search_status']} | {result['search_calls']} | {show(result.get('search_p90'))} | {show(bloom)} | {show(result.get('search_objective'))} | {result['runtime_check_status']} | {result['selected_candidate_source'] or '—'} |"
        )
    lines.extend(
        [
            "",
            "A 3/3 result is three observed passes for one frozen table and bid; it is not a universal reliability guarantee.",
            "CPU timings are descriptive and are not a five-minute benchmark claim.",
            "",
        ]
    )
    (directory / "report.md").write_text("\n".join(lines), encoding="utf8")
    return summaries


def archive(directory: Path) -> Path:
    output = directory.with_suffix(".zip")
    temporary = output.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.name == ".campaign.lock" or path.suffix == ".tmp":
                continue
            relative = path.relative_to(directory)
            if relative.parts[0] == "cache" and path.name != "manifest.json":
                continue
            if "evaluations" in relative.parts and path.name not in {
                "request.json",
                "raw_result.json",
                "job_summary.csv",
                "qos_accounting.csv",
                "observation.json",
                "worker.log",
            }:
                continue
            z.write(path, relative.as_posix())
    temporary.replace(output)
    return output


def run(
    root: Path,
    directory: Path,
    workers: int,
    seed_plan: str = SEED_PLAN,
    episode_plan: str = EPISODE_PLAN,
) -> Path:
    if not 1 <= workers <= 10:
        raise ValueError("--max-workers must be in [1,10]")
    manifest = new_experiment(root, directory, workers, seed_plan, episode_plan)
    seeds, rows = load_plan(root, seed_plan, episode_plan)
    with campaign_lock(directory):
        adapter = None
        model_seconds = 0.0
        for workload in WORKLOADS:
            relevant = [r for r in rows if r["workload"] == workload]
            if all((directory / r["episode_path"] / "result.json").exists() for r in relevant):
                continue
            if adapter is None:
                started = time.perf_counter()
                adapter = V3Adapter(root, 4, "cpu")
                model_seconds = time.perf_counter() - started
                write_json(
                    directory / "model_timing.json",
                    {
                        "model_loading_setup_seconds": model_seconds,
                        "device": adapter.device_metadata,
                    },
                )
            bank_data = bank_for(root, directory, workload, seeds, manifest, adapter, workers)
            for index, row in enumerate(relevant):
                path = directory / row["episode_path"] / "result.json"
                if path.exists():
                    continue
                episode_bank = (*bank_data[:6], bank_data[6] or index > 0, bank_data[7])
                result = episode_result(root, directory, row, manifest, episode_bank, workers)
                result["model_loading_setup_seconds"] = model_seconds if index == 0 else 0.0
                result["total_seconds"] = (
                    result["episode_seconds"]
                    + (0.0 if episode_bank[6] else bank_data[5]["wall_seconds"])
                    + result["model_loading_setup_seconds"]
                )
                write_json(path, result)
                print(
                    f"{workload} arrival {row['arrival_seed']}: {result['search_status']}; {result['runtime_check_status']}",
                    flush=True,
                )
                collect(directory, rows)
        results = collect(directory, rows)
        if (
            len(results) != 6
            or sum(r["search_calls"] for r in results) > 192
            or sum(r["runtime_checks_executed"] for r in results) > 18
        ):
            raise ValueError("Incomplete or over-budget fixed-table experiment")
        path = archive(directory)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run six independent W2 ARGOS searches, each with one frozen FlexDC job table"
    )
    parser.add_argument(
        "--experiment-dir", type=Path, help="New or previously prepared result directory"
    )
    parser.add_argument(
        "--max-workers", type=int, default=10, help="Global FlexDC process cap (1–10)"
    )
    parser.add_argument(
        "--seed-plan", default=SEED_PLAN, help="Frozen repository-relative seed plan"
    )
    parser.add_argument(
        "--episode-plan", default=EPISODE_PLAN, help="Frozen repository-relative episode plan"
    )
    parser.add_argument(
        "--validate-plan",
        action="store_true",
        help="Check frozen inputs without running V3 or FlexDC",
    )
    args = parser.parse_args(argv)
    root = ROOT
    for label, name in (("seed plan", args.seed_plan), ("episode plan", args.episode_plan)):
        if Path(name).is_absolute() or ".." in Path(name).parts:
            parser.error(f"{label} must be repository-relative without parent traversal")
        path = (root / name).resolve()
        if not path.is_relative_to((root / "configs/fixed_table").resolve()) or not path.is_file():
            parser.error(f"{label} must be an existing file in configs/fixed_table")
    if args.validate_plan:
        evidence = verify_environment(root, args.seed_plan, args.episode_plan)
        seeds, rows = load_plan(root, args.seed_plan, args.episode_plan)
        print(
            json.dumps(
                {
                    "episodes": len(rows),
                    "arrival_seeds": seeds["arrival_seeds"],
                    "search_runtime_seed": seeds["search_runtime_seed"],
                    "final_runtime_seeds": seeds["final_runtime_seeds"],
                    "checkpoint": evidence["checkpoint_sha256"],
                },
                indent=2,
            )
        )
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    directory = (
        args.experiment_dir or root / "runs/experiments" / f"argos_fixed_job_table_{stamp}"
    ).resolve()
    if not directory.is_relative_to((root / "runs/experiments").resolve()):
        parser.error("Experiment directory must be inside runs/experiments")
    path = run(root, directory, args.max_workers, args.seed_plan, args.episode_plan)
    print(directory)
    print(path)


if __name__ == "__main__":
    main()
