"""CLI orchestration, preflight gates and immutable episode manifests."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from argos.audit_provenance import source_identity
from argos.config import Config
from argos.context import check_context
from argos.controller.argos_controller import Controller
from argos.environment import package_versions
from argos.provenance import (
    ARTIFACT,
    CHECKPOINT,
    git,
    read_json,
    sha256,
    verify_dependencies,
    write_json,
)
from argos.reporting.report import report
from argos.search.candidates import Domain
from argos.search.integrity import verify_search_manifest, write_search_manifest
from argos.search.regions import extract_regions, from_snapshot, promising
from argos.simulator.configuration import canonical_cost_provenance, canonical_costs, read_ini
from argos.simulator.flexdc_adapter import FlexDCRunner
from argos.surrogate.v3_adapter import V3Adapter, resolve_device
from argos.types import Candidate, Metrics, Region, candidate_from_dict
from argos.versions import SOFTWARE_VERSION


def doctor(root: Path, config: Config) -> dict:
    config.validate()
    if config.run_mode == "paper" and git(root, "status", "--porcelain"):
        raise ValueError("Paper mode requires a clean ARGOS working tree")
    context = check_context(root, config)
    dependencies = verify_dependencies(root)
    manifest = read_json(root / "artifact_manifest.json")
    for name, expected in manifest["files"].items():
        if sha256(root / ARTIFACT / name) != expected["sha256"]:
            raise ValueError(f"Immutable artifact changed: {name}")
    costs = canonical_costs(root)
    adapter = V3Adapter(root, config.torch_threads, config.device)
    constants = adapter.loaded.constants
    if [
        costs.psi1,
        costs.psi2,
        costs.beta,
        costs.rho,
        costs.tracking_error_constraint,
        costs.qos_constraint,
    ] != [
        constants.ctrack_psi,
        constants.ctrack_mu,
        constants.qos_beta,
        constants.qos_rho,
        constants.tracking_threshold,
        constants.qos_threshold,
    ]:
        raise ValueError("V3 and canonical cost constants disagree")
    flexdc = root / ".deps/FlexDC"
    for relative in [
        config.workload,
        config.experiment,
        config.cluster,
        "configs/gradient_descent/gradient_descent.ini",
        "src/peacsim/am_data_extraction_wizard.py",
        "am_generate_paper_iso_experiment_configs.py",
    ]:
        if not (flexdc / relative).is_file():
            raise FileNotFoundError(relative)
    experiment = read_ini(flexdc / config.experiment)
    if experiment.getint("system", "simulation_duration") != 3600:
        raise ValueError("Validated FlexDC objective currently requires 3600 seconds")
    if not (flexdc / "src/peacsim" / experiment["iso"]["iso_file_path"]).resolve().is_file():
        raise FileNotFoundError("ISO signal")
    run_dir = root / "runs"
    run_dir.mkdir(exist_ok=True)
    probe = run_dir / "doctor_write_probe.json"
    write_json(probe, {"writable": True})
    probe.unlink()
    result = {
        "status": "PASS",
        "context": context,
        "run_mode": config.run_mode,
        "argos_dirty": bool(git(root, "status", "--porcelain")),
        "device_metadata": adapter.device_metadata,
        "python": sys.version,
        "platform": platform.platform(),
        "device": str(adapter.loaded.device),
        "argos_version": SOFTWARE_VERSION,
        "packages": package_versions(),
        "dependencies": dependencies,
        "checkpoint_sha256": manifest["files"][CHECKPOINT]["sha256"],
        "costs": asdict(costs),
    }
    write_json(root / "runs/doctor_environment.json", result)
    return result


def episode_identity(root: Path, config: Config) -> dict:
    flexdc = root / ".deps/FlexDC"
    return {
        "context_contract": check_context(root, config),
        "device_metadata": resolve_device(config.device, config.torch_threads)[1],
        "runtime": {
            n: importlib.metadata.version(n)
            for n in ["numpy", "pandas", "scipy", "torch", "PyYAML"]
        },
        "dependencies": verify_dependencies(root),
        "artifact_manifest_sha256": sha256(root / "artifact_manifest.json"),
        "checkpoint_sha256": sha256(root / ARTIFACT / CHECKPOINT),
        "source_files": source_identity(root),
        "context_hashes": {
            p: sha256(flexdc / p) for p in [config.workload, config.experiment, config.cluster]
        },
        "canonical_cost_sha256": sha256(root / "configs/canonical_cost_source.ini"),
        "canonical_cost_provenance": canonical_cost_provenance(root),
        "software_version": SOFTWARE_VERSION,
    }


def run_episode(root: Path, config_path: Path | None = None, resume: Path | None = None) -> Path:
    root = root.resolve()
    if resume:
        episode = resume.resolve()
        config = Config.load(episode / "resolved_config.yaml")
        manifest = read_json(episode / "manifest.json")
        if sha256(episode / "resolved_config.yaml") != manifest["resolved_config_sha256"]:
            raise ValueError("Resolved episode configuration changed")
        if "v3_search_manifest_sha256" not in manifest:
            raise ValueError("LEGACY_UNTRUSTED_SEARCH: explicit audit only; cannot resume")
        verify_search_manifest(episode / "v3", config, manifest["v3_search_manifest_sha256"])
        doctor(root, config)
        if episode_identity(root, config) != manifest["input_identity"]:
            raise ValueError("Resume source/dependency/artifact/context identity changed")
    else:
        config = Config.load(config_path)
        doctor(root, config)
        episode = root / "runs" / datetime.now(timezone.utc).strftime("argos_%Y%m%dT%H%M%S_%fZ")
        episode.mkdir(parents=True)
        config.save(episode / "resolved_config.yaml")
        write_json(
            episode / "manifest.json",
            {
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "argos_git_head": git(root, "rev-parse", "HEAD"),
                "argos_version": SOFTWARE_VERSION,
                "argos_dirty": bool(git(root, "status", "--porcelain")),
                "resolved_config_sha256": sha256(episode / "resolved_config.yaml"),
                "input_identity": episode_identity(root, config),
            },
        )
        write_json(episode / "dependency_manifest.json", read_json(root / "dependency_lock.json"))
        write_json(episode / "artifact_manifest.json", read_json(root / "artifact_manifest.json"))
    print(f"Episode: {episode}", flush=True)
    adapter = V3Adapter(root, config.torch_threads, config.device)
    workload, experiment = adapter.context(
        root / ".deps/FlexDC" / config.workload,
        root / ".deps/FlexDC" / config.experiment,
        config.server_count,
        config.utilization,
        config.search_seed,
    )
    weight_min, weight_max = config.weight_bounds(workload.job_count)
    settings = adapter.api.OptimizationSettings(
        starts=config.starts,
        iterations=config.iterations,
        random_seed=config.candidate_seed,
        weight_min=weight_min,
        weight_max=weight_max,
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

    def predict(candidate: Candidate) -> Candidate:
        if candidate.prediction:
            return candidate
        p = adapter.predict(
            workload, experiment, candidate.Pbar, candidate.R, list(candidate.weights)
        )
        metrics = Metrics(
            p["Predicted_Mean_Tracking"],
            p["Predicted_P90_Tracking"],
            tuple(p["Predicted_QoS_Probabilities"]),
            p["Predicted_Full_Objective"],
        )
        return replace(candidate, prediction=metrics)

    v3dir = episode / "v3"
    v3dir.mkdir(exist_ok=True)
    if not (v3dir / "regions.json").exists():
        if (episode / "state.json").exists() or any(
            (episode / "flexdc_raw").glob("*/attempt-*/execution.json")
        ):
            raise ValueError("Cannot regenerate V3 candidates after simulator work")
        start = time.perf_counter()
        endpoints, snapshots, trajectory = adapter.optimize(
            workload=workload,
            experiment=experiment,
            settings=settings,
            snapshot_every=config.snapshot_every,
        )
        v3_seconds = time.perf_counter() - start
        for name, frame in [
            ("endpoints", endpoints),
            ("snapshots", snapshots),
            ("starts", snapshots[snapshots.Iteration == 0]),
            ("trajectory", trajectory),
        ]:
            frame = frame.copy()
            for col in frame:
                if any(isinstance(x, (list, tuple)) for x in frame[col]):
                    frame[col] = frame[col].map(
                        lambda x: json.dumps(x) if isinstance(x, (list, tuple)) else x
                    )
            frame.to_csv(v3dir / f"{name}.csv", index=False)
        candidates = [from_snapshot(row, config.iterations) for row in snapshots.to_dict("records")]
        pool, regions = extract_regions(
            promising(candidates, config.promising_per_snapshot, domain),
            domain,
            config.max_regions,
            config.region_distance,
            config.dedupe_distance,
        )
        write_json(v3dir / "candidate_pool.json", [asdict(c) for c in pool])
        write_json(v3dir / "regions.json", [asdict(r) for r in regions])
        write_json(
            v3dir / "search_timing.json",
            {
                "wall_seconds": v3_seconds,
                "device": str(adapter.loaded.device),
                "device_metadata": adapter.device_metadata,
                "torch_threads": config.torch_threads,
                "starts": config.starts,
                "iterations": config.iterations,
                "snapshot_every": config.snapshot_every,
                "settings": asdict(settings),
                "domain": asdict(domain),
                "regions": len(regions),
            },
        )
        manifest = read_json(episode / "manifest.json")
        manifest["v3_search_manifest_sha256"] = write_search_manifest(v3dir, config)
        manifest["device_metadata"] = adapter.device_metadata
        write_json(episode / "manifest.json", manifest)
        print(
            f"V3: {len(snapshots)} snapshots, {len(pool)} distinct promising candidates, {len(regions)} regions, {v3_seconds:.2f} seconds",
            flush=True,
        )
    else:
        verify_search_manifest(
            v3dir, config, read_json(episode / "manifest.json")["v3_search_manifest_sha256"]
        )
        regions = [
            Region(
                r["region_id"],
                candidate_from_dict(r["representative"]),
                tuple(r["members"]),
                tuple(r["center"]),
                tuple(r["iterations"]),
            )
            for r in read_json(v3dir / "regions.json")
        ]
    simulator = FlexDCRunner(root, episode, config)
    controller = Controller(episode, config, domain, regions, simulator, predict)
    if resume:
        for observation in controller.state.observations:
            cache = episode / "flexdc_raw" / observation.execution_id / "observation.json"
            if not cache.is_file():
                raise ValueError("Missing completed observation cache on resume")
            if (
                simulator.evaluate(
                    observation.candidate, observation.seed, observation.phase, observation.batch
                )
                != observation
            ):
                raise ValueError("Resume state/cache observation mismatch")
    try:
        state = controller.run()
    except Exception as exc:
        # Preserve the recoverable state and produce a failure report before propagating.
        write_json(episode / "failure.json", {"type": type(exc).__name__, "message": str(exc)})
        report(episode, config, controller.state)
        raise
    summary = report(episode, config, state)
    timing = read_json(v3dir / "search_timing.json")
    summary["v3"] = timing
    summary["total_active_wall_seconds"] = timing["wall_seconds"] + state.elapsed_seconds
    write_json(episode / "summary.json", summary)
    print(f"Result: {summary['status']}; report: {episode / 'report.md'}", flush=True)
    return episode
