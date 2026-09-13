"""Strict source-preserving config generation using the pinned FlexDC generator."""

from __future__ import annotations

import configparser
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


def canonical_costs(root: Path) -> Costs:
    path = root / "configs/canonical_cost_source.ini"
    if sha256(path) != read_json(root / "configs/canonical_cost_source.json")["sha256"]:
        raise ValueError("Canonical cost source hash mismatch")
    config = read_ini(path)
    if config["dr_program"]["program_type"] != "RSR":
        raise ValueError("RSR program required")
    costs = Costs(**{k: config.getfloat("cost_function", k) for k in Costs.__dataclass_fields__})
    costs.validate()
    return costs


def overlay(root: Path, source: Path, target: Path, changes: dict[tuple[str, str], str]) -> dict:
    generator = import_file(
        "_argos_ini_generator", root / ".deps/FlexDC/am_generate_paper_iso_experiment_configs.py"
    )
    original = read_ini(source)
    text = source.read_text(encoding="utf-8")
    result = generator.replace_ini_values(text, changes, source)
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
