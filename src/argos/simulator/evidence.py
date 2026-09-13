"""Exact reconstruction of pinned FlexDC's ranked, censored delay statistic."""

from __future__ import annotations

import configparser
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from argos.types import JobIdentity, QoSEvidence

FIELDS = (
    "min_job_power_watts",
    "max_job_power_watts",
    "min_time_seconds",
    "max_time_seconds",
    "qos_constraint",
    "job_size",
)


def ordered_jobs(path: Path) -> tuple[JobIdentity, ...]:
    parser = configparser.ConfigParser()
    if not parser.read(path, encoding="utf-8"):
        raise ValueError("Missing workload identity source")
    jobs = tuple(
        JobIdentity(
            i,
            name,
            tuple(
                parser.getfloat(name, f, fallback=1)
                if f == "job_size"
                else parser.getfloat(name, f)
                for f in FIELDS
            ),
        )
        for i, name in enumerate(parser.sections())
    )
    if not jobs or not np.isfinite([j.descriptors for j in jobs]).all():
        raise ValueError("Invalid ordered workload descriptors")
    return jobs


def workload_fingerprint(jobs: tuple[JobIdentity, ...]) -> str:
    return hashlib.sha256(
        json.dumps([asdict(j) for j in jobs], sort_keys=True).encode()
    ).hexdigest()


def verify_order(jobs, mix, names_path: Path, weights) -> bool:
    expected = np.asarray([j.descriptors for j in jobs])
    actual = np.asarray(mix, dtype=float)
    if actual.shape != expected.shape or not np.allclose(actual, expected, rtol=0, atol=1e-9):
        raise ValueError("Ordered workload_mix descriptors mismatch")
    if not names_path.is_file():
        return False  # Historical missing identity evidence is UNKNOWN.
    names = pd.read_csv(names_path)
    if names.job_type_id.tolist() != [j.section for j in jobs]:
        raise ValueError("Ordered simulator job names mismatch")
    if len(names) != len(weights) or not np.allclose(names.weights, weights, rtol=0, atol=1e-9):
        raise ValueError("Ordered base weights mismatch")
    return True


def reconstruct(table: pd.DataFrame, jobs, probabilities, sim_hour=1) -> tuple[QoSEvidence, ...]:
    required = ["job_type_id", "arrival_time", "end_time"]
    if not set(required).issubset(table.columns) or not np.isfinite(table[required]).all().all():
        raise ValueError("Missing/nonfinite raw QoS table columns")
    if not table.job_type_id.isin(range(len(jobs))).all():
        raise ValueError("Unknown numeric job index")
    first = 1 if sim_hour > 2 else 0
    last = sim_hour - 1 if sim_hour > 2 else sim_hour
    evidence = []
    if len(probabilities) != len(jobs):
        raise ValueError("QoS identity dimension mismatch")
    for job, pj in zip(jobs, probabilities):
        mt, qos = job.descriptors[2], job.descriptors[4]
        rows = table[table.job_type_id == job.index]
        for col, expected in [("min_execution_time", mt), ("qos_constraint", qos)]:
            if col in rows and not np.allclose(rows[col], expected, rtol=0, atol=1e-9):
                raise ValueError("Raw table job descriptor mismatch")
        f = rows[(rows.end_time != -1) & (rows.arrival_time > first * 3600)]
        u = rows[
            (rows.end_time == -1)
            & (rows.arrival_time > first * 3600)
            & (rows.arrival_time <= last * 3600)
            & (rows.arrival_time + mt < sim_hour * 3600)
        ]
        delays = np.r_[f.end_time - f.arrival_time - mt, sim_hour * 3600 - u.arrival_time - mt]
        n, m = len(delays), int(np.sum(delays > qos * mt))
        numerator = max(m - 1, 0) if n >= 2 else m if n else None
        denominator = n - 1 if n >= 2 else 1 if n else None
        reconstructed = numerator / denominator if n else 0.0
        if not np.isclose(pj, reconstructed, rtol=1e-10, atol=1e-12):
            raise ValueError("Raw-table/reported Pj mismatch")
        evidence.append(
            QoSEvidence(
                job,
                pj,
                n,
                len(f),
                len(u),
                m,
                numerator,
                denominator,
                horizon_seconds=sim_hour * 3600,
                threshold_sojourn_seconds=mt * (1 + qos),
                threshold_exceeds_horizon=mt * (1 + qos) >= sim_hour * 3600,
            )
        )
    return tuple(evidence)
