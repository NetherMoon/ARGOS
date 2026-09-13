"""Tamper-evident generated V3 search boundary, verified before state resumes."""

from pathlib import Path

import pandas as pd

from argos.provenance import read_json, sha256, write_json
from argos.versions import REGION_POLICY, RETENTION_POLICY, SEARCH_SCHEMA, SNAPSHOT_POLICY

FILES = (
    "starts.csv",
    "snapshots.csv",
    "endpoints.csv",
    "trajectory.csv",
    "candidate_pool.json",
    "regions.json",
    "search_timing.json",
)


def policies() -> dict:
    return {
        "schema": SEARCH_SCHEMA,
        "retention": RETENTION_POLICY,
        "regions": REGION_POLICY,
        "snapshots": SNAPSHOT_POLICY,
    }


def file_record(path: Path) -> dict:
    record = {"sha256": sha256(path)}
    if path.suffix == ".csv":
        record["rows"] = len(pd.read_csv(path))
    elif path.name in {"candidate_pool.json", "regions.json"}:
        record["rows"] = len(read_json(path))
    return record


def write_search_manifest(directory: Path, config) -> str:
    if (directory / "search_manifest.json").exists():
        raise ValueError("Search manifest already exists; cannot replace trusted generated search")
    write_json(
        directory / "search_manifest.json",
        {
            "policies": policies(),
            "snapshot_settings": {
                "starts": config.starts,
                "iterations": config.iterations,
                "snapshot_every": config.snapshot_every,
            },
            "files": {name: file_record(directory / name) for name in FILES},
        },
    )
    return sha256(directory / "search_manifest.json")


def verify_search_manifest(directory: Path, config=None, expected_hash=None) -> dict:
    path = directory / "search_manifest.json"
    if not path.is_file():
        raise ValueError("LEGACY_UNTRUSTED_SEARCH: missing manifest; explicit audit only")
    if expected_hash is not None and sha256(path) != expected_hash:
        raise ValueError("V3 search manifest hash changed")
    manifest = read_json(path)
    if manifest["policies"] != policies() or set(manifest["files"]) != set(FILES):
        raise ValueError("V3 search schema/policy/files mismatch")
    if config is not None and manifest["snapshot_settings"] != {
        "starts": config.starts,
        "iterations": config.iterations,
        "snapshot_every": config.snapshot_every,
    }:
        raise ValueError("V3 snapshot settings changed")
    for name in FILES:
        if file_record(directory / name) != manifest["files"][name]:
            raise ValueError(f"V3 generated search integrity failure: {name}")
    return manifest
