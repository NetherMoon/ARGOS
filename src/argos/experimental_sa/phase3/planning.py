"""Phase 3 provenance gates and immutable experiment-plan construction."""

from __future__ import annotations

import configparser
import csv
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

from argos.diagnostics.workload_seed_forensics import load_generator, sha
from argos.experimental_sa.paper_consistent.domain import load_domain
from argos.experimental_sa.phase3.scenarios import (
    generate_search_draws,
    generate_seed_plan,
    write_search_draws,
)

EXPECTED_SHAS = {
    "ARGOS": "6c95e4b77eebbf25f32522c5836d69759f225963",
    "FlexDC": "525dc684d73ab0c6f6c479f5b54811ddf02f1221",
    "CONDOR-FLEXDC": "2b653facf31de356d8c682ee76d814bd81b8e95d",
}
EXPECTED_CHECKPOINT = "7f60e28dfc836053064c772c95acc56eb73999b145fa314e98f7b39cf4d0c38a"
SEED_ROOT = 20260920
PHASE2B = Path(
    "runs/diagnostics/w2_seed_characterization_10x3_20260919T165931_783442Z/manifest.json"
)
PHASE2C = Path("runs/diagnostics/phase2c_sa_contract_audit_20260919T175140_507750Z/manifest.json")
PHASE3_CODE_FILES = [
    "src/argos/experimental_sa/phase3/__init__.py",
    "src/argos/experimental_sa/phase3/scenarios.py",
    "src/argos/experimental_sa/phase3/engine.py",
    "src/argos/experimental_sa/phase3/evaluator.py",
    "src/argos/experimental_sa/phase3/planning.py",
    "src/argos/experimental_sa/phase3/reporting.py",
    "src/argos/experimental_sa/phase3/runner.py",
    "scripts/run_phase3_sa_arrival_uncertainty.py",
    "tests/unit/test_phase3_sa_arrival_uncertainty.py",
    "docs/PHASE3_SA_ARRIVAL_UNCERTAINTY.md",
]
FROZEN_PLAN_FILES = [
    "seed_plan.json",
    "arrival_schedule.csv",
    "assessment_seed_panel.csv",
    "run_plan.csv",
    "search_draw_schedule/A.csv",
    "search_draw_schedule/B.csv",
    "search_draw_schedule/smoke_B.csv",
]


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf8"))


def _collect_keyed_seeds(value, key="") -> set[int]:
    found = set()
    if isinstance(value, dict):
        for name, child in value.items():
            found |= _collect_keyed_seeds(child, name.lower())
    elif isinstance(value, list):
        for child in value:
            found |= _collect_keyed_seeds(child, key)
    elif (
        "seed" in key
        and isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value < 2**32
    ):
        found.add(value)
    return found


def collect_prior_seeds(root: Path) -> set[int]:
    paths = [
        root / "configs/campaigns/seed_ledger_v1.json",
        root / "configs/vnext/seed_ledger.json",
        root / PHASE2B,
        root / "runs/diagnostics/phase2c_sa_contract_audit_20260919T175140_507750Z/smoke_plan.json",
    ]
    values = set()
    for path in paths:
        if path.exists():
            values |= _collect_keyed_seeds(_json(path))
    return values


def verify_lineage(root: Path) -> tuple[dict, dict, dict]:
    shas = {
        "ARGOS": _git(root, "rev-parse", "HEAD"),
        "FlexDC": _git(root / ".deps/FlexDC", "rev-parse", "HEAD"),
        "CONDOR-FLEXDC": _git(root / ".deps/CONDOR-FLEXDC", "rev-parse", "HEAD"),
    }
    if shas != EXPECTED_SHAS:
        raise ValueError(f"Repository lineage mismatch: {shas}")
    for dependency in [root / ".deps/FlexDC", root / ".deps/CONDOR-FLEXDC"]:
        if _git(dependency, "status", "--short"):
            raise ValueError("Pinned dependency is dirty: " + str(dependency))
    checkpoint = root / (
        "condor_set_transformer_sweep_v3_behavior_v3_best_feasibility_artifacts/"
        "condor_set_transformer_sweep_v3_behavior_v3_best_feasibility.pt"
    )
    if sha(checkpoint) != EXPECTED_CHECKPOINT:
        raise ValueError("V3 checkpoint mismatch")
    phase2b = _json(root / PHASE2B)
    phase2c = _json(root / PHASE2C)
    if phase2b.get("status") != "COMPLETE" or not phase2c.get("ready_for_phase3_design"):
        raise ValueError("Phase 2B/2C provenance is not complete")
    spec = phase2b["specification"]
    if spec["repo_shas"] != EXPECTED_SHAS:
        raise ValueError("Phase 2B lineage mismatch")
    expected = {
        "c005": (
            0.473702073097229,
            0.10366622393131254,
            [0.26254186034202576, 0.2516586482524872, 0.2489594668149948, 0.23684002459049225],
        ),
        "c007": (
            0.47039860486984253,
            0.06610638229846953,
            [0.26837557554244995, 0.25136417150497437, 0.24770696461200714, 0.23255328834056854],
        ),
    }
    for case in spec["cases"]:
        actual = (case["Pbar"], case["R"], case["weights"])
        if actual != expected[case["case"]]:
            raise ValueError("Starting candidate mismatch: " + case["case"])
    return shas, phase2b, phase2c


def create_plan(root: Path, output: Path | None = None) -> Path:
    shas, phase2b, _phase2c = verify_lineage(root)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = (
        output or root / "runs/experiments" / f"phase3_sa_arrival_uncertainty_{stamp}"
    ).resolve()
    output.mkdir(parents=True, exist_ok=False)
    spec = phase2b["specification"]
    prior = collect_prior_seeds(root)
    seed_plan = generate_seed_plan(SEED_ROOT, prior)
    (output / "seed_plan.json").write_text(json.dumps(seed_plan, indent=2), encoding="utf8")
    with (output / "arrival_schedule.csv").open("x", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["iteration", "arrival_seed"])
        writer.writeheader()
        writer.writerows(
            {"iteration": i, "arrival_seed": seed}
            for i, seed in enumerate(seed_plan["arrival_schedule"])
        )
    with (output / "assessment_seed_panel.csv").open("x", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["panel_index", "seed", "role"])
        writer.writeheader()
        writer.writerows(
            {"panel_index": i, "seed": seed, "role": "INDEPENDENT_FRESH_COUPLED"}
            for i, seed in enumerate(seed_plan["assessment_seeds"], 1)
        )
    for case_name in ["A", "B"]:
        write_search_draws(
            output / "search_draw_schedule" / f"{case_name}.csv",
            generate_search_draws(seed_plan["search_seeds"][case_name], 400, 4),
        )
    write_search_draws(
        output / "search_draw_schedule" / "smoke_B.csv",
        generate_search_draws(seed_plan["smoke"]["search_seed"], 5, 4),
    )
    config = configparser.ConfigParser()
    config.read(root / "configs/canonical_cost_source.ini")
    _tables, Experiment, Jobs = load_generator(root)
    domains = {}
    for case in spec["cases"]:
        experiment = Experiment(str(root / spec["experiment_path"]))
        experiment._utilization = case["U"]
        jobs = Jobs(str(root / case["workload_path"]))
        domains[case["case"]] = load_domain(root, "argos_v3_physical", jobs, experiment).to_dict()
    source_contract = {
        "simulator_policy_contract": "normal_v3_argos_aqa",
        "normal_import": "peacsim.aqa_runtimepolicy.AQARuntimePolicy",
        "normal_source": ".deps/FlexDC/src/peacsim/aqa_runtimepolicy.py",
        "normal_source_sha256": sha(root / ".deps/FlexDC/src/peacsim/aqa_runtimepolicy.py"),
        "legacy_import": "peacsim.AQA_runtime_policy.AQARuntimePolicy",
        "legacy_source": ".deps/FlexDC/src/peacsim/AQA_runtime_policy.py",
        "legacy_source_sha256": sha(root / ".deps/FlexDC/src/peacsim/AQA_runtime_policy.py"),
        "phase2c_evaluator": "src/argos/experimental_sa/paper_consistent/evaluator.py",
        "phase2c_evaluator_sha256": sha(
            root / "src/argos/experimental_sa/paper_consistent/evaluator.py"
        ),
        "repo_shas": shas,
        "v3_checkpoint_sha256": EXPECTED_CHECKPOINT,
        "grid_path": spec["grid_path"],
        "grid_sha256": sha(root / spec["grid_path"]),
        "expected_grid_hash": phase2b["expected_grid_hash"],
        "domains": domains,
    }
    (output / "source_contract.json").write_text(
        json.dumps(source_contract, indent=2), encoding="utf8"
    )
    run_rows = []
    mapping = [("A", "c005"), ("B", "c007")]
    for label, case_id in mapping:
        for method in ["fixed", "varying"]:
            run_rows.append(
                {
                    "trajectory": f"{label}_{method}",
                    "case": case_id,
                    "method": method,
                    "transitions": 400,
                    "nominal_evaluations": 401,
                    "runtime_seed": seed_plan["training_runtime_seed"],
                    "search_seed": seed_plan["search_seeds"][label],
                    "arrival_policy": "arrival_schedule[0] repeated"
                    if method == "fixed"
                    else "arrival_schedule[i]",
                }
            )
    with (output / "run_plan.csv").open("x", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(run_rows[0]))
        writer.writeheader()
        writer.writerows(run_rows)
    manifest = {
        "schema": 1,
        "phase": "3",
        "status": "PREPARED_PENDING_SMOKE",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "primary_factor": "workload_arrival_policy",
        "fixed_method": {
            "arrival": "one fixed generated trace",
            "runtime": "one fixed runtime seed",
        },
        "varying_method": {
            "arrival": "new predeclared trace per iteration",
            "runtime": "same fixed runtime seed",
        },
        "matched": [
            "initial candidate",
            "argos_v3_physical domain",
            "normal V3/ARGOS AQA",
            "grid signal",
            "objective",
            "feasibility",
            "temperature",
            "cooling",
            "400 transitions",
            "proposal settings",
            "per-iteration search draws",
        ],
        "context_manifest": str(PHASE2B).replace("\\", "/"),
        "phase2c_manifest": str(PHASE2C).replace("\\", "/"),
        "repo_shas": shas,
        "settings": {
            "temperature": float(config["simulated_annealing"]["temperature"]),
            "cooling_rate": float(config["simulated_annealing"]["cooling_rate"]),
            "transitions": 400,
            "smart_weight": config["simulated_annealing"].getboolean("smart_weight"),
            "p_step_ratio": float(config["step_size"]["p_step"]),
            "r_step_ratio": float(config["step_size"]["r_step"]),
            "w_step": float(config["step_size"]["w_step"]),
            "domain": "argos_v3_physical",
        },
        "call_budget": {
            "optimization": 1604,
            "assessment": 60,
            "total": 1664,
            "smoke_excluded": 12,
        },
        "assessment_no_feasible_policy": "assess predeclared best-violation point, labeled diagnostic",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
    (output / "optimization").mkdir()
    (output / "assessment").mkdir()
    (output / "smoke").mkdir()
    (output / "plots").mkdir()
    return output


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def freeze_code_and_plan_contract(root: Path, experiment: Path) -> None:
    contract_path = experiment / "source_contract.json"
    contract = _json(contract_path)
    contract["phase3_files"] = {name: sha(root / name) for name in PHASE3_CODE_FILES}
    contract["frozen_plan_files"] = {name: sha(experiment / name) for name in FROZEN_PLAN_FILES}
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf8")


def verify_frozen_contract(root: Path, experiment: Path) -> None:
    contract = _json(experiment / "source_contract.json")
    if not contract.get("phase3_files") or not contract.get("frozen_plan_files"):
        raise ValueError("Phase 3 source/plan contract is not frozen")
    for name, digest in contract["phase3_files"].items():
        if sha(root / name) != digest:
            raise ValueError("Phase 3 source changed after smoke: " + name)
    for name, digest in contract["frozen_plan_files"].items():
        if sha(experiment / name) != digest:
            raise ValueError("Frozen Phase 3 run plan changed: " + name)


def accept_reporting_only_update(root: Path, experiment: Path) -> None:
    """Update hashes only when runner/reporting are the sole source changes."""
    permitted = {
        "src/argos/experimental_sa/phase3/planning.py",
        "src/argos/experimental_sa/phase3/reporting.py",
        "src/argos/experimental_sa/phase3/runner.py",
        "tests/unit/test_phase3_sa_arrival_uncertainty.py",
    }
    contract_path = experiment / "source_contract.json"
    contract = _json(contract_path)
    for name, digest in contract["phase3_files"].items():
        if name not in permitted and sha(root / name) != digest:
            raise ValueError("Non-reporting source changed after scientific run: " + name)
    for name, digest in contract["frozen_plan_files"].items():
        if sha(experiment / name) != digest:
            raise ValueError("Frozen Phase 3 run plan changed: " + name)
    for name in permitted:
        contract["phase3_files"][name] = sha(root / name)
    contract["reporting_only_recovery"] = (
        "Accepted case-label plotting fix after all scientific cells completed"
    )
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf8")
