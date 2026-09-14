"""Expand and seal experiment plans without model inference or simulator calls."""

from pathlib import Path

import pandas as pd

from argos.campaign.identity import digest, frozen_core, immutable_json
from argos.campaign.ledger import validate_case_seeds, validate_ledger
from argos.campaign.workloads import generate
from argos.config import Config
from argos.context import check_context
from argos.environment import package_versions
from argos.provenance import ARTIFACT, CHECKPOINT, read_json, sha256, verify_dependencies
from argos.surrogate.weights import WEIGHT_PARAMETERIZATION
from argos.versions import OBSERVATION_SCHEMA


def load_config(data):
    data = dict(data)
    data["confirmation_seeds"] = tuple(data["confirmation_seeds"])
    config = Config(**data)
    config.validate()
    return config


def source_files(root):
    return {
        str(p.relative_to(root)).replace("\\", "/"): sha256(p)
        for p in sorted((root / "src/argos").rglob("*.py"))
    }


def campaign_identity(root, protocol):
    artifact = read_json(root / "artifact_manifest.json")
    for name, record in artifact["files"].items():
        if sha256(root / ARTIFACT / name) != record["sha256"]:
            raise ValueError("Artifact changed")
    return {
        "core": frozen_core(root, protocol["frozen_core"], protocol["core_tag"]),
        "dependencies": verify_dependencies(root),
        "artifact_manifest_sha256": sha256(root / "artifact_manifest.json"),
        "checkpoint_sha256": sha256(root / ARTIFACT / CHECKPOINT),
        "source_files": source_files(root),
        "runtime": package_versions(),
        "extraction_schema": OBSERVATION_SCHEMA,
        "weight_parameterization": WEIGHT_PARAMETERIZATION,
    }


def bank_identity(case, identity, context, workload):
    config = dict(case["settings"])
    for key in [
        "search_seed",
        "confirmation_seeds",
        "search_mode",
        "max_search_calls",
        "max_search_batches",
        "max_wall_seconds",
        "simulator_timeout_seconds",
        "run_mode",
    ]:
        config.pop(key, None)
    return {
        "schema": 1,
        "scientific_identity": identity,
        "settings": config,
        "workload_sha256": workload["sha256"],
        "ordered_jobs": workload["ordered_jobs"],
        "context": context,
        "optimizer_defaults": "Pinned inference source OptimizationSettings; full resolved settings stored in bank",
    }


def plan(root: Path, config_path: Path) -> Path:
    root = root.resolve()
    protocol = read_json(config_path)
    directory = (root / protocol["output"]).resolve()
    if not directory.is_relative_to((root / "runs").resolve()):
        raise ValueError("Campaign output must be under ARGOS runs")
    ledger = validate_ledger(root / protocol["ledger"], protocol["ledger_sha256"])
    if sha256(root / protocol["provenance"]) != protocol["provenance_sha256"]:
        raise ValueError("Provenance changed")
    identity = campaign_identity(root, protocol)
    workloads = generate(root, directory / "workloads", protocol)
    cases = []
    for declared in protocol["cases"]:
        validate_case_seeds(declared, ledger)
        case = {**declared, "settings": dict(declared["settings"])}
        w = workloads[case["workload"]]
        case["settings"].update(
            workload=w["path"], weight_policy="fixed" if w["J"] == 4 else "relative_to_equal"
        )
        c = load_config(case["settings"])
        c.weight_bounds(w["J"])
        context = check_context(root, c)
        input_hashes = {
            key: sha256(root / ".deps/FlexDC" / getattr(c, key))
            for key in ["workload", "experiment", "cluster"]
        }
        context.update(
            input_hashes=input_hashes,
            canonical_cost_sha256=sha256(root / "configs/canonical_cost_source.ini"),
            gradient_template_sha256=sha256(
                root / ".deps/FlexDC/configs/gradient_descent/gradient_descent.ini"
            ),
        )
        case.update(
            J=w["J"], workload_sha256=w["sha256"], context=context, context_hash=digest(context)
        )
        bank = bank_identity(case, identity, context, w)
        case.update(bank_id=digest(bank), bank_identity=bank)
        case["expected_logical_search_budget"] = sum(
            1 if m == "v3_only" else c.max_search_calls for m in case["methods"]
        )
        cases.append(case)
    manifest = {
        "schema": 1,
        "campaign_id": protocol["campaign_id"],
        "protocol_path": str(config_path.resolve()),
        "protocol_sha256": sha256(config_path),
        "ledger_sha256": ledger["sha256"],
        "seed_group_counts": ledger["counts"],
        "identity": identity,
        "cases": cases,
    }
    immutable_json(directory / "campaign_manifest.json", manifest)
    immutable_json(directory / "resolved_protocol.json", protocol)
    flat = []
    for case in cases:
        for method in case["methods"]:
            c = case["settings"]
            flat.append(
                {
                    k: case[k]
                    for k in ["case_id", "phase", "tier", "workload", "category", "J", "bank_id"]
                }
                | {
                    "method": method,
                    "N": c["server_count"],
                    "U": c["utilization"],
                    "scenario_seed": c["search_seed"],
                    "confirmation_seeds": str(c["confirmation_seeds"]),
                    "candidate_bank_seed": c["candidate_seed"],
                    "starts": c["starts"] if method != "simulator_only_adaptive" else 0,
                    "iterations": c["iterations"] if method != "simulator_only_adaptive" else 0,
                    "search_budget": 1 if method == "v3_only" else c["max_search_calls"],
                    "max_workers": c["max_workers"],
                    "weight_policy": c["weight_policy"],
                }
            )
    csv = pd.DataFrame(flat).to_csv(index=False).encode()
    from argos.campaign.workloads import immutable_bytes

    immutable_bytes(directory / "campaign_cases.csv", csv)
    print(pd.DataFrame(flat).to_string(index=False), flush=True)
    print(f"SEALED PLAN: {directory}; {len(cases)} contexts; {len(flat)} method cases", flush=True)
    return directory
