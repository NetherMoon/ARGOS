"""Phase 2B orchestration: reuse the proven Phase 2 worker; never resimulate old cells."""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from argos.contracts import assessment
from argos.diagnostics import seed_factorization as pilot
from argos.diagnostics.seed_factorization_worker import (
    JOB_COLUMNS,
    atomic_json,
    create_initial,
    run_cell,
)
from argos.diagnostics.workload_seed_forensics import (
    arrival_hash,
    read_json,
    safe_path,
    sha,
    summarize,
    table_hash,
    write_csv,
)
from argos.types import observation_from_dict

CONFIG = "configs/diagnostics/w2_seed_characterization_10x3.json"
SHARED_WORKER = "src/argos/diagnostics/seed_factorization_worker.py"
TOOL_FILES = [
    "src/argos/diagnostics/seed_characterization.py",
    "src/argos/diagnostics/seed_characterization_reporting.py",
    "scripts/run_w2_seed_characterization_10x3.py",
    "docs/W2_SEED_CHARACTERIZATION_2B.md",
    SHARED_WORKER,
]


def verify_archive(directory, expected_zip, expected_manifest):
    if (
        sha(Path(str(directory) + ".zip")) != expected_zip
        or sha(directory / "manifest.json") != expected_manifest
    ):
        raise ValueError("Authoritative artifact identity changed")
    manifest = read_json(directory / "manifest.json")
    hashes = manifest.get("output_file_hashes") or read_json(directory / "artifact_hashes.json")
    for relative, expected in hashes.items():
        if sha(safe_path(directory, relative)) != expected:
            raise ValueError(f"Historical artifact hash mismatch: {relative}")
    with zipfile.ZipFile(str(directory) + ".zip") as z:
        if z.testzip() is not None:
            raise ValueError("Historical ZIP CRC failure")
        for item in z.infolist():
            if item.is_dir():
                continue
            relative = Path(item.filename)
            if relative.parts[0] == directory.name:
                relative = Path(*relative.parts[1:])
            if z.read(item) != safe_path(directory, relative).read_bytes():
                raise ValueError("Historical ZIP/directory mismatch")
    return manifest


def select_seeds(root, config):
    excluded = {20, 21, 22, *config["historical_seed_union"]}
    for relative, expected in config["exclusion_ledgers"].items():
        if sha(root / relative) != expected:
            raise ValueError("Seed exclusion ledger changed")
        ledger = read_json(root / relative)
        excluded.update(v for values in ledger["groups"].values() for v in values)
    rng = random.Random(config["selection_root_seed"])
    seeds = []
    while len(seeds) < 7:
        value = rng.randrange(1, 2**32)
        if value not in excluded and value not in seeds:
            seeds.append(value)
    if seeds != config["new_seeds"] or len(excluded) != config["excluded_count"]:
        raise ValueError("Frozen new seed selection no longer reproduces")
    if sha(root / config["panel_path"]) != config["panel_sha256"]:
        raise ValueError("Frozen panel CSV changed")
    panel = pd.read_csv(root / config["panel_path"])
    if panel.seed.tolist() != seeds or panel.already_used.any():
        raise ValueError("Invalid new-seed panel")
    return seeds


def plan_runs(specification, seeds):
    rows = []
    for case in specification["cases"]:
        if set(seeds) & set(case["seeds"]) or len(set(seeds)) != 7:
            raise ValueError("New seeds overlap old axes or each other")
        for seed in seeds:
            for role, runtime in [
                ("COUPLED_NEW", seed),
                *[("FACTORIZATION_NEW", r) for r in case["seeds"]],
            ]:
                rows.append(
                    {
                        "plan_index": len(rows) + 1,
                        "case": case["case"],
                        "workload": case["workload"],
                        "candidate_id": case["candidate_id"],
                        "arrival_seed": seed,
                        "runtime_seed": runtime,
                        "role": role,
                        "cell_id": pilot.cell_name(case["case"], seed, runtime),
                        "Pbar": case["Pbar"],
                        "R": case["R"],
                        "weights": json.dumps(case["weights"]),
                        "initial_reference_key": f"{case['case']}_{seed}",
                    }
                )
    if len(rows) != 56 or len({r["cell_id"] for r in rows}) != 56:
        raise ValueError("Expected exactly 56 distinct new cells")
    return rows


def load_inputs(root):
    config = read_json(root / CONFIG)
    # This validates all pinned simulator/config/cost sources and the exact historical candidates.
    specification = pilot.validate(root, root / "configs/diagnostics/w2_seed_factorization.json")
    phase1 = root / config["phase1_directory"]
    phase2 = root / config["phase2_directory"]
    verify_archive(phase1, config["phase1_zip_sha256"], config["phase1_manifest_sha256"])
    old = verify_archive(phase2, config["phase2_zip_sha256"], config["phase2_manifest_sha256"])
    if (
        specification != old["specification"]
        or sha(root / "configs/diagnostics/w2_seed_factorization.json")
        != old["specification_sha256"]
    ):
        raise ValueError(
            "Current candidate/context/panels disagree with the actual completed Phase 2 specification"
        )
    for relative, expected in config["phase2_tool_baseline"].items():
        # Only the documented reference/plan extension is allowed to differ. Its new version is frozen per run.
        if relative != SHARED_WORKER and sha(root / relative) != expected:
            raise ValueError(f"Undeclared Phase 2 tooling change: {relative}")
    checks = pd.read_csv(phase2 / "replay_checks.csv")
    if (
        old["status"] != "COMPLETE"
        or old["completed_cells"] != 18
        or len(checks) != 60
        or not checks.passed.all()
        or checks.absolute_difference.dropna().max() != 0
    ):
        raise ValueError("The saved exact historical replay gate did not pass")
    old_results = []
    for case in specification["cases"]:
        for arrival in case["seeds"]:
            for runtime in case["seeds"]:
                result = pilot.completed_cell(
                    phase2,
                    pilot.cell_name(case["case"], arrival, runtime),
                    old["input_fingerprint"],
                )
                if result is None:
                    raise ValueError("Missing old matrix cell; rerunning it is prohibited")
                old_results.append(result)
    pilot.invariants(old, old_results)
    historical = pd.read_csv(phase1 / "historical_outcomes.csv", float_precision="round_trip")
    traces = pd.read_csv(phase1 / "trace_hashes.csv")
    confirmations = []
    for case in specification["cases"]:
        for seed in config["old_fixed_confirmation_seeds"][case["case"]]:
            row = historical[(historical.case == case["case"]) & (historical.seed == seed)].iloc[0]
            if row.phase != "fresh_confirmation":
                raise ValueError(
                    "Goal A must reuse actual fresh confirmations, not selected pilot diagonals"
                )
            source = read_json(root / row.source_artifact)
            entry = source[int(row.source_observation_index)]
            observation = observation_from_dict(entry.get("observation", entry))
            for key in ["candidate_id", "Pbar", "R"]:
                if getattr(observation.candidate, key) != case[key]:
                    raise ValueError("Historical confirmation candidate mismatch")
            if list(observation.candidate.weights) != case["weights"] or observation.seed != seed:
                raise ValueError("Historical confirmation weights/seed mismatch")
            qualified = assessment(observation)
            if (
                observation.metrics.p90 != row.p90
                or list(observation.metrics.pj) != json.loads(row.Pj)
                or observation.metrics.objective != row.objective
                or qualified["per_job_evidence_counts"] != json.loads(row.evidence_counts)
                or qualified["evidence_qualified_feasible"] != bool(row.evidence_qualified_pass)
            ):
                raise ValueError("Historical confirmation outcome mismatch")
            trace = traces[(traces.workload == case["workload"]) & (traces.seed == seed)].iloc[0]
            confirmations.append(
                {
                    "cell_id": pilot.cell_name(case["case"], seed, seed),
                    "case": case["case"],
                    "workload": case["workload"],
                    "candidate_id": case["candidate_id"],
                    "arrival_seed": seed,
                    "runtime_seed": seed,
                    "Pbar": case["Pbar"],
                    "R": case["R"],
                    "weights": case["weights"],
                    "p90": row.p90,
                    "Pj": json.loads(row.Pj),
                    "objective": row.objective,
                    "evidence_counts": json.loads(row.evidence_counts),
                    "evidence_qualified_pass": bool(row.evidence_qualified_pass),
                    "initial_job_table_hash": trace.full_table_sha256,
                    "arrival_hash": trace.arrival_sha256,
                    "grid_signal_hash": old["expected_grid_hash"],
                    "target_trace_hash": old["expected_target_hashes"][case["case"]],
                    "status": "COMPLETE",
                    "origin": "ORIGINAL_CONFIRMATION",
                    "role": "COUPLED_OLD",
                    "source_artifact": row.source_artifact,
                    "source_sha256": row.source_sha256,
                    "initial_hash_evidence": "Phase 1 reconstruction; original runtime hash not retained",
                    "grid_hash_evidence": "fixed-context reference; original confirmation trace not rehashed",
                }
            )
    seeds = select_seeds(root, config)
    return config, specification, old, old_results, confirmations, plan_runs(specification, seeds)


def run_identity(root, config):
    files = {relative: sha(root / relative) for relative in TOOL_FILES}
    value = {
        "configuration_sha256": sha(root / CONFIG),
        "configuration": config,
        "tool_files": files,
    }
    return {**value, "input_fingerprint": pilot.digest(value)}


def setup(root, output, identity, specification, old, old_results, confirmations, plan):
    inputs = output / "inputs"
    inputs.mkdir()
    (output / "cells").mkdir()
    (output / "initial_jobs").mkdir()
    config = identity["configuration"]
    phase1, phase2 = root / config["phase1_directory"], root / config["phase2_directory"]
    shutil.copyfile(root / config["panel_path"], output / "new_seed_panel.csv")
    write_csv(output / "new_run_plan.csv", pd.DataFrame(plan))
    atomic_json(inputs / "old_matrix_results.json", old_results)
    atomic_json(inputs / "old_fresh_confirmations.json", confirmations)
    for name in [
        "per_job_run_summary.csv",
        "qos_accounting.csv",
        "queue_summary.csv",
        "replay_checks.csv",
    ]:
        shutil.copyfile(phase2 / name, inputs / ("phase2_" + name))
    shutil.copyfile(phase1 / "per_seed_per_job_summary.csv", inputs / "phase1_arrival_summary.csv")
    for case in specification["cases"]:
        shutil.copyfile(
            phase2 / "inputs" / (case["case"] + "_actual_grid_target.csv.gz"),
            inputs / (case["case"] + "_actual_grid_target.csv.gz"),
        )
        shutil.copyfile(root / case["workload_path"], inputs / (case["workload"] + ".ini"))
        for seed in case["seeds"]:
            shutil.copyfile(
                phase2 / "initial_jobs" / f"{case['case']}_{seed}.csv.gz",
                output / "initial_jobs" / f"{case['case']}_{seed}.csv.gz",
            )
    for name, relative in [
        ("experiment.ini", specification["experiment_path"]),
        ("cluster.ini", specification["cluster_path"]),
        ("costs.ini", "configs/canonical_cost_source.ini"),
    ]:
        shutil.copyfile(root / relative, inputs / name)
    for relative in TOOL_FILES:
        shutil.copyfile(root / relative, inputs / Path(relative).name)
    shutil.copyfile(root / "docs/W2_SEED_CHARACTERIZATION_2B.md", output / "source_audit.md")
    lineage = []
    for row in confirmations:
        lineage.append(
            {
                "case": row["case"],
                "role": "GOAL_A_ORIGINAL_FRESH",
                "arrival_seed": row["arrival_seed"],
                "runtime_seed": row["runtime_seed"],
                "source_artifact": row["source_artifact"],
                "source_sha256": row["source_sha256"],
            }
        )
    for row in old_results:
        path = phase2 / "cells" / row["cell_id"] / "result.json"
        lineage.append(
            {
                "case": row["case"],
                "role": "GOAL_B_ORIGINAL_MATRIX",
                "arrival_seed": row["arrival_seed"],
                "runtime_seed": row["runtime_seed"],
                "source_artifact": path.relative_to(root).as_posix(),
                "source_sha256": sha(path),
            }
        )
    write_csv(output / "existing_seed_lineage.csv", pd.DataFrame(lineage))
    links = {
        "phase1": {
            "path": config["phase1_directory"],
            "manifest_sha256": config["phase1_manifest_sha256"],
            "zip_sha256": config["phase1_zip_sha256"],
        },
        "phase2": {
            "path": config["phase2_directory"],
            "manifest_sha256": config["phase2_manifest_sha256"],
            "zip_sha256": config["phase2_zip_sha256"],
        },
        "source_observations": lineage,
        "old_runtime_series": "Referenced in Phase 2 ZIP, not duplicated here; merged old aggregate summaries are included.",
        "missing_detail": "c007 seed144392579 original confirmation has metrics and Phase1 arrival reconstruction; no Phase2 runtime queue/job detail. Never invented or rerun.",
    }
    atomic_json(output / "provenance_links.json", links)
    manifest = {
        **identity,
        "tool": "argos.seed_characterization",
        "version": "1.0",
        "phase": "2B",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PLANNED",
        "specification": deepcopy(specification),
        "new_run_plan": plan,
        "maximum_new_runs": 56,
        "existing_matrix_runs_reused": 18,
        "existing_confirmations_reused": 6,
        "expected_grid_hash": old["expected_grid_hash"],
        "expected_target_hashes": old["expected_target_hashes"],
        "repo_shas": specification["repo_shas"],
        "runtime": specification["runtime"],
        "python_executable": sys.executable,
        "frozen_runtime_axes": {c["case"]: c["seeds"] for c in specification["cases"]},
        "arrival_axes": {
            c["case"]: c["seeds"] + config["new_seeds"] for c in specification["cases"]
        },
        "working_tree_status": pilot.git(root, "status", "--porcelain"),
        "retries": [],
        "replay_gate": "All 60 existing historical replay checks exactly passed; reused, not rerun",
    }
    manifest["setup_hashes"] = {
        p.relative_to(output).as_posix(): sha(p)
        for p in output.rglob("*")
        if p.is_file() and p.name != ".factorization.lock"
    }
    atomic_json(output / "manifest.json", manifest)
    return manifest


def prepare_new_arrivals(root, output, manifest):
    if "preparation_sha256" in manifest:
        if sha(output / "prepared_initial_states.json") != manifest["preparation_sha256"]:
            raise ValueError("Frozen prepared states changed")
        prepared = read_json(output / "prepared_initial_states.json")
        if prepared["specification"] != manifest["specification"]:
            raise ValueError("Manifest initial-state references changed")
        for rel, expected in prepared["file_hashes"].items():
            if sha(safe_path(output, rel)) != expected:
                raise ValueError("Prepared initial file changed")
        return manifest
    if any((output / "cells").iterdir()):
        raise ValueError("Cannot prepare/rebuild references after executions have started")
    spec = deepcopy(manifest["specification"])
    summaries = []
    for case in spec["cases"]:
        case["initial_references"] = deepcopy(case["historical"])
        case["seeds"] = manifest["arrival_axes"][case["case"]]
        for seed in manifest["configuration"]["new_seeds"]:
            tables, exp, jobs, trace, table, prefill = create_initial(
                root, spec, case, seed, require_reference=False
            )
            case["initial_references"].append(
                {
                    "seed": seed,
                    "initial_job_table_hash": table_hash(table),
                    "arrival_hash": arrival_hash(trace),
                }
            )
            write_csv(
                output / "initial_jobs" / f"{case['case']}_{seed}.csv.gz",
                pd.DataFrame(table.T, columns=JOB_COLUMNS),
            )
            stats, _bins = summarize(
                trace,
                case["workload"],
                seed,
                tables.generate_arrival_rates(exp, jobs),
                3600,
                prefill,
                jobs.all_jobs,
            )
            summaries.extend(
                {**row, "case": case["case"], "origin": "NEW_PREDECLARED"} for row in stats
            )
    # Shared-seed arrivals across the two workload definitions must remain exactly identical.
    for seed in manifest["configuration"]["new_seeds"]:
        hashes = [
            next(r for r in c["initial_references"] if r["seed"] == seed)["arrival_hash"]
            for c in spec["cases"]
        ]
        if len(set(hashes)) != 1:
            raise ValueError("Same-seed arrivals differ between W2 contexts")
    old = pd.read_csv(output / "inputs/phase1_arrival_summary.csv", float_precision="round_trip")
    old["case"] = old.workload.map({c["workload"]: c["case"] for c in spec["cases"]})
    old["origin"] = "PHASE1_REUSED"
    write_csv(
        output / "arrival_diagnostics.csv",
        pd.DataFrame([*old.to_dict("records"), *summaries]),
    )
    prepared = {
        "specification": spec,
        "file_hashes": {
            p.relative_to(output).as_posix(): sha(p) for p in (output / "initial_jobs").glob("*.gz")
        },
    }
    prepared["file_hashes"]["arrival_diagnostics.csv"] = sha(output / "arrival_diagnostics.csv")
    atomic_json(output / "prepared_initial_states.json", prepared)
    manifest["specification"] = spec
    manifest["preparation_sha256"] = sha(output / "prepared_initial_states.json")
    atomic_json(output / "manifest.json", manifest)
    return manifest


def validate_result(manifest, row, result):
    if (result["case"], result["arrival_seed"], result["runtime_seed"]) != (
        row["case"],
        row["arrival_seed"],
        row["runtime_seed"],
    ):
        raise ValueError("Completed result disagrees with planned identity")
    case = next(c for c in manifest["specification"]["cases"] if c["case"] == row["case"])
    ref = next(r for r in case["initial_references"] if r["seed"] == row["arrival_seed"])
    for field in ["initial_job_table_hash", "arrival_hash"]:
        if result[field] != ref[field]:
            raise ValueError("Initial-state invariant failed")
    if (
        result["grid_signal_hash"] != manifest["expected_grid_hash"]
        or result["target_trace_hash"] != manifest["expected_target_hashes"][row["case"]]
    ):
        raise ValueError("Grid/target invariant failed")
    for field in ["Pbar", "R", "weights"]:
        if result[field] != case[field]:
            raise ValueError("Frozen candidate changed")
    return {
        **result,
        "origin": "NEW",
        "role": row["role"],
        "source_artifact": f"cells/{row['cell_id']}/result.json",
        "initial_hash_evidence": "preflight and actual run matched",
        "grid_hash_evidence": "actual simulator trace verified",
    }


def collect(output, manifest, tolerate_incomplete=False):
    results = []
    for row in manifest["new_run_plan"]:
        cell = output / "cells" / row["cell_id"]
        if tolerate_incomplete and cell.exists() and not (cell / "completion.json").exists():
            continue
        result = pilot.completed_cell(output, row["cell_id"], manifest["input_fingerprint"])
        if result is not None:
            results.append(validate_result(manifest, row, result))
    return results


def execute(root, output, manifest, max_workers):
    from argos.diagnostics.seed_characterization_reporting import export

    existing = collect(output, manifest)
    complete = {r["cell_id"] for r in existing}
    pending = [r for r in manifest["new_run_plan"] if r["cell_id"] not in complete]

    def launch(row):
        cell = output / "cells" / row["cell_id"]
        cell.mkdir()
        atomic_json(
            cell / "started.json",
            {
                **row,
                "input_fingerprint": manifest["input_fingerprint"],
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "attempt": 1,
            },
        )
        env = os.environ.copy()
        env.update(
            PYTHONDONTWRITEBYTECODE="1",
            OMP_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            NUMEXPR_NUM_THREADS="1",
            PYTHONHASHSEED="0",
            MPLBACKEND="Agg",
        )
        command = [
            sys.executable,
            "-B",
            str(root / "scripts/run_w2_seed_characterization_10x3.py"),
            "--root",
            str(root),
            "--worker-output",
            str(output),
            "--cell-id",
            row["cell_id"],
        ]
        print(f"START {row['role']} {row['cell_id']}", flush=True)
        with (cell / "worker.log").open("w", encoding="utf8") as log:
            completed = subprocess.run(
                command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, check=False
            )
        path = cell / "worker.log"
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 24576))
            tail = stream.read()
        path.write_bytes(tail)
        if completed.returncode:
            atomic_json(
                cell / "execution_error.json",
                {"returncode": completed.returncode, "attempt": 1, "retry": False},
            )
            raise RuntimeError(
                f"Execution error in {row['cell_id']}; inspect its worker.log; no automatic retry"
            )
        result = pilot.completed_cell(output, row["cell_id"], manifest["input_fingerprint"])
        if result is None:
            raise ValueError("Worker completed without a sealed result")
        print(f"DONE {row['cell_id']}", flush=True)
        return validate_result(manifest, row, result)

    errors = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(launch, row) for row in pending]
        for future in as_completed(futures):
            if future.cancelled():
                continue
            try:
                existing.append(future.result())
            except Exception as exc:  # noqa: BLE001 - retain partial evidence and stop undispatched work
                errors.append(str(exc))
                for other in futures:
                    other.cancel()
    status = "COMPLETE" if len(existing) == 56 and not errors else "ABORTED"
    export(output, manifest, existing, status, "; ".join(errors) or None)
    if errors:
        raise RuntimeError("; ".join(errors))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Phase 2B: reuse old evidence; run ONLY 14 new coupled and 42 new crossed cells. No optimization."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--max-workers", type=int, default=10)
    parser.add_argument(
        "--resume",
        type=Path,
        help="Skip valid sealed cells. Interrupted/unsealed executions require review; never automatically retried.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify old evidence, freeze the 56-cell plan and test old-result merging; zero generation or simulations",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Prepare hashes/arrival summaries for frozen seeds, then stop; zero simulations",
    )
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--cell-id", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not 1 <= args.max_workers <= 10:
        parser.error("--max-workers must be between 1 and 10")
    if args.worker_output:
        output = args.worker_output.resolve()
        manifest = read_json(output / "manifest.json")
        if (
            "preparation_sha256" not in manifest
            or sha(output / "prepared_initial_states.json") != manifest["preparation_sha256"]
        ):
            raise ValueError("Worker requires sealed initial states")
        row = next(r for r in manifest["new_run_plan"] if r["cell_id"] == args.cell_id)
        run_cell(root, output, row["case"], row["arrival_seed"], row["runtime_seed"])
        return 0
    config, spec, old, old_results, confirmations, plan = load_inputs(root)
    identity = run_identity(root, config)
    if args.resume:
        output = args.resume.resolve()
        if not output.is_relative_to((root / "runs/diagnostics").resolve()):
            parser.error("Resume path must be inside runs/diagnostics")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        output = root / "runs/diagnostics" / ("w2_seed_characterization_10x3_" + stamp)
        output.mkdir(parents=True)
    print(f"OUTPUT: {output}", flush=True)
    from argos.diagnostics.seed_characterization_reporting import export

    with pilot.lock(output):
        if args.resume:
            manifest = read_json(output / "manifest.json")
            if (
                any(manifest.get(k) != v for k, v in identity.items())
                or manifest["new_run_plan"] != plan
            ):
                raise ValueError("Resume tool/config/plan identity changed")
            for relative, expected in manifest["setup_hashes"].items():
                if sha(safe_path(output, relative)) != expected:
                    raise ValueError(f"Prepared input changed: {relative}")
        else:
            manifest = setup(root, output, identity, spec, old, old_results, confirmations, plan)
        try:
            if args.dry_run:
                available = collect(output, manifest, tolerate_incomplete=True)
                export(
                    output,
                    manifest,
                    available,
                    "COMPLETE" if len(available) == 56 else "DRY_RUN_NO_SIMULATIONS",
                )
            else:
                manifest = prepare_new_arrivals(root, output, manifest)
                if args.prepare_only:
                    export(output, manifest, collect(output, manifest), "PREPARED_NO_SIMULATIONS")
                else:
                    execute(root, output, manifest, args.max_workers)
        except Exception as exc:  # noqa: BLE001 - export failures without retrying scientific cells
            results = collect(output, manifest, tolerate_incomplete=True)
            export(output, manifest, results, "ABORTED", str(exc))
            print(f"ABORTED: {exc}\nZIP: {output}.zip", file=sys.stderr)
            return 2
    print(f"ZIP: {output}.zip", flush=True)
    return 0
