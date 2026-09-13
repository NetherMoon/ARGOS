"""Shared immutable upstream V3 exploration; ordinary core region extraction."""

import json
import time
from dataclasses import asdict, replace
from pathlib import Path

from argos.campaign.identity import digest, file_manifest, immutable_json, verify_files
from argos.provenance import read_json, write_json
from argos.search.candidates import Domain
from argos.search.regions import extract_regions, from_snapshot, promising
from argos.types import Metrics, Region, candidate_from_dict


def setup(adapter, root, config):
    workload, experiment = adapter.context(
        root / ".deps/FlexDC" / config.workload,
        root / ".deps/FlexDC" / config.experiment,
        config.server_count,
        config.utilization,
        config.search_seed,
    )
    lo, hi = config.weight_bounds(workload.job_count)
    settings = adapter.api.OptimizationSettings(
        starts=config.starts,
        iterations=config.iterations,
        random_seed=config.candidate_seed,
        weight_min=lo,
        weight_max=hi,
        r_over_p_max=config.r_over_p_max,
    )
    bounds = adapter.api.calculate_pr_bounds(workload)
    weights = adapter.api.resolve_effective_weight_bounds(
        settings, job_count=workload.job_count, server_count=config.server_count
    )
    domain = Domain(
        bounds.pbar_lower_kw_per_server,
        bounds.pbar_upper_kw_per_server,
        bounds.pr_upper_kw_per_server,
        bounds.r_lower_kw_per_server,
        config.r_over_p_max,
        (weights.final_lower,) * workload.job_count,
        (weights.final_upper,) * workload.job_count,
    )

    def predict(candidate):
        if candidate.prediction is not None:
            return candidate
        p = adapter.predict(
            workload, experiment, candidate.Pbar, candidate.R, list(candidate.weights)
        )
        return replace(
            candidate,
            prediction=Metrics(
                p["Predicted_Mean_Tracking"],
                p["Predicted_P90_Tracking"],
                tuple(p["Predicted_QoS_Probabilities"]),
                p["Predicted_Full_Objective"],
            ),
        )

    return workload, experiment, settings, bounds, domain, predict


def original_selection(api, endpoints, bounds, job_count, settings):
    return api.select_distinct_top_k(
        endpoints,
        bounds=bounds,
        job_count=job_count,
        top_k=settings.top_k,
        minimum_distance=settings.candidate_distance,
        feasibility_column="Safety_Both_Pass"
        if settings.mode == "margin_constrained"
        else "Exact_Both_Pass",
    )


def get_bank(directory: Path, case: dict, adapter, config, setup_values):
    bank = directory / "cache/v3_banks" / case["bank_id"]
    manifest_path = bank / "manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        if (
            manifest["identity"] != case["bank_identity"]
            or digest(manifest["identity"]) != case["bank_id"]
        ):
            raise ValueError("V3 bank identity mismatch")
        verify_files(bank, manifest["files"])
        return read_bank(bank), manifest, True
    bank.mkdir(parents=True, exist_ok=True)
    attempt = bank / f"attempt-{time.time_ns()}"
    attempt.mkdir()
    workload, experiment, settings, bounds, domain, _ = setup_values
    start = time.perf_counter()
    endpoints, snapshots, trajectory = adapter.optimize(
        workload=workload,
        experiment=experiment,
        settings=settings,
        snapshot_every=config.snapshot_every,
    )
    seconds = time.perf_counter() - start
    top = original_selection(adapter.api, endpoints, bounds, workload.job_count, settings)
    selected = None
    if not top.empty:
        row = top.iloc[0].to_dict()
        row["Iteration"] = settings.iterations
        selected = from_snapshot(row, settings.iterations)
        domain.validate(selected)
    candidates = [from_snapshot(row, config.iterations) for row in snapshots.to_dict("records")]
    pool, regions = extract_regions(
        promising(candidates, config.promising_per_snapshot, domain),
        domain,
        config.max_regions,
        config.region_distance,
        config.dedupe_distance,
    )
    for name, frame in [
        ("endpoints", endpoints),
        ("snapshots", snapshots),
        ("starts", snapshots[snapshots.Iteration == 0]),
        ("trajectory", trajectory),
        ("original_top_k", top),
    ]:
        frame = frame.copy()
        for col in frame:
            if any(isinstance(v, (list, tuple)) for v in frame[col]):
                frame[col] = frame[col].map(
                    lambda v: json.dumps(v) if isinstance(v, (list, tuple)) else v
                )
        frame.to_csv(attempt / (name + ".csv"), index=False)
    write_json(attempt / "selection.json", asdict(selected) if selected else None)
    write_json(attempt / "regions.json", [asdict(r) for r in regions])
    write_json(attempt / "pool.json", [asdict(c) for c in pool])
    data = {
        "identity": case["bank_identity"],
        "bank_id": case["bank_id"],
        "wall_seconds": seconds,
        "settings": asdict(settings),
        "domain": asdict(domain),
        "snapshot_count": len(snapshots),
        "region_count": len(regions),
        "completed_attempt": attempt.name,
    }
    data["files"] = {f"{attempt.name}/{k}": v for k, v in file_manifest(attempt).items()}
    immutable_json(manifest_path, data)
    return read_bank(bank), data, False


def read_bank(bank):
    manifest = read_json(bank / "manifest.json")
    attempt = bank / manifest["completed_attempt"]
    regions = [
        Region(
            r["region_id"],
            candidate_from_dict(r["representative"]),
            tuple(r["members"]),
            tuple(r["center"]),
            tuple(r["iterations"]),
        )
        for r in read_json(attempt / "regions.json")
    ]
    selected = read_json(attempt / "selection.json")
    return regions, candidate_from_dict(selected) if selected else None
