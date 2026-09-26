"""Frozen original-16 ARGOS-OC breadth inputs; no simulator calls."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

import pandas as pd

from argos.campaign.identity import verify_files
from argos.fixed_table import original16
from argos.oc_basic import runner as legacy
from argos.provenance import ARTIFACT, CHECKPOINT, git, read_json, sha256
from argos.simulator.evidence import ordered_jobs

ORIGINAL_RUN = "runs/experiments/argos_original16_fixed_table_20260923T173830Z"
V3_RUN = "runs/experiments/v3_only_breadth_16_20260926T032800Z"
OC_V1 = "runs/experiments/argos_oc_basic_w2_n1000_u06_20260926T064500Z"
SEARCH_LEDGER = "benchmark/argos_oc_breadth_search_seed_ledger.json"
ASSESSMENT_LEDGER = "benchmark/argos_oc_breadth_assessment_ledger.json"
CONTRACT_CSV = "benchmark/original16_context_contract.csv"
PROTOCOL = "benchmark/frozen_argos_oc_breadth_protocol.json"
ROOT_SEED = 2026092701
SMOKE_SEEDS = (4294967293,)
SEARCH_PANEL_SIZE = 10
REQUIRED_PASSES = 8
ASSESSMENT_PAIRS = 30
SOFT_SEARCH_SECONDS = 1200
HARD_SEARCH_CALLS = 400
MAX_WORKERS = 10
SOURCE_FILES = (
    "src/argos/oc_basic/core.py",
    "src/argos/oc_basic/generic.py",
    "src/argos/oc_basic/runner.py",
    "src/argos/oc_basic/scheduling.py",
    "src/argos/oc_basic/breadth_plan.py",
    "src/argos/oc_basic/breadth_runner.py",
    "scripts/freeze_argos_oc_breadth.py",
    "scripts/run_argos_oc_breadth.py",
    "src/argos/experimental_sa/paper_consistent/evaluator.py",
    "src/argos/experimental_sa/paper_consistent/objective.py",
    "src/argos/fixed_table/original16.py",
    "src/argos/fixed_table/simulator.py",
    "src/argos/simulator/evidence.py",
    "src/argos/search/candidates.py",
    "src/argos/search/regions.py",
    "src/argos/vnext/device.py",
    "src/argos/surrogate/v3_adapter.py",
    "src/argos/types.py",
    "configs/canonical_cost_source.ini",
)


def context_key(workload: str, n: int, u: float) -> str:
    return f"{workload}/N{n}_U{u:.1f}"


def preflight(root: Path) -> tuple[dict, list[dict]]:
    """Verify two frozen historical baselines and all 16 V3 bank identities."""
    root = root.resolve()
    evidence = original16.verify_environment(root)
    original = root / ORIGINAL_RUN
    v3 = root / V3_RUN
    original_manifest = read_json(original / "manifest.json")
    v3_manifest = read_json(v3 / "manifest.json")
    if (
        read_json(original / "run_status.json")["status"] != "COMPLETED"
        or read_json(v3 / "run_status.json")["status"] != "COMPLETE"
    ):
        raise ValueError("Frozen original-16 or V3 breadth study is incomplete")
    if (
        sha256(original / "manifest.json") != v3_manifest["frozen_argos_manifest_sha256"]
        or original_manifest["repo_head"] != v3_manifest["repo_head"]
        or original_manifest["dependency_shas"] != v3_manifest["dependency_shas"]
        or original_manifest["checkpoint_sha256"] != v3_manifest["checkpoint_sha256"]
    ):
        raise ValueError("Frozen V3 and ARGOS source/input lineage differs")
    if sha256(root / ARTIFACT / CHECKPOINT) != original_manifest["checkpoint_sha256"]:
        raise ValueError("Frozen V3 checkpoint changed")
    argos_rows = pd.read_csv(original / "context_summary.csv").to_dict("records")
    v3_rows = pd.read_csv(v3 / "v3_only_context_summary.csv").to_dict("records")
    by_argos = {
        (r["workload"], int(r["server_count"]), float(r["utilization"])): r for r in argos_rows
    }
    by_v3 = {(r["workload"], int(r["N"]), float(r["U"])): r for r in v3_rows}
    planned = {
        (r["workload"], int(r["server_count"]), float(r["utilization"])) for r in evidence["rows"]
    }
    if len(planned) != 16 or set(by_argos) != planned or set(by_v3) != planned:
        raise ValueError("Historical context matrices differ")
    contracts = []
    for episode in evidence["rows"]:
        workload = episode["workload"]
        n, u = int(episode["server_count"]), float(episode["utilization"])
        key = context_key(workload, n, u)
        old, model = by_argos[(workload, n, u)], by_v3[(workload, n, u)]
        if (
            old["job_table_hash"] != model["job_table_hash"]
            or model["grid_hash"] != original_manifest["grid_trace_hash"]
            or int(old["arrival_seed"]) != int(episode["arrival_seed"])
        ):
            raise ValueError("Historical anchor table or grid differs: " + key)
        spec = original16.spec_for(root, episode, evidence["source"])
        if spec["fixed"]["duration_seconds"] != 3600 or spec["policy"] != "AQA":
            raise ValueError("Original context duration/policy changed: " + key)
        receipt = read_json(original / key / "v3_bank_receipt.json")
        bank_rel = f"{ORIGINAL_RUN}/cache/v3_banks/{receipt['bank_id']}"
        bank = root / bank_rel
        manifest = read_json(bank / "manifest.json")
        if (
            sha256(bank / "manifest.json") != receipt["manifest_sha256"]
            or manifest["bank_id"] != receipt["bank_id"]
            or manifest["identity"]["workload"] != workload
            or manifest["identity"]["workload_sha256"]
            != spec["files"][spec["cases"][workload]["workload_path"]]
            or manifest["identity"]["experiment_sha256"] != spec["files"][spec["experiment_path"]]
            or manifest["identity"]["checkpoint"] != evidence["checkpoint_sha256"]
        ):
            raise ValueError("Historical V3 bank identity changed: " + key)
        verify_files(bank, manifest["files"])
        names = tuple(
            job.section for job in ordered_jobs(root / spec["cases"][workload]["workload_path"])
        )
        if len(names) != len(manifest["domain"]["lower"]):
            raise ValueError("V3 checkpoint weight dimension differs from configured jobs: " + key)
        contracts.append(
            {
                "context": key,
                "workload": workload,
                "N": n,
                "U": u,
                "is_oc_development_context": workload == "W2-short-qos5_4.5_4_3.5"
                and n == 1000
                and u == 0.6,
                "original_arrival_seed": int(episode["arrival_seed"]),
                "original_job_table_hash": old["job_table_hash"],
                "search_runtime_seed": int(episode["search_runtime_seed"]),
                "workload_path": spec["cases"][workload]["workload_path"],
                "workload_sha256": spec["files"][spec["cases"][workload]["workload_path"]],
                "experiment_path": spec["experiment_path"],
                "experiment_sha256": spec["files"][spec["experiment_path"]],
                "cluster_path": spec["cluster_path"],
                "cluster_sha256": spec["files"][spec["cluster_path"]],
                "grid_path": spec["grid_path"],
                "grid_sha256": spec["files"][spec["grid_path"]],
                "grid_trace_hash": original_manifest["grid_trace_hash"],
                "policy": spec["policy"],
                "policy_parameters": json.dumps(spec["policy_parameters"]),
                "duration_seconds": spec["fixed"]["duration_seconds"],
                "iso_start_hour": spec["fixed"]["iso_start_hour"],
                "job_types": json.dumps(names),
                "domain": json.dumps(manifest["domain"], sort_keys=True),
                "tracking_limit": 0.30,
                "qos_limit": 0.10,
                "cost_config_sha256": sha256(root / "configs/canonical_cost_source.ini"),
                "v3_checkpoint_sha256": evidence["checkpoint_sha256"],
                "v3_bank_path": bank_rel,
                "v3_bank_id": receipt["bank_id"],
                "v3_bank_manifest_sha256": receipt["manifest_sha256"],
                "v3_bank_original_seconds": manifest["wall_seconds"],
                "original16_manifest_sha256": sha256(original / "manifest.json"),
                "v3_breadth_manifest_sha256": sha256(v3 / "manifest.json"),
            }
        )
    return evidence, contracts


def seed_ledgers(root: Path, anchor: int) -> tuple[dict, dict]:
    excluded, hashes = legacy.historical_seed_exclusions(root)
    extra = [
        f"{OC_V1}/arrival_panel/seeds.json",
        "runs/experiments/argos_oc_1_2_existence_20260926T182000Z/manifest.json",
    ]
    for relative in extra:
        path = (
            root / relative
            if (root / relative).exists()
            else Path(__file__).resolve().parents[3] / relative
        )
        if not path.exists():
            raise FileNotFoundError("Historical OC seed ledger missing: " + str(path))
        hashes[relative] = sha256(path)
        excluded |= legacy.recursive_seed_values(read_json(path))
    excluded.add(anchor)
    excluded.add(3122970382)  # verified original-16 search runtime seed
    excluded.update(SMOKE_SEEDS)
    rng = random.Random(ROOT_SEED)
    chosen = []
    while len(chosen) < 9 + 2 * ASSESSMENT_PAIRS:
        value = rng.randrange(1, 2**32)
        if value not in excluded:
            chosen.append(value)
            excluded.add(value)
    search = {
        "schema": 1,
        "root_seed": ROOT_SEED,
        "selection_method": "Python random.Random(root_seed).randrange(1,2**32); sequential reject against source ledgers and prior draws",
        "excluded_source_sha256": hashes,
        "original_breadth_anchor_seed": anchor,
        "additional_arrival_seeds": chosen[:9],
        "search_order": "original anchor first, then additional_arrival_seeds in ledger order",
        "panel_size": SEARCH_PANEL_SIZE,
        "required_passes": REQUIRED_PASSES,
    }
    assessment = {
        "schema": 1,
        "root_seed": ROOT_SEED,
        "selection_method": search["selection_method"],
        "excluded_source_sha256": hashes,
        "pairs": [
            {"arrival_seed": chosen[9 + 2 * i], "runtime_seed": chosen[10 + 2 * i]}
            for i in range(ASSESSMENT_PAIRS)
        ],
    }
    return search, assessment


def write_preparation(root: Path, source: Path) -> dict:
    evidence, contracts = preflight(root)
    anchors = {c["original_arrival_seed"] for c in contracts}
    if len(anchors) != 1:
        raise ValueError("Original-16 contexts did not share one anchor seed")
    search, assessment = seed_ledgers(root, anchors.pop())
    destination = source / "benchmark"
    destination.mkdir(exist_ok=True)
    products = {SEARCH_LEDGER: search, ASSESSMENT_LEDGER: assessment}
    for relative, payload in products.items():
        path = source / relative
        if path.exists():
            if read_json(path) != payload:
                raise ValueError("Frozen seed ledger differs: " + relative)
        else:
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf8")
    contract_path = source / CONTRACT_CSV
    if contract_path.exists():
        with contract_path.open(newline="", encoding="utf8") as stream:
            prior = list(csv.DictReader(stream))
        normalized = [{key: str(value) for key, value in row.items()} for row in contracts]
        if prior != normalized:
            raise ValueError("Frozen context contract differs")
    else:
        with contract_path.open("w", newline="", encoding="utf8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(contracts[0]))
            writer.writeheader()
            writer.writerows(contracts)
    return {
        "contexts": len(contracts),
        "search_seed_ledger_sha256": sha256(source / SEARCH_LEDGER),
        "assessment_seed_ledger_sha256": sha256(source / ASSESSMENT_LEDGER),
        "context_contract_sha256": sha256(contract_path),
        "original16_manifest_sha256": sha256(root / ORIGINAL_RUN / "manifest.json"),
        "v3_manifest_sha256": sha256(root / V3_RUN / "manifest.json"),
        "dependency_shas": evidence["dependencies"],
    }


def freeze_protocol(root: Path, source: Path) -> dict:
    prepared = write_preparation(root, source)
    files = {
        path: sha256(source / path) if (source / path).exists() else sha256(root / path)
        for path in SOURCE_FILES
    }
    protocol = {
        "schema": 1,
        "version": "OC_GENERIC_BREADTH_1",
        "source_commit_before_freeze": git(source, "rev-parse", "HEAD"),
        "scientific_root_commit": git(root, "rev-parse", "HEAD"),
        "source_hashes": files,
        **prepared,
        "search_panel_size": SEARCH_PANEL_SIZE,
        "required_search_passes": REQUIRED_PASSES,
        "search_seed_order": "anchor_first_then_frozen_ledger",
        "search_runtime_seed": 3122970382,
        "tracking_limit": 0.30,
        "qos_limit": 0.10,
        "initial_candidates": 15,
        "initial_independent": 3,
        "refinement_candidates": 8,
        "refinement_independent": 2,
        "anchor_count": 2,
        "proposal_rule": "generic critical-constraint counts/severity/configured-order; legal symmetric P, conditional-R and weight-transfer probes",
        "probe_scales": {
            "weight": [0.01, 0.02, 0.04],
            "P": [-0.04, -0.02, -0.01, 0.01, 0.02, 0.04],
            "conditional_R": [-0.04, -0.02, 0.02, 0.04],
            "batch_multiplier": "1+0.15*(batch%7)",
            "local_radius": 0.035,
        },
        "scheduler": "deterministic_fanout_max4; at most ten concurrent workers",
        "early_rejection": "passes + remaining_unmeasured < required_search_passes",
        "selection": "complete valid panel with >=required passes; minimum mean canonical objective over every search table; then more passes, smaller g_target, candidate ID",
        "soft_search_seconds_per_context": SOFT_SEARCH_SECONDS,
        "hard_search_calls_per_context": HARD_SEARCH_CALLS,
        "assessment_pairs_per_selected_method": ASSESSMENT_PAIRS,
        "max_workers": MAX_WORKERS,
        "no_simulator_result_reuse": True,
    }
    path = source / PROTOCOL
    if path.exists() and read_json(path) != protocol:
        raise ValueError("Frozen breadth protocol changed")
    if not path.exists():
        path.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf8")
    return protocol


def verify_protocol(root: Path, source: Path) -> tuple[dict, list[dict], dict, dict]:
    protocol = read_json(source / PROTOCOL)
    _, contracts = preflight(root)
    for path, expected in protocol["source_hashes"].items():
        actual = source / path if (source / path).exists() else root / path
        if sha256(actual) != expected:
            raise ValueError("Frozen source changed: " + path)
    for key, relative in (
        ("search_seed_ledger_sha256", SEARCH_LEDGER),
        ("assessment_seed_ledger_sha256", ASSESSMENT_LEDGER),
        ("context_contract_sha256", CONTRACT_CSV),
    ):
        if sha256(source / relative) != protocol[key]:
            raise ValueError("Frozen benchmark configuration changed: " + relative)
    search = read_json(source / SEARCH_LEDGER)
    assessment = read_json(source / ASSESSMENT_LEDGER)
    if (
        len(contracts) != 16
        or len(search["additional_arrival_seeds"]) != 9
        or len(assessment["pairs"]) != ASSESSMENT_PAIRS
    ):
        raise ValueError("Frozen breadth plan incomplete")
    return protocol, contracts, search, assessment
