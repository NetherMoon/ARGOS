"""Small per-episode discrepancy models; never train on confirmations."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
from scipy.linalg import helmert
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern


def coordinates(domain, candidates):
    """Five independent coordinates preserving H1's normalized J=4 metric."""
    if len(domain.lower) != 4 or not np.allclose(
        np.subtract(domain.upper, domain.lower), domain.upper[0] - domain.lower[0]
    ):
        raise ValueError("vNext geometry requires four equally bounded weight coordinates")
    z = np.asarray([domain.encode(c) for c in candidates], dtype=np.float64)
    return np.c_[z[:, :2] / np.sqrt(3), z[:, 2:] @ helmert(4).T / np.sqrt(12)]


def behaviors(metrics):
    return np.array([metrics.mean_tracking, metrics.p90, *metrics.pj], dtype=np.float64)


@dataclass(frozen=True)
class CorrectionSpec:
    model: str = "C0"
    space: str = "physical"
    bandwidth: float = 0.24
    ridge_alpha: float = 0.1
    gp_noise: float = 0.05
    gp_length: float = 0.24
    gp_bounds: tuple = (0.03, 0.8)
    # Fixed regularization floor, not an estimate of scenario variability.
    tracking_floor: tuple = (1e-6, 1e-3)
    fallback: str = "C2"


class Correction:
    def __init__(self, domain, spec=None):
        spec = spec or CorrectionSpec()
        if spec.model not in {"C0", "C1", "C2", "C3"} or spec.space not in {
            "physical",
            "tracking_log",
        }:
            raise ValueError("Unknown discrepancy specification")
        self.domain, self.spec = domain, spec
        self.x = np.empty((0, 5))
        self.y = np.empty((0, 6))
        self.gps = []
        self.events = []
        self.training_ids = []
        self.scale = np.array([0.3, 0.3, 0.1, 0.1, 0.1, 0.1])

    def transform(self, values):
        values = np.asarray(values, dtype=np.float64).copy()
        if self.spec.space == "tracking_log":
            values[..., :2] = np.log(values[..., :2] + self.spec.tracking_floor)
            return values / np.array([1, 1, 0.1, 0.1, 0.1, 0.1])
        return values / self.scale

    def inverse(self, values):
        values = np.asarray(values, dtype=np.float64).copy()
        if self.spec.space == "tracking_log":
            values *= np.array([1, 1, 0.1, 0.1, 0.1, 0.1])
            values[..., :2] = np.exp(np.clip(values[..., :2], -30, 20)) - self.spec.tracking_floor
        else:
            values *= self.scale
        values[..., :2] = np.maximum(values[..., :2], 0)
        values[..., 2:] = np.clip(values[..., 2:], 0, 1)
        return values

    def fit(self, observations):
        if any(o.phase != "search" for o in observations):
            raise ValueError("Confirmation outcomes cannot train discrepancy models")
        valid = [
            o
            for o in observations
            if o.valid and o.metrics is not None and o.candidate.prediction is not None
        ]
        self.training_ids = [o.execution_id for o in valid]
        self.gps = []
        self.events = []
        if not valid:
            self.x = np.empty((0, 5))
            self.y = np.empty((0, 6))
            return self
        x = coordinates(self.domain, [o.candidate for o in valid])
        y = np.array(
            [
                self.transform(behaviors(o.metrics))
                - self.transform(behaviors(o.candidate.prediction))
                for o in valid
            ]
        )
        # Repeats contribute measurements to one geometric site, not extra geometry.
        groups = {}
        for i, row in enumerate(x):
            groups.setdefault(tuple(np.round(row, 12)), []).append(i)
        self.x = np.array([x[idx].mean(axis=0) for idx in groups.values()])
        self.y = np.array([y[idx].mean(axis=0) for idx in groups.values()])
        self.counts = [len(idx) for idx in groups.values()]
        if self.spec.model == "C3":
            try:
                for j in range(6):
                    gp = GaussianProcessRegressor(
                        kernel=ConstantKernel(1.0, (0.1, 10))
                        * Matern(self.spec.gp_length, self.spec.gp_bounds, nu=2.5),
                        alpha=self.spec.gp_noise**2,
                        normalize_y=False,
                        n_restarts_optimizer=0,
                        random_state=0,
                    )
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always")
                        gp.fit(self.x, self.y[:, j])
                    self.events.extend(
                        {"kind": "gp_warning", "output": j, "message": str(w.message)}
                        for w in caught
                    )
                    self.gps.append(gp)
            except (ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
                self.events.append(
                    {"kind": "gp_failure", "fallback": self.spec.fallback, "message": str(exc)}
                )
                self.gps = []
        return self

    def predict(self, candidates):
        base = np.array([self.transform(behaviors(c.prediction)) for c in candidates])
        if self.spec.model == "C0" or not len(self.x):
            return self.inverse(base), None
        x = coordinates(self.domain, candidates)
        if len(self.gps) == 6:
            pairs = [g.predict(x, return_std=True) for g in self.gps]
            delta = np.column_stack([p[0] for p in pairs])
            std = np.column_stack([p[1] for p in pairs])
            mean = self.inverse(base + delta)
            # Latent model standard deviation only, propagated through physical decoding.
            uncertainty = np.maximum(self.inverse(base + delta + std) - mean, 0)
            return mean, uncertainty
        model = self.spec.fallback if self.spec.model == "C3" else self.spec.model
        predictions = []
        for q in x:
            d = self.x - q
            weights = np.exp(-0.5 * np.sum(d * d, axis=1) / self.spec.bandwidth**2)
            weights = np.maximum(weights, 1e-12)
            if model == "C1":
                predictions.append(np.average(self.y, axis=0, weights=weights))
            else:
                design = np.c_[np.ones(len(d)), d / self.spec.bandwidth]
                penalty = np.diag([1e-8] + [self.spec.ridge_alpha] * 5)
                coef = np.linalg.solve(
                    design.T @ (weights[:, None] * design) + penalty,
                    design.T @ (weights[:, None] * self.y),
                )
                predictions.append(coef[0])
        return self.inverse(base + np.asarray(predictions)), None
