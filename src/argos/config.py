"""Finite, explicit episode settings. Unknown configuration keys are rejected."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    workload: str = "configs/workload/W1-train-qos3333.ini"
    experiment: str = "configs/experiment/new_iso/traditional_signal/generated_server_counts/exp_traditional_iso16_servers_1000.ini"
    cluster: str = "configs/cluster/cluster.ini"
    server_count: int = 1000
    utilization: float = 0.6
    policy: str = "AQA"
    search_seed: int = 20
    candidate_seed: int = 20260912
    confirmation_seeds: tuple[int, ...] = (100020, 100021)
    starts: int = 512
    iterations: int = 1500
    snapshot_every: int = 50
    torch_threads: int = 4
    weight_min: float = 0.15
    weight_max: float = 0.45
    r_over_p_max: float = 0.6
    max_regions: int = 6
    region_distance: float = 0.12
    dedupe_distance: float = 0.0001
    promising_per_snapshot: int = 24
    batch_size: int = 8
    independent_per_batch: int = 2
    max_workers: int = 4
    max_search_batches: int = 4
    max_search_calls: int = 32
    local_radius: float = 0.12
    max_wall_seconds: float | None = None
    simulator_timeout_seconds: float = 1800.0

    def validate(self) -> None:
        for name in [
            "server_count",
            "starts",
            "iterations",
            "snapshot_every",
            "torch_threads",
            "max_regions",
            "promising_per_snapshot",
            "batch_size",
            "independent_per_batch",
            "max_workers",
            "max_search_batches",
            "max_search_calls",
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        for seed in [self.search_seed, self.candidate_seed, *self.confirmation_seeds]:
            if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
                raise ValueError("Seeds must be integers in [0, 2**32)")
        if self.search_seed in self.confirmation_seeds or len(set(self.confirmation_seeds)) != len(
            self.confirmation_seeds
        ):
            raise ValueError("Confirmation seeds must be fresh and distinct")
        if self.policy != "AQA":
            raise ValueError("This validated V3 context supports AQA only")
        if not 0 < self.utilization <= 1 or not 0 <= self.weight_min <= self.weight_max <= 1:
            raise ValueError("Invalid utilization or weight bounds")
        if self.r_over_p_max != 0.6:
            raise ValueError("Reviewed V3 domain requires R <= 0.6 * Pbar")
        if self.independent_per_batch > self.batch_size:
            raise ValueError("Independent slots exceed batch size")
        for name in [
            "region_distance",
            "dedupe_distance",
            "local_radius",
            "simulator_timeout_seconds",
        ]:
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.max_wall_seconds is not None and (
            not math.isfinite(self.max_wall_seconds) or self.max_wall_seconds <= 0
        ):
            raise ValueError("Wall budget must be finite and positive")

    @classmethod
    def load(cls, path: Path) -> Config:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("Configuration must be a mapping")
        if "confirmation_seeds" in data:
            data["confirmation_seeds"] = tuple(data["confirmation_seeds"])
        config = cls(**data)
        config.validate()
        return config

    def save(self, path: Path) -> None:
        data = asdict(self)
        data["confirmation_seeds"] = list(self.confirmation_seeds)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
