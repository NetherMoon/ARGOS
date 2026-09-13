"""Measured truth drives refinement; confirmation never selects an incumbent."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Protocol

import numpy as np

from argos.config import Config
from argos.contracts import observation_rank, qualified
from argos.controller.stopping import early_stop_details
from argos.provenance import read_json, write_json
from argos.search.candidates import Domain, FixedRadius
from argos.search.regions import tradeoff_select
from argos.types import (
    Candidate,
    FlexDCObservation,
    Region,
    candidate_from_dict,
    observation_from_dict,
)


class Simulator(Protocol):
    def evaluate_batch(
        self, candidates: list[Candidate], seed: int, phase: str, batch: int
    ) -> list[FlexDCObservation]: ...


@dataclass
class SearchState:
    episode_id: str
    completed_batches: int = 0
    search_calls: int = 0
    phase: str = "SEARCH"
    observations: list[FlexDCObservation] = field(default_factory=list)
    pending: list[Candidate] = field(default_factory=list)
    incumbent: Candidate | None = None
    confirmation_index: int = 0
    elapsed_seconds: float = 0.0
    stop_reason: str | None = None

    @classmethod
    def load(cls, path: Path) -> SearchState:
        d = read_json(path)
        d["observations"] = [observation_from_dict(o) for o in d["observations"]]
        d["pending"] = [candidate_from_dict(c) for c in d["pending"]]
        d["incumbent"] = candidate_from_dict(d["incumbent"]) if d["incumbent"] else None
        return cls(**d)


class Controller:
    def __init__(
        self,
        episode: Path,
        config: Config,
        domain: Domain,
        regions: list[Region],
        simulator: Simulator,
        predictor: Callable[[Candidate], Candidate],
    ):
        config.validate()
        self.episode = episode
        self.config = config
        self.domain = domain
        self.radius_policy = FixedRadius(config.local_radius)
        self.regions = regions
        self.simulator = simulator
        self.predictor = predictor
        episode.mkdir(parents=True, exist_ok=True)
        self.path = episode / "state.json"
        self.state = (
            SearchState.load(self.path) if self.path.exists() else SearchState(episode.name)
        )
        self.start = time.perf_counter()
        self.previous_elapsed = self.state.elapsed_seconds
        if not self.path.exists():
            self.save()

    def save(self) -> None:
        self.state.elapsed_seconds = self.previous_elapsed + time.perf_counter() - self.start
        write_json(self.path, asdict(self.state))

    def measured(self) -> list[FlexDCObservation]:
        return sorted(
            [o for o in self.state.observations if o.phase == "search" and o.valid],
            key=lambda o: (
                observation_rank(o, self.config.min_qos_observations_per_type),
                o.candidate.candidate_id,
            ),
        )

    def next_batch(self) -> list[Candidate]:
        s = self.state
        c = self.config
        size = min(c.batch_size, c.max_search_calls - s.search_calls)
        batch = s.completed_batches + 1
        rng = np.random.default_rng(np.random.SeedSequence([c.candidate_seed, batch]))
        used = [o.candidate for o in s.observations if o.phase == "search"]
        chosen = []
        serial = 0

        def add(candidate: Candidate) -> bool:
            self.domain.validate(candidate)
            if all(
                self.domain.distance(candidate, other) > c.dedupe_distance
                for other in used + chosen
            ):
                chosen.append(candidate)
                return True
            return False

        unused = [
            r.representative
            for r in self.regions
            if all(self.domain.distance(r.representative, o) > c.dedupe_distance for o in used)
        ]
        guided_slots = max(0, size - min(c.independent_per_batch, size))
        measured = self.measured()
        if not measured:
            for representative in unused:
                if len(chosen) >= guided_slots:
                    break
                add(representative)
        else:
            # Keep one as-yet unprobed V3 region in every refinement batch when available.
            if unused and guided_slots:
                add(unused[0])
            anchors = []
            for observation in measured:
                if all(
                    self.domain.distance(observation.candidate, a) > c.region_distance / 2
                    for a in anchors
                ):
                    anchors.append(observation.candidate)
                if len(anchors) >= c.max_regions:
                    break
            local_pool = []
            target = (guided_slots - len(chosen)) * c.local_screen_pool_factor
            while (
                len(local_pool) < target
                if c.local_proposal_mode == "v3_screened"
                else len(chosen) < guided_slots
            ) and serial < 500:
                anchor = anchors[serial % len(anchors)]
                proposal = self.domain.local(
                    anchor,
                    rng,
                    self.radius_policy.radius(batch=batch, observations=tuple(s.observations)),
                    f"b{batch:03d}-local-{serial:04d}",
                )
                if c.local_proposal_mode == "v3_screened":
                    if all(
                        self.domain.distance(proposal, other) > c.dedupe_distance
                        for other in used + chosen + local_pool
                    ):
                        local_pool.append(self.predictor(proposal))
                else:
                    add(proposal)
                serial += 1
            if local_pool:
                for proposal in tradeoff_select(
                    local_pool, guided_slots - len(chosen), self.domain
                ):
                    add(proposal)
        while len(chosen) < size and serial < 1500:
            add(self.domain.independent(rng, f"b{batch:03d}-independent-{serial:04d}"))
            serial += 1
        return [self.predictor(candidate) for candidate in chosen]

    def run(self) -> SearchState:
        s = self.state
        c = self.config
        while s.phase not in {"DONE", "NO_BID", "ERROR"}:
            if s.phase == "SEARCH":
                elapsed = self.previous_elapsed + time.perf_counter() - self.start
                exhausted = (
                    s.completed_batches >= c.max_search_batches
                    or s.search_calls >= c.max_search_calls
                    or (c.max_wall_seconds is not None and elapsed >= c.max_wall_seconds)
                )
                early = (
                    c.search_mode == "early_stop" and early_stop_details(s.observations, c)["stop"]
                )
                if not s.pending and (exhausted or early):
                    reason = (
                        "HARD_MAX_SEARCH_CALLS"
                        if s.search_calls >= c.max_search_calls
                        else "HARD_MAX_SEARCH_BATCHES"
                        if s.completed_batches >= c.max_search_batches
                        else "HARD_MAX_WALL_SECONDS"
                        if exhausted
                        else "EARLY_STOP_QUALIFIED_LOCAL_PATIENCE"
                    )
                    self.select_for_confirmation(reason)
                    continue
                if not s.pending:
                    s.pending = self.next_batch()
                    if not s.pending:
                        self.select_for_confirmation("no distinct legal candidates")
                        continue
                    s.search_calls += len(s.pending)
                    self.save()  # reserve budget and deterministic candidate identities BEFORE execution
                batch = s.completed_batches + 1
                start = time.perf_counter()
                results = self.simulator.evaluate_batch(s.pending, c.search_seed, "search", batch)
                if len(results) != len(s.pending):
                    raise ValueError("Simulator returned wrong batch size")
                for candidate, observation in zip(s.pending, results):
                    if (
                        observation.candidate != candidate
                        or observation.seed != c.search_seed
                        or observation.phase != "search"
                    ):
                        raise ValueError("Simulator result identity mismatch")
                if hasattr(self.simulator, "search_attempts"):
                    s.search_calls = max(s.search_calls, self.simulator.search_attempts())
                s.observations.extend(results)
                s.pending = []
                s.completed_batches += 1
                write_json(
                    self.episode / "search" / f"batch_{batch:03d}.json",
                    {
                        "wall_seconds": time.perf_counter() - start,
                        "observations": [asdict(o) for o in results],
                    },
                )
                valid = self.measured()
                if valid and qualified(valid[0], self.config.min_qos_observations_per_type):
                    s.incumbent = valid[0].candidate
                if any(not o.valid for o in results):
                    s.phase = "ERROR"
                    s.stop_reason = "invalid simulator evidence; inspect preserved raw outputs"
                self.save()
                print(
                    f"Batch {batch}: {sum(o.valid for o in results)}/{len(results)} valid, {sum(qualified(o, c.min_qos_observations_per_type) for o in results)} observed feasible; {s.search_calls}/{c.max_search_calls} search calls",
                    flush=True,
                )
            elif s.phase == "CONFIRM":
                if s.confirmation_index >= len(c.confirmation_seeds):
                    s.phase = "DONE"
                    self.save()
                    continue
                seed = c.confirmation_seeds[s.confirmation_index]
                # Incumbent is immutable throughout this phase, including after failed seeds.
                result = self.simulator.evaluate_batch(
                    [s.incumbent], seed, "confirmation", s.confirmation_index + 1
                )[0]
                if (
                    result.candidate != s.incumbent
                    or result.seed != seed
                    or result.phase != "confirmation"
                ):
                    raise ValueError("Confirmation identity mismatch")
                s.observations.append(result)
                s.confirmation_index += 1
                if not result.valid:
                    s.phase = "ERROR"
                    s.stop_reason = "invalid confirmation evidence"
                self.save()
                print(f"Confirmation seed {seed}: {result.status}", flush=True)
            else:
                raise ValueError(f"Unknown search phase {s.phase}")
        return s

    def select_for_confirmation(self, reason: str) -> None:
        s = self.state
        s.stop_reason = reason
        valid = self.measured()
        if valid and qualified(valid[0], self.config.min_qos_observations_per_type):
            s.incumbent = replace(valid[0].candidate)
            s.phase = "CONFIRM"
            write_json(self.episode / "final/selected_candidate.json", asdict(s.incumbent))
        else:
            s.phase = "NO_BID"
        self.save()
