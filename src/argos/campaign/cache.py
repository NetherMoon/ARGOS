"""Exact physical reuse with independent logical query receipts."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace

from argos.campaign.identity import digest, immutable_json
from argos.provenance import read_json, sha256, write_json
from argos.simulator.flexdc_adapter import FlexDCRunner
from argos.types import Candidate, observation_from_dict


def physical_key(candidate, seed, context):
    return digest(
        {
            "schema": 1,
            "context": context,
            "seed": seed,
            "Pbar": float(candidate.Pbar).hex(),
            "R": float(candidate.R).hex(),
            "weights": [float(w).hex() for w in candidate.weights],
        }
    )


def logical_observation(observation, candidate, phase, batch):
    residuals = {}
    if observation.valid and candidate.prediction:
        m, p = observation.metrics, candidate.prediction
        residuals = {
            "mean_tracking": m.mean_tracking - p.mean_tracking,
            "p90": m.p90 - p.p90,
            "pj": [x - y for x, y in zip(m.pj, p.pj)],
            "max_pj": max(m.pj) - max(p.pj),
            "objective": m.objective - p.objective,
        }
    return replace(observation, candidate=candidate, phase=phase, batch=batch, residuals=residuals)


def scheduled_seconds(durations, workers):
    slots = [0.0] * workers
    for duration in durations:
        i = min(range(workers), key=lambda j: (slots[j], j))
        slots[i] += duration
    return max(slots, default=0.0)


class SimulatorCache:
    def __init__(self, root, directory, identity, runner_factory=FlexDCRunner):
        self.root = root
        self.directory = directory
        self.identity = identity
        self.runner_factory = runner_factory
        self._guard = threading.Lock()
        self._locks = {}

    def method(self, case, method, episode, config):
        return MethodSimulator(self, case, method, episode, config)

    def lock(self, key):
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())


class MethodSimulator:
    def __init__(self, cache, case, method, episode, config):
        self.cache = cache
        self.case = case
        self.method_name = method
        self.episode = episode
        self.config = config
        self.context = {
            "identity": cache.identity,
            "context": case["context"],
            "workload": config.workload,
            "workload_sha256": case["workload_sha256"],
            "N": config.server_count,
            "U": config.utilization,
            "policy": config.policy,
            "weight_policy": config.weight_policy,
            "weight_bounds": config.weight_bounds(case["J"]),
            "r_over_p_max": config.r_over_p_max,
        }

    def evaluate_one(self, candidate, seed, phase, batch):
        key = physical_key(candidate, seed, self.context)
        logical_id = digest(
            {"candidate": asdict(candidate), "seed": seed, "phase": phase, "batch": batch}
        )
        receipt_path = self.episode / "logical_queries" / (logical_id + ".json")
        physical = self.cache.directory / "cache/flexdc" / key
        owner = {
            "case_id": self.case["case_id"],
            "method": self.method_name,
            "logical_id": logical_id,
        }
        canonical = Candidate(key, candidate.Pbar, candidate.R, candidate.weights, "campaign_cache")
        with self.cache.lock(key):
            runner = self.cache.runner_factory(self.cache.root, physical, self.config)
            owner_path = physical / "owner.json"
            if owner_path.exists():
                old = read_json(owner_path)
                if old["context_digest"] != digest(self.context) or old["key"] != key:
                    raise ValueError("Physical cache context mismatch")
            else:
                immutable_json(
                    owner_path,
                    {
                        "key": key,
                        "context_digest": digest(self.context),
                        "owner": owner,
                        "candidate": asdict(canonical),
                        "seed": seed,
                    },
                )
            completed = physical / "physical_observation.json"
            attempts = list((physical / "flexdc_raw").glob("*/attempt-*/execution.json"))
            cached = list((physical / "flexdc_raw").glob("*/observation.json"))
            if attempts and not cached and not completed.exists():
                raise RuntimeError(
                    "Interrupted physical execution preserved; audit required before retry"
                )
            observation = runner.evaluate(canonical, seed, "search", 1)
            if completed.exists():
                if observation != observation_from_dict(read_json(completed)):
                    raise ValueError("Physical observation changed")
            else:
                immutable_json(completed, asdict(observation))
            origin = read_json(owner_path)["owner"]
            record = {
                "logical_id": logical_id,
                "case_id": self.case["case_id"],
                "method": self.method_name,
                "phase": phase,
                "batch": batch,
                "seed": seed,
                "candidate": asdict(candidate),
                "cache_key": key,
                "physical_owner": origin,
                "physical_execution_reused": origin != owner,
                "physical_observation_sha256": sha256(completed),
                "runtime_seconds": observation.runtime_seconds,
                "execution_id": observation.execution_id,
                "valid": observation.valid,
            }
            immutable_json(receipt_path, record)
        return logical_observation(observation, candidate, phase, batch)

    def evaluate_batch(self, candidates, seed, phase, batch):
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = [
                executor.submit(self.evaluate_one, c, seed, phase, batch) for c in candidates
            ]
            values = [f.result() for f in futures]
        timing = self.episode / "batch_accounting" / f"{phase}-{batch:03d}.json"
        if not timing.exists():
            write_json(
                timing,
                {
                    "phase": phase,
                    "batch": batch,
                    "logical_queries": len(candidates),
                    "physical_wall_seconds": time.perf_counter() - start,
                    "logical_simulator_seconds": scheduled_seconds(
                        [v.runtime_seconds for v in values],
                        min(self.config.max_workers, len(values)),
                    ),
                },
            )
        return values


class EarlyReplay:
    def __init__(self, delegate, fixed_observations):
        self.delegate = delegate
        self.fixed = [o for o in fixed_observations if o.phase == "search"]

    def evaluate_batch(self, candidates, seed, phase, batch):
        if phase == "search":
            expected = [o for o in self.fixed if o.batch == batch]
            if [asdict(o.candidate) for o in expected] != [asdict(c) for c in candidates] or any(
                o.seed != seed for o in expected
            ):
                raise ValueError("Early-stop proposals differ from fixed-budget prefix")
        results = self.delegate.evaluate_batch(candidates, seed, phase, batch)
        if phase == "search" and results != expected:
            raise ValueError("Early-stop observations differ from fixed-budget prefix")
        return results
