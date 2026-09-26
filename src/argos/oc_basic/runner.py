"""ARGOS-OC basic: V3 prescreening, measured ten-arrival search, held-out assessment."""

from __future__ import annotations

import argparse
import json
import numbers
import os
import platform
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from argos.campaign.identity import verify_files
from argos.contracts import QOS_LIMIT, TRACKING_LIMIT
from argos.diagnostics.seed_factorization_worker import JOB_COLUMNS
from argos.experimental_sa.paper_consistent.evaluator import FixedEvaluator, prepare
from argos.experimental_sa.paper_consistent.objective import ObjectiveContract
from argos.fixed_table.protocol import CHECKPOINT_SHA, EXPECTED_DEPS, GRID_TRACE_HASH, load_source
from argos.fixed_table.simulator import evidence_from_accounting
from argos.oc_basic.core import (
    ASSESSMENT_PAIRS,
    HARD_CALL_CAP,
    INITIAL_CANDIDATES,
    MAX_WORKERS,
    SEARCH_TABLES,
    SEARCH_TARGET,
    candidate_aggregate,
    choose_seeds,
    geometry,
    geometry_key,
    measured_rank,
    next_batch,
    result_status,
    select_final,
    select_initial,
)
from argos.provenance import ARTIFACT, CHECKPOINT, git, read_json, sha256
from argos.search.candidates import Domain
from argos.search.regions import from_snapshot
from argos.simulator.evidence import ordered_jobs
from argos.types import Candidate, Metrics, candidate_from_dict
from argos.vnext.device import V3Adapter

WORKLOAD = "W2-short-qos5_4.5_4_3.5"
OLD_EXPERIMENT = "runs/experiments/argos_original16_fixed_table_20260923T173830Z"
PHASE2B = "runs/diagnostics/w2_seed_characterization_10x3_20260919T165931_783442Z"
ORIGINAL16_SOURCE = "3c4949fc4a2694daa243f077073875b9ffb45e21"
ROOT_SEED_FILES = (
    "configs/campaigns/seed_ledger_v1.json",
    "configs/vnext/seed_ledger.json",
    "configs/diagnostics/w2_characterization_new_seed_panel.csv",
    "configs/diagnostics/w2_seed_historical_outcomes.csv",
    "configs/fixed_table/seed_plan.json",
    "configs/fixed_table/validation_seed_plan.json",
    "configs/fixed_table/original16_seed_plan.json",
    "runs/diagnostics/w2_seed_factorization_20260919T002931_161214Z/seed_panels.csv",
    "runs/diagnostics/w2_seed_characterization_10x3_20260919T165931_783442Z/new_seed_panel.csv",
    "runs/experiments/phase3_sa_arrival_uncertainty_20260919T192854_241405Z/assessment_seed_panel.csv",
    "runs/experiments/phase3b_sa_repeatability_20260920T013845_702021Z/assessment_seed_panel.csv",
    "runs/experiments/phase3c_shared_scenario_final_20260921T030010_482207Z/assessment_seed_panel.csv",
)
JOB_NAMES = ("ResNet", "GPT2", "Llama", "Bloom")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False, default=str), encoding="utf8")
    temp.replace(path)


def atomic_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    pd.DataFrame(rows).to_csv(temp, index=False)
    temp.replace(path)


def recursive_seed_values(value) -> set[int]:
    if isinstance(value, dict):
        return set().union(*(recursive_seed_values(v) for v in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(recursive_seed_values(v) for v in value)) if value else set()
    if isinstance(value, numbers.Integral) and not isinstance(value, bool) and 0 < value < 2**32:
        return {int(value)}
    if isinstance(value, str) and value.isdecimal():
        n = int(value)
        return {n} if 0 < n < 2**32 else set()
    return set()


def historical_seed_exclusions(root: Path) -> tuple[set[int], dict]:
    excluded: set[int] = set()
    hashes = {}
    for relative in ROOT_SEED_FILES:
        path = root / relative
        if not path.exists():
            raise FileNotFoundError(path)
        hashes[relative] = sha256(path)
        if path.suffix == ".json":
            excluded |= recursive_seed_values(read_json(path))
        else:
            excluded |= recursive_seed_values(pd.read_csv(path).to_dict("records"))
    old_plan = read_json(root / OLD_EXPERIMENT / "seed_plan.json")
    excluded |= recursive_seed_values(old_plan)
    return excluded, hashes


def phase2b_panel(root: Path) -> tuple[list[int], dict[int, str], dict]:
    base = root / PHASE2B
    if read_json(base / "manifest.json").get("status") == "FAILED":
        raise ValueError("Phase 2B did not complete")
    frame = pd.read_csv(base / "factorization_10x3_results.csv")
    frame = frame[(frame["case"] == "c005") & (frame["workload"] == WORKLOAD)]
    seeds = list(dict.fromkeys(int(s) for s in frame.arrival_seed))
    if len(seeds) != SEARCH_TABLES or len(frame) != 3 * SEARCH_TABLES:
        raise ValueError("Phase 2B ten-by-three source panel is incomplete")
    hashes = {}
    for seed in seeds:
        rows = frame[frame.arrival_seed == seed]
        identities = set(rows.initial_job_table_hash)
        if len(rows) != 3 or len(identities) != 1:
            raise ValueError("Phase 2B initial table identity is not fixed by arrival seed")
        hashes[seed] = identities.pop()
    return seeds, hashes, {
        "manifest_sha256": sha256(base / "manifest.json"),
        "factorization_csv_sha256": sha256(base / "factorization_10x3_results.csv"),
    }


def bank_source(root: Path) -> tuple[Path, dict]:
    receipt = read_json(root / OLD_EXPERIMENT / WORKLOAD / "N1000_U0.6" / "v3_bank_receipt.json")
    bank = root / receipt["source_receipt"]["source"]
    manifest = read_json(bank / "manifest.json")
    if sha256(bank / "manifest.json") != receipt["manifest_sha256"]:
        raise ValueError("Historical V3 bank receipt changed")
    if manifest["identity"]["checkpoint"] != CHECKPOINT_SHA or manifest["identity"]["workload"] != WORKLOAD:
        raise ValueError("Historical V3 bank is incompatible")
    verify_files(bank, manifest["files"])
    return bank, manifest


def preflight(root: Path, oc_source: Path) -> tuple[dict, dict, Path, dict, list[int], dict[int, str], dict]:
    if git(root, "rev-parse", "HEAD") != ORIGINAL16_SOURCE:
        raise ValueError("Frozen scientific root advanced; inspect before running")
    if git(oc_source, "rev-parse", "--abbrev-ref", "HEAD") != "ARGOS-OC":
        raise ValueError("OC source must run from ARGOS-OC branch")
    for name, expected in EXPECTED_DEPS.items():
        dep = root / ".deps" / name
        if git(dep, "rev-parse", "HEAD") != expected or git(dep, "status", "--porcelain"):
            raise ValueError(f"Pinned {name} dependency changed")
    if sha256(root / ARTIFACT / CHECKPOINT) != CHECKPOINT_SHA:
        raise ValueError("V3 checkpoint changed")
    frozen = read_json(root / OLD_EXPERIMENT / "manifest.json")
    if frozen["repo_head"] != ORIGINAL16_SOURCE:
        raise ValueError("Frozen ARGOS archive source changed")
    spec = load_source(root)
    bank, bank_manifest = bank_source(root)
    seeds, table_hashes, source_receipt = phase2b_panel(root)
    excluded, exclusion_hashes = historical_seed_exclusions(root)
    seed_plan = choose_seeds(excluded, seeds)
    if set(seed_plan["search_arrival_seeds"]) & {
        seed_plan["search_runtime_seed"],
        *(pair["arrival_seed"] for pair in seed_plan["assessment_pairs"]),
        *(pair["runtime_seed"] for pair in seed_plan["assessment_pairs"]),
    }:
        raise ValueError("OC search and assessment seed collision")
    source_receipt["seed_exclusion_files_sha256"] = exclusion_hashes
    return spec, frozen, bank, bank_manifest, seeds, table_hashes, {"seed_plan": seed_plan, "phase2b": source_receipt}


def table_statistics(path: Path, prefill: int) -> dict:
    frame = pd.read_csv(path, float_precision="round_trip")
    if list(frame.columns) != JOB_COLUMNS:
        raise ValueError("Frozen job-table schema changed")
    summary = {"total_jobs": len(frame), "prefill": prefill, "later_arrivals": len(frame) - prefill}
    for job_id, name in enumerate(JOB_NAMES):
        subset = frame[frame.job_type_id == job_id]
        summary[f"{name}_jobs"] = len(subset)
        summary[f"{name}_later_arrivals"] = int((subset.arrival_time > 0).sum())
    return summary


def ensure_search_tables(root: Path, output: Path, spec: dict, seed_plan: dict, expected_hashes: dict[int, str]) -> list[dict]:
    directory = output / "arrival_panel"
    directory.mkdir(exist_ok=True)
    rows = []
    case = spec["cases"][WORKLOAD]
    for seed in seed_plan["search_arrival_seeds"]:
        episode = directory / f"table_{seed}"
        if episode.exists():
            context = read_json(episode / "fixed_context.json")
        else:
            context, _, _ = prepare(root, episode, spec, case, seed, GRID_TRACE_HASH)
        if context["arrival_seed"] != seed or context["initial_job_table_hash"] != expected_hashes[seed]:
            raise ValueError("Newly frozen OC search table disagrees with Phase 2B historical hash")
        if sha256(episode / "initial_jobs.csv.gz") != context["initial_file_sha256"]:
            raise ValueError("OC frozen table file changed")
        rows.append({
            "arrival_seed": seed,
            "initial_job_table_hash": context["initial_job_table_hash"],
            "table_file_sha256": context["initial_file_sha256"],
            "grid_signal_hash": context["grid_signal_hash"],
            "context_path": str(episode / "fixed_context.json"),
            **table_statistics(episode / "initial_jobs.csv.gz", context["prefill"]),
        })
    atomic_csv(directory / "table_manifest.csv", rows)
    atomic_json(directory / "table_hashes.json", {str(r["arrival_seed"]): r["initial_job_table_hash"] for r in rows})
    return rows


def candidate_row(candidate: Candidate) -> dict:
    prediction = candidate.prediction
    return {
        "candidate_id": candidate.candidate_id,
        "source": candidate.source,
        "Pbar": candidate.Pbar,
        "R": candidate.R,
        "weights": json.dumps(candidate.weights),
        "geometry_key": geometry_key(candidate),
        "anchor": candidate.provenance.get("anchor"),
        "start_id": candidate.start_id,
        "iteration": candidate.iteration,
        "predicted_p90": prediction.p90 if prediction else None,
        "predicted_max_Pj": max(prediction.pj) if prediction else None,
        "predicted_objective": prediction.objective if prediction else None,
    }


def build_cloud(root: Path, output: Path, bank: Path, manifest: dict, _search_runtime_seed: int) -> tuple[list[Candidate], Domain, dict]:
    cloud_path = output / "v3" / "candidate_cloud.csv"
    timing_path = output / "v3" / "timing.json"
    domain = Domain(**manifest["domain"])
    if cloud_path.exists():
        frame = pd.read_csv(cloud_path)
        cloud = []
        for row in frame.to_dict("records"):
            cloud.append(Candidate(
                row["candidate_id"], float(row["Pbar"]), float(row["R"]),
                tuple(json.loads(row["weights"])), row["source"],
                prediction=Metrics(float(row["predicted_mean"]), float(row["predicted_p90"]),
                                   tuple(json.loads(row["predicted_Pj"])), float(row["predicted_objective"])),
            ))
        return cloud, domain, read_json(timing_path)
    (output / "v3").mkdir(exist_ok=True)
    started = time.monotonic()
    attempt = bank / manifest["completed_attempt"]
    snapshot_frame = pd.read_csv(attempt / "snapshots.csv")
    cloud = []
    for row in snapshot_frame.to_dict("records"):
        row["weights"] = json.loads(row["weights"])
        row["Predicted_QoS_Probabilities"] = json.loads(row["Predicted_QoS_Probabilities"])
        candidate = from_snapshot(row, int(manifest["identity"]["iterations"]))
        try:
            domain.validate(candidate)
        except ValueError:
            continue
        cloud.append(candidate)
    generation_seconds = time.monotonic() - started
    adapter_start = time.monotonic()
    adapter = V3Adapter(root, threads=2, device="auto")
    spec = load_source(root)
    bank_context_seed = read_json(root / OLD_EXPERIMENT / "seed_plan.json")["search_runtime_seed"]
    workload, experiment = adapter.context(
        root / spec["cases"][WORKLOAD]["workload_path"],
        root / spec["experiment_path"], 1000, 0.6, bank_context_seed,
    )
    model_load_seconds = time.monotonic() - adapter_start
    independent_start = time.monotonic()
    rng = np.random.default_rng(20260926)
    for i in range(256):
        candidate = domain.independent(rng, f"cloud-independent-{i:04d}")
        p = adapter.predict(workload, experiment, candidate.Pbar, candidate.R, list(candidate.weights))
        candidate = replace(candidate, prediction=Metrics(
            float(p["Predicted_Mean_Tracking"]), float(p["Predicted_P90_Tracking"]),
            tuple(float(x) for x in p["Predicted_QoS_Probabilities"]),
            float(p["Predicted_Full_Objective"]),
        ))
        cloud.append(candidate)
    scoring_seconds = time.monotonic() - independent_start
    rows = [{
        **candidate_row(c), "predicted_mean": c.prediction.mean_tracking,
        "predicted_Pj": json.dumps(c.prediction.pj),
    } for c in cloud]
    atomic_csv(cloud_path, rows)
    timing = {
        "bank_status": "REUSED_VERIFIED_HISTORICAL",
        "bank_path": str(bank),
        "bank_manifest_sha256": sha256(bank / "manifest.json"),
        "bank_original_generation_seconds": manifest["wall_seconds"],
        "bank_v3_context_seed": bank_context_seed,
        "cloud_snapshot_count": len(cloud) - 256,
        "cloud_independent_count": 256,
        "cloud_generation_seconds": generation_seconds,
        "v3_model_load_seconds": model_load_seconds,
        "v3_independent_scoring_seconds": scoring_seconds,
        "device": adapter.device_metadata,
    }
    atomic_json(timing_path, timing)
    return cloud, domain, timing


def parse_execution(root: Path, episode: Path, candidate: Candidate, number: int, runtime_seed: int, raw: dict, role: str) -> dict:
    context = read_json(episode / "fixed_context.json")
    cell = episode / "evaluations" / f"{number:06d}"
    if (
        raw.get("status") != "COMPLETE"
        or raw.get("runtime_seed") != runtime_seed
        or raw.get("arrival_seed") != context["arrival_seed"]
        or raw.get("initial_job_table_hash") != context["initial_job_table_hash"]
        or raw.get("grid_signal_hash") != GRID_TRACE_HASH
        or len(raw.get("Pj", [])) != 4
    ):
        raise ValueError(f"OC worker identity/output mismatch: {cell}")
    if len(raw.get("effective_policy_weights", [])) != len(candidate.weights) or any(
        abs(float(a) - float(b)) > 1e-9
        for a, b in zip(raw["effective_policy_weights"], candidate.weights)
    ):
        raise ValueError("OC worker effective weights differ from frozen complete candidate")
    jobs = ordered_jobs(root / context["case"]["workload_path"])
    evidence = evidence_from_accounting(cell / "qos_accounting.csv", jobs, raw["Pj"])
    counts = [e.observation_count for e in evidence]
    if counts != raw["evidence_counts"]:
        raise ValueError("OC worker QoS evidence count mismatch")
    objective = ObjectiveContract(root).evaluate(raw["M_RSR"], raw["p90"], raw["Pj"]).Cfull
    row = {
        "role": role,
        "candidate_id": candidate.candidate_id,
        "candidate_source": candidate.source,
        "geometry_key": geometry_key(candidate),
        "Pbar": candidate.Pbar,
        "R": candidate.R,
        "weights": json.dumps(candidate.weights),
        "arrival_seed": context["arrival_seed"],
        "runtime_seed": runtime_seed,
        "initial_job_table_hash": context["initial_job_table_hash"],
        "grid_signal_hash": raw["grid_signal_hash"],
        "target_trace_hash": raw["target_trace_hash"],
        "p90": float(raw["p90"]),
        "mean_tracking": float(raw["mean_tracking"]),
        "Pj": [float(x) for x in raw["Pj"]],
        "objective": objective,
        "evidence_counts": counts,
        "evidence_valid": all(n is not None and n >= 1 for n in counts),
        "execution_status": raw["status"],
        "elapsed_seconds": float(raw["elapsed_seconds"]),
        "cell_path": str(cell),
    }
    row["feasible"] = result_status(row)
    row["failure_constraints"] = ",".join(
        (["tracking"] if row["p90"] > TRACKING_LIMIT else [])
        + [name for name, p in zip(JOB_NAMES, row["Pj"]) if p > QOS_LIMIT]
        + (["evidence"] if not row["evidence_valid"] else [])
    ) or "none"
    return row


def one_execution(root: Path, episode: Path, candidate: Candidate, number: int, runtime_seed: int, role: str) -> dict:
    cell = episode / "evaluations" / f"{number:06d}"
    if cell.exists():
        request = read_json(cell / "request.json")
        if (
            request["runtime_seed"] != runtime_seed
            or request["params"] != list(geometry(candidate))
            or Path(request["context"]).resolve() != (episode / "fixed_context.json").resolve()
            or not (cell / "raw_result.json").exists()
        ):
            raise RuntimeError(f"Incomplete or mismatched OC cell requires review: {cell}")
        raw = read_json(cell / "raw_result.json")
    else:
        raw = FixedEvaluator(root, episode)(geometry(candidate), number, runtime_seed)
    return parse_execution(root, episode, candidate, number, runtime_seed, raw, role)


def run_panel(root: Path, output: Path, candidate: Candidate, number: int, seed_plan: dict, workers: int) -> tuple[list[dict], float]:
    arrivals = seed_plan["search_arrival_seeds"]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                one_execution, root, output / "arrival_panel" / f"table_{seed}",
                candidate, number, seed_plan["search_runtime_seed"], "SEARCH",
            )
            for seed in arrivals
        ]
        rows = [future.result() for future in futures]
    if [r["arrival_seed"] for r in rows] != arrivals or len({r["geometry_key"] for r in rows}) != 1:
        raise ValueError("Candidate/table scheduling crossed identities")
    return rows, time.monotonic() - started


def read_candidate_batches(output: Path) -> dict[str, Candidate]:
    candidates = {}
    for path in sorted((output / "search").glob("batch_*_candidates.json")):
        for data in read_json(path):
            candidate = candidate_from_dict(data)
            if candidate.candidate_id in candidates or geometry_key(candidate) in {geometry_key(c) for c in candidates.values()}:
                raise ValueError("Duplicate OC candidate ID or complete geometry")
            candidates[candidate.candidate_id] = candidate
    return candidates


def run_search(root: Path, output: Path, seed_plan: dict, bank: Path, bank_manifest: dict, workers: int, soft_seconds: float, hard_cap: int) -> tuple[list[dict], list[dict], dict]:
    search_dir = output / "search"
    search_dir.mkdir(exist_ok=True)
    started = time.monotonic()
    cloud, domain, v3_timing = build_cloud(root, output, bank, bank_manifest, seed_plan["search_runtime_seed"])
    all_rows = pd.read_csv(search_dir / "all_scenario_executions.csv").to_dict("records") if (search_dir / "all_scenario_executions.csv").exists() else []
    for row in all_rows:
        row["Pj"] = json.loads(row["Pj"]) if isinstance(row["Pj"], str) else row["Pj"]
        row["evidence_counts"] = json.loads(row["evidence_counts"]) if isinstance(row["evidence_counts"], str) else row["evidence_counts"]
        row["evidence_valid"] = str(row["evidence_valid"]).lower() == "true"
    aggregates = pd.read_csv(search_dir / "all_candidate_panels.csv").to_dict("records") if (search_dir / "all_candidate_panels.csv").exists() else []
    for aggregate in aggregates:
        aggregate["search_panel_target_met"] = str(aggregate["search_panel_target_met"]).lower() == "true"
    candidates = read_candidate_batches(output)
    if len(all_rows) != SEARCH_TABLES * len(aggregates):
        raise ValueError("Saved OC search rows do not form complete ten-table panels")
    if len(aggregates) > hard_cap // SEARCH_TABLES:
        raise ValueError("Saved OC search exceeds hard simulator cap")
    prior_seconds = max((float(r["cumulative_search_wall_seconds"]) for r in aggregates), default=0.0)

    def elapsed_search() -> float:
        return prior_seconds + time.monotonic() - started

    rng = np.random.default_rng(2026092601)
    waves = []
    batch_number = 1
    stop_reason = "HARD_CALL_CAP"
    while len(aggregates) < hard_cap // SEARCH_TABLES:
        if len(aggregates) >= INITIAL_CANDIDATES and elapsed_search() >= soft_seconds:
            stop_reason = "SOFT_WALL_TARGET"
            break
        batch_json = search_dir / f"batch_{batch_number:03d}_candidates.json"
        if batch_json.exists():
            batch = [candidate_from_dict(data) for data in read_json(batch_json)]
        else:
            if batch_number == 1:
                batch = select_initial(cloud, domain)
            else:
                try:
                    batch = next_batch(batch=batch_number, candidates=candidates, aggregates=aggregates, cloud=cloud, domain=domain, rng=rng)
                except RuntimeError as exc:
                    if "distinct" not in str(exc).lower():
                        raise
                    stop_reason = "NO_MORE_DISTINCT_LEGAL_PROPOSALS"
                    break
            if len(aggregates) + len(batch) > hard_cap // SEARCH_TABLES:
                raise ValueError("Proposed batch exceeds hard simulator cap")
            atomic_json(batch_json, [asdict(c) for c in batch])
            atomic_csv(search_dir / f"batch_{batch_number:03d}_candidates.csv", [candidate_row(c) for c in batch])
        for candidate in batch:
            domain.validate(candidate)
            candidates[candidate.candidate_id] = candidate
            if any(r["candidate_id"] == candidate.candidate_id for r in aggregates):
                continue
            if len(aggregates) * SEARCH_TABLES + SEARCH_TABLES > hard_cap:
                raise ValueError("OC hard simulator cap would be exceeded")
            number = len(aggregates) + 1
            rows, wave_seconds = run_panel(root, output, candidate, number, seed_plan, workers)
            aggregate = candidate_aggregate(rows)
            aggregate.update({
                "candidate_source": candidate.source,
                "candidate_number": number,
                "Pbar": candidate.Pbar,
                "R": candidate.R,
                "weights": json.dumps(candidate.weights),
                "geometry_key": geometry_key(candidate),
                "batch": batch_number,
                "wave_wall_seconds": wave_seconds,
                "cumulative_search_wall_seconds": elapsed_search(),
            })
            all_rows.extend(rows)
            aggregates.append(aggregate)
            waves.append(wave_seconds)
            serial_rows = [{**r, "Pj": json.dumps(r["Pj"]), "evidence_counts": json.dumps(r["evidence_counts"])} for r in all_rows]
            atomic_csv(search_dir / "all_scenario_executions.csv", serial_rows)
            atomic_csv(search_dir / "all_candidate_panels.csv", aggregates)
            atomic_csv(search_dir / f"batch_{batch_number:03d}_results.csv", [r for r in aggregates if r["batch"] == batch_number])
            atomic_json(search_dir / "progress.json", {
                "candidate_panels_complete": len(aggregates), "simulator_executions_complete": len(all_rows),
                "best_arrival_pass_count": max(r["arrival_pass_count"] for r in aggregates),
                "elapsed_search_seconds": elapsed_search(),
            })
            print(f"OC candidate {number}: {aggregate['arrival_pass_count']}/10; mean objective {aggregate['mean_objective_all_ten']:.6f}", flush=True)
            if len(aggregates) >= INITIAL_CANDIDATES and elapsed_search() >= soft_seconds:
                stop_reason = "SOFT_WALL_TARGET"
                break
        if len(aggregates) >= INITIAL_CANDIDATES and elapsed_search() >= soft_seconds:
            stop_reason = "SOFT_WALL_TARGET"
            break
        batch_number += 1
    timing = {
        "search_wall_seconds_this_invocation": time.monotonic() - started,
        "search_wall_seconds_total": elapsed_search(),
        "stop_reason": stop_reason,
        "candidate_panels": len(aggregates),
        "search_simulator_executions": len(all_rows),
        "parallel_waves": len(aggregates),
        "max_workers": workers,
        "wave_seconds_this_invocation": waves,
        "aggregate_simulator_seconds": sum(float(r["elapsed_seconds"]) for r in all_rows),
        "v3_timing": v3_timing,
    }
    atomic_json(search_dir / "search_timing.json", timing)
    return all_rows, aggregates, timing


def ensure_assessment_table(root: Path, output: Path, spec: dict, arrival_seed: int) -> tuple[Path, dict]:
    episode = output / "final" / f"assessment_{arrival_seed}"
    if episode.exists():
        context = read_json(episode / "fixed_context.json")
    else:
        context, _, _ = prepare(root, episode, spec, spec["cases"][WORKLOAD], arrival_seed, GRID_TRACE_HASH)
    if context["arrival_seed"] != arrival_seed or context["grid_signal_hash"] != GRID_TRACE_HASH:
        raise ValueError("Final assessment table identity mismatch")
    if sha256(episode / "initial_jobs.csv.gz") != context["initial_file_sha256"]:
        raise ValueError("Final assessment table file changed")
    return episode, context


def run_assessment(root: Path, output: Path, spec: dict, candidate: Candidate, seed_plan: dict, workers: int) -> tuple[list[dict], dict]:
    final = output / "final"
    final.mkdir(exist_ok=True)
    selected_path = final / "selected_candidate.json"
    frozen = {
        "candidate": asdict(candidate),
        "candidate_geometry_key": geometry_key(candidate),
        "selection_rule": "minimum mean canonical objective over all ten search scenarios among measured candidates passing at least 8/10",
        "assessment_seeds_predeclared_before_search": True,
    }
    if selected_path.exists():
        prior = read_json(selected_path)
        if prior != frozen:
            raise ValueError("Frozen selected OC candidate changed during assessment")
    else:
        atomic_json(selected_path, frozen)
    started = time.monotonic()
    rows = []
    table_rows = []
    pairs = seed_plan["assessment_pairs"]
    for start in range(0, len(pairs), workers):
        group = pairs[start : start + workers]
        tasks = []
        for pair in group:
            episode, context = ensure_assessment_table(root, output, spec, pair["arrival_seed"])
            table_rows.append({
                "arrival_seed": pair["arrival_seed"], "runtime_seed": pair["runtime_seed"],
                "initial_job_table_hash": context["initial_job_table_hash"],
                "table_file_sha256": context["initial_file_sha256"],
                **table_statistics(episode / "initial_jobs.csv.gz", context["prefill"]),
            })
            tasks.append((episode, pair["runtime_seed"]))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(one_execution, root, episode, candidate, 1, runtime_seed, "HELD_OUT_ASSESSMENT") for episode, runtime_seed in tasks]
            rows.extend(future.result() for future in futures)
        atomic_csv(final / "fresh_assessment_results.csv", [
            {**r, "Pj": json.dumps(r["Pj"]), "evidence_counts": json.dumps(r["evidence_counts"])} for r in rows
        ])
        atomic_csv(final / "assessment_table_manifest.csv", table_rows)
        print(f"OC held-out assessment {len(rows)}/{len(pairs)}", flush=True)
    if len(rows) != ASSESSMENT_PAIRS or len({r["arrival_seed"] for r in rows}) != ASSESSMENT_PAIRS:
        raise ValueError("Incomplete or duplicate held-out assessment")
    timing = {"assessment_wall_seconds": time.monotonic() - started, "simulator_executions": len(rows), "passes": sum(r["feasible"] for r in rows)}
    atomic_json(final / "assessment_timing.json", timing)
    return rows, timing


def make_figures(output: Path, search_rows: list[dict], aggregates: list[dict], assessment_rows: list[dict]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    if not aggregates:
        return
    frame = pd.DataFrame(aggregates)
    fig, ax = plt.subplots(figsize=(8, 5))
    points = ax.scatter(frame.Pbar, frame.R, c=frame.arrival_pass_count, vmin=0, vmax=10, cmap="viridis", s=60)
    hit = frame[frame.arrival_pass_count >= SEARCH_TARGET]
    ax.scatter(hit.Pbar, hit.R, facecolors="none", edgecolors="black", s=130, linewidths=1.4, label=">=8/10 measured")
    ax.set(xlabel="Pbar (kW/server)", ylabel="R (kW/server)", title="Measured complete bids projected onto Pbar/R")
    if not hit.empty:
        ax.legend()
    fig.colorbar(points, ax=ax, label="Search arrival tables passed / 10")
    fig.tight_layout()
    fig.savefig(figures / "pbar_r_pass_count.png", dpi=170)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    points = ax.scatter(frame.Pbar, frame.R, c=frame.mean_objective_all_ten, cmap="plasma", s=70)
    ax.set(xlabel="Pbar (kW/server)", ylabel="R (kW/server)", title="Measured mean objective, all ten tables (Pbar/R projection)")
    fig.colorbar(points, ax=ax, label="Mean canonical objective")
    fig.tight_layout()
    fig.savefig(figures / "pbar_r_mean_objective.png", dpi=170)
    plt.close(fig)

    by_seed = pd.DataFrame(search_rows)
    seeds = list(dict.fromkeys(int(x) for x in by_seed.arrival_seed))
    fig, axes = plt.subplots(2, 5, figsize=(17, 7), sharex=True, sharey=True)
    for ax, seed in zip(axes.flat, seeds):
        group = by_seed[by_seed.arrival_seed == seed]
        ax.scatter(group.Pbar, group.R, c=np.where(group.feasible, "#267a50", "#be4040"), s=25)
        ax.set_title(f"Arrival {seed}")
    fig.supxlabel("Pbar (kW/server)")
    fig.supylabel("R (kW/server)")
    fig.suptitle("Each point is a complete measured bid; green passes this one table")
    fig.tight_layout()
    fig.savefig(figures / "per_arrival_pbar_r_projection.png", dpi=150)
    plt.close(fig)

    weights = np.array([json.loads(x) if isinstance(x, str) else x for x in frame.weights])
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, row in enumerate(weights):
        ax.plot(range(4), row, color=plt.cm.viridis(float(frame.arrival_pass_count.iloc[i]) / 10), alpha=0.6)
    ax.set_xticks(range(4), JOB_NAMES)
    ax.set(ylabel="Scheduling weight", title="Complete measured bid weights, colored by search pass count")
    fig.tight_layout()
    fig.savefig(figures / "weight_parallel_coordinates.png", dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    t = frame.cumulative_search_wall_seconds / 60
    axes[0].step(t, frame.arrival_pass_count.cummax(), where="post")
    axes[0].axhline(SEARCH_TARGET, color="red", ls="--", lw=1)
    axes[0].set(xlabel="Search elapsed minutes", ylabel="Best table pass count", ylim=(-0.3, 10.3))
    costs = [min(frame.iloc[: i + 1][frame.iloc[: i + 1].arrival_pass_count >= SEARCH_TARGET].mean_objective_all_ten, default=np.nan) for i in range(len(frame))]
    axes[1].plot(t, costs, marker=".")
    axes[1].set(xlabel="Search elapsed minutes", ylabel="Best eligible mean objective")
    fig.tight_layout()
    fig.savefig(figures / "search_progress.png", dpi=170)
    plt.close(fig)

    if assessment_rows:
        final = pd.DataFrame(assessment_rows)
        max_pj = [max(row) for row in final.Pj]
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        axes[0].scatter(range(1, len(final) + 1), final.p90, c=np.where(final.feasible, "#267a50", "#be4040"))
        axes[0].axhline(TRACKING_LIMIT, color="black", ls="--")
        axes[0].set(xlabel="Held-out scenario", ylabel="Tracking p90")
        axes[1].scatter(range(1, len(final) + 1), max_pj, c=np.where(final.feasible, "#267a50", "#be4040"))
        axes[1].axhline(QOS_LIMIT, color="black", ls="--")
        axes[1].set(xlabel="Held-out scenario", ylabel="Maximum job Pj")
        fig.suptitle("Frozen bid on fresh arrival/runtime pairs")
        fig.tight_layout()
        fig.savefig(figures / "fresh_assessment.png", dpi=170)
        plt.close(fig)


def write_report(root: Path, output: Path, rows: list[dict], aggregates: list[dict], assessment_rows: list[dict], timing: dict, v3_baseline: Path) -> None:
    best = select_final(aggregates)
    max_pass = max((r["arrival_pass_count"] for r in aggregates), default=0)
    selected_rows = [r for r in rows if best and r["candidate_id"] == best["candidate_id"]]
    source_groups = {}
    for r in aggregates:
        source_groups.setdefault(r["candidate_source"], []).append(r)
    source_summary = {
        source: {"candidate_count": len(group), "best_pass_count": max(r["arrival_pass_count"] for r in group)}
        for source, group in source_groups.items()
    }
    initial_v3 = next((r for r in aggregates if r["candidate_id"] == "b01-initial-00"), None)
    best_measured = min(aggregates, key=measured_rank) if aggregates else None
    selected_parameters = {
        "Pbar": best["Pbar"], "R": best["R"], "weights": json.loads(best["weights"])
    } if best else None
    failure_counts = {name: sum(name in str(r["failure_constraints"]).split(",") for r in rows) for name in ("tracking", *JOB_NAMES, "evidence")}
    assessment_failures = {name: sum(name in str(r["failure_constraints"]).split(",") for r in assessment_rows) for name in ("tracking", *JOB_NAMES, "evidence")}
    frozen = pd.read_csv(root / OLD_EXPERIMENT / "context_summary.csv")
    frozen_row = frozen[(frozen.workload == WORKLOAD) & (frozen.server_count == 1000) & (frozen.utilization == 0.6)].iloc[0].to_dict()
    v3_timing = read_json(v3_baseline / "timing.json")
    v3_head = pd.read_csv(v3_baseline / "head_to_head.csv")
    v3_row = v3_head[v3_head.context == f"{WORKLOAD}/N1000_U0.6"].iloc[0].to_dict()
    comparison = [
        {"method": "Pure V3", "search_arrival_tables": 0, "simulator_feedback": "none", "search_simulator_executions": 0, "fixed_table_result": bool(v3_row["V3_final_bid_actually_feasible"]), "fresh_runtime": v3_row["V3_runtime_checks"], "fresh_arrival": None, "objective": v3_row["V3_actual_objective"]},
        {"method": "Frozen standard ARGOS", "search_arrival_tables": 1, "simulator_feedback": "32 calls on one fixed table", "search_simulator_executions": 32, "fixed_table_result": frozen_row["search_status"], "fresh_runtime": f"{frozen_row['runtime_checks_passed']}/{frozen_row['runtime_checks_total']}", "fresh_arrival": None, "objective": frozen_row["search_objective"]},
        {"method": "ARGOS-OC basic", "search_arrival_tables": SEARCH_TABLES, "simulator_feedback": "full ten-table panels", "search_simulator_executions": len(rows), "fixed_table_result": None, "fresh_runtime": None, "fresh_arrival": f"{sum(r['feasible'] for r in assessment_rows)}/{len(assessment_rows)}" if assessment_rows else None, "objective": best["mean_objective_all_ten"] if best else None},
    ]
    atomic_csv(output / "three_way_comparison.csv", comparison)
    summary = {
        "measured_candidate_count": len(aggregates),
        "search_simulator_executions": len(rows),
        "search_parallel_waves": len(aggregates),
        "best_search_arrival_pass_count": max_pass,
        "eligible_candidate_count": sum(r["search_panel_target_met"] for r in aggregates),
        "selected_candidate_id": best["candidate_id"] if best else None,
        "selected_search_panel_mean_objective": best["mean_objective_all_ten"] if best else None,
        "selected_search_panel_pass_count": best["arrival_pass_count"] if best else None,
        "search_failure_constraints": failure_counts,
        "source_summary": source_summary,
        "initial_v3_preferred_pass_count": initial_v3["arrival_pass_count"] if initial_v3 else None,
        "best_measured_candidate_id": best_measured["candidate_id"] if best_measured else None,
        "selected_parameters": selected_parameters,
        "fresh_assessment_passes": sum(r["feasible"] for r in assessment_rows),
        "fresh_assessment_total": len(assessment_rows),
        "fresh_assessment_failure_constraints": assessment_failures,
        "v3_breadth_confirmed_contexts": v3_timing["simulator_confirmed_contexts"],
        "v3_breadth_runtime_checks": f"{v3_timing['runtime_checks_passed']}/{v3_timing['runtime_checks_total']}",
        "frozen_argos_breadth_successes": "15/16",
        "frozen_argos_breadth_runtime_checks": "44/45",
    }
    atomic_json(output / "summary.json", summary)
    lines = [
        "# ARGOS-OC basic: W2 N1000 U0.6",
        "",
        "This first OC run tested complete Pbar/R/weight vectors on ten frozen arrival tables",
        "with one fixed search runtime seed. V3 screened candidate geometry but no unmeasured",
        "point was called feasible. The 30 predeclared fresh arrival/runtime pairs, when present,",
        "were assessed only after the selected bid was frozen.",
        "",
        f"- Best measured search-panel support: **{max_pass}/10**.",
        f"- Measured candidates: **{len(aggregates)}**; search FlexDC executions: **{len(rows)}** in {len(aggregates)} ten-table waves.",
        f"- Selected eligible candidate: **{best['candidate_id'] if best else 'none'}**.",
        f"- Selected mean canonical objective over all ten tables: **{best['mean_objective_all_ten'] if best else 'N/A'}**.",
        f"- Independent fresh arrival/runtime assessment: **{sum(r['feasible'] for r in assessment_rows)}/{len(assessment_rows)}** tested scenarios.",
        f"- Search wall time: **{timing['search_wall_seconds_total']:.1f} s**; aggregate simulator time: **{timing['aggregate_simulator_seconds']:.1f} s**.",
        f"- Search stop reason: **{timing['stop_reason']}**.",
        f"- V3 bank: verified historical reuse; original bank generation {timing['v3_timing']['bank_original_generation_seconds']:.1f} s (not charged again).",
        f"- This run's V3 model load/scoring: {timing['v3_timing']['v3_model_load_seconds']:.1f} s / {timing['v3_timing']['v3_independent_scoring_seconds']:.1f} s.",
        f"- Frozen-table generation: {timing['job_table_generation_seconds_this_invocation']:.1f} s; held-out assessment: {timing['assessment']['assessment_wall_seconds']:.1f} s.",
        "",
        "The 8/10 search-panel threshold is a finite-panel decision rule, not a certified reliability probability.",
        "The held-out count is also descriptive and was not used to revise the bid.",
        "",
        "## Selected measured search-panel cells",
        "",
        "| Arrival seed | p90 | ResNet Pj | GPT2 Pj | Llama Pj | Bloom Pj | Objective | Pass |",
        "|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in selected_rows:
        lines.append(f"| {r['arrival_seed']} | {r['p90']:.4f} | {r['Pj'][0]:.4f} | {r['Pj'][1]:.4f} | {r['Pj'][2]:.4f} | {r['Pj'][3]:.4f} | {r['objective']:.4f} | {r['feasible']} |")
    lines += [
        "",
        "## Measured search interpretation",
        "",
        (
            f"The first V3-preferred initial point passed {initial_v3['arrival_pass_count'] if initial_v3 else 'N/A'}/10 tables. "
            f"The strongest measured point was {best_measured['candidate_id'] if best_measured else 'N/A'} "
            f"({best_measured['candidate_source'] if best_measured else 'N/A'}), with {max_pass}/10 support."
        ),
        f"Source-group counts and best pass counts: {source_summary}.",
        f"Selected full bid: {selected_parameters if selected_parameters else 'none reached the declared 8/10 target'}.",
        "A measured candidate meeting the finite-panel target is evidence of a common tested",
        "point across those tables. Nearby untested geometry is not certified. If no point",
        "met the target, this budget gives no measured 8/10 pocket; it does not prove none exists.",
        "Independent-source successes are descriptive; their observed ancestry and scores are",
        "recorded in the candidate and scenario CSVs. V3 agreement cannot be inferred from",
        "Pbar/R alone because scheduling weights are part of the bid.",
        "",
        "## Scope-aware comparison",
        "",
        "| Method | Search arrival tables | Search simulator calls | Single fixed-table result | Fresh runtime | Fresh arrivals | Objective |",
        "|---|---:|---:|---|---|---|---:|",
    ]
    for r in comparison:
        lines.append(f"| {r['method']} | {r['search_arrival_tables']} | {r['search_simulator_executions']} | {r['fixed_table_result']} | {r['fresh_runtime']} | {r['fresh_arrival']} | {r['objective']} |")
    lines += [
        "",
        "Pure V3 used no FlexDC feedback during optimization. Standard ARGOS optimized one",
        "fixed table and then checked fresh runtime seeds. OC optimized across ten arrival",
        "tables and used a separate fresh-arrival/runtime assessment. Their call counts and",
        "wall times measure different tasks and are not direct speedups.",
        "",
        f"Search failure counts (constraints can overlap): {failure_counts}.",
        f"Held-out failure counts (constraints can overlap): {assessment_failures}.",
        (
            "Held-out p90 min/median/max: "
            f"{min(r['p90'] for r in assessment_rows):.4f}/"
            f"{statistics.median(r['p90'] for r in assessment_rows):.4f}/"
            f"{max(r['p90'] for r in assessment_rows):.4f}; "
            "maximum-Pj min/median/max: "
            f"{min(max(r['Pj']) for r in assessment_rows):.4f}/"
            f"{statistics.median(max(r['Pj']) for r in assessment_rows):.4f}/"
            f"{max(max(r['Pj']) for r in assessment_rows):.4f}."
        ) if assessment_rows else "No independent assessment: no candidate met the search-panel target.",
        "Pbar/R figures are projections of full measured candidates; they do not certify",
        "an interpolated continuous feasible region. Per-table rows and complete weights are",
        "in search/all_scenario_executions.csv and search/all_candidate_panels.csv.",
        "",
    ]
    (output / "report.md").write_text("\n".join(lines), encoding="utf8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="ARGOS-OC basic ten-arrival measured search and independent assessment")
    parser.add_argument("--scientific-root", required=True, type=Path, help="Frozen ARGOS original16 checkout containing pinned dependencies and data")
    parser.add_argument("--output", type=Path, default=None, help="New ARGOS-OC experiment directory; default under this branch's runs/experiments")
    parser.add_argument("--v3-baseline", required=True, type=Path, help="Completed pure V3 breadth baseline directory")
    parser.add_argument("--max-workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--soft-search-seconds", type=float, default=1200.0)
    parser.add_argument("--hard-call-cap", type=int, default=HARD_CALL_CAP)
    parser.add_argument("--smoke-only", action="store_true", help="Check provenance and one historical generator hash, then stop before FlexDC")
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parents[3]
    root = args.scientific_root.resolve()
    baseline = args.v3_baseline.resolve()
    if not (baseline / "run_status.json").exists() or read_json(baseline / "run_status.json").get("status") != "COMPLETE":
        raise ValueError("Stage A V3 baseline must complete before OC full execution")
    if not 1 <= args.max_workers <= MAX_WORKERS:
        raise ValueError("OC worker limit must be 1..10")
    if not INITIAL_CANDIDATES * SEARCH_TABLES <= args.hard_call_cap <= HARD_CALL_CAP or args.hard_call_cap % SEARCH_TABLES:
        raise ValueError("OC hard cap must be a multiple of ten between 100 and 400")
    if args.soft_search_seconds <= 0:
        raise ValueError("OC soft search time must be positive")
    spec, _frozen, bank, bank_manifest, historical_seeds, expected_hashes, provenance = preflight(root, source)
    seed_plan = provenance["seed_plan"]
    if args.smoke_only:
        from argos.diagnostics.workload_seed_forensics import generate, load_generator, table_hash

        tables, Experiment, Jobs = load_generator(root)
        e = Experiment(str(root / spec["experiment_path"]))
        e._utilization = 0.6
        j = Jobs(str(root / spec["cases"][WORKLOAD]["workload_path"]))
        seed = historical_seeds[0]
        _, initial, _ = generate(tables, e, j, seed)
        if table_hash(initial) != expected_hashes[seed]:
            raise ValueError("Historical Phase 2B generator-only smoke hash mismatch")
        print(json.dumps({"status": "SMOKE_PASS_NO_FLEXDC", "seed": seed, "table_hash": expected_hashes[seed]}, indent=2))
        return
    output = (args.output or source / "runs" / "experiments" / f"argos_oc_basic_w2_n1000_u06_{utc_stamp()}").resolve()
    if output == root or output == baseline or output.is_relative_to(root / OLD_EXPERIMENT):
        raise ValueError("OC output cannot overwrite frozen scientific evidence")
    manifest_path = output / "manifest.json"
    source_hashes = {p: sha256(source / p) for p in (
        "src/argos/oc_basic/core.py", "src/argos/oc_basic/runner.py", "scripts/run_argos_oc_basic.py"
    )}
    identity = {
        "schema": 1,
        "mode": "ARGOS_OC_BASIC_W2_N1000_U06",
        "scientific_root": str(root),
        "oc_source_root": str(source),
        "oc_branch": git(source, "rev-parse", "--abbrev-ref", "HEAD"),
        "oc_source_commit": git(source, "rev-parse", "HEAD"),
        "frozen_original16_commit": git(root, "rev-parse", "HEAD"),
        "frozen_original16_manifest_sha256": sha256(root / OLD_EXPERIMENT / "manifest.json"),
        "dependency_shas": EXPECTED_DEPS,
        "checkpoint_sha256": CHECKPOINT_SHA,
        "source_hashes": source_hashes,
        "phase2b_provenance": provenance["phase2b"],
        "bank_manifest_sha256": sha256(bank / "manifest.json"),
        "bank_identity": bank_manifest["identity"],
        "seed_plan": seed_plan,
        "workload": WORKLOAD,
        "N": 1000,
        "U": 0.6,
        "duration_seconds": 3600,
        "grid_trace_hash": GRID_TRACE_HASH,
        "normal_policy": "peacsim.aqa_runtimepolicy.AQARuntimePolicy",
        "search_rule": "complete candidate measured on all ten frozen arrival tables at fixed runtime seed; target >=8/10; lowest mean canonical objective over all ten among target-meeting candidates",
        "refinement_allocation": "four measured-anchor legal local proposals and two independent/diverse proposals per six-candidate round; V3 does not veto measured anchors",
        "assessment_rule": "30 predeclared fresh arrival/runtime pairs after candidate freeze; no feedback",
        "hard_search_simulator_cap": args.hard_call_cap,
        "soft_search_wall_target_seconds": args.soft_search_seconds,
        "max_workers": args.max_workers,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "torch_version": torch.__version__,
        "python_version": sys.version,
        "cpu_count": os.cpu_count(),
        "platform": platform.platform(),
    }
    if manifest_path.exists():
        prior = read_json(manifest_path)
        if prior != identity:
            raise ValueError("OC experiment identity/source/config changed on resume")
    else:
        output.mkdir(parents=True, exist_ok=False)
        atomic_json(manifest_path, identity)
        atomic_json(output / "dependency_manifest.json", {
            "FlexDC": EXPECTED_DEPS["FlexDC"], "CONDOR-FLEXDC": EXPECTED_DEPS["CONDOR-FLEXDC"],
            "checkpoint_sha256": CHECKPOINT_SHA, "original16_manifest_sha256": identity["frozen_original16_manifest_sha256"],
            "phase2b": provenance["phase2b"],
        })
        atomic_json(output / "arrival_panel" / "seeds.json", seed_plan)
        # JSON is valid YAML 1.2 and preserves exact floating-point limits/seeds.
        (output / "resolved_config.yaml").write_text(json.dumps({
            "workload": WORKLOAD, "N": 1000, "U": 0.6, "duration_seconds": 3600,
            "search_arrival_tables": SEARCH_TABLES, "search_target_passes": SEARCH_TARGET,
            "fixed_search_runtime_seed": seed_plan["search_runtime_seed"],
            "assessment_pairs": ASSESSMENT_PAIRS, "max_workers": args.max_workers,
            "soft_search_seconds": args.soft_search_seconds, "hard_search_calls": args.hard_call_cap,
            "domain": bank_manifest["domain"],
        }, indent=2), encoding="utf8")
    if (output / "run_status.json").exists() and read_json(output / "run_status.json").get("status") in {"COMPLETE", "COMPLETE_NO_TARGET_CANDIDATE"}:
        print(f"Already complete: {output}")
        return
    experiment_started = time.monotonic()
    atomic_json(output / "run_status.json", {"status": "RUNNING", "started_utc": datetime.now(timezone.utc).isoformat()})
    table_started = time.monotonic()
    ensure_search_tables(root, output, spec, seed_plan, expected_hashes)
    table_seconds = time.monotonic() - table_started
    rows, aggregates, timing = run_search(root, output, seed_plan, bank, bank_manifest, args.max_workers, args.soft_search_seconds, args.hard_call_cap)
    best = select_final(aggregates)
    assessment_rows = []
    assessment_timing = {"assessment_wall_seconds": 0.0, "simulator_executions": 0, "passes": 0}
    if best:
        candidates = read_candidate_batches(output)
        selected = candidates[best["candidate_id"]]
        assessment_rows, assessment_timing = run_assessment(root, output, spec, selected, seed_plan, args.max_workers)
        atomic_csv(output / "final" / "search_panel_results.csv", [
            {**r, "Pj": json.dumps(r["Pj"]), "evidence_counts": json.dumps(r["evidence_counts"])}
            for r in rows if r["candidate_id"] == best["candidate_id"]
        ])
    timing.update({
        "job_table_generation_seconds_this_invocation": table_seconds,
        "assessment": assessment_timing,
        "end_to_end_wall_seconds_this_invocation": time.monotonic() - experiment_started,
        "search_worker_limit": args.max_workers,
        "assessment_worker_limit": args.max_workers,
    })
    atomic_json(output / "timing.json", timing)
    make_figures(output, rows, aggregates, assessment_rows)
    write_report(root, output, rows, aggregates, assessment_rows, timing, baseline)
    atomic_json(output / "run_status.json", {
        "status": "COMPLETE" if best else "COMPLETE_NO_TARGET_CANDIDATE",
        "selected_candidate_id": best["candidate_id"] if best else None,
        "search_simulator_executions": len(rows),
        "fresh_assessment_executions": len(assessment_rows),
        "completed_utc": datetime.now(timezone.utc).isoformat(),
    })
    print(output)
    print(json.dumps(read_json(output / "summary.json"), indent=2))


if __name__ == "__main__":
    main()
