"""Compare recorded provenance independently of historical raw-data reconstruction."""

import subprocess
from pathlib import Path

from argos.provenance import ARTIFACT, CHECKPOINT, git, read_json, sha256
from argos.simulator.configuration import canonical_cost_provenance


def source_identity(root: Path) -> dict:
    return {str(p.relative_to(root)): sha256(p) for p in sorted((root / "src/argos").rglob("*.py"))}


def _dependency(root: Path, name: str) -> dict:
    path = root / ".deps" / name
    return {
        "commit": git(path, "rev-parse", "HEAD"),
        "dirty": bool(git(path, "status", "--porcelain")),
        "url": git(path, "remote", "get-url", "origin").removesuffix(".git"),
    }


def _artifact(root: Path) -> dict:
    path = root / "artifact_manifest.json"
    manifest = read_json(path)
    return {
        "sha256": sha256(path),
        "files_match": all(
            sha256(root / ARTIFACT / name) == item["sha256"]
            for name, item in manifest["files"].items()
        ),
    }


def _canonical_cost(root: Path) -> dict:
    # Preserve observed bytes even when metadata validation fails, so a changed
    # cost source is reported as MISMATCH rather than an unavailable environment.
    metadata = read_json(root / "configs/canonical_cost_source.json")
    value = {
        "sha256": sha256(root / "configs/canonical_cost_source.ini"),
        "metadata_sha256": sha256(root / "configs/canonical_cost_source.json"),
        "upstream_repository": metadata.get("upstream_repository"),
        "upstream_commit": metadata.get("upstream_commit"),
        "upstream_path": metadata.get("upstream_path"),
    }
    try:
        canonical_cost_provenance(root)
        value["metadata_valid"] = True
    except ValueError:
        value["metadata_valid"] = False
    return value


def current_provenance(root: Path) -> dict:
    collectors = {
        "argos_source": lambda: {
            "head": git(root, "rev-parse", "HEAD"),
            "dirty": bool(git(root, "status", "--porcelain")),
            "files": source_identity(root),
        },
        "flexdc": lambda: _dependency(root, "FlexDC"),
        "condor_flexdc": lambda: _dependency(root, "CONDOR-FLEXDC"),
        "checkpoint": lambda: sha256(root / ARTIFACT / CHECKPOINT),
        "artifact_manifest": lambda: _artifact(root),
        "canonical_cost_source": lambda: _canonical_cost(root),
        "context_contract": lambda: sha256(root / "configs/v3_context_contract.json"),
    }
    result = {}
    for name, collect in collectors.items():
        try:
            result[name] = {"value": collect(), "error": None}
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            result[name] = {"value": None, "error": f"{type(exc).__name__}: {exc}"}
    return result


def recorded_provenance(manifest: dict) -> dict:
    identity = manifest.get("input_identity", manifest.get("identity", {}))

    def dependency(name):
        d = identity.get("dependencies", {}).get(name, {})
        return {k: d.get(k) for k in ("commit", "dirty", "url")}

    return {
        "argos_source": {
            "head": manifest.get("argos_git_head"),
            "dirty": manifest.get("argos_dirty"),
            "files": identity.get("source_files"),
        },
        "flexdc": dependency("FlexDC"),
        "condor_flexdc": dependency("CONDOR-FLEXDC"),
        "checkpoint": identity.get("checkpoint_sha256"),
        "artifact_manifest": {
            "sha256": identity.get("artifact_manifest_sha256"),
            "files_match": True,
        },
        "canonical_cost_source": identity.get(
            "canonical_cost_provenance",
            {
                "sha256": identity.get("canonical_cost_sha256"),
                "metadata_sha256": None,
                "upstream_repository": None,
                "upstream_commit": None,
                "upstream_path": None,
            },
        ),
        "context_contract": identity.get("context_contract", {}).get("contract_sha256"),
    }


def audit_provenance(root: Path, manifest: dict, allow_historical: bool = False) -> dict:
    recorded = recorded_provenance(manifest)
    current = current_provenance(root)
    dimensions = {}
    for name, actual in current.items():
        expected, value = recorded[name], actual["value"]
        missing = expected is None
        mismatch = False
        if value is not None and expected is not None:
            if isinstance(expected, dict):
                missing = any(v is None for v in expected.values())
                mismatch = any(v is not None and value.get(k) != v for k, v in expected.items())
            else:
                mismatch = expected != value
        status = (
            "UNAVAILABLE"
            if value is None
            else "MISMATCH"
            if mismatch
            else "HISTORICAL"
            if missing and allow_historical
            else "UNAVAILABLE"
            if missing
            else "MATCH"
        )
        field_matches = (
            {
                k: None if v is None or value is None else value.get(k) == v
                for k, v in expected.items()
            }
            if isinstance(expected, dict)
            else None
        )
        if (
            name == "canonical_cost_source"
            and value is not None
            and value.get("metadata_valid") is False
        ):
            status = "MISMATCH"
        dimensions[name] = {
            "status": status,
            "recorded": expected,
            "current": value,
            "recorded_fields_missing": missing,
            "field_matches": field_matches,
            "error": actual["error"],
        }
    exact = all(d["status"] == "MATCH" for d in dimensions.values())
    return {
        "status": "MATCH" if exact else "HISTORICAL" if allow_historical else "MISMATCH",
        "exact_match": exact,
        "historical_audit_allowed": allow_historical,
        "dimensions": dimensions,
    }
