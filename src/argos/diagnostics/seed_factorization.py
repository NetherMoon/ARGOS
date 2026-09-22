"""Frozen two-seed W2 experiment with a mandatory historical replay barrier."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
import traceback
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from argos.contracts import assessment
from argos.diagnostics.seed_factorization_reporting import export
from argos.diagnostics.seed_factorization_worker import (
    JOB_COLUMNS,
    array_hash,
    atomic_json,
    create_initial,
    run_cell,
)
from argos.diagnostics.workload_seed_forensics import git, read_json, safe_path, sha, write_csv
from argos.types import observation_from_dict

DEFAULT_SPEC = "configs/diagnostics/w2_seed_factorization.json"
TOOL_FILES = [
    "scripts/run_w2_seed_factorization.py",
    "src/argos/diagnostics/seed_factorization.py",
    "src/argos/diagnostics/seed_factorization_worker.py",
    "src/argos/diagnostics/seed_factorization_reporting.py",
    "docs/W2_SEED_FACTORIZATION.md",
]


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@contextmanager
def lock(output):
    with (output / ".factorization.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def validate(root, spec_path):
    spec = read_json(spec_path)
    if git(root, "rev-parse", "HEAD") != spec["repo_shas"]["ARGOS"]:
        raise ValueError("ARGOS HEAD disagrees with frozen Phase 1 lineage; review before running")
    for name in ["FlexDC", "CONDOR-FLEXDC"]:
        dep = root / ".deps" / name
        if git(dep, "rev-parse", "HEAD") != spec["repo_shas"][name] or git(
            dep, "status", "--porcelain"
        ):
            raise ValueError(f"Pinned dependency changed: {name}")
    for rel, expected in {**spec["files"], **spec["historical_sources"]}.items():
        if sha(safe_path(root, rel)) != expected:
            raise ValueError(f"Immutable input/source mismatch: {rel}")
    actual_runtime = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }
    if actual_runtime != spec["runtime"]:
        raise ValueError(
            f"Use the recorded paper Python runtime: expected {spec['runtime']}, got {actual_runtime}"
        )
    phase = safe_path(root, spec["phase1_directory"])
    if (
        sha(phase / "manifest.json") != spec["phase1_manifest_sha256"]
        or sha(Path(str(phase) + ".zip")) != spec["phase1_zip_sha256"]
    ):
        raise ValueError("Authoritative Phase 1 manifest/ZIP changed")
    phase_manifest = read_json(phase / "manifest.json")
    for rel, expected in phase_manifest["output_file_hashes"].items():
        if sha(safe_path(phase, rel)) != expected:
            raise ValueError(f"Phase 1 artifact changed: {rel}")
    with zipfile.ZipFile(str(phase) + ".zip") as z:
        for member in z.infolist():
            if member.is_dir():
                continue
            rel = Path(member.filename)
            if rel.parts[0] == phase.name:
                rel = Path(*rel.parts[1:])
            if z.read(member) != safe_path(phase, rel).read_bytes():
                raise ValueError(f"Phase 1 ZIP/directory disagreement: {rel}")
    for case in spec["cases"]:
        if len(case["seeds"]) != 3 or len(set(case["seeds"])) != 3:
            raise ValueError("Expected three distinct frozen historical seeds per candidate")
        if {r["seed"] for r in case["historical"]} != set(case["seeds"]):
            raise ValueError("Panel lacks historical references")
        if {r["evidence_qualified_pass"] for r in case["historical"]} != {True, False}:
            raise ValueError("Panel must contain historical passes and failures")
        for ref in case["historical"]:
            artifact = read_json(root / ref["source_artifact"])
            entries = artifact["observations"] if isinstance(artifact, dict) else artifact
            entry = entries[ref["source_observation_index"]]
            observation = entry.get("observation", entry)
            candidate = observation["candidate"]
            for key in ["candidate_id", "Pbar", "R", "weights"]:
                if candidate[key] != case[key]:
                    raise ValueError(f"Exact saved candidate mismatch: {case['case']} {key}")
            if (
                assessment(observation_from_dict(observation))["evidence_qualified_feasible"]
                != ref["evidence_qualified_pass"]
            ):
                raise ValueError("Historical qualified pass/fail mismatch")
            if observation["seed"] != ref["seed"]:
                raise ValueError("Historical seed mismatch")
            for key in ["p90", "objective"]:
                if observation["metrics"][key] != ref[key]:
                    raise ValueError(f"Historical {key} mismatch")
            if (
                observation["metrics"]["pj"] != ref["Pj"]
                or [e["observation_count"] for e in observation["qos_evidence"]]
                != ref["evidence_counts"]
            ):
                raise ValueError("Historical QoS evidence mismatch")
    return spec


def identity(root, spec_path, spec):
    tools = {p: sha(root / p) for p in TOOL_FILES}
    value = {"specification": spec, "specification_sha256": sha(spec_path), "tool_files": tools}
    return {**value, "input_fingerprint": digest(value)}


def prepare(root, output, frozen, mode):
    spec = frozen["specification"]
    initial_dir = output / "initial_jobs"
    initial_dir.mkdir()
    inputs = output / "inputs"
    inputs.mkdir()
    (output / "cells").mkdir()
    for name, rel in [
        ("experiment.ini", spec["experiment_path"]),
        ("cluster.ini", spec["cluster_path"]),
        ("costs.ini", "configs/canonical_cost_source.ini"),
    ]:
        shutil.copyfile(root / rel, inputs / name)
    shutil.copyfile(root / "docs/W2_SEED_FACTORIZATION.md", output / "source_audit.md")
    phase = root / spec["phase1_directory"]
    for name in [
        "historical_outcomes.csv",
        "historical_outcome_join.csv",
        "report.md",
        "source_audit.md",
    ]:
        shutil.copyfile(phase / name, inputs / ("phase1_" + name))
    for rel in TOOL_FILES:
        if rel.endswith(".py"):
            shutil.copyfile(root / rel, inputs / Path(rel).name)
    atomic_json(inputs / "frozen_specification.json", spec)
    panels, initial_hashes, targets, grid_hashes = [], [], {}, []
    sys.path.insert(0, str(root / ".deps/FlexDC/src/peacsim"))
    old_cwd = Path.cwd()
    try:
        os.chdir(root / ".deps/FlexDC/src/peacsim")
        for case in spec["cases"]:
            shutil.copyfile(root / case["workload_path"], inputs / (case["workload"] + ".ini"))
            for index, seed in enumerate(case["seeds"]):
                _tables, exp, jobs, _trace, table, prefill = create_initial(root, spec, case, seed)
                ref = next(r for r in case["historical"] if r["seed"] == seed)
                # Save all ten initial fields once per arrival context; runtime copies must hash identically.
                path = initial_dir / f"{case['case']}_{seed}.csv.gz"
                write_csv(path, pd.DataFrame(table.T, columns=JOB_COLUMNS))
                panels.append(
                    {
                        "case": case["case"],
                        "workload": case["workload"],
                        "axis_index": index + 1,
                        "arrival_seed": seed,
                        "runtime_seed": seed,
                        "reason": ref["reason"],
                        "historical_pass": ref["evidence_qualified_pass"],
                        "historical_Bloom_Pj": ref["Pj"][3],
                    }
                )
                initial_hashes.append(
                    {
                        "case": case["case"],
                        "arrival_seed": seed,
                        "initial_job_table_hash": ref["initial_job_table_hash"],
                        "arrival_hash": ref["arrival_hash"],
                        "prefill_count": prefill,
                        "table_file": str(path.relative_to(output)),
                        "file_sha256": sha(path),
                    }
                )
            iso = importlib.import_module("peacsim.iso_signal")
            wizard = importlib.import_module("peacsim.am_data_extraction_wizard")
            pr = wizard.convert_kw_per_server_to_flexdc_pr(case["Pbar"], case["R"], exp, jobs)
            signal = iso.read_iso_signal(exp, 3600, 2, True)
            caps = iso.calculate_cluster_power_caps(
                signal, pr["P_actual_watts"], pr["R_actual_watts"], 0, 3600, 2
            )
            ticks = np.arange(3601)
            grid = np.column_stack([ticks, np.asarray(signal)[ticks // 2]])
            target = np.column_stack([ticks, np.asarray(caps)[ticks // 2]])
            grid_hashes.append(array_hash(grid))
            targets[case["case"]] = array_hash(target)
            write_csv(
                inputs / f"{case['case']}_actual_grid_target.csv.gz",
                pd.DataFrame(
                    {
                        "time": ticks,
                        "normalized_grid": grid[:, 1],
                        "power_target_watts": target[:, 1],
                    }
                ),
            )
    finally:
        os.chdir(old_cwd)
    if len(set(grid_hashes)) != 1:
        raise ValueError("Grid differs across candidate contexts")
    write_csv(output / "seed_panels.csv", pd.DataFrame(panels))
    write_csv(output / "initial_state_catalog.csv", pd.DataFrame(initial_hashes))
    manifest = {
        "tool": "argos.seed_factorization",
        "version": "1.0",
        **frozen,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "status": "PREPARED",
        "repo_shas": spec["repo_shas"],
        "working_tree_status": git(root, "status", "--porcelain"),
        "python_executable": sys.executable,
        "runtime": spec["runtime"],
        "expected_grid_hash": grid_hashes[0],
        "expected_target_hashes": targets,
        "initial_state_catalog": initial_hashes,
        "maximum_matrix_cells": 18,
        "replay_diagonal_cells": 6,
        "grid_invariant_scope": "signal global; target within candidate because P/R differ",
        "replay_tolerance_reason": "1e-12 absolute, zero relative: decimal serialization/float summation only; counts/pass/hashes exact",
        "generator": "peacsim.create_tables.init_job_table",
        "simulator": "peacsim.simulator.Simulator.run",
        "observer_override": "record_state output only; same nine aggregate column formats; no state mutation/RNG",
        "initial_hash_reference": "Phase 1 regenerated complete table; archived historical runtime hash unavailable",
    }
    manifest["prepared_file_hashes"] = {
        p.relative_to(output).as_posix(): sha(p)
        for p in output.rglob("*")
        if p.is_file() and p.name != ".factorization.lock"
    }
    atomic_json(output / "manifest.json", manifest)
    return manifest


def cell_name(case, arrival, runtime):
    return f"{case}_a{arrival}_r{runtime}"


def completed_cell(output, name, fingerprint):
    cell = output / "cells" / name
    seal_path = cell / "completion.json"
    if not seal_path.exists():
        if cell.exists():
            raise ValueError(
                f"Incomplete/interrupted cell {name}; not silently rerunning it. Preserve this directory and request review."
            )
        return None
    seal = read_json(seal_path)
    if seal["input_fingerprint"] != fingerprint:
        raise ValueError(f"Completed cell input fingerprint mismatch: {name}")
    for relative, expected in seal["files"].items():
        if sha(safe_path(cell, relative)) != expected:
            raise ValueError(f"Completed cell seal mismatch: {name}/{relative}")
    result = read_json(cell / "result.json")
    if result["cell_id"] != name or result["status"] != "COMPLETE":
        raise ValueError("Invalid completed cell identity")
    return result


def replay_check(spec, case, reference, result):
    rows = []
    pairs = [
        ("p90", reference["p90"], result["p90"], True),
        ("objective", reference["objective"], result["objective"], True),
        (
            "initial_job_table_hash",
            reference["initial_job_table_hash"],
            result["initial_job_table_hash"],
            False,
        ),
        ("arrival_hash", reference["arrival_hash"], result["arrival_hash"], False),
        ("evidence_counts", reference["evidence_counts"], result["evidence_counts"], False),
        (
            "evidence_qualified_pass",
            reference["evidence_qualified_pass"],
            result["evidence_qualified_pass"],
            False,
        ),
    ]
    pairs += [
        (f"Pj_{i}", a, b, True) for i, (a, b) in enumerate(zip(reference["Pj"], result["Pj"]))
    ]
    if len(result["Pj"]) != 4:
        raise ValueError("Incomplete replay Pj vector")
    for field, expected, actual, numeric in pairs:
        tolerance = spec["replay_absolute_tolerance"] if numeric else 0
        difference = abs(float(actual) - float(expected)) if numeric else None
        passed = (
            bool(np.isfinite(actual) and difference <= tolerance) if numeric else actual == expected
        )
        rows.append(
            {
                "case": case,
                "seed": reference["seed"],
                "field": field,
                "expected": json.dumps(expected),
                "actual": json.dumps(actual),
                "absolute_difference": difference,
                "tolerance": tolerance,
                "passed": passed,
            }
        )
    return rows


def invariants(manifest, results):
    for r in results:
        case = next(c for c in manifest["specification"]["cases"] if c["case"] == r["case"])
        ref = next(h for h in case["historical"] if h["seed"] == r["arrival_seed"])
        if (
            r["initial_job_table_hash"] != ref["initial_job_table_hash"]
            or r["arrival_hash"] != ref["arrival_hash"]
        ):
            raise ValueError("Runtime variants started from different initial jobs")
        if (
            r["grid_signal_hash"] != manifest["expected_grid_hash"]
            or r["target_trace_hash"] != manifest["expected_target_hashes"][r["case"]]
        ):
            raise ValueError("Grid/target invariant failed")


def execute_stage(root, output, manifest, cells, max_workers):
    results, pending, errors = [], [], []
    for case, arrival, runtime in cells:
        name = cell_name(case, arrival, runtime)
        prior = completed_cell(output, name, manifest["input_fingerprint"])
        if prior is not None:
            results.append(prior)
        else:
            pending.append((case, arrival, runtime))
    if errors:
        raise ValueError(str(errors))

    def execute(cell_tuple):
        case, arrival, runtime = cell_tuple
        name = cell_name(case, arrival, runtime)
        cell = output / "cells" / name
        cell.mkdir()
        atomic_json(
            cell / "started.json",
            {
                "input_fingerprint": manifest["input_fingerprint"],
                "cell_id": name,
                "arrival_seed": arrival,
                "runtime_seed": runtime,
                "started_utc": datetime.now(timezone.utc).isoformat(),
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
            str(root / "scripts/run_w2_seed_factorization.py"),
            "--root",
            str(root),
            "--worker-output",
            str(output),
            "--case",
            case,
            "--arrival-seed",
            str(arrival),
            "--runtime-seed",
            str(runtime),
        ]
        print(f"START {name}", flush=True)
        with (cell / "worker.log").open("w", encoding="utf8") as log:
            done = subprocess.run(
                command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, check=False
            )
        # Keep the final 24KiB, not thousands of repeated tqdm updates.
        log_path = cell / "worker.log"
        with log_path.open("rb") as stream:
            stream.seek(max(0, log_path.stat().st_size - 24576))
            tail = stream.read()
        log_path.write_bytes(tail)
        if done.returncode:
            raise RuntimeError(
                f"Worker {name} failed ({done.returncode}); see cells/{name}/worker.log"
            )
        result = completed_cell(output, name, manifest["input_fingerprint"])
        if result is None:
            raise RuntimeError(f"Worker did not seal {name}")
        print(f"DONE  {name}", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(execute, cell): cell for cell in pending}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001 - export stage evidence before aborting
                errors.append(str(exc))
    if errors:
        raise RuntimeError("; ".join(errors))
    invariants(manifest, results)
    return results


def run_stages(root, output, manifest, max_workers, smoke_replays=0, single=None):
    spec = manifest["specification"]
    diagonals = [(c["case"], s, s) for c in spec["cases"] for s in c["seeds"]]
    crossed = [
        (c["case"], a, r) for c in spec["cases"] for a in c["seeds"] for r in c["seeds"] if a != r
    ]
    if smoke_replays:
        diagonals = [(c["case"], c["seeds"][0], c["seeds"][0]) for c in spec["cases"]][
            :smoke_replays
        ]
    if single is not None and single[1] == single[2]:
        diagonals = [single]
    results = execute_stage(root, output, manifest, diagonals, max_workers)
    checks = []
    for r in results:
        case = next(c for c in spec["cases"] if c["case"] == r["case"])
        ref = next(h for h in case["historical"] if h["seed"] == r["arrival_seed"])
        checks.extend(replay_check(spec, case["case"], ref, r))
    if not all(row["passed"] for row in checks):
        export(
            output,
            results,
            checks,
            "REPLAY_FAILED",
            "At least one historical replay field mismatched. No off-diagonal cells dispatched.",
        )
        return 2
    if smoke_replays or (single is not None and single[1] == single[2]):
        export(output, results, checks, "SMOKE_REPLAY_PASSED")
        return 0
    # Only this barrier authorizes off-diagonals. A historical FAIL that is reproduced is a successful replay.
    atomic_json(
        output / "replay_gate.json",
        {
            "passed": True,
            "diagonal_cells": [r["cell_id"] for r in results],
            "input_fingerprint": manifest["input_fingerprint"],
            "replay_checks": checks,
        },
    )
    export(output, results, checks, "REPLAY_GATE_PASSED")
    if single is not None:
        crossed = [single]
    results += execute_stage(root, output, manifest, crossed, max_workers)
    invariants(manifest, results)
    export(output, results, checks, "COMPLETE" if len(results) == 18 else "PARTIAL")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Frozen 18-cell W2 arrival/runtime seed diagnostic. Six historical diagonals MUST replay before twelve crossed cells. No optimizer."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--spec", default=DEFAULT_SPEC)
    parser.add_argument(
        "--max-workers",
        type=int,
        default=10,
        help="Concurrent isolated FlexDC processes, 1..10 (default 10)",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="Resume a matching artifact; sealed cells are never rerun. Interrupted/unsealed cells stop for review.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Generate/hash six initial contexts and ZIP; zero simulations",
    )
    parser.add_argument(
        "--smoke-replays",
        type=int,
        choices=[1, 2],
        default=0,
        help="Run only first historical diagonal for 1 or 2 candidates, then stop",
    )
    parser.add_argument(
        "--case", choices=["c005", "c007"], help="Optional single-cell mode; requires both seeds"
    )
    parser.add_argument(
        "--arrival-seed", type=int, help="Generate initial jobs with this frozen panel seed"
    )
    parser.add_argument(
        "--runtime-seed",
        type=int,
        help="Seed the simulator after jobs exist; may differ from arrival seed",
    )
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not 1 <= args.max_workers <= 10:
        parser.error("--max-workers must be between 1 and 10")
    if args.worker_output:
        output = args.worker_output.resolve()
        if args.case is None or args.arrival_seed is None or args.runtime_seed is None:
            parser.error("Worker requires case and both seeds")
        if args.arrival_seed != args.runtime_seed:
            gate = read_json(output / "replay_gate.json")
            if (
                not gate.get("passed")
                or len(gate["diagonal_cells"]) != 6
                or gate["input_fingerprint"]
                != read_json(output / "manifest.json")["input_fingerprint"]
            ):
                raise ValueError("Off-diagonal worker requires the six-cell replay gate")
        run_cell(root, output, args.case, args.arrival_seed, args.runtime_seed)
        return 0
    spec_path = safe_path(root, args.spec)
    spec = validate(root, spec_path)
    frozen = identity(root, spec_path, spec)
    single = None
    if any(v is not None for v in [args.case, args.arrival_seed, args.runtime_seed]):
        if (
            any(v is None for v in [args.case, args.arrival_seed, args.runtime_seed])
            or args.smoke_replays
        ):
            parser.error("Single-cell mode needs --case and both seeds, without --smoke-replays")
        case = next(c for c in spec["cases"] if c["case"] == args.case)
        if args.arrival_seed not in case["seeds"] or args.runtime_seed not in case["seeds"]:
            parser.error("Seeds must belong to the frozen case panel")
        single = (args.case, args.arrival_seed, args.runtime_seed)
    if args.resume:
        output = args.resume.resolve()
        if not output.is_relative_to((root / "runs/diagnostics").resolve()):
            parser.error("Resume directory must be inside runs/diagnostics")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        suffix = "_smoke" if args.smoke_replays else ""
        output = root / "runs/diagnostics" / ("w2_seed_factorization_" + stamp + suffix)
        output.mkdir(parents=True)
    print(f"OUTPUT: {output}", flush=True)
    with lock(output):
        if args.resume:
            manifest = read_json(output / "manifest.json")
            if any(manifest.get(key) != value for key, value in frozen.items()):
                raise ValueError(
                    "Resume source/config fingerprint changed; do not mix implementations"
                )
            for rel, expected in manifest["prepared_file_hashes"].items():
                if sha(safe_path(output, rel)) != expected:
                    raise ValueError(f"Prepared input changed on resume: {rel}")
        else:
            manifest = prepare(root, output, frozen, "smoke" if args.smoke_replays else "full")
        try:
            if args.prepare_only:
                export(output, [], [], "PREPARED_NO_SIMULATIONS")
                print(f"ZIP: {output}.zip", flush=True)
                return 0
            code = run_stages(root, output, manifest, args.max_workers, args.smoke_replays, single)
        except Exception as exc:  # noqa: BLE001 - export stage evidence before aborting
            results = []
            for cell in sorted((output / "cells").iterdir()):
                if (cell / "completion.json").exists():
                    results.append(completed_cell(output, cell.name, manifest["input_fingerprint"]))
            checks = []
            for r in results:
                if r["arrival_seed"] == r["runtime_seed"]:
                    case = next(c for c in spec["cases"] if c["case"] == r["case"])
                    ref = next(h for h in case["historical"] if h["seed"] == r["arrival_seed"])
                    checks.extend(replay_check(spec, r["case"], ref, r))
            export(output, results, checks, "ABORTED", str(exc))
            print(f"ABORTED: {exc}", file=sys.stderr)
            code = 2
    print(f"ZIP: {output}.zip", flush=True)
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # noqa: BLE001 - command boundary reports failure
        traceback.print_exc()
        raise SystemExit(2)
