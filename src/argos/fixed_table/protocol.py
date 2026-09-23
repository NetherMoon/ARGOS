"""Frozen scientific inputs for the six W2 fixed-job-table episodes."""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

from argos.config import Config
from argos.context import check_context
from argos.provenance import ARTIFACT, CHECKPOINT, git, read_json, sha256
from argos.simulator.configuration import canonical_costs

ROOT = Path(__file__).resolve().parents[3]
SOURCE_SPEC = "configs/diagnostics/w2_seed_factorization.json"
SEED_PLAN = "configs/fixed_table/seed_plan.json"
EPISODE_PLAN = "configs/fixed_table/episode_plan.csv"
EXPECTED_DEPS = {
    "FlexDC": "525dc684d73ab0c6f6c479f5b54811ddf02f1221",
    "CONDOR-FLEXDC": "2b653facf31de356d8c682ee76d814bd81b8e95d",
}
CHECKPOINT_SHA = "7f60e28dfc836053064c772c95acc56eb73999b145fa314e98f7b39cf4d0c38a"
GRID_TRACE_HASH = "9b3a11b9e02c40c81b25a0a73aef2c60189f73028d162a91160a43321b384ce5"
WORKLOADS = ("W2-short-qos5_4.5_4_3.5", "W2-short-qos5555")
WORKLOAD_HASHES = {
    WORKLOADS[0]: "432b2d7a9f3eb87d305692001c25b83efa4db49387149d3f0ef523bf6ea10c15",
    WORKLOADS[1]: "086a98b3cf7733c3ac08220bb606ca59e6c583cefb06b59518ebc706856cfdeb",
}


def load_plan(root: Path = ROOT) -> tuple[dict, list[dict]]:
    seeds = read_json(root / SEED_PLAN)
    with (root / EPISODE_PLAN).open(newline="", encoding="utf8") as stream:
        rows = list(csv.DictReader(stream))
    arrival = seeds["arrival_seeds"]
    runtime = seeds["search_runtime_seed"]
    checks = seeds["final_runtime_seeds"]
    if (
        len(arrival) != 3
        or len(checks) != 3
        or len({*arrival, runtime, *checks}) != 7
        or any(
            isinstance(s, bool) or not isinstance(s, int) or not 0 <= s < 2**32
            for s in [*arrival, runtime, *checks]
        )
        or len(rows) != 6
        or {(r["workload"], int(r["arrival_seed"])) for r in rows}
        != {(w, s) for w in WORKLOADS for s in arrival}
        or any(int(r["server_count"]) != 1000 or float(r["utilization"]) != 0.6 for r in rows)
        or any(int(r["search_runtime_seed"]) != runtime for r in rows)
        or any(r["episode_path"] != f"{r['workload']}/arrival_{r['arrival_seed']}" for r in rows)
    ):
        raise ValueError("Frozen fixed-table seed/episode plan is inconsistent")
    return seeds, rows


def load_source(root: Path = ROOT) -> dict:
    """Use pinned Phase 2 context and identical dependency workload files."""
    old = read_json(root / SOURCE_SPEC)
    spec = {
        k: v
        for k, v in old.items()
        if k
        in {"fixed", "experiment_path", "cluster_path", "grid_path", "policy", "policy_parameters"}
    }
    if (
        spec["fixed"]
        != {
            "duration_seconds": 3600,
            "N": 1000,
            "U": 0.6,
            "iso_start_hour": 16,
            "randomize_iso_start": False,
            "time_granularity": 1,
            "workload_trace": "poisson",
        }
        or spec["policy"] != "AQA"
        or spec["policy_parameters"] != {"node_count_control": True}
    ):
        raise ValueError("W2 experiment or normal AQA context changed")
    spec["files"] = {
        path: digest
        for path, digest in old["files"].items()
        if not path.startswith("runs/vnext_originals/workloads/")
    }
    cases = {}
    for old_case in old["cases"]:
        name = old_case["workload"]
        if name not in WORKLOAD_HASHES or old_case["workload_sha256"] != WORKLOAD_HASHES[name]:
            raise ValueError("Historical W2 workload identity changed")
        path = f".deps/FlexDC/configs/workload/{name}.ini"
        spec["files"][path] = WORKLOAD_HASHES[name]
        cases[name] = {"workload": name, "workload_path": path, "N": 1000, "U": 0.6}
    if set(cases) != set(WORKLOADS):
        raise ValueError("Expected both W2 workload definitions")
    for path, digest in spec["files"].items():
        if sha256(root / path) != digest:
            raise ValueError("Pinned fixed-table source changed: " + path)
    spec["cases"] = cases
    return spec


def config_for(workload: str, seeds: dict, workers: int) -> Config:
    if workload not in WORKLOADS or not 1 <= workers <= 10:
        raise ValueError("Invalid fixed-table workload or worker count")
    config = replace(
        Config(),
        workload=f"configs/workload/{workload}.ini",
        search_seed=seeds["search_runtime_seed"],
        candidate_seed=seeds["controller_seeds"][workload],
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
        raise ValueError("Serious V3/ARGOS effort allocation changed")
    return config


def verify_environment(root: Path = ROOT) -> dict:
    seeds, _ = load_plan(root)
    spec = load_source(root)
    deps = {}
    for name, expected in EXPECTED_DEPS.items():
        path = root / ".deps" / name
        actual = git(path, "rev-parse", "HEAD")
        if actual != expected or git(path, "status", "--porcelain"):
            raise ValueError(f"Pinned {name} dependency mismatch")
        deps[name] = actual
    checkpoint = sha256(root / ARTIFACT / CHECKPOINT)
    if checkpoint != CHECKPOINT_SHA:
        raise ValueError("V3 checkpoint mismatch")
    artifact = read_json(root / "artifact_manifest.json")
    if artifact["directory"] != ARTIFACT or artifact["selected_checkpoint"] != CHECKPOINT:
        raise ValueError("V3 artifact manifest selection changed")
    for name, record in artifact["files"].items():
        if sha256(root / ARTIFACT / name) != record["sha256"]:
            raise ValueError("V3 artifact companion file changed: " + name)
    canonical_costs(root)
    contexts = {}
    for workload in WORKLOADS:
        config = config_for(workload, seeds, 10)
        contexts[workload] = check_context(root, config)
    return {
        "spec": spec,
        "dependencies": deps,
        "checkpoint_sha256": checkpoint,
        "artifact_manifest_sha256": sha256(root / "artifact_manifest.json"),
        "v3_contexts": contexts,
    }
