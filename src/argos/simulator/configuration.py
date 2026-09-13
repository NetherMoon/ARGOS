"""Strict source-preserving config generation using the pinned FlexDC generator."""

from __future__ import annotations

import configparser
import hashlib
import threading
from collections.abc import Callable
from pathlib import Path

from argos.contracts import Costs
from argos.provenance import import_file, read_json, sha256, write_json


def read_ini(path: Path) -> configparser.ConfigParser:
    config = configparser.ConfigParser(interpolation=None, strict=True)
    with path.open(encoding="utf-8") as stream:
        config.read_file(stream)
    if config.defaults():
        raise ValueError("DEFAULT overrides are not allowed in scientific configs")
    return config


def canonical_cost_provenance(root: Path) -> dict:
    path = root / "configs/canonical_cost_source.ini"
    metadata_path = root / "configs/canonical_cost_source.json"
    metadata = read_json(metadata_path)
    digest = sha256(path)
    if digest != metadata["sha256"] or digest != metadata.get("upstream_file_sha256", digest):
        raise ValueError("Canonical cost source hash mismatch")
    allowed = {"cost_function", "dr_program"}
    if set(metadata["used_sections"]) != allowed:
        raise ValueError("Canonical cost source allows only cost_function and dr_program")
    if set(metadata["ignored_sections"]) != set(read_ini(path).sections()) - allowed:
        raise ValueError("Canonical cost ignored-section metadata mismatch")
    return {
        "sha256": digest,
        "metadata_sha256": sha256(metadata_path),
        "upstream_repository": metadata.get("upstream_repository"),
        "upstream_commit": metadata.get("upstream_commit"),
        "upstream_path": metadata.get("upstream_path"),
    }


def canonical_costs(root: Path) -> Costs:
    canonical_cost_provenance(root)
    path = root / "configs/canonical_cost_source.ini"
    config = read_ini(path)
    if config["dr_program"]["program_type"] != "RSR":
        raise ValueError("RSR program required")
    costs = Costs(**{k: config.getfloat("cost_function", k) for k in Costs.__dataclass_fields__})
    costs.validate()
    return costs


_HELPER_LOCK = threading.Lock()
_REPLACERS: dict[Path, Callable] = {}


def load_ini_replacer(root: Path) -> Callable:
    """Load the pinned pure replacement function once per dependency path."""
    path = (root / ".deps/FlexDC/am_generate_paper_iso_experiment_configs.py").resolve()
    with _HELPER_LOCK:
        if path not in _REPLACERS:
            name = "_argos_ini_generator_" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
            _REPLACERS[path] = import_file(name, path).replace_ini_values
        return _REPLACERS[path]


def overlay(root: Path, source: Path, target: Path, changes: dict[tuple[str, str], str]) -> dict:
    replace_ini_values = load_ini_replacer(root)
    original = read_ini(source)
    text = source.read_text(encoding="utf-8")
    result = replace_ini_values(text, changes, source)
    record = {
        "source": str(source),
        "source_sha256": sha256(source),
        "changes": [
            {"section": s, "key": k, "old": original[s][k], "new": v}
            for (s, k), v in changes.items()
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result, encoding="utf-8")
    actual = read_ini(target)
    expected = {s: dict(original[s]) for s in original.sections()}
    for (s, k), v in changes.items():
        expected[s][k.lower()] = v
    if {s: dict(actual[s]) for s in actual.sections()} != expected:
        raise ValueError("Unexpected generated configuration change")
    record["generated_sha256"] = sha256(target)
    write_json(target.with_suffix(".audit.json"), record)
    return record


def gradient_config(root: Path, output: Path) -> Path:
    costs = canonical_costs(root)
    changes = {
        ("calculate_gradient", "psi1"): str(costs.psi1),
        ("calculate_gradient", "psi2"): str(costs.psi2),
        ("calculate_gradient", "TRACKING_ERROR_CONSTRAINT"): str(costs.tracking_error_constraint),
        ("calculate_gradient", "QOS_THRESHOLD"): str(costs.qos_constraint),
        ("gradient_driver", "beta"): str(costs.beta),
        ("gradient_driver", "rho"): str(costs.rho),
        ("dr_program", "program_type"): "RSR",
    }
    overlay(
        root, root / ".deps/FlexDC/configs/gradient_descent/gradient_descent.ini", output, changes
    )
    return output
