"""Bounded subprocess execution with unique run folders and strict provenance."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import psutil

from argos.config import Config
from argos.contracts import feasible
from argos.provenance import read_json, sha256, write_json
from argos.simulator.configuration import canonical_costs, gradient_config, overlay, read_ini
from argos.simulator.output_parser import parse_output
from argos.types import Candidate, FlexDCObservation, observation_from_dict


class FlexDCRunner:
    def __init__(self, root: Path, episode: Path, config: Config):
        self.root = root.resolve()
        self.episode = episode.resolve()
        self.config = config
        self.flexdc = self.root / ".deps/FlexDC"
        self.costs = canonical_costs(root)
        self.workload = (self.flexdc / config.workload).resolve()
        self.base_experiment = (self.flexdc / config.experiment).resolve()
        self.cluster = (self.flexdc / config.cluster).resolve()
        self.gradient = self.episode / "generated_configs/argos_gradient.ini"
        if not self.gradient.exists():
            gradient_config(root, self.gradient)
        if (
            sha256(self.gradient)
            != read_json(self.gradient.with_suffix(".audit.json"))["generated_sha256"]
        ):
            raise ValueError("Generated gradient config changed")
        self.context_id = hashlib.sha256(
            json.dumps(
                {
                    "workload": sha256(self.workload),
                    "experiment": sha256(self.base_experiment),
                    "cluster": sha256(self.cluster),
                    "gradient": sha256(self.gradient),
                    "N": config.server_count,
                    "U": config.utilization,
                    "policy": config.policy,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

    def evaluate_batch(
        self, candidates: list[Candidate], seed: int, phase: str, batch: int
    ) -> list[FlexDCObservation]:
        remaining = self.config.max_search_calls - self.search_attempts()
        for candidate in candidates:
            identity = {
                "candidate": asdict(candidate),
                "seed": seed,
                "phase": phase,
                "batch": batch,
                "context": self.context_id,
            }
            key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
            directory = self.episode / "flexdc_raw" / key
            if not (directory / "observation.json").exists():
                for previous in directory.glob("attempt-*/process.json"):
                    record = read_json(previous)
                    if psutil.pid_exists(record["pid"]):
                        process = psutil.Process(record["pid"])
                        if abs(process.create_time() - record["created"]) < 0.01:
                            raise RuntimeError(
                                "Previous simulator is still running; resume after it exits"
                            )
                if phase == "search":
                    if remaining < 1:
                        raise RuntimeError(
                            "Insufficient remaining budget to retry interrupted batch"
                        )
                    remaining -= 1
        with ThreadPoolExecutor(
            max_workers=self.config.max_workers, thread_name_prefix="argos-flexdc"
        ) as executor:
            futures = [executor.submit(self.evaluate, c, seed, phase, batch) for c in candidates]
            return [f.result() for f in futures]

    def search_attempts(self) -> int:
        return sum(
            read_json(p)["identity"]["phase"] == "search"
            for p in (self.episode / "flexdc_raw").glob("*/attempt-*/execution.json")
        )

    def evaluate(
        self, candidate: Candidate, seed: int, phase: str, batch: int
    ) -> FlexDCObservation:
        identity = {
            "candidate": asdict(candidate),
            "seed": seed,
            "phase": phase,
            "batch": batch,
            "context": self.context_id,
        }
        execution_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[
            :24
        ]
        directory = self.episode / "flexdc_raw" / execution_id
        cache = directory / "observation.json"
        if cache.exists():
            observation = observation_from_dict(read_json(cache))
            if (
                observation.candidate != candidate
                or observation.seed != seed
                or observation.phase != phase
            ):
                raise ValueError("Recovery cache identity mismatch")
            # Re-parse completed valid files. Recovery never creates another execution count.
            if observation.valid:
                raw = observation.raw_paths
                parsed, _ = parse_output(
                    Path(raw["results"]),
                    Path(raw["diagnostics"]),
                    candidate,
                    self.config,
                    seed,
                    execution_id,
                    self.context_id,
                    self.workload,
                    self.costs,
                )
                if parsed != observation.metrics:
                    raise ValueError("Cached simulator metrics changed")
                for path, expected in observation.reported["input_hashes"].items():
                    if sha256(Path(path)) != expected:
                        raise ValueError("Recovery input hash mismatch")
            return observation
        # Interrupted attempts are preserved. A new attempt cannot be confused with completion.
        directory.mkdir(parents=True, exist_ok=True)
        attempt = 1
        while (directory / f"attempt-{attempt:03d}").exists():
            attempt += 1
        attempt_dir = directory / f"attempt-{attempt:03d}"
        cwd = attempt_dir / "engine/peacsim"
        cwd.mkdir(parents=True)
        experiment = self.episode / "generated_configs" / f"{execution_id}.ini"
        overlay(
            self.root,
            self.base_experiment,
            experiment,
            {
                ("system", "server_count"): str(self.config.server_count),
                ("system", "utilization"): str(self.config.utilization),
                ("system", "random_seed"): str(seed),
            },
        )
        # Preserve the exact ISO path text by recreating its relative filesystem layout.
        iso_ref = Path(read_ini(experiment)["iso"]["iso_file_path"])
        source = (self.flexdc / "src/peacsim" / iso_ref).resolve()
        target = (cwd / iso_ref).resolve()
        if not target.is_relative_to(attempt_dir.resolve()):
            raise ValueError("ISO runtime path escapes isolated attempt")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        plan = attempt_dir / "plan.json"
        write_json(
            plan,
            [
                {
                    "plan_row_id": execution_id,
                    "context_id": self.context_id,
                    "workload_config": str(self.workload),
                    "experiment_config": str(experiment),
                    "server_count": self.config.server_count,
                    "job_type_count": len(candidate.weights),
                    "utilization": self.config.utilization,
                    "Pbar_kw_per_server": candidate.Pbar,
                    "R_kw_per_server": candidate.R,
                    "weights": list(candidate.weights),
                    "simulation_seed": seed,
                    "configured_r_over_p_max": self.config.r_over_p_max,
                    "configured_weight_lower": self.config.weight_min,
                    "configured_weight_upper": self.config.weight_max,
                }
            ],
        )
        command = [
            sys.executable,
            "-B",
            str(self.flexdc / "src/peacsim/am_data_extraction_wizard.py"),
            "--gradient-config",
            str(self.gradient),
            "--experiment-config",
            str(experiment),
            "--cluster-config",
            str(self.cluster),
            "--policy-name",
            self.config.policy,
            "--job-config",
            str(self.workload),
            "--output-dir",
            "candidate",
            "--sweep-plan-file",
            str(plan),
            "--plan-chunk-index",
            "0",
            "--plan-num-chunks",
            "1",
            "--node-count-control",
            "true",
            "--r-over-p-max",
            str(self.config.r_over_p_max),
            "--configured-weight-lower",
            str(self.config.weight_min),
            "--configured-weight-upper",
            str(self.config.weight_max),
        ]
        env = os.environ.copy()
        env.update(
            PYTHONPATH=str(self.flexdc / "src"),
            PYTHONDONTWRITEBYTECODE="1",
            MPLBACKEND="Agg",
            OMP_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
        )
        inputs = {
            str(p): sha256(p)
            for p in [self.workload, self.cluster, self.gradient, experiment, plan, source, target]
        }
        write_json(
            attempt_dir / "execution.json",
            {
                "command": command,
                "cwd": str(cwd),
                "identity": identity,
                "input_hashes": inputs,
                "attempt": attempt,
            },
        )
        start = time.perf_counter()
        returncode = None
        metrics = None
        reported = {}
        error = None
        valid = False
        paths = {
            "stdout": str(attempt_dir / "stdout.log"),
            "stderr": str(attempt_dir / "stderr.log"),
            "execution": str(attempt_dir / "execution.json"),
        }
        try:
            with (
                Path(paths["stdout"]).open("w", encoding="utf-8") as out,
                Path(paths["stderr"]).open("w", encoding="utf-8") as err,
            ):
                process = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err)
                write_json(
                    attempt_dir / "process.json",
                    {"pid": process.pid, "created": psutil.Process(process.pid).create_time()},
                )
                try:
                    process.wait(timeout=self.config.simulator_timeout_seconds)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise
            returncode = process.returncode
            if returncode:
                raise RuntimeError(f"Simulator exit status {returncode}; see stderr")
            result_paths = list(cwd.glob("output/optimization/*/grid_search_results.csv"))
            if len(result_paths) != 1:
                raise ValueError("Expected exactly one simulator result file")
            result = result_paths[0]
            diag = result.with_name("grid_search_diagnostics.csv")
            paths.update(results=str(result), diagnostics=str(diag))
            for path, expected in inputs.items():
                if sha256(Path(path)) != expected:
                    raise ValueError(f"Input changed during execution: {path}")
            metrics, reported = parse_output(
                result,
                diag,
                candidate,
                self.config,
                seed,
                execution_id,
                self.context_id,
                self.workload,
                self.costs,
            )
            reported["input_hashes"] = inputs
            valid = True
            status = (
                "SIMULATOR_OBSERVED_FEASIBLE"
                if feasible(metrics)
                else "SIMULATOR_OBSERVED_INFEASIBLE"
            )
        except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as exc:
            error = f"{type(exc).__name__}: {exc}"
            status = (
                "SIMULATOR_EXECUTION_FAILED"
                if returncode is None or returncode != 0
                else "CONTRACT_MISMATCH"
            )
        residuals = {}
        if valid and candidate.prediction:
            residuals = {
                "mean_tracking": metrics.mean_tracking - candidate.prediction.mean_tracking,
                "p90": metrics.p90 - candidate.prediction.p90,
                "pj": [a - b for a, b in zip(metrics.pj, candidate.prediction.pj)],
                "objective": metrics.objective - candidate.prediction.objective,
            }
        observation = FlexDCObservation(
            candidate,
            seed,
            phase,
            batch,
            valid,
            metrics,
            status,
            time.perf_counter() - start,
            execution_id,
            reported,
            paths,
            error,
            returncode,
            threading.current_thread().name,
            residuals,
        )
        write_json(cache, asdict(observation))
        return observation
