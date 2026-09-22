"""Explicit domains in kW/server; legacy ratio bounds are converted, never relabeled."""

import configparser
from dataclasses import asdict, dataclass

import numpy as np

from argos.search.candidates import Domain as ArgosDomain


@dataclass(frozen=True)
class Domain:
    name: str
    p_low: float
    p_high: float
    r_low: float
    r_high: float
    w_low: float
    w_high: float
    count: int
    pr_max: float | None = None
    r_over_p: float | None = None
    p_ratio_scale: float = 1.0
    r_ratio_scale: float = 1.0

    def __post_init__(self):
        vals = [
            self.p_low,
            self.p_high,
            self.r_low,
            self.r_high,
            self.w_low,
            self.w_high,
            self.p_ratio_scale,
            self.r_ratio_scale,
        ]
        if (
            not np.isfinite(vals).all()
            or self.count < 1
            or self.p_low <= 0
            or self.p_high < self.p_low
            or self.r_low < 0
            or self.r_high < self.r_low
        ):
            raise ValueError("Invalid domain")
        if (
            not 0 <= self.w_low <= self.w_high <= 1
            or self.count * self.w_low > 1 + 1e-12
            or self.count * self.w_high < 1 - 1e-12
        ):
            raise ValueError("Impossible bounded simplex")
        if any(self.r_max(p) < self.r_low for p in [self.p_low, self.p_high]):
            raise ValueError("Empty physical reserve interval")

    def r_max(self, p):
        return min(
            self.r_high,
            self.pr_max - p if self.pr_max is not None else self.r_high,
            self.r_over_p * p if self.r_over_p is not None else self.r_high,
        )

    def project(self, params):
        x = np.asarray(params, dtype=float)
        if x.shape != (self.count + 2,) or not np.isfinite(x).all():
            raise ValueError("Malformed candidate")
        p = float(np.clip(x[0], self.p_low, self.p_high))
        r = float(np.clip(x[1], self.r_low, self.r_max(p)))
        # Reuse the tested existing ARGOS bounded-simplex implementation without changing it.
        simplex = ArgosDomain(
            1.0, 2.0, 100.0, 0.0, 10.0, (self.w_low,) * self.count, (self.w_high,) * self.count
        )
        y = (p, r, *simplex.project(x[2:]))
        self.validate(y)
        return y

    def validate(self, x):
        if len(x) != self.count + 2 or not np.isfinite(x).all():
            raise ValueError("Malformed candidate")
        p, r, *w = x
        e = 1e-10
        if (
            not self.p_low - e <= p <= self.p_high + e
            or not self.r_low - e <= r <= self.r_max(p) + e
            or abs(sum(w) - 1) > e
            or min(w) < self.w_low - e
            or max(w) > self.w_high + e
        ):
            raise ValueError("Candidate outside " + self.name)

    def to_dict(self):
        return dict(asdict(self), units="kW/server; weights unitless")


def load_domain(root, name, jobs, experiment):
    c = configparser.ConfigParser()
    c.read(root / "configs/canonical_cost_source.ini")
    n = jobs.job_type_count
    maxpower = float(np.mean(list(jobs.all_max_job_power.values())))
    minpower = float(np.mean(list(jobs.all_min_job_power.values())))
    if name == "legacy_sa":
        ps = (
            maxpower * experiment.utilization + experiment.idle_power * (1 - experiment.utilization)
        ) / 1000
        rs = (maxpower - experiment.idle_power) / 2000
        v = c["boundaries"]
        return Domain(
            name,
            float(v["p_low"]) * ps,
            float(v["p_high"]) * ps,
            float(v["r_low"]) * rs,
            float(v["r_high"]) * rs,
            float(v["w_low"]),
            float(v["w_high"]),
            n,
            p_ratio_scale=ps,
            r_ratio_scale=rs,
        )
    if name == "argos_v3_physical":
        from argos.config import Config

        lo, hi = Config().weight_bounds(n)
        # Pinned generic V3 calculate_pr_bounds defaults; parity-tested against its real function.
        return Domain(
            name,
            0.9 * (minpower / 1000),
            min(maxpower / 1000, 1.2 * (maxpower / 1000) - 0.01),
            0.01,
            1.2 * (maxpower / 1000),
            lo,
            hi,
            n,
            pr_max=1.2 * (maxpower / 1000),
            r_over_p=0.6,
        )
    raise ValueError("Explicit domain profile required")
