"""ARGOS observation adapter around the validated pinned fixed-table FlexDC worker."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from argos.campaign.identity import digest
from argos.experimental_sa.paper_consistent.evaluator import FixedEvaluator
from argos.experimental_sa.paper_consistent.objective import ObjectiveContract
from argos.fixed_table.protocol import GRID_TRACE_HASH
from argos.provenance import read_json, sha256, write_json
from argos.simulator.evidence import ordered_jobs
from argos.types import Candidate, FlexDCObservation, Metrics, QoSEvidence, observation_from_dict


def geometry(candidate: Candidate) -> tuple:
    return (candidate.Pbar, candidate.R, *candidate.weights)


def evidence_from_accounting(path: Path, jobs, probabilities) -> tuple[QoSEvidence, ...]:
    frame = pd.read_csv(path, float_precision="round_trip")
    if frame.job_type_id.tolist() != list(range(len(jobs))) or frame.job_type.tolist() != [
        job.section for job in jobs
    ]:
        raise ValueError("Fixed-table job evidence ordering changed")
    result = []
    for job, pj, row in zip(jobs, probabilities, frame.itertuples(index=False)):
        if float(row.Pj) != pj:
            raise ValueError("Reported Pj and compact QoS evidence disagree")
        result.append(
            QoSEvidence(
                job=job,
                pj=pj,
                observation_count=int(row.qos_observations),
                finished_count=int(row.eligible_completed),
                unfinished_count=int(row.eligible_unfinished),
                exceedance_count=int(row.violation_count),
                estimator_numerator=int(row.estimator_numerator),
                estimator_denominator=int(row.estimator_denominator),
                estimator=str(row.estimator),
                horizon_seconds=float(row.horizon_seconds),
                threshold_sojourn_seconds=float(row.threshold_sojourn_seconds),
            )
        )
    return tuple(result)


class FixedTableSimulator:
    def __init__(self, root: Path, episode: Path, config, context: dict, workers: int):
        self.root = root.resolve()
        self.episode = episode.resolve()
        self.config = config
        self.context = context
        self.workers = workers
        self.evaluator = FixedEvaluator(self.root, self.episode)
        self.objective = ObjectiveContract(self.root)
        self.jobs = ordered_jobs(self.root / context["case"]["workload_path"])
        self.table_path = self.episode / "initial_jobs.csv.gz"
        self.context_path = self.episode / "fixed_context.json"
        self._check_context()

    def _check_context(self):
        if read_json(self.context_path) != self.context:
            raise ValueError("Fixed-table context receipt changed")
        if sha256(self.table_path) != self.context["initial_file_sha256"]:
            raise ValueError("Fixed-table artifact changed")
        if self.context["grid_signal_hash"] != GRID_TRACE_HASH:
            raise ValueError("Grid identity changed")

    def search_attempts(self) -> int:
        area = self.episode / "evaluations"
        return (
            sum(
                p.is_dir() and p.name.isdecimal() and 1 <= int(p.name) <= 32 for p in area.glob("*")
            )
            if area.exists()
            else 0
        )

    def _index(self, phase: str, batch: int, index: int) -> int:
        if phase == "search" and 1 <= batch <= 4 and 0 <= index < 8:
            return (batch - 1) * 8 + index + 1
        if phase == "confirmation" and 1 <= batch <= 3 and index == 0:
            return 32 + batch
        raise ValueError("Fixed-table call outside frozen 32+3 episode plan")

    def evaluate_batch(
        self, candidates: list[Candidate], seed: int, phase: str, batch: int
    ) -> list[FlexDCObservation]:
        self._check_context()
        if not candidates or len(candidates) > 8:
            raise ValueError("Invalid fixed-table batch size")
        if phase == "search" and seed != self.config.search_seed:
            raise ValueError("Search runtime seed changed")
        if phase == "confirmation" and seed != self.config.confirmation_seeds[batch - 1]:
            raise ValueError("Unplanned final runtime seed")
        if phase == "search" and len({geometry(c) for c in candidates}) != len(candidates):
            raise ValueError("Duplicate candidate geometry in batch")
        entries = [(c, self._index(phase, batch, i)) for i, c in enumerate(candidates)]
        if phase == "search":
            for prior in (self.episode / "evaluations").glob("*/request.json"):
                old_cell = prior.parent
                if old_cell.name.isdecimal() and 1 <= int(old_cell.name) <= 32:
                    old = read_json(prior)
                    for candidate, number in entries:
                        if (
                            int(old_cell.name) != number
                            and old["runtime_seed"] == seed
                            and tuple(old["params"]) == geometry(candidate)
                        ):
                            raise ValueError("Duplicate fixed-table candidate/runtime evaluation")
        if (
            phase == "search"
            and self.search_attempts()
            + sum(
                not (self.episode / "evaluations" / f"{number:06d}").exists()
                for _, number in entries
            )
            > 32
        ):
            raise ValueError("32 launched search attempts exhausted")
        # No worker is started until all existing cells pass recovery checks.
        for candidate, number in entries:
            cell = self.episode / "evaluations" / f"{number:06d}"
            if cell.exists():
                if not (cell / "observation.json").exists():
                    raise RuntimeError(f"Incomplete prior attempt retained for review: {cell}")
                self._cached(candidate, seed, phase, batch, cell)
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = [
                pool.submit(self._evaluate, candidate, seed, phase, batch, number)
                for candidate, number in entries
            ]
            return [f.result() for f in futures]

    def _identity(self, candidate, seed, phase, batch):
        return {
            "table_hash": self.context["initial_job_table_hash"],
            "table_file_hash": self.context["initial_file_sha256"],
            "grid_hash": GRID_TRACE_HASH,
            "workload": self.context["case"]["workload"],
            "workload_hash": self.context["spec"]["files"][self.context["case"]["workload_path"]],
            "experiment_hash": self.context["spec"]["files"][
                self.context["spec"]["experiment_path"]
            ],
            "runtime_seed": seed,
            "phase": phase,
            "batch": batch,
            "geometry": list(geometry(candidate)),
            "policy": self.context["spec"]["policy"],
            "fixed_context_file_hash": sha256(self.context_path),
        }

    def _cached(self, candidate, seed, phase, batch, cell):
        observation = observation_from_dict(read_json(cell / "observation.json"))
        identity = self._identity(candidate, seed, phase, batch)
        if (
            observation.candidate != candidate
            or observation.seed != seed
            or observation.phase != phase
            or observation.batch != batch
            or observation.execution_id != digest(identity)[:24]
            or observation.reported.get("identity") != identity
        ):
            raise ValueError("Fixed-table cache identity mismatch")
        for filename, expected in observation.reported.get("file_hashes", {}).items():
            if sha256(cell / filename) != expected:
                raise ValueError("Fixed-table cached output changed: " + filename)
        return observation

    def _evaluate(self, candidate, seed, phase, batch, number):
        cell = self.episode / "evaluations" / f"{number:06d}"
        if cell.exists():
            return self._cached(candidate, seed, phase, batch, cell)
        identity = self._identity(candidate, seed, phase, batch)
        execution_id = digest(identity)[:24]
        raw = None
        error = None
        try:
            raw = self.evaluator(geometry(candidate), number, seed)
            if (
                raw["initial_job_table_hash"] != self.context["initial_job_table_hash"]
                or raw["grid_signal_hash"] != GRID_TRACE_HASH
                or raw["runtime_seed"] != seed
                or raw["arrival_seed"] != self.context["arrival_seed"]
                or len(raw["Pj"]) != len(self.jobs)
                or len(raw["effective_policy_weights"]) != len(candidate.weights)
            ):
                raise ValueError("Fixed-table worker scientific identity mismatch")
            if any(
                abs(a - b) > 1e-9
                for a, b in zip(raw["effective_policy_weights"], candidate.weights)
            ):
                raise ValueError("Effective scheduling weights changed")
            objective = self.objective.evaluate(raw["M_RSR"], raw["p90"], raw["Pj"])
            metrics = Metrics(raw["mean_tracking"], raw["p90"], tuple(raw["Pj"]), objective.Cfull)
            evidence = evidence_from_accounting(cell / "qos_accounting.csv", self.jobs, metrics.pj)
            if [e.observation_count for e in evidence] != raw["evidence_counts"]:
                raise ValueError("Worker evidence counts disagree")
            files = {
                name: sha256(cell / name)
                for name in (
                    "request.json",
                    "raw_result.json",
                    "job_summary.csv",
                    "qos_accounting.csv",
                )
            }
            reported = {
                "identity": identity,
                "raw": raw,
                "objective_components": objective.to_dict(),
                "file_hashes": files,
                "ordered_jobs": [j.section for j in self.jobs],
            }
            observation = FlexDCObservation(
                candidate,
                seed,
                phase,
                batch,
                True,
                metrics,
                "PARSED",
                raw["elapsed_seconds"],
                execution_id,
                reported,
                {"cell": str(cell)},
                None,
                0,
                "fixed-table-worker",
                {},
                evidence,
            )
        except (OSError, ValueError, RuntimeError, KeyError, TypeError, OverflowError) as exc:
            error = f"{type(exc).__name__}: {exc}"
            observation = FlexDCObservation(
                candidate,
                seed,
                phase,
                batch,
                False,
                None,
                "SIMULATOR_EXECUTION_FAILED",
                0.0,
                execution_id,
                {"identity": identity},
                {"cell": str(cell)},
                error,
            )
        if cell.exists():
            write_json(cell / "observation.json", asdict(observation))
        else:
            # A prelaunch failure still consumes its reserved scientific slot.
            cell.mkdir(parents=True, exist_ok=False)
            write_json(cell / "observation.json", asdict(observation))
        return observation
