from dataclasses import asdict, replace

import numpy as np
import pandas as pd
import pytest

from argos.contracts import assessment, qualified
from argos.simulator.evidence import (
    ordered_jobs,
    validate_reported_qos_evidence,
    verify_order,
    workload_fingerprint,
)
from argos.types import Candidate, FlexDCObservation, JobIdentity, Metrics, observation_from_dict

JOB = JobIdentity(0, "same-name-is-not-a-numeric-index", (100, 200, 10, 20, 1, 1))


def table(delays):
    return pd.DataFrame(
        {
            "job_type_id": [0] * len(delays),
            "arrival_time": [1] * len(delays),
            "end_time": [11 + d for d in delays],
        }
    )


@pytest.mark.parametrize(
    "delays,pj,numerator,denominator",
    [
        ([], 0, None, None),
        ([0], 0, 0, 1),
        ([11], 1, 1, 1),
        ([0, 11], 0, 0, 1),
        ([11, 12], 1, 1, 1),
        ([0, 11, 12], 0.5, 1, 2),
        ([10, 10], 0, 0, 1),
    ],
)
def test_exact_estimator_empty_singleton_exceedance_quirks(delays, pj, numerator, denominator):
    e = validate_reported_qos_evidence(table(delays), [JOB], [pj])[0]
    assert (e.observation_count, e.estimator_numerator, e.estimator_denominator) == (
        len(delays),
        numerator,
        denominator,
    )
    assert e.exceedance_count == sum(d > 10 for d in delays)


def test_exact_inclusion_filters_and_censored_observations():
    t = pd.DataFrame(
        {
            "job_type_id": [0] * 6,
            "arrival_time": [0, 1, 3590, 3589, 3600, -10],
            "end_time": [100, -1, -1, -1, -1, 100],
        }
    )
    # Arrival zero/prefill excluded; strict minimum-runtime cutoff excludes 3590.
    e = validate_reported_qos_evidence(t, [JOB], [0])[0]
    assert (e.finished_count, e.unfinished_count, e.observation_count, e.exceedance_count) == (
        0,
        2,
        2,
        1,
    )
    with pytest.raises(ValueError, match="Pj mismatch"):
        validate_reported_qos_evidence(t, [JOB], [0.5])


def test_later_hours_finished_filter_has_no_upper_cutoff():
    t = pd.DataFrame(
        {"job_type_id": [0] * 3, "arrival_time": [3600, 8000, 8000], "end_time": [9000, 8030, -1]}
    )
    e = validate_reported_qos_evidence(t, [JOB], [1], sim_hour=3)[0]
    assert (e.finished_count, e.unfinished_count, e.observation_count) == (1, 0, 1)


def test_qualification_unknown_empty_and_objective_unchanged():
    c = Candidate("a", 0.4, 0.1, (1,), "test")
    o = FlexDCObservation(c, 20, "search", 1, True, Metrics(0.1, 0.2, (0,), 42), "legacy", 0, "a")
    legacy = asdict(o)
    legacy.pop("qos_evidence")
    legacy.pop("schema_version")
    parsed = observation_from_dict(legacy)
    assert parsed.schema_version == 1 and assessment(parsed)["evidence_status"] == "UNKNOWN"
    empty = replace(o, qos_evidence=validate_reported_qos_evidence(table([]), [JOB], [0]))
    nonempty = replace(o, qos_evidence=validate_reported_qos_evidence(table([0]), [JOB], [0]))
    assert not qualified(empty) and assessment(empty)["evidence_status"] == "INSUFFICIENT"
    assert qualified(nonempty) and not qualified(nonempty, 2)
    assert o.metrics.objective == empty.metrics.objective == nonempty.metrics.objective == 42
    assert not qualified(replace(nonempty, valid=False))
    assert observation_from_dict(asdict(nonempty)) == nonempty


def test_ordered_descriptors_names_and_duplicates(tmp_path):
    p = tmp_path / "workload.ini"
    profile = "min_job_power_watts=100\nmax_job_power_watts=200\nmin_time_seconds=10\nmax_time_seconds=20\nqos_constraint=1\njob_size=1\n"
    p.write_text("[a]\n" + profile + "[b]\n" + profile)
    jobs = ordered_jobs(p)
    assert jobs[0].descriptors == jobs[1].descriptors and jobs[0].section != jobs[1].section
    names = tmp_path / "base_weights.csv"
    pd.DataFrame({"job_type_id": ["a", "b"], "weights": [0.4, 0.6]}).to_csv(names, index=False)
    mix = [j.descriptors for j in jobs]
    assert verify_order(jobs, mix, names, [0.4, 0.6])
    fingerprint = workload_fingerprint(jobs)
    assert fingerprint != workload_fingerprint(tuple(reversed(jobs)))
    pd.DataFrame({"job_type_id": ["b", "a"], "weights": [0.4, 0.6]}).to_csv(names, index=False)
    with pytest.raises(ValueError, match="job names"):
        verify_order(jobs, mix, names, [0.4, 0.6])
    mix = np.array(mix)
    mix[1, 0] = 99
    with pytest.raises(ValueError, match="descriptors"):
        verify_order(jobs, mix, names, [0.4, 0.6])
