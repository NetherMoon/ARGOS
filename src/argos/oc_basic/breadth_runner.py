"""Generic ARGOS-OC original-16 benchmark using the pinned FlexDC worker.

All scientific identities are frozen in benchmark/frozen_argos_oc_breadth_protocol.json.
Contexts run sequentially; at most ten isolated FlexDC workers run at once.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from argos.campaign.identity import verify_files
from argos.diagnostics.seed_factorization_worker import JOB_COLUMNS
from argos.experimental_sa.paper_consistent.evaluator import FixedEvaluator, prepare
from argos.experimental_sa.paper_consistent.objective import ObjectiveContract
from argos.fixed_table import original16
from argos.fixed_table.simulator import evidence_from_accounting
from argos.oc_basic import runner as legacy
from argos.oc_basic.breadth_plan import (
    ASSESSMENT_PAIRS,
    HARD_SEARCH_CALLS,
    MAX_WORKERS,
    ORIGINAL_RUN,
    REQUIRED_PASSES,
    SEARCH_PANEL_SIZE,
    SOFT_SEARCH_SECONDS,
    V3_RUN,
    context_key,
    verify_protocol,
)
from argos.oc_basic.core import distinct, geometry, geometry_key
from argos.oc_basic.generic import (
    PanelRule,
    PanelState,
    next_batch,
    panel_state,
    select_final,
    select_initial,
    serialize_state,
)
from argos.oc_basic.scheduling import execute_fanout_batch
from argos.provenance import git, read_json, sha256
from argos.search.candidates import Domain
from argos.search.regions import from_snapshot
from argos.simulator.evidence import ordered_jobs
from argos.types import Candidate, Metrics, candidate_from_dict
from argos.vnext.device import V3Adapter


def _json(path: Path, value: object) -> None:
    for attempt in range(10):
        try:
            legacy.atomic_json(path, value)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.1)


def _csv(path: Path, rows: list[dict]) -> None:
    serial = [
        {
            key: json.dumps(value) if isinstance(value, (list, tuple, dict)) else value
            for key, value in row.items()
        }
        for row in rows
    ]
    for attempt in range(10):
        try:
            legacy.atomic_csv(path, serial)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.1)


def _rows(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    frame = pd.read_csv(path, keep_default_na=False)
    result = frame.to_dict("records")
    for row in result:
        for key in ("Pj", "weights", "evidence_counts"):
            if key in row and isinstance(row[key], str) and row[key].startswith("["):
                row[key] = json.loads(row[key])
        for key in ("evidence_valid", "feasible"):
            if key in row and isinstance(row[key], str):
                row[key] = row[key].lower() == "true"
    return result


def _assert_rows(
    rows: list[dict],
    seeds: tuple[int, ...],
    runtime_seed: int,
    table_hashes: dict[int, str],
    grid_hash: str,
) -> None:
    pairs = [(r["candidate_id"], int(r["arrival_seed"])) for r in rows]
    if len(pairs) != len(set(pairs)):
        raise ValueError("Duplicate candidate/table execution")
    for row in rows:
        seed = int(row["arrival_seed"])
        if (
            seed not in seeds
            or int(row["runtime_seed"]) != runtime_seed
            or row["initial_job_table_hash"] != table_hashes[seed]
            or row["grid_signal_hash"] != grid_hash
            or row["execution_status"] != "COMPLETE"
            or not row["evidence_valid"]
        ):
            raise ValueError("Search row lost frozen table/runtime/grid/evidence identity")


def arrival_stats(path: Path, prefill: int, names: tuple[str, ...], seed: int) -> list[dict]:
    """Long-format per-job arrival descriptors, with no special job label."""
    frame = pd.read_csv(path, float_precision="round_trip")
    if list(frame.columns) != JOB_COLUMNS:
        raise ValueError("Frozen initial-job schema changed")
    result = []
    for index, name in enumerate(names):
        jobs = frame[frame.job_type_id == index]
        times = np.sort(jobs.loc[jobs.job_id >= prefill, "arrival_time"].to_numpy(dtype=float))
        gaps = np.diff(times)
        burst = (
            int(np.max(np.arange(len(times)) - np.searchsorted(times, times - 60, side="left") + 1))
            if len(times)
            else 0
        )
        result.append(
            {
                "arrival_seed": seed,
                "job_type": name,
                "job_type_index": index,
                "job_count": len(jobs),
                "prefill_count": int((jobs.job_id < prefill).sum()),
                "later_arrival_count": len(times),
                "mean_interarrival": float(gaps.mean()) if len(gaps) else None,
                "interarrival_cv": float(gaps.std() / gaps.mean())
                if len(gaps) and gaps.mean()
                else None,
                "max_arrivals_60s": burst,
                "arrivals_final_300s": int((times >= 3300).sum()),
            }
        )
    return result


def _table(
    root: Path,
    episode: Path,
    spec: dict,
    case: dict,
    seed: int,
    grid_hash: str,
    expected_hash: str | None = None,
    historical_anchor: Path | None = None,
) -> dict:
    if episode.exists():
        context = read_json(episode / "fixed_context.json")
    elif historical_anchor is not None:
        original = read_json(historical_anchor / "fixed_context.json")
        if (
            int(original["arrival_seed"]) != seed
            or original["initial_job_table_hash"] != expected_hash
            or original["grid_signal_hash"] != grid_hash
            or original["spec"] != spec
            or original["case"] != case
        ):
            raise ValueError("Historical anchor context changed: " + str(historical_anchor))
        episode.mkdir(parents=True, exist_ok=False)
        shutil.copy2(historical_anchor / "initial_jobs.csv.gz", episode / "initial_jobs.csv.gz")
        context = {**original, "output": str(episode.resolve())}
        _json(episode / "fixed_context.json", context)
    else:
        context, _, _ = prepare(root, episode, spec, case, seed, grid_hash)
    if (
        int(context["arrival_seed"]) != seed
        or context["grid_signal_hash"] != grid_hash
        or (expected_hash and context["initial_job_table_hash"] != expected_hash)
        or Path(context["output"]).resolve() != episode.resolve()
        or sha256(episode / "initial_jobs.csv.gz") != context["initial_file_sha256"]
    ):
        raise ValueError("Frozen initial job-table identity changed: " + str(episode))
    return context


def _cloud(
    root: Path, episode: Path, contract: dict, spec: dict, runtime_seed: int
) -> tuple[list[Candidate], Domain, dict]:
    cloud_path = episode / "v3" / "candidate_cloud.json"
    timing_path = episode / "v3" / "timing.json"
    bank = root / contract["v3_bank_path"]
    bank_manifest = read_json(bank / "manifest.json")
    if sha256(bank / "manifest.json") != contract["v3_bank_manifest_sha256"]:
        raise ValueError("V3 bank manifest changed")
    verify_files(bank, bank_manifest["files"])
    domain = Domain(**bank_manifest["domain"])
    if cloud_path.exists():
        return (
            [candidate_from_dict(item) for item in read_json(cloud_path)],
            domain,
            read_json(timing_path),
        )
    started = time.monotonic()
    attempt = bank / bank_manifest["completed_attempt"]
    frame = pd.read_csv(attempt / "snapshots.csv")
    cloud = []
    for row in frame.to_dict("records"):
        row["weights"] = json.loads(row["weights"])
        row["Predicted_QoS_Probabilities"] = json.loads(row["Predicted_QoS_Probabilities"])
        candidate = from_snapshot(row, int(bank_manifest["identity"]["iterations"]))
        try:
            domain.validate(candidate)
        except ValueError:
            continue
        cloud.append(candidate)
    snapshots_seconds = time.monotonic() - started
    adapter_start = time.monotonic()
    adapter = V3Adapter(root, threads=2, device="auto")
    workload, experiment = adapter.context(
        root / contract["workload_path"],
        root / contract["experiment_path"],
        int(contract["N"]),
        float(contract["U"]),
        runtime_seed,
    )
    model_seconds = time.monotonic() - adapter_start
    rng = np.random.default_rng(20260926)
    score_start = time.monotonic()
    for index in range(256):
        candidate = domain.independent(rng, f"cloud-independent-{index:04d}")
        prediction = adapter.predict(
            workload, experiment, candidate.Pbar, candidate.R, list(candidate.weights)
        )
        cloud.append(
            replace(
                candidate,
                prediction=Metrics(
                    float(prediction["Predicted_Mean_Tracking"]),
                    float(prediction["Predicted_P90_Tracking"]),
                    tuple(float(x) for x in prediction["Predicted_QoS_Probabilities"]),
                    float(prediction["Predicted_Full_Objective"]),
                ),
            )
        )
    timing = {
        "bank_reused": True,
        "bank_path": contract["v3_bank_path"],
        "bank_manifest_sha256": contract["v3_bank_manifest_sha256"],
        "bank_original_generation_seconds": float(contract["v3_bank_original_seconds"]),
        "bank_generation_seconds_this_run": 0.0,
        "snapshot_load_seconds": snapshots_seconds,
        "model_context_seconds": model_seconds,
        "independent_scoring_seconds": time.monotonic() - score_start,
        "candidate_cloud_seconds": time.monotonic() - started,
        "snapshot_count": len(cloud) - 256,
        "independent_count": 256,
        "device": adapter.device_metadata,
    }
    _json(cloud_path, [asdict(candidate) for candidate in cloud])
    _json(timing_path, timing)
    return cloud, domain, timing


def _parse_execution(
    root: Path,
    table: Path,
    candidate: Candidate,
    number: int,
    runtime_seed: int,
    role: str,
    raw: dict,
    rule: PanelRule,
    grid_hash: str,
) -> dict:
    context = read_json(table / "fixed_context.json")
    cell = table / "evaluations" / f"{number:06d}"
    if (
        raw.get("status") != "COMPLETE"
        or int(raw["runtime_seed"]) != runtime_seed
        or int(raw["arrival_seed"]) != int(context["arrival_seed"])
        or raw["initial_job_table_hash"] != context["initial_job_table_hash"]
        or raw["grid_signal_hash"] != grid_hash
        or len(raw["Pj"]) != len(rule.job_types)
    ):
        raise ValueError("FlexDC output identity or job count changed: " + str(cell))
    effective = tuple(float(x) for x in raw["effective_policy_weights"])
    if len(effective) != len(candidate.weights) or any(
        abs(a - b) > 1e-9 for a, b in zip(effective, candidate.weights)
    ):
        raise ValueError("Simulator effective weights differ from frozen bid")
    jobs = ordered_jobs(root / context["case"]["workload_path"])
    if tuple(job.section for job in jobs) != rule.job_types:
        raise ValueError("Configured job order changed")
    pj = tuple(float(x) for x in raw["Pj"])
    evidence = evidence_from_accounting(cell / "qos_accounting.csv", jobs, pj)
    counts = [item.observation_count for item in evidence]
    if counts != raw["evidence_counts"]:
        raise ValueError("QoS accounting/evidence count mismatch")
    objective = ObjectiveContract(root).evaluate(raw["M_RSR"], raw["p90"], pj).Cfull
    row = {
        "role": role,
        "candidate_id": candidate.candidate_id,
        "candidate_source": candidate.source,
        "geometry_key": geometry_key(candidate),
        "Pbar": candidate.Pbar,
        "R": candidate.R,
        "weights": list(candidate.weights),
        "arrival_seed": int(context["arrival_seed"]),
        "runtime_seed": runtime_seed,
        "initial_job_table_hash": context["initial_job_table_hash"],
        "grid_signal_hash": raw["grid_signal_hash"],
        "target_trace_hash": raw["target_trace_hash"],
        "p90": float(raw["p90"]),
        "mean_tracking": float(raw["mean_tracking"]),
        "Pj": list(pj),
        "objective": float(objective),
        "evidence_counts": counts,
        "evidence_valid": all(n is not None and n >= 1 for n in counts),
        "execution_status": raw["status"],
        "elapsed_seconds": float(raw["elapsed_seconds"]),
        "cell_path": str(cell),
    }
    row["feasible"] = (
        row["evidence_valid"]
        and row["p90"] <= rule.tracking_limit
        and all(p <= rule.qos_limit for p in pj)
    )
    row["failure_constraints"] = (
        ",".join(
            (["tracking"] if row["p90"] > rule.tracking_limit else [])
            + [name for name, value in zip(rule.job_types, pj) if value > rule.qos_limit]
            + (["evidence"] if not row["evidence_valid"] else [])
        )
        or "none"
    )
    return row


def _one_execution(
    root: Path,
    table: Path,
    candidate: Candidate,
    number: int,
    runtime_seed: int,
    role: str,
    rule: PanelRule,
    grid_hash: str,
) -> dict:
    cell = table / "evaluations" / f"{number:06d}"
    if cell.exists():
        request = read_json(cell / "request.json")
        if (
            int(request["runtime_seed"]) != runtime_seed
            or request["params"] != list(geometry(candidate))
            or Path(request["context"]).resolve() != (table / "fixed_context.json").resolve()
            or not (cell / "raw_result.json").exists()
        ):
            raise RuntimeError(
                "Interrupted or mismatched simulator cell requires review: " + str(cell)
            )
        raw = read_json(cell / "raw_result.json")
    else:
        raw = FixedEvaluator(root, table)(geometry(candidate), number, runtime_seed)
    return _parse_execution(
        root, table, candidate, number, runtime_seed, role, raw, rule, grid_hash
    )


def _candidate_batches(episode: Path) -> dict[str, Candidate]:
    candidates = {}
    geometries = set()
    for path in sorted((episode / "search").glob("batch_*_candidates.json")):
        for item in read_json(path):
            candidate = candidate_from_dict(item)
            key = geometry_key(candidate)
            if candidate.candidate_id in candidates or key in geometries:
                raise ValueError("Duplicate frozen candidate geometry/ID")
            candidates[candidate.candidate_id] = candidate
            geometries.add(key)
    return candidates


def _states(
    candidates: dict[str, Candidate], rows: list[dict], seeds: tuple[int, ...], rule: PanelRule
) -> list[PanelState]:
    grouped = {candidate_id: [] for candidate_id in candidates}
    for row in rows:
        grouped[row["candidate_id"]].append(row)
    return [
        panel_state(candidate_id, values, seeds, rule) for candidate_id, values in grouped.items()
    ]


def _search(
    root: Path,
    episode: Path,
    cloud: list[Candidate],
    domain: Domain,
    rule: PanelRule,
    seeds: tuple[int, ...],
    runtime_seed: int,
    table_hashes: dict[int, str],
    grid_hash: str,
    controller_seed: int,
    workers: int,
) -> tuple[Candidate | None, list[dict], dict]:
    search = episode / "search"
    search.mkdir(exist_ok=True)
    rows_path = search / "scenario_executions.csv"
    rows = _rows(rows_path)
    candidates = _candidate_batches(episode)
    progress_path = search / "search_progress.json"
    prior = read_json(progress_path) if progress_path.exists() else {}
    # A stopped process may have persisted a complete worker cell just before
    # recording its CSV row. Recover that immutable result without rerunning it.
    recorded = {(r["candidate_id"], int(r["arrival_seed"])) for r in rows}
    number_by_id = {candidate_id: i + 1 for i, candidate_id in enumerate(candidates)}
    batch_by_id = {}
    for batch_path in sorted(search.glob("batch_*_candidates.json")):
        for item in read_json(batch_path):
            batch_by_id[item["candidate_id"]] = int(batch_path.stem.split("_")[1])
    for candidate_id, candidate in candidates.items():
        number = number_by_id[candidate_id]
        for seed in seeds:
            if (candidate_id, seed) in recorded:
                continue
            table = episode / "arrival_panel" / f"table_{seed}"
            cell = table / "evaluations" / f"{number:06d}"
            if cell.exists():
                recovered = _one_execution(
                    root, table, candidate, number, runtime_seed, "SEARCH", rule, grid_hash
                )
                recovered["batch"] = batch_by_id[candidate_id]
                recovered["candidate_number"] = number
                recovered["cumulative_search_wall_seconds"] = prior.get("elapsed_seconds", 0)
                rows.append(recovered)
                recorded.add((candidate_id, seed))
    if len(recorded) != len(_rows(rows_path)):
        _csv(rows_path, rows)
    _assert_rows(rows, seeds, runtime_seed, table_hashes, grid_hash)
    if prior.get("status") == "COMPLETE":
        summary = read_json(search / "summary.json")
        selected = candidates.get(summary["selected_candidate_id"])
        return selected, rows, summary
    prior_elapsed = max(
        float(prior.get("elapsed_seconds", 0)),
        max((float(r.get("cumulative_search_wall_seconds", 0)) for r in rows), default=0),
    )
    started = time.monotonic() - prior_elapsed
    peak = 0
    first_call = prior.get("first_eligible_call")
    first_seconds = prior.get("first_eligible_seconds")
    launched_total = max(len(rows), int(prior.get("launched_calls", 0)))
    stop_reason = "HARD_CALL_CAP"
    resume_existing_batch = bool(candidates)
    while len(rows) < HARD_SEARCH_CALLS:
        elapsed = time.monotonic() - started
        if elapsed >= SOFT_SEARCH_SECONDS:
            stop_reason = "SOFT_SEARCH_WALL_TARGET"
            break
        batch_number = len(list(search.glob("batch_*_candidates.json"))) + (
            0 if resume_existing_batch else 1
        )
        if resume_existing_batch:
            batch = [
                candidate_from_dict(item)
                for item in read_json(search / f"batch_{batch_number:03d}_candidates.json")
            ]
        elif batch_number == 1:
            batch = select_initial(cloud, domain, rule)
        else:
            states = _states(candidates, rows, seeds, rule)
            grouped = {
                key: [row for row in rows if row["candidate_id"] == key] for key in candidates
            }
            batch = next_batch(
                batch=batch_number,
                candidates=candidates,
                rows_by_candidate=grouped,
                states=states,
                cloud=cloud,
                domain=domain,
                rule=rule,
                rng=np.random.default_rng(
                    np.random.SeedSequence([20260926011, batch_number, controller_seed])
                ),
            )
        if not resume_existing_batch:
            for candidate in batch:
                domain.validate(candidate)
                if candidate.candidate_id in candidates or not distinct(
                    candidate, candidates.values(), domain, 0
                ):
                    raise ValueError("Duplicate or illegal benchmark candidate")
            _json(search / f"batch_{batch_number:03d}_candidates.json", [asdict(c) for c in batch])
            candidates.update({c.candidate_id: c for c in batch})
        numbers = {candidate_id: i + 1 for i, candidate_id in enumerate(candidates)}

        def evaluate(
            candidate: Candidate, seed: int, numbers=numbers, batch_number=batch_number
        ) -> dict:
            row = _one_execution(
                root,
                episode / "arrival_panel" / f"table_{seed}",
                candidate,
                numbers[candidate.candidate_id],
                runtime_seed,
                "SEARCH",
                rule,
                grid_hash,
            )
            row["batch"] = batch_number
            row["candidate_number"] = numbers[candidate.candidate_id]
            row["cumulative_search_wall_seconds"] = time.monotonic() - started
            return row

        def record(row: dict) -> None:
            nonlocal first_call, first_seconds
            rows.append(row)
            _assert_rows(rows, seeds, runtime_seed, table_hashes, grid_hash)
            _csv(rows_path, rows)
            states_now = _states(candidates, rows, seeds, rule)
            _csv(search / "partial_candidate_states.csv", [serialize_state(s) for s in states_now])
            selected_now = select_final(states_now, rule)
            if selected_now and first_call is None:
                first_call = launched_total
                first_seconds = time.monotonic() - started
            _json(
                progress_path,
                {
                    "status": "RUNNING",
                    "completed_calls": len(rows),
                    "launched_calls": launched_total,
                    "elapsed_seconds": time.monotonic() - started,
                    "first_eligible_call": first_call,
                    "first_eligible_seconds": first_seconds,
                    "best_complete_support": max(
                        (s.passes for s in states_now if s.complete_panel), default=0
                    ),
                    "best_g_target": min(
                        (s.g_target for s in states_now if s.g_target is not None), default=None
                    ),
                },
            )

        def planned(cells) -> None:
            nonlocal launched_total
            launched_total += len(cells)
            _json(
                progress_path,
                {
                    "status": "RUNNING",
                    "completed_calls": len(rows),
                    "launched_calls": launched_total,
                    "elapsed_seconds": time.monotonic() - started,
                    "first_eligible_call": first_call,
                    "first_eligible_seconds": first_seconds,
                },
            )

        result = execute_fanout_batch(
            batch=batch,
            rows=rows,
            seed_order=seeds,
            workers=workers,
            call_room=lambda: HARD_SEARCH_CALLS - len(rows),
            deadline_reached=lambda: time.monotonic() - started >= SOFT_SEARCH_SECONDS,
            evaluate=evaluate,
            record=record,
            on_wave_planned=planned,
            rule=rule,
            allow_first_wave_past_deadline=False,
        )
        peak = max(peak, result["peak_workers"])
        states_now = _states(candidates, rows, seeds, rule)
        print(
            f"{episode.name} batch {batch_number}: {len(rows)} calls, "
            f"best {max((s.passes for s in states_now if s.complete_panel), default=0)}/{rule.panel_size}",
            flush=True,
        )
        if resume_existing_batch:
            resume_existing_batch = False
            if time.monotonic() - started < SOFT_SEARCH_SECONDS and len(rows) < HARD_SEARCH_CALLS:
                continue
        if not result["launches"]:
            stop_reason = "NO_NEW_TASKS_OR_DEADLINE"
            break
    elapsed = time.monotonic() - started
    states = _states(candidates, rows, seeds, rule)
    selected_state = select_final(states, rule)
    selected = candidates[selected_state.candidate_id] if selected_state else None
    complete = [s for s in states if s.g_target is not None]
    summary = {
        "search_status": "SEARCH_ELIGIBLE" if selected else "NO_ELIGIBLE_BID_WITHIN_BUDGET",
        "selected_candidate_id": selected.candidate_id if selected else None,
        "selected_parameters": asdict(selected) if selected else None,
        "selected_search_passes": selected_state.passes if selected_state else None,
        "selected_g_target": selected_state.g_target if selected_state else None,
        "selected_mean_objective": selected_state.mean_objective_all if selected_state else None,
        "best_complete_passes": max((s.passes for s in complete), default=0),
        "eligible_candidates": sum(s.status == "TARGET_MET_COMPLETE" for s in states),
        "total_search_calls": len(rows),
        "search_wall_seconds": elapsed,
        "first_eligible_call": first_call,
        "first_eligible_seconds": first_seconds,
        "peak_workers": peak,
        "simulator_aggregate_seconds": sum(float(r["elapsed_seconds"]) for r in rows),
        "worker_utilization_proxy": sum(float(r["elapsed_seconds"]) for r in rows)
        / max(1e-9, workers * elapsed),
        "stop_reason": stop_reason,
        "soft_deadline_crossed": elapsed >= SOFT_SEARCH_SECONDS,
        "late_task_launches_allowed": False,
    }
    _csv(search / "candidate_summary.csv", [serialize_state(s) for s in states])
    _csv(search / "timing.csv", [summary])
    _json(search / "summary.json", summary)
    _json(progress_path, {"status": "COMPLETE", **summary})
    _json(
        episode / "final" / "selected_oc_candidate.json",
        {
            "candidate": asdict(selected) if selected else None,
            "selection_rule": "complete valid panel; >=required passes; lowest mean objective over all tables",
        },
    )
    _csv(
        episode / "final" / "oc_search_panel.csv",
        [row for row in rows if selected and row["candidate_id"] == selected.candidate_id],
    )
    return selected, rows, summary


def _baseline_candidates(root: Path, contract: dict, domain: Domain) -> dict[str, Candidate | None]:
    key = contract["context"]
    v3 = pd.read_csv(root / V3_RUN / "v3_only_context_summary.csv")
    v3_row = v3.loc[v3.context == key]
    if len(v3_row) != 1:
        raise ValueError("Missing frozen pure-V3 context: " + key)
    v3_item = v3_row.iloc[0]
    if pd.isna(v3_item.weights):
        pure = None
    else:
        weights = tuple(float(x) for x in json.loads(v3_item.weights))
        pure = Candidate(
            "frozen-pure-v3", float(v3_item.Pbar), float(v3_item.R), weights, "frozen_pure_v3"
        )
    argos = pd.read_csv(root / ORIGINAL_RUN / "selected_candidates.csv", keep_default_na=False)
    argos_row = argos.loc[argos.context == key]
    if len(argos_row) != 1:
        raise ValueError("Missing frozen standard-ARGOS context: " + key)
    item = argos_row.iloc[0]
    standard = candidate_from_dict(json.loads(item.candidate)) if item.candidate else None
    for candidate in (pure, standard):
        if candidate is not None:
            domain.validate(candidate)
    return {"pure_v3": pure, "standard_argos": standard}


def _assessment(
    root: Path,
    episode: Path,
    spec: dict,
    case: dict,
    contract: dict,
    pairs: list[dict],
    selected: Candidate | None,
    domain: Domain,
    rule: PanelRule,
    grid_hash: str,
    workers: int,
) -> tuple[list[dict], dict]:
    final = episode / "final"
    baselines = _baseline_candidates(root, contract, domain)
    bids = {"argos_oc": selected, **baselines}
    _json(
        final / "frozen_comparison_bids.json",
        {
            name: asdict(candidate) if candidate is not None else None
            for name, candidate in bids.items()
        },
    )
    prepared = []
    for pair_index, pair in enumerate(pairs, 1):
        seed = int(pair["arrival_seed"])
        table = episode / "assessment" / f"pair_{pair_index:02d}_arrival_{seed}"
        context = _table(root, table, spec, case, seed, grid_hash)
        prepared.append((pair_index, pair, table, context))
    table_hashes = {
        int(p["arrival_seed"]): context["initial_job_table_hash"] for _, p, _, context in prepared
    }
    rows_path = final / "matched_assessment.csv"
    rows = _rows(rows_path)
    planned = []
    for pair_index, pair, table, _ in prepared:
        for number, (name, candidate) in enumerate(bids.items(), 1):
            if candidate is not None:
                planned.append((pair_index, pair, table, number, name, candidate))
    identities = {(r["method"], int(r["pair_index"])) for r in rows}
    if len(identities) != len(rows):
        raise ValueError("Duplicate matched assessment cell")
    for row in rows:
        seed = int(row["arrival_seed"])
        if (
            seed not in table_hashes
            or row["initial_job_table_hash"] != table_hashes[seed]
            or row["grid_signal_hash"] != grid_hash
            or int(row["runtime_seed"]) != int(pairs[int(row["pair_index"]) - 1]["runtime_seed"])
        ):
            raise ValueError("Assessment cell lost frozen identity")
    remaining = [item for item in planned if (item[4], item[0]) not in identities]
    _json(
        final / "assessment_progress.json",
        {"status": "RUNNING", "completed_cells": len(rows), "planned_cells": len(planned)},
    )
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for pair_index, pair, table, number, name, candidate in remaining:
            future = pool.submit(
                _one_execution,
                root,
                table,
                candidate,
                number,
                int(pair["runtime_seed"]),
                "HELD_OUT_ASSESSMENT",
                rule,
                grid_hash,
            )
            futures[future] = (pair_index, name)
        for future in as_completed(futures):
            pair_index, name = futures[future]
            row = future.result()
            row["method"] = name
            row["pair_index"] = pair_index
            rows.append(row)
            _csv(rows_path, rows)
            _json(
                final / "assessment_progress.json",
                {"status": "RUNNING", "completed_cells": len(rows), "planned_cells": len(planned)},
            )
    if len(rows) != len(planned) or len({(r["method"], int(r["pair_index"])) for r in rows}) != len(
        planned
    ):
        raise ValueError("Matched 30-pair assessment incomplete")
    rows.sort(key=lambda r: (int(r["pair_index"]), r["method"]))
    _csv(rows_path, rows)
    summary = {
        "status": "COMPLETE",
        "assessment_wall_seconds_this_session": time.monotonic() - start,
        "planned_cells": len(planned),
        "completed_cells": len(rows),
        "oc_assessed": selected is not None,
        "pure_v3_assessed": baselines["pure_v3"] is not None,
        "standard_argos_assessed": baselines["standard_argos"] is not None,
    }
    for name in bids:
        observed = [r for r in rows if r["method"] == name]
        summary[f"{name}_passes"] = sum(r["feasible"] for r in observed) if observed else None
    _json(final / "assessment_summary.json", summary)
    _json(final / "assessment_progress.json", summary)
    return rows, summary


def _figure(path: Path, draw) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    draw(ax)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _context_report(
    episode: Path,
    contract: dict,
    search_rows: list[dict],
    search: dict,
    assessment_rows: list[dict],
    assessment: dict,
    arrivals: list[dict],
    rule: PanelRule,
    total: float,
) -> None:
    figures = episode / "figures"
    figures.mkdir(exist_ok=True)
    grouped = {}
    timeline = []
    for row in search_rows:
        grouped.setdefault(row["candidate_id"], []).append(row)
        completed = [
            panel_state(
                candidate_id,
                values,
                tuple(
                    int(x["arrival_seed"]) for x in arrivals if x["job_type"] == rule.job_types[0]
                ),
                rule,
            )
            for candidate_id, values in grouped.items()
        ]
        full = [s for s in completed if s.complete_panel and s.g_target is not None]
        timeline.append(
            (
                float(row["cumulative_search_wall_seconds"]),
                max((s.passes for s in completed), default=0),
                min((s.g_target for s in full), default=None),
                min(
                    (s.mean_objective_all for s in full if s.status == "TARGET_MET_COMPLETE"),
                    default=None,
                ),
            )
        )

    def trend(ax, index, title, label, threshold=None):
        points = [(t / 60, item[index]) for t, *item in timeline if item[index] is not None]
        ax.plot([x for x, _ in points], [y for _, y in points], linewidth=1.8)
        if threshold is not None:
            ax.axhline(threshold, color="red", linestyle="--")
        ax.set(xlabel="Search minutes", ylabel=label, title=title)

    def support(ax):
        ax.plot([x[0] / 60 for x in timeline], [x[1] for x in timeline])
        ax.axhline(rule.required_passes, color="red", linestyle="--")
        ax.set(
            xlabel="Search minutes", ylabel="Best observed table passes", title="Support over time"
        )

    _figure(figures / "support_vs_time.png", support)
    _figure(
        figures / "gtarget_vs_time.png",
        lambda ax: trend(ax, 1, "Best complete-panel signed violation", "g_target", 0),
    )
    _figure(
        figures / "objective_vs_time.png",
        lambda ax: trend(ax, 2, "Best eligible mean objective", "Canonical objective"),
    )

    def matrix(ax):
        candidate_ids = list(grouped)[:25]
        seeds = list(dict.fromkeys(int(x["arrival_seed"]) for x in arrivals))
        values = np.full((len(candidate_ids), len(seeds)), np.nan)
        for i, candidate_id in enumerate(candidate_ids):
            for row in grouped[candidate_id]:
                values[i, seeds.index(int(row["arrival_seed"]))] = 1 if row["feasible"] else 0
        ax.imshow(values, aspect="auto", vmin=0, vmax=1, cmap="RdYlGn")
        ax.set(
            xlabel="Search arrival table",
            ylabel="First 25 candidates",
            title="Measured candidate × table feasibility",
        )

    _figure(figures / "candidate_arrival_matrix.png", matrix)

    def projection(ax):
        first = [values[0] for values in grouped.values()]
        ax.scatter(
            [r["Pbar"] for r in first],
            [r["R"] for r in first],
            c=[sum(item["feasible"] for item in values) for values in grouped.values()],
            cmap="viridis",
            vmin=0,
            vmax=rule.panel_size,
            s=22,
        )
        ax.set(xlabel="Pbar", ylabel="R", title="Measured bid geometry and panel support")

    _figure(figures / "pr_projection.png", projection)

    def failure(ax):
        names = ["tracking", *rule.job_types]
        counts = [sum(float(r["p90"]) > rule.tracking_limit for r in search_rows)]
        counts.extend(
            sum(float(r["Pj"][i]) > rule.qos_limit for r in search_rows)
            for i in range(len(rule.job_types))
        )
        ax.bar(names, counts)
        ax.tick_params(axis="x", rotation=20)
        ax.set(ylabel="Failed search scenario cells", title="Constraint failures")

    _figure(figures / "failure_breakdown.png", failure)
    lines = [
        f"# {contract['context']}",
        "",
        (
            f"Search: {search['search_status']}; "
            f"{search['total_search_calls']} simulator calls; {search['search_wall_seconds']:.1f} s."
        ),
        f"Best complete support: {search['best_complete_passes']}/{rule.panel_size}.",
        (
            f"Selected bid: {search['selected_candidate_id'] or 'none'}; "
            f"search passes: {search['selected_search_passes']}; mean objective: {search['selected_mean_objective']}."
        ),
        "",
        "## Matched fresh assessment",
        "",
        (
            "The same 30 frozen arrival/runtime pairs were used for every available method. "
            "Assessment did not affect bid selection."
        ),
        "",
    ]
    for name in ("pure_v3", "standard_argos", "argos_oc"):
        passes = assessment.get(f"{name}_passes")
        lines.append(
            f"- {name}: {passes}/30 observed passes"
            if passes is not None
            else f"- {name}: NO_SELECTED_BID; no held-out assessment"
        )
    lines.extend(
        [
            "",
            f"Total episode wall time: {total:.1f} s.",
            "This finite panel is descriptive; it is not a certified reliability probability.",
            "",
        ]
    )
    (episode / "report.md").write_text("\n".join(lines), encoding="utf8")


def _run_context(
    root: Path,
    output: Path,
    contract: dict,
    original_row: dict,
    source: dict,
    search_seed_ledger: dict,
    assessment_pairs: list[dict],
    controller_seed: int,
    workers: int,
) -> dict:
    start = time.monotonic()
    episode = output / contract["context"]
    episode.mkdir(parents=True, exist_ok=True)
    final_summary = episode / "context_summary.json"
    if final_summary.exists():
        existing = read_json(final_summary)
        if existing.get("status") == "COMPLETE":
            return existing
    spec = original16.spec_for(root, original_row, source)
    case = spec["cases"][contract["workload"]]
    names = tuple(json.loads(contract["job_types"]))
    rule = PanelRule(
        names,
        SEARCH_PANEL_SIZE,
        REQUIRED_PASSES,
        float(contract["tracking_limit"]),
        float(contract["qos_limit"]),
    )
    grid_hash = contract["grid_trace_hash"]
    anchor = int(contract["original_arrival_seed"])
    seeds = (anchor, *tuple(int(x) for x in search_seed_ledger["additional_arrival_seeds"]))
    episode_manifest = {
        "context": contract["context"],
        "workload": contract["workload"],
        "N": contract["N"],
        "U": contract["U"],
        "job_types": names,
        "original_anchor_arrival_seed": anchor,
        "search_arrival_seeds": seeds,
        "search_runtime_seed": contract["search_runtime_seed"],
        "grid_signal_hash": grid_hash,
        "historical_anchor_table_hash": contract["original_job_table_hash"],
        "original16_manifest_sha256": contract["original16_manifest_sha256"],
        "v3_breadth_manifest_sha256": contract["v3_breadth_manifest_sha256"],
        "v3_bank_manifest_sha256": contract["v3_bank_manifest_sha256"],
        "workload_sha256": contract["workload_sha256"],
        "experiment_sha256": contract["experiment_sha256"],
        "is_oc_development_context": contract["is_oc_development_context"],
    }
    for path, value in (
        (episode / "manifest.json", episode_manifest),
        (episode / "resolved_config.json", spec),
        (
            episode / "source_provenance.json",
            {
                "original16": f"{ORIGINAL_RUN}/{contract['context']}",
                "v3_baseline": V3_RUN,
                "v3_bank": contract["v3_bank_path"],
                "original16_manifest_sha256": contract["original16_manifest_sha256"],
                "v3_breadth_manifest_sha256": contract["v3_breadth_manifest_sha256"],
            },
        ),
    ):
        if path.exists() and read_json(path) != value:
            raise ValueError("Frozen episode identity changed: " + str(path))
        if not path.exists():
            _json(path, value)
    table_hashes = {}
    arrival_rows = []
    for seed in seeds:
        table = episode / "arrival_panel" / f"table_{seed}"
        original_table = root / ORIGINAL_RUN / contract["context"] if seed == anchor else None
        context = _table(
            root,
            table,
            spec,
            case,
            seed,
            grid_hash,
            contract["original_job_table_hash"] if seed == anchor else None,
            original_table,
        )
        table_hashes[seed] = context["initial_job_table_hash"]
        arrival_rows.extend(
            arrival_stats(table / "initial_jobs.csv.gz", int(context["prefill"]), names, seed)
        )
    _csv(
        episode / "arrival_panel" / "table_identity.csv",
        [
            {
                "arrival_seed": seed,
                "initial_job_table_hash": digest,
                "grid_signal_hash": grid_hash,
                "is_historical_anchor": seed == anchor,
            }
            for seed, digest in table_hashes.items()
        ],
    )
    _csv(episode / "arrival_panel" / "arrival_statistics.csv", arrival_rows)
    cloud, domain, v3_timing = _cloud(
        root, episode, contract, spec, int(contract["search_runtime_seed"])
    )
    selected, search_rows, search_summary = _search(
        root,
        episode,
        cloud,
        domain,
        rule,
        seeds,
        int(contract["search_runtime_seed"]),
        table_hashes,
        grid_hash,
        controller_seed,
        workers,
    )
    _csv(
        episode / "search" / "search_progress.csv",
        [
            {
                "completed_call": index,
                "candidate_id": row["candidate_id"],
                "batch": row["batch"],
                "candidate_number": row["candidate_number"],
                "search_elapsed_seconds": row["cumulative_search_wall_seconds"],
                "scenario_pass": row["feasible"],
            }
            for index, row in enumerate(search_rows, 1)
        ],
    )
    assessment_rows, assessment = _assessment(
        root,
        episode,
        spec,
        case,
        contract,
        assessment_pairs,
        selected,
        domain,
        rule,
        grid_hash,
        workers,
    )
    for name, filename in (
        ("argos_oc", "oc_assessment_30.csv"),
        ("pure_v3", "v3_matched_assessment_30.csv"),
        ("standard_argos", "argos_matched_assessment_30.csv"),
    ):
        _csv(
            episode / "final" / filename, [row for row in assessment_rows if row["method"] == name]
        )
    total = time.monotonic() - start
    _context_report(
        episode,
        contract,
        search_rows,
        search_summary,
        assessment_rows,
        assessment,
        arrival_rows,
        rule,
        total,
    )
    row = {
        "status": "COMPLETE",
        "context": contract["context"],
        "workload": contract["workload"],
        "N": int(contract["N"]),
        "U": float(contract["U"]),
        "is_oc_development_context": contract["is_oc_development_context"],
        "search_status": search_summary["search_status"],
        "selected_candidate_id": search_summary["selected_candidate_id"],
        "selected_parameters": search_summary["selected_parameters"],
        "search_passes": search_summary["selected_search_passes"],
        "search_mean_objective": search_summary["selected_mean_objective"],
        "search_calls": search_summary["total_search_calls"],
        "first_eligible_call": search_summary["first_eligible_call"],
        "first_eligible_seconds": search_summary["first_eligible_seconds"],
        "first_eligible_by_5min": (
            search_summary["first_eligible_seconds"] is not None
            and search_summary["first_eligible_seconds"] <= 300
        ),
        "first_eligible_by_10min": (
            search_summary["first_eligible_seconds"] is not None
            and search_summary["first_eligible_seconds"] <= 600
        ),
        "first_eligible_by_15min": (
            search_summary["first_eligible_seconds"] is not None
            and search_summary["first_eligible_seconds"] <= 900
        ),
        "first_eligible_by_20min": (
            search_summary["first_eligible_seconds"] is not None
            and search_summary["first_eligible_seconds"] <= 1200
        ),
        "search_wall_seconds": search_summary["search_wall_seconds"],
        "candidate_cloud_seconds": v3_timing["candidate_cloud_seconds"],
        "v3_bank_reused": v3_timing["bank_reused"],
        "assessment_wall_seconds_this_session": assessment["assessment_wall_seconds_this_session"],
        "assessment_cells": assessment["completed_cells"],
        "oc_assessment_passes": assessment["argos_oc_passes"],
        "v3_assessment_passes": assessment["pure_v3_passes"],
        "argos_assessment_passes": assessment["standard_argos_passes"],
        "oc_assessment_total": ASSESSMENT_PAIRS if selected else 0,
        "v3_assessment_total": ASSESSMENT_PAIRS if assessment["pure_v3_assessed"] else 0,
        "argos_assessment_total": ASSESSMENT_PAIRS if assessment["standard_argos_assessed"] else 0,
        "oc_tracking_failures": sum(
            r["method"] == "argos_oc" and float(r["p90"]) > rule.tracking_limit
            for r in assessment_rows
        ),
        "oc_qos_failures_total": sum(
            r["method"] == "argos_oc" and any(float(x) > rule.qos_limit for x in r["Pj"])
            for r in assessment_rows
        ),
        "episode_wall_seconds_this_session": total,
        "initial_table_hashes": table_hashes,
        "grid_signal_hash": grid_hash,
    }
    _json(final_summary, row)
    return row


def _aggregate(
    root: Path,
    output: Path,
    results: list[dict],
    contracts: list[dict],
    protocol: dict,
    elapsed: float,
) -> None:
    if len(results) != 16 or any(r["status"] != "COMPLETE" for r in results):
        raise ValueError("Aggregate report requires 16 complete contexts")
    _csv(output / "summary.csv", results)
    benchmark = output / "benchmark"
    benchmark.mkdir(exist_ok=True)
    _csv(benchmark / "argos_oc_16_context_summary.csv", results)
    matched = []
    failures = []
    for contract in contracts:
        episode = output / contract["context"]
        rows = _rows(episode / "final" / "matched_assessment.csv")
        by_pair = {}
        for row in rows:
            row["context"] = contract["context"]
            row["workload"] = contract["workload"]
            row["N"] = contract["N"]
            row["U"] = contract["U"]
            matched.append(row)
            by_pair.setdefault(int(row["pair_index"]), {})[row["method"]] = row
            if float(row["p90"]) > float(contract["tracking_limit"]):
                value = float(row["p90"])
                failures.append(
                    {
                        "context": contract["context"],
                        "method": row["method"],
                        "scenario": row["pair_index"],
                        "arrival_seed": row["arrival_seed"],
                        "runtime_seed": row["runtime_seed"],
                        "constraint_family": "tracking",
                        "job_type": None,
                        "threshold": contract["tracking_limit"],
                        "measured_value": value,
                        "normalized_violation": value / float(contract["tracking_limit"]) - 1,
                    }
                )
            for name, value in zip(json.loads(contract["job_types"]), row["Pj"]):
                value = float(value)
                if value > float(contract["qos_limit"]):
                    failures.append(
                        {
                            "context": contract["context"],
                            "method": row["method"],
                            "scenario": row["pair_index"],
                            "arrival_seed": row["arrival_seed"],
                            "runtime_seed": row["runtime_seed"],
                            "constraint_family": "qos",
                            "job_type": name,
                            "threshold": contract["qos_limit"],
                            "measured_value": value,
                            "normalized_violation": value / float(contract["qos_limit"]) - 1,
                        }
                    )
        for methods in by_pair.values():
            if "argos_oc" in methods:
                for baseline in ("pure_v3", "standard_argos"):
                    if baseline in methods:
                        oc, old = methods["argos_oc"], methods[baseline]
                        if (
                            oc["initial_job_table_hash"] != old["initial_job_table_hash"]
                            or oc["runtime_seed"] != old["runtime_seed"]
                            or oc["target_trace_hash"] != old["target_trace_hash"]
                        ):
                            raise ValueError("Matched comparison identities diverged")
                        methods[baseline]["oc_minus_baseline_objective"] = float(
                            oc["objective"]
                        ) - float(old["objective"])
    _csv(output / "matched_assessment.csv", matched)
    _csv(benchmark / "failure_events.csv", failures)
    comparisons = []
    for result in results:
        episode_rows = [row for row in matched if row["context"] == result["context"]]
        by_pair = {
            i: {r["method"]: r for r in episode_rows if int(r["pair_index"]) == i}
            for i in range(1, ASSESSMENT_PAIRS + 1)
        }
        for baseline in ("pure_v3", "standard_argos"):
            paired = [
                (values["argos_oc"], values[baseline])
                for values in by_pair.values()
                if "argos_oc" in values and baseline in values
            ]
            comparisons.append(
                {
                    "context": result["context"],
                    "baseline": baseline,
                    "paired_cells": len(paired),
                    "oc_passes": sum(a["feasible"] for a, _ in paired),
                    "baseline_passes": sum(b["feasible"] for _, b in paired),
                    "oc_only_pass": sum(a["feasible"] and not b["feasible"] for a, b in paired),
                    "baseline_only_pass": sum(
                        b["feasible"] and not a["feasible"] for a, b in paired
                    ),
                    "objective_difference_mean": (
                        float(
                            np.mean(
                                [float(a["objective"]) - float(b["objective"]) for a, b in paired]
                            )
                        )
                        if paired
                        else None
                    ),
                }
            )
    _csv(output / "matched_comparison.csv", comparisons)
    v3_old = pd.read_csv(root / V3_RUN / "v3_only_context_summary.csv").set_index("context")
    argos_old = pd.read_csv(root / ORIGINAL_RUN / "context_summary.csv").set_index("context")
    paper = []
    for row in results:
        key = row["context"]
        v3 = v3_old.loc[key]
        argos = argos_old.loc[key]
        bids = read_json(output / key / "final" / "frozen_comparison_bids.json")
        cells = [r for r in matched if r["context"] == key]
        paper.append(
            {
                "context": key,
                "workload": row["workload"],
                "N": row["N"],
                "U": row["U"],
                "is_oc_development_context": row["is_oc_development_context"],
                "v3_frozen_bid": bids["pure_v3"],
                "v3_original_fixed_table_feasible": bool(v3.actual_feasible),
                "v3_fresh_assessment_passes": row["v3_assessment_passes"],
                "v3_fresh_mean_objective": (
                    float(np.mean([r["objective"] for r in cells if r["method"] == "pure_v3"]))
                    if bids["pure_v3"]
                    else None
                ),
                "argos_frozen_bid": bids["standard_argos"],
                "argos_original_search_status": argos.search_status,
                "argos_original_runtime_checks_passed": argos.runtime_checks_passed,
                "argos_fresh_assessment_passes": row["argos_assessment_passes"],
                "argos_fresh_mean_objective": (
                    float(
                        np.mean([r["objective"] for r in cells if r["method"] == "standard_argos"])
                    )
                    if bids["standard_argos"]
                    else None
                ),
                "oc_frozen_bid": bids["argos_oc"],
                "oc_search_status": row["search_status"],
                "oc_first_eligible_call": row["first_eligible_call"],
                "oc_first_eligible_seconds": row["first_eligible_seconds"],
                "oc_search_wall_seconds": row["search_wall_seconds"],
                "oc_search_passes": row["search_passes"],
                "oc_fresh_assessment_passes": row["oc_assessment_passes"],
                "oc_fresh_mean_objective": (
                    float(np.mean([r["objective"] for r in cells if r["method"] == "argos_oc"]))
                    if bids["argos_oc"]
                    else None
                ),
            }
        )
    _csv(benchmark / "v3_argos_argosoc_comparison.csv", paper)
    successes = sum(r["search_status"] == "SEARCH_ELIGIBLE" for r in results)
    external = [r for r in results if not r["is_oc_development_context"]]
    external_successes = sum(r["search_status"] == "SEARCH_ELIGIBLE" for r in external)
    _figure(
        output / "figures" / "search_success_by_workload.png",
        lambda ax: (
            ax.bar(
                list(dict.fromkeys(r["workload"] for r in results)),
                [
                    sum(
                        r["search_status"] == "SEARCH_ELIGIBLE"
                        for r in results
                        if r["workload"] == w
                    )
                    for w in dict.fromkeys(r["workload"] for r in results)
                ],
            ),
            ax.set(ylabel="Eligible searches out of four", ylim=(0, 4.2)),
            ax.tick_params(axis="x", rotation=20),
        ),
    )
    _figure(
        output / "figures" / "assessment_passes.png",
        lambda ax: (
            ax.scatter(
                [
                    r["v3_assessment_passes"] if r["v3_assessment_passes"] is not None else np.nan
                    for r in results
                ],
                [
                    r["oc_assessment_passes"] if r["oc_assessment_passes"] is not None else np.nan
                    for r in results
                ],
                label="OC versus V3",
            ),
            ax.scatter(
                [
                    r["argos_assessment_passes"]
                    if r["argos_assessment_passes"] is not None
                    else np.nan
                    for r in results
                ],
                [
                    r["oc_assessment_passes"] if r["oc_assessment_passes"] is not None else np.nan
                    for r in results
                ],
                label="OC versus standard ARGOS",
            ),
            ax.plot([0, 30], [0, 30], linestyle="--", color="gray"),
            ax.set(xlabel="Baseline passes / 30", ylabel="OC passes / 30"),
            ax.legend(),
        ),
    )
    _figure(
        output / "figures" / "search_calls.png",
        lambda ax: (
            ax.bar(range(len(results)), [r["search_calls"] for r in results]),
            ax.set(xlabel="Context index", ylabel="FlexDC search calls", title="OC search effort"),
        ),
    )
    workloads = list(dict.fromkeys(r["workload"] for r in results))
    columns = [(250, 0.6), (250, 0.8), (1000, 0.6), (1000, 0.8)]
    grid = np.array(
        [
            [
                int(
                    next(r for r in results if r["workload"] == w and r["N"] == n and r["U"] == u)[
                        "search_status"
                    ]
                    == "SEARCH_ELIGIBLE"
                )
                for n, u in columns
            ]
            for w in workloads
        ]
    )

    def success_grid(ax):
        ax.imshow(grid, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
        ax.set(
            xticks=range(4),
            xticklabels=[f"N{n} U{u}" for n, u in columns],
            yticks=range(4),
            yticklabels=workloads,
            title="OC search success (8/10)",
        )
        ax.tick_params(axis="x", rotation=20)

    _figure(output / "figures" / "context_success_grid.png", success_grid)
    _figure(
        output / "figures" / "first_eligibility_time.png",
        lambda ax: (
            ax.bar(
                range(16),
                [
                    r["first_eligible_seconds"] / 60
                    if r["first_eligible_seconds"] is not None
                    else 0
                    for r in results
                ],
            ),
            ax.axhline(20, color="red", linestyle="--"),
            ax.set(
                xlabel="Context index (missing bar: no eligible bid)",
                ylabel="Minutes to first eligibility",
            ),
        ),
    )
    _figure(
        output / "figures" / "contexts_solved_vs_budget.png",
        lambda ax: (
            ax.step(
                [5, 10, 15, 20],
                [
                    sum(r[f"first_eligible_by_{minute}min"] for r in results)
                    for minute in (5, 10, 15, 20)
                ],
                where="post",
            ),
            ax.set(
                xlabel="Search budget (minutes)",
                ylabel="Contexts reaching eligibility",
                ylim=(0, 16),
            ),
        ),
    )
    _figure(
        output / "figures" / "per_context_pass_counts.png",
        lambda ax: (
            ax.plot(range(16), [r["v3_assessment_passes"] for r in results], label="pure V3"),
            ax.plot(
                range(16),
                [
                    r["argos_assessment_passes"]
                    if r["argos_assessment_passes"] is not None
                    else np.nan
                    for r in results
                ],
                label="standard ARGOS",
            ),
            ax.plot(
                range(16),
                [
                    r["oc_assessment_passes"] if r["oc_assessment_passes"] is not None else np.nan
                    for r in results
                ],
                label="ARGOS-OC",
            ),
            ax.set(xlabel="Context index", ylabel="Passes / 30 fresh pairs"),
            ax.legend(),
        ),
    )

    def failure_plot(ax):
        frame = pd.DataFrame(failures)
        if frame.empty:
            return
        counts = frame.groupby(["constraint_family", "job_type"], dropna=False).size()
        ax.bar(
            ["tracking" if family == "tracking" else str(job) for family, job in counts.index],
            counts.values,
        )
        ax.tick_params(axis="x", rotation=20)
        ax.set(ylabel="Failed method/scenario constraints", title="Fresh assessment failures")

    _figure(output / "figures" / "failure_type_breakdown.png", failure_plot)
    _figure(
        output / "figures" / "first_eligible_calls.png",
        lambda ax: (
            ax.bar(range(16), [r["first_eligible_call"] or 0 for r in results]),
            ax.set(xlabel="Context index", ylabel="Launched calls to first eligible bid"),
        ),
    )

    def objectives(ax):
        frame = pd.DataFrame(paper)
        for name, column in (
            ("V3", "v3_fresh_mean_objective"),
            ("ARGOS", "argos_fresh_mean_objective"),
            ("OC", "oc_fresh_mean_objective"),
        ):
            ax.plot(range(16), frame[column], marker=".", label=name)
        ax.set(xlabel="Context index", ylabel="Mean objective on available matched bids")
        ax.legend()

    _figure(output / "figures" / "objective_comparison.png", objectives)
    lines = [
        "# ARGOS-OC generic original-16 breadth benchmark",
        "",
        (
            f"Frozen protocol: `{protocol['version']}`. Source commit before freeze: "
            f"`{protocol['source_commit_before_freeze']}`."
        ),
        "",
        (
            f"Search-qualified contexts: **{successes}/16**, and **{external_successes}/15** "
            "excluding the OC development context. Historical standard ARGOS: 15/16; "
            "pure V3: 5/16 under their frozen search protocols."
        ),
        (
            "These denominators describe different search procedures; the 30-pair held-out "
            "comparison below is matched on fresh arrival/runtime pairs."
        ),
        "",
        "| Context | OC search | Calls | OC /30 | V3 /30 | ARGOS /30 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            f"| {row['context']} | {row['search_status']} | {row['search_calls']} | "
            f"{row['oc_assessment_passes']} | {row['v3_assessment_passes']} | "
            f"{row['argos_assessment_passes']} |"
        )
    for minute in (5, 10, 15, 20):
        lines.append(
            f"- Eligible by {minute} min: "
            f"{sum(r[f'first_eligible_by_{minute}min'] for r in results)}/16"
        )
    for key, label in (
        ("oc_assessment_passes", "ARGOS-OC"),
        ("v3_assessment_passes", "pure V3"),
        ("argos_assessment_passes", "standard ARGOS"),
    ):
        total_pass = sum(r[key] or 0 for r in results)
        total_cells = sum(r[key.replace("passes", "total")] for r in results)
        lines.append(
            f"- {label} fresh matched assessment: {total_pass}/{total_cells} observed passes"
        )
    lines.extend(
        [
            "",
            f"End-to-end wall time: {elapsed:.1f} s. ",
            (
                "The W2-short-qos5_4.5_4_3.5/N1000_U0.6 context was used in OC development "
                "and is flagged in the summary. Interpret the other 15 separately for external breadth."
            ),
            "Observed pass counts on 30 selected fresh pairs are descriptive, not certified reliability estimates.",
            (
                "W1 training jobs may extend beyond the one-hour observation horizon; retain the "
                "existing simulator's QoS interpretation."
            ),
            "",
        ]
    )
    (output / "report.md").write_text("\n".join(lines), encoding="utf8")


def _package(output: Path) -> Path:
    archive = output.with_suffix(".zip")
    permitted = {".json", ".csv", ".md", ".png"}
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as dest:
        for path in output.rglob("*"):
            if (
                not path.is_file()
                or path.suffix not in permitted
                or "evaluations" in path.parts
                or path.name == "candidate_cloud.json"
            ):
                continue
            dest.write(path, path.relative_to(output.parent))
    with zipfile.ZipFile(archive) as check:
        if check.testzip() is not None:
            raise ValueError("Final supervisor ZIP failed integrity check")
    return archive


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Frozen generic ARGOS-OC original-16 breadth benchmark"
    )
    parser.add_argument(
        "--scientific-root",
        type=Path,
        required=True,
        help="ARGOS Hybrid checkout containing the immutable original16/V3 studies",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="New or resumable ARGOS-OC benchmark directory"
    )
    parser.add_argument("--max-workers", type=int, default=10)
    parser.add_argument(
        "--validate-plan",
        action="store_true",
        help="Read-only preflight, no table generation or FlexDC calls",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.max_workers <= MAX_WORKERS:
        parser.error("--max-workers must be in [1,10]")
    root = args.scientific_root.resolve()
    source = Path(__file__).resolve().parents[3]
    protocol, contracts, search, assessment = verify_protocol(root, source)
    if args.validate_plan:
        print(
            f"VALID: {len(contracts)} contexts; panel {SEARCH_PANEL_SIZE}/{REQUIRED_PASSES}; "
            f"{ASSESSMENT_PAIRS} fresh pairs; cap {HARD_SEARCH_CALLS}/context"
        )
        return
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": 1,
        "protocol_sha256": sha256(source / "benchmark/frozen_argos_oc_breadth_protocol.json"),
        "source_head_at_start": git(source, "rev-parse", "HEAD"),
        "scientific_root_head_at_start": git(root, "rev-parse", "HEAD"),
        "source_commit_before_freeze": protocol["source_commit_before_freeze"],
        "search_seed_ledger": search,
        "assessment_seed_ledger": assessment,
        "context_contract_sha256": protocol["context_contract_sha256"],
        "max_workers": args.max_workers,
        "contexts": [c["context"] for c in contracts],
    }
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        old = read_json(manifest_path)
        for key in (
            "protocol_sha256",
            "search_seed_ledger",
            "assessment_seed_ledger",
            "context_contract_sha256",
            "max_workers",
            "contexts",
        ):
            if old[key] != manifest[key]:
                raise ValueError("Resume identity changed: " + key)
    else:
        _json(manifest_path, manifest)
    status_path = output / "run_status.json"
    if status_path.exists() and read_json(status_path)["status"] == "COMPLETE":
        print(output)
        print(output.with_suffix(".zip"))
        return
    _json(
        status_path,
        {
            "status": "RUNNING",
            "completed_contexts": sum(
                (output / c["context"] / "context_summary.json").exists() for c in contracts
            ),
        },
    )
    evidence = original16.verify_environment(root)
    by_context = {
        context_key(r["workload"], int(r["server_count"]), float(r["utilization"])): r
        for r in evidence["rows"]
    }
    started = time.monotonic()
    results = []
    try:
        for contract in contracts:
            original_row = by_context[contract["context"]]
            controller_seed = int(evidence["seed_plan"]["controller_seeds"][contract["workload"]])
            result = _run_context(
                root,
                output,
                contract,
                original_row,
                evidence["source"],
                search,
                assessment["pairs"],
                controller_seed,
                args.max_workers,
            )
            results.append(result)
            _csv(output / "summary_partial.csv", results)
            _json(
                status_path,
                {
                    "status": "RUNNING",
                    "completed_contexts": len(results),
                    "total_contexts": len(contracts),
                },
            )
            print(
                f"{contract['context']}: {result['search_status']}; "
                f"OC {result['oc_assessment_passes']}/30 fresh checks",
                flush=True,
            )
        elapsed = time.monotonic() - started
        _aggregate(output, results, contracts, protocol, elapsed)
        archive = _package(output)
        _json(
            status_path,
            {
                "status": "COMPLETE",
                "completed_contexts": 16,
                "total_contexts": 16,
                "end_to_end_seconds_this_session": elapsed,
                "archive": str(archive),
            },
        )
        _package(output)
        print(output)
        print(archive)
    except BaseException as error:
        _json(
            status_path,
            {
                "status": "INTERRUPTED_NEEDS_REVIEW",
                "completed_contexts": len(results),
                "error": repr(error),
            },
        )
        raise


if __name__ == "__main__":
    main()
