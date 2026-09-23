"""Breadth validation of the unchanged fixed-table ARGOS method on original V3 contexts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import time
import zipfile
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from argos.campaign.identity import verify_files
from argos.campaign.runner import campaign_lock
from argos.config import Config
from argos.context import check_context
from argos.contracts import assessment, observation_rank, qualified
from argos.fixed_table.protocol import (
    CHECKPOINT_SHA,
    EXPECTED_DEPS,
    GRID_TRACE_HASH,
    ROOT,
    load_source,
)
from argos.fixed_table.protocol import (
    verify_environment as verify_w2_environment,
)
from argos.fixed_table.runner import SOURCE_FILES, archive, bank_for, episode_result
from argos.provenance import git, read_json, sha256, write_json
from argos.types import observation_from_dict
from argos.vnext.device import V3Adapter

WORKLOADS = (
    "W1-train-qos3333",
    "W1-train-qos4444",
    "W2-short-qos5_4.5_4_3.5",
    "W2-short-qos5555",
)
COUNTS = (250, 1000)
UTILIZATIONS = (0.6, 0.8)
SEED_PLAN = "configs/fixed_table/original16_seed_plan.json"
EPISODE_PLAN = "configs/fixed_table/original16_episode_plan.csv"
SOURCE_PLAN = "configs/fixed_table/original16_source.json"
PRIOR = "runs/experiments/argos_fixed_job_table_validation_20260923T024923Z"
HISTORICAL_BANKS = {
    "W2-short-qos5_4.5_4_3.5": "b0667ee062d81e3d2fedd1a1c3b6d3742b8211ca6ff9e4434f82af17f2ed76b1",
    "W2-short-qos5555": "b8be987c46d458d14a41f21ac414f7807cd2a9577105e43e535e634f431bc4bb",
}


def _paths(root: Path) -> tuple[Path, Path, Path]:
    return tuple(root / p for p in (SEED_PLAN, EPISODE_PLAN, SOURCE_PLAN))


def load_plan(root: Path = ROOT) -> tuple[dict, list[dict], dict]:
    seed_path, episode_path, source_path = _paths(root)
    seeds, source = read_json(seed_path), read_json(source_path)
    with episode_path.open(newline="", encoding="utf8") as stream:
        rows = list(csv.DictReader(stream))
    arrival = seeds["arrival_seed"]
    runtime = seeds["search_runtime_seed"]
    checks = seeds["final_runtime_seeds"]
    controllers = seeds["controller_seeds"]
    all_scientific = [arrival, runtime, *checks]
    if (
        len(checks) != 3
        or len(set(all_scientific)) != 5
        or any(type(s) is not int or not 0 <= s < 2**32 for s in all_scientific)
        or set(controllers) != set(WORKLOADS)
        or any(type(s) is not int or not 0 <= s < 2**32 for s in controllers.values())
        or len(rows) != 16
        or {(r["workload"], int(r["server_count"]), float(r["utilization"])) for r in rows}
        != {(w, n, u) for w in WORKLOADS for n in COUNTS for u in UTILIZATIONS}
    ):
        raise ValueError("Original-16 seed or context panel changed")
    for row in rows:
        w, n, u = row["workload"], int(row["server_count"]), float(row["utilization"])
        if (
            int(row["arrival_seed"]) != arrival
            or int(row["search_runtime_seed"]) != runtime
            or row["episode_path"] != f"{w}/N{n}_U{u:.1f}"
            or int(row["max_search_calls"]) != 32
            or int(row["max_final_checks"]) != 3
        ):
            raise ValueError("Original-16 episode row changed: " + str(row))
    for path, digest in source["files"].items():
        if sha256(root / path) != digest:
            raise ValueError("Original-16 frozen input changed: " + path)
    return seeds, rows, source


def config_for(row: dict, seeds: dict, workers: int) -> Config:
    w, n, u = row["workload"], int(row["server_count"]), float(row["utilization"])
    config = replace(
        Config(),
        workload=f"configs/workload/{w}.ini",
        experiment=(
            "configs/experiment/new_iso/traditional_signal/"
            f"generated_server_counts/exp_traditional_iso16_servers_{n}.ini"
        ),
        server_count=n,
        utilization=u,
        search_seed=seeds["search_runtime_seed"],
        candidate_seed=seeds["controller_seeds"][w],
        confirmation_seeds=tuple(seeds["final_runtime_seeds"]),
        max_workers=workers,
        max_wall_seconds=None,
    )
    config.validate()
    if (
        config.starts,
        config.iterations,
        config.snapshot_every,
        config.batch_size,
        config.max_search_batches,
        config.max_search_calls,
        config.independent_per_batch,
    ) != (512, 1500, 50, 8, 4, 32, 2):
        raise ValueError("Frozen V3 or 32-call search allocation changed")
    return config


def spec_for(root: Path, row: dict, source: dict) -> dict:
    old = load_source(root)
    w, n, u = row["workload"], int(row["server_count"]), float(row["utilization"])
    experiment = (
        ".deps/FlexDC/configs/experiment/new_iso/traditional_signal/"
        f"generated_server_counts/exp_traditional_iso16_servers_{n}.ini"
    )
    workload = f".deps/FlexDC/configs/workload/{w}.ini"
    if source["files"].get(experiment) != sha256(root / experiment):
        raise ValueError("Server-count experiment file not frozen")
    if source["files"].get(workload) != sha256(root / workload):
        raise ValueError("Workload file not frozen")
    spec = {k: v for k, v in old.items() if k != "cases"}
    spec["files"] = {**old["files"], **source["files"]}
    spec["fixed"] = {**old["fixed"], "N": n, "U": u}
    spec["experiment_path"] = experiment
    spec["cases"] = {w: {"workload": w, "workload_path": workload, "N": n, "U": u}}
    return spec


def verify_environment(root: Path = ROOT) -> dict:
    seeds, rows, source = load_plan(root)
    old = verify_w2_environment(root)
    if old["dependencies"] != EXPECTED_DEPS or old["checkpoint_sha256"] != CHECKPOINT_SHA:
        raise ValueError("Historical pinned dependencies or V3 checkpoint changed")
    contexts = {}
    for row in rows:
        config = config_for(row, seeds, 10)
        context = check_context(root, config)
        if context["context_ood"]:
            raise ValueError("Original V3 context unexpectedly outside contract")
        contexts[row["episode_path"]] = context
        spec = spec_for(root, row, source)
        if spec["policy"] != "AQA" or spec["policy_parameters"] != {"node_count_control": True}:
            raise ValueError("Normal AQA changed")
    return {
        "seed_plan": seeds,
        "rows": rows,
        "source": source,
        "dependencies": old["dependencies"],
        "checkpoint_sha256": CHECKPOINT_SHA,
        "artifact_manifest_sha256": old["artifact_manifest_sha256"],
        "v3_contexts": contexts,
    }


def source_hashes(root: Path) -> dict:
    names = set(SOURCE_FILES) | {
        "src/argos/fixed_table/original16.py",
        "scripts/run_argos_original16_fixed_table.py",
        SEED_PLAN,
        EPISODE_PLAN,
        SOURCE_PLAN,
    }
    return {name: sha256(root / name) for name in sorted(names)}


def new_experiment(root: Path, directory: Path, workers: int) -> dict:
    evidence = verify_environment(root)
    hashes = source_hashes(root)
    if directory.exists():
        manifest = read_json(directory / "manifest.json")
        if (
            manifest["repo_head"] != git(root, "rev-parse", "HEAD")
            or manifest["source_hashes"] != hashes
            or manifest["dependency_shas"] != evidence["dependencies"]
            or manifest["requested_workers"] != workers
        ):
            raise ValueError("Original-16 source changed; cannot resume scientific run")
        verify_files(directory, manifest["frozen_files"])
        return manifest
    directory.mkdir(parents=True, exist_ok=False)
    for source, name in zip(
        _paths(root), ("seed_plan.json", "episode_plan.csv", "source_plan.json")
    ):
        shutil.copyfile(source, directory / name)
    write_json(
        directory / "resolved_config.json",
        {
            "schema": 1,
            "mode": "ARGOS_ORIGINAL16_FIXED_TABLE_BREADTH_VALIDATION",
            "contexts": [
                {
                    "episode": row,
                    "config": asdict(config_for(row, evidence["seed_plan"], workers)),
                    "specification": spec_for(root, row, evidence["source"]),
                }
                for row in evidence["rows"]
            ],
        },
    )
    frozen = {
        name: sha256(directory / name)
        for name in (
            "seed_plan.json",
            "episode_plan.csv",
            "source_plan.json",
            "resolved_config.json",
        )
    }
    manifest = {
        "schema": 1,
        "mode": "ARGOS_ORIGINAL16_FIXED_TABLE_BREADTH_VALIDATION",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "repo_head": git(root, "rev-parse", "HEAD"),
        "dependency_shas": evidence["dependencies"],
        "checkpoint_sha256": evidence["checkpoint_sha256"],
        "artifact_manifest_sha256": evidence["artifact_manifest_sha256"],
        "source_hashes": hashes,
        "frozen_files": frozen,
        "seed_plan": evidence["seed_plan"],
        "v3_contexts": evidence["v3_contexts"],
        "grid_trace_hash": GRID_TRACE_HASH,
        "budget": {
            "episodes": 16,
            "search_per_episode": 32,
            "checks_per_selected": 3,
            "max_search": 512,
            "max_checks": 48,
            "max_total": 560,
            "global_worker_limit": 10,
        },
        "requested_workers": workers,
        "selection": "lowest measured canonical objective among evidence-qualified feasible search observations",
        "v3": {
            "starts": 512,
            "iterations": 1500,
            "snapshot_every": 50,
            "bank_policy": "one bank per workload/N/U; historical W2 N1000/U0.6 bank reusable only on exact identity",
        },
    }
    write_json(directory / "manifest.json", manifest)
    write_json(
        directory / "run_status.json", {"status": "PREPARED_NOT_RUN", "completed_episodes": 0}
    )
    return manifest


def import_historical_bank(root: Path, directory: Path, row: dict) -> dict | None:
    if (int(row["server_count"]), float(row["utilization"])) != (1000, 0.6):
        return None
    workload = row["workload"]
    if workload not in HISTORICAL_BANKS:
        return None
    bank_id = HISTORICAL_BANKS[workload]
    old = root / PRIOR / "cache/v3_banks" / bank_id
    if not (old / "manifest.json").is_file():
        raise FileNotFoundError("Historical W2 bank missing: " + str(old))
    from argos.campaign.identity import digest

    old_manifest = read_json(old / "manifest.json")
    if digest(old_manifest["identity"]) != bank_id:
        raise ValueError("Historical bank identity damaged")
    verify_files(old, old_manifest["files"])
    target = directory / "cache/v3_banks" / bank_id
    if not target.exists():
        shutil.copytree(old, target)
    verify_files(target, old_manifest["files"])
    return {
        "source": str(old.relative_to(root)).replace("\\", "/"),
        "bank_id": bank_id,
        "manifest_sha256": sha256(old / "manifest.json"),
        "status": "IMPORTED_VERIFIED_HISTORICAL_BANK",
    }


def _failure_examples(search) -> dict:
    valid = [o for o in search if o.valid and o.metrics]
    tracking = [o for o in valid if o.metrics.p90 <= 0.30]
    qos = [o for o in valid if all(p <= 0.10 for p in o.metrics.pj)]
    choices = {
        "closest_violation": min(valid, key=observation_rank) if valid else None,
        "best_tracking_pass_qos_fail": min(
            (o for o in tracking if o not in qos), key=lambda o: max(o.metrics.pj), default=None
        ),
        "best_qos_pass_tracking_fail": min(
            (o for o in qos if o not in tracking), key=lambda o: o.metrics.p90, default=None
        ),
    }
    return {
        name: (
            {
                "candidate_id": o.candidate.candidate_id,
                "source": o.candidate.source,
                "Pbar": o.candidate.Pbar,
                "R": o.candidate.R,
                "weights": list(o.candidate.weights),
                "p90": o.metrics.p90,
                "Pj": list(o.metrics.pj),
                "objective": o.metrics.objective,
            }
            if o
            else None
        )
        for name, o in choices.items()
    }


def collect(directory: Path, rows: list[dict], *, final: bool = False) -> list[dict]:
    summary, search_rows, selection_rows, check_rows, contexts = [], [], [], [], []
    for row in rows:
        episode = directory / row["episode_path"]
        result_path = episode / "result.json"
        if not result_path.is_file():
            continue
        result = read_json(result_path)
        state = read_json(episode / "vnext_state.json")
        search = [
            observation_from_dict(raw) for raw in state["observations"] if raw["phase"] == "search"
        ]
        if len(search) != 32 or result["search_calls"] != 32 or state["repeats"] != 0:
            raise ValueError("Original-16 search call or repeat contract violated")
        if any(
            o.reported.get("identity", {}).get("table_hash") != result["initial_job_table_hash"]
            or o.seed != result["search_runtime_seed"]
            or o.reported.get("raw", {}).get("grid_signal_hash") != GRID_TRACE_HASH
            for o in search
        ):
            raise ValueError("Search changed table, grid, or runtime seed")
        checks = []
        for index, seed in enumerate(
            read_json(directory / "seed_plan.json")["final_runtime_seeds"], 1
        ):
            path = episode / "evaluations" / f"{32 + index:06d}" / "observation.json"
            if path.exists():
                o = observation_from_dict(read_json(path))
                if (
                    o.reported.get("identity", {}).get("table_hash")
                    != result["initial_job_table_hash"]
                    or o.seed != seed
                    or o.reported.get("raw", {}).get("grid_signal_hash") != GRID_TRACE_HASH
                ):
                    raise ValueError("Final check changed table, grid, or runtime seed")
                checks.append(o)
                check_rows.append(
                    {
                        "context": row["episode_path"],
                        "workload": row["workload"],
                        "server_count": int(row["server_count"]),
                        "utilization": float(row["utilization"]),
                        "arrival_seed": int(row["arrival_seed"]),
                        "runtime_seed": seed,
                        "job_table_hash": result["initial_job_table_hash"],
                        "candidate_id": o.candidate.candidate_id,
                        "p90": o.metrics.p90 if o.metrics else None,
                        "Pj": json.dumps(o.metrics.pj) if o.metrics else None,
                        "objective": o.metrics.objective if o.metrics else None,
                        "evidence_counts": json.dumps(assessment(o)["per_job_evidence_counts"]),
                        "qualified_pass": qualified(o),
                        "assessment": json.dumps(assessment(o)),
                        "grid_hash": o.reported.get("raw", {}).get("grid_signal_hash"),
                        "target_hash": o.reported.get("raw", {}).get("target_trace_hash"),
                    }
                )
        if len(checks) != (3 if result["selected_candidate_id"] else 0):
            raise ValueError("Incomplete final runtime checks")
        selection = read_json(episode / "selection.json")
        selection_rows.append(
            {
                "context": row["episode_path"],
                **{
                    k: json.dumps(v) if isinstance(v, (dict, list)) else v
                    for k, v in selection.items()
                },
            }
        )
        for index, o in enumerate(search, 1):
            search_rows.append(
                {
                    "context": row["episode_path"],
                    "workload": row["workload"],
                    "server_count": int(row["server_count"]),
                    "utilization": float(row["utilization"]),
                    "arrival_seed": int(row["arrival_seed"]),
                    "job_table_hash": result["initial_job_table_hash"],
                    "grid_hash": o.reported.get("raw", {}).get("grid_signal_hash"),
                    "call_number": index,
                    "batch": o.batch,
                    "candidate_id": o.candidate.candidate_id,
                    "candidate_source": o.candidate.source,
                    "Pbar": o.candidate.Pbar,
                    "R": o.candidate.R,
                    "weights": json.dumps(o.candidate.weights),
                    "p90": o.metrics.p90 if o.metrics else None,
                    "Pj": json.dumps(o.metrics.pj) if o.metrics else None,
                    "objective": o.metrics.objective if o.metrics else None,
                    "evidence_counts": json.dumps(assessment(o)["per_job_evidence_counts"]),
                    "qualified_pass": qualified(o),
                    "valid": o.valid,
                    "source_prediction": json.dumps(o.candidate.prediction.__dict__)
                    if o.candidate.prediction
                    else None,
                }
            )
        if result["selected_candidate_id"]:
            selected = next(
                o for o in search if o.candidate.candidate_id == result["selected_candidate_id"]
            )
            if selected != min(
                (o for o in search if qualified(o)),
                key=lambda o: (o.metrics.objective, o.candidate.candidate_id),
            ):
                raise ValueError("Selected bid not lowest measured qualified objective")
        failure = _failure_examples(search) if not result["selected_candidate_id"] else None
        if failure:
            write_json(episode / "no_feasible_diagnostics.json", failure)
        summary.append(result)
        pj = result.get("search_Pj_by_job") or {}
        contexts.append(
            {
                "workload": row["workload"],
                "server_count": int(row["server_count"]),
                "utilization": float(row["utilization"]),
                "arrival_seed": int(row["arrival_seed"]),
                "job_table_hash": result["initial_job_table_hash"],
                "search_runtime_seed": result["search_runtime_seed"],
                "search_status": result["search_status"],
                "first_feasible_call_number": result["first_feasible_call_number"],
                "first_feasible_elapsed_seconds": None,
                "qualified_candidates_total": result["qualified_candidates_total"],
                "first_feasible_candidate_id": result["first_feasible_candidate_id"],
                "first_feasible_candidate_source": result["first_feasible_candidate_source"],
                "hybrid_contribution": result["hybrid_contribution"],
                "selected_candidate_id": result["selected_candidate_id"],
                "selected_candidate_source": result["selected_candidate_source"],
                "Pbar": result["Pbar"],
                "R": result["R"],
                "weights": json.dumps(result["weights"]),
                "search_p90": result["search_p90"],
                **{
                    f"search_Pj_{name}": next(
                        (
                            value
                            for key, value in pj.items()
                            if key.split(".")[0].lower() == name.lower()
                        ),
                        None,
                    )
                    for name in ("ResNet", "GPT2", "Llama", "Bloom")
                },
                "search_objective": result["search_objective"],
                "search_objective_components": json.dumps(result["search_objective_components"]),
                "runtime_checks_passed": result["runtime_checks_passed"],
                "runtime_checks_total": result["runtime_checks_executed"],
                "runtime_check_failures_by_constraint": json.dumps(
                    result["runtime_check_failure_reasons"]
                ),
                "v3_bank_generated_or_reused": result["v3_bank_generated_or_reused"],
                "v3_bank_seconds": result["v3_bank_seconds"],
                "search_seconds": result["search_seconds"],
                "simulator_search_seconds": state["timing"]["simulator_wall"],
                "runtime_check_seconds": result["runtime_check_seconds"],
                "total_seconds": result["total_seconds"],
                "max_workers": result["max_workers"],
            }
        )
    for name, data in (
        ("summary.csv", summary),
        ("search_results.csv", search_rows),
        ("selected_candidates.csv", selection_rows),
        ("runtime_checks.csv", check_rows),
        ("context_summary.csv", contexts),
        ("first_feasible_summary.csv", contexts),
        ("hybrid_contribution_summary.csv", contexts),
    ):
        if data:
            pd.DataFrame(data).to_csv(directory / name, index=False)
    if final:
        if (
            len(summary) != 16
            or sum(r["search_calls"] for r in summary) > 512
            or sum(r["runtime_checks_executed"] for r in summary) > 48
        ):
            raise ValueError("Incomplete or over-budget original-16 experiment")
        frame = pd.DataFrame(contexts)
        comparisons = []
        for n in COUNTS:
            for u in UTILIZATIONS:
                for family in ("W1", "W2"):
                    pair = [
                        r
                        for r in rows
                        if r["workload"].startswith(family + "-")
                        and int(r["server_count"]) == n
                        and float(r["utilization"]) == u
                    ]
                    if len(pair) != 2:
                        raise ValueError("Missing same-context workload pair")
                    fingerprints = []
                    for row in pair:
                        path = directory / row["episode_path"] / "initial_jobs.csv.gz"
                        arrivals = pd.read_csv(
                            path,
                            usecols=["job_id", "job_type_id", "arrival_time"],
                            float_precision="round_trip",
                        )
                        fingerprints.append(
                            hashlib.sha256(
                                arrivals.to_numpy(dtype="<f8").tobytes(order="C")
                            ).hexdigest()
                        )
                    comparisons.append(
                        {
                            "family": family,
                            "server_count": n,
                            "utilization": u,
                            "workload_a": pair[0]["workload"],
                            "workload_b": pair[1]["workload"],
                            "arrival_hash_a": fingerprints[0],
                            "arrival_hash_b": fingerprints[1],
                            "same_arrival_identity": fingerprints[0] == fingerprints[1],
                        }
                    )
        pd.DataFrame(comparisons).to_csv(
            directory / "same_seed_workload_arrival_comparison.csv", index=False
        )
        success = frame.search_status.eq("SEARCH_OBSERVED_FEASIBLE")
        calls = frame.first_feasible_call_number.dropna()
        lines = [
            "# Original 16-context fixed-table ARGOS breadth validation",
            "",
            "Each row is one separately frozen generated workload realization. Search used one fixed runtime seed and at most 32 FlexDC calls. Three final checks changed only runtime seed and never influenced selection.",
            "",
            frame.to_markdown(index=False),
            "",
            f"Search successes: {int(success.sum())}/16. Final runtime checks passed: {int(frame.runtime_checks_passed.sum())}/{int(frame.runtime_checks_total.sum())}.",
            "",
            "| Group | Search successes | Contexts |",
            "|---|---:|---:|",
        ]
        for col in ("workload", "server_count", "utilization"):
            for key, group in frame.groupby(col, sort=False):
                lines.append(
                    f"| {col}={key} | {int(group.search_status.eq('SEARCH_OBSERVED_FEASIBLE').sum())} | {len(group)} |"
                )
        lines += [
            "",
            f"Initial V3-guided feasible: {int(frame.hybrid_contribution.eq('INITIAL_V3_GUIDED_FEASIBLE').sum())}; initial independent probe feasible: {int(frame.hybrid_contribution.eq('INITIAL_INDEPENDENT_PROBE_FEASIBLE').sum())}; ARGOS adaptive refinement found feasibility: {int(frame.hybrid_contribution.eq('ARGOS_REFINEMENT_FOUND_FEASIBILITY').sum())}; none within 32: {int(frame.hybrid_contribution.eq('NO_FEASIBLE_WITHIN_32_CALLS').sum())}.",
            f"First feasible call among successes: min {calls.min()}, median {calls.median()}, mean {calls.mean()}, max {calls.max()}.",
            f"For the shared arrival seed, same-context workload pairs with identical arrival identities: {sum(r['same_arrival_identity'] for r in comparisons)}/8; see same_seed_workload_arrival_comparison.csv.",
            "",
            "W1 training workloads use a one-hour horizon; long-running jobs may be censored by this measurement contract.",
            "The unchanged controller records evaluation order but not per-batch elapsed time; first-feasible elapsed seconds is therefore unavailable.",
            "Three same-table runtime checks are observations, not certified reliability probabilities. CPU V3 timing is descriptive, not a GPU speed claim.",
            "",
        ]
        (directory / "report.md").write_text("\n".join(lines), encoding="utf8")
    return summary


def run(root: Path, directory: Path, workers: int) -> Path:
    if not 1 <= workers <= 10:
        raise ValueError("--max-workers must be in [1,10]")
    started = time.perf_counter()
    manifest = new_experiment(root, directory, workers)
    status = read_json(directory / "run_status.json")
    if status["status"] == "COMPLETED":
        output = directory.with_suffix(".zip")
        with zipfile.ZipFile(output) as zipped:
            if zipped.testzip() is not None or "context_summary.csv" not in zipped.namelist():
                raise ValueError("Completed original-16 archive failed integrity check")
        return output
    seeds, rows, source = load_plan(root)
    with campaign_lock(directory):
        adapter = None
        model_seconds = 0.0
        model_charge_pending = False
        try:
            for row in rows:
                result_path = directory / row["episode_path"] / "result.json"
                if result_path.exists():
                    continue
                write_json(
                    directory / "run_status.json",
                    {
                        "status": "RUNNING",
                        "completed_episodes": len(
                            [
                                r
                                for r in rows
                                if (directory / r["episode_path"] / "result.json").exists()
                            ]
                        ),
                    },
                )
                if adapter is None:
                    tick = time.perf_counter()
                    adapter = V3Adapter(root, 4, "cpu")
                    model_seconds = time.perf_counter() - tick
                    model_charge_pending = True
                    write_json(
                        directory / "model_timing.json",
                        {
                            "model_loading_setup_seconds": model_seconds,
                            "device": adapter.device_metadata,
                        },
                    )
                config = config_for(row, seeds, workers)
                spec = spec_for(root, row, source)
                per_manifest = {
                    **manifest,
                    "specification": spec,
                    "v3_contexts": {row["workload"]: manifest["v3_contexts"][row["episode_path"]]},
                }
                imported = import_historical_bank(root, directory, row)
                tick = time.perf_counter()
                bank = bank_for(
                    root, directory, row["workload"], seeds, per_manifest, adapter, workers, config
                )
                bank_seconds = time.perf_counter() - tick
                if imported and bank[7] != imported["bank_id"]:
                    raise ValueError(
                        "Historical W2 bank identity differs from current exact context"
                    )
                if imported and not bank[6]:
                    raise ValueError("Historical W2 bank was unexpectedly regenerated")
                result = episode_result(root, directory, row, per_manifest, bank, workers)
                if not result["selected_candidate_id"]:
                    result["search_status"] = "NO_FEASIBLE_BID_FOUND_WITHIN_32_CALLS"
                write_json(
                    directory / row["episode_path"] / "v3_bank_receipt.json",
                    {
                        "bank_id": bank[7],
                        "status": "REUSED" if bank[6] else "GENERATED",
                        "source_receipt": imported,
                        "manifest_sha256": sha256(
                            directory / "cache/v3_banks" / bank[7] / "manifest.json"
                        ),
                    },
                )
                result["v3_bank_seconds"] = bank_seconds
                result["model_loading_setup_seconds"] = (
                    model_seconds if model_charge_pending else 0.0
                )
                model_charge_pending = False
                result["max_workers"] = workers
                result["total_seconds"] = (
                    result["episode_seconds"] + bank_seconds + result["model_loading_setup_seconds"]
                )
                write_json(result_path, result)
                print(
                    f"{row['episode_path']}: {result['search_status']}; {result['runtime_check_status']}",
                    flush=True,
                )
                collect(directory, rows)
            collect(directory, rows, final=True)
            results = [read_json(directory / r["episode_path"] / "result.json") for r in rows]
            write_json(
                directory / "run_status.json",
                {
                    "status": "COMPLETED",
                    "completed_episodes": 16,
                    "search_calls": sum(r["search_calls"] for r in results),
                    "final_checks": sum(r["runtime_checks_executed"] for r in results),
                    "total_v3_bank_seconds": sum(r["v3_bank_seconds"] for r in results),
                    "generated_v3_bank_seconds": sum(
                        r["v3_bank_seconds"]
                        for r in results
                        if r["v3_bank_generated_or_reused"] == "GENERATED"
                    ),
                    "total_search_seconds": sum(r["search_seconds"] for r in results),
                    "total_runtime_check_seconds": sum(r["runtime_check_seconds"] for r in results),
                    "total_end_to_end_seconds": sum(r["total_seconds"] for r in results),
                    "current_invocation_wall_seconds": time.perf_counter() - started,
                },
            )
            output = archive(directory)
            with zipfile.ZipFile(output) as zipped:
                if zipped.testzip() is not None or not {
                    "manifest.json",
                    "run_status.json",
                    "report.md",
                    "context_summary.csv",
                }.issubset(zipped.namelist()):
                    raise ValueError("Final archive integrity check failed")
            return output
        except Exception as exc:
            write_json(
                directory / "run_status.json",
                {"status": "INCOMPLETE_REVIEW_REQUIRED", "error": f"{type(exc).__name__}: {exc}"},
            )
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run 16 original V3-supported contexts with the unchanged fixed-table ARGOS search"
    )
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        help="New or resumable result directory inside runs/experiments",
    )
    parser.add_argument(
        "--max-workers", type=int, default=10, help="Global FlexDC process cap (1–10)"
    )
    parser.add_argument(
        "--validate-plan",
        action="store_true",
        help="Validate frozen plan and pinned inputs without V3 or FlexDC calls",
    )
    args = parser.parse_args(argv)
    if args.validate_plan:
        evidence = verify_environment(ROOT)
        print(
            json.dumps(
                {
                    "contexts": len(evidence["rows"]),
                    "seeds": evidence["seed_plan"],
                    "checkpoint": evidence["checkpoint_sha256"],
                },
                indent=2,
            )
        )
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    directory = (
        args.experiment_dir or ROOT / "runs/experiments" / f"argos_original16_fixed_table_{stamp}"
    ).resolve()
    if not directory.is_relative_to((ROOT / "runs/experiments").resolve()):
        parser.error("Experiment directory must be inside runs/experiments")
    output = run(ROOT, directory, args.max_workers)
    print(directory)
    print(output)


if __name__ == "__main__":
    main()
