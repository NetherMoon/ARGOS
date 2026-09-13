"""Protect reported simulator truth and orthogonal assessment dimensions."""

from dataclasses import replace
from importlib import metadata

import pandas as pd
import pytest
from test_output_parser import inputs

from argos.contracts import assessment, confirmation_status
from argos.environment import RUNTIME_PACKAGES, package_versions
from argos.simulator.evidence import ordered_jobs, validate_reported_qos_evidence
from argos.simulator.output_parser import parse_output
from argos.types import Candidate, FlexDCObservation, Metrics


def test_reported_pj_authoritative_and_mismatch_rejected(tmp_path):
    args, _ = inputs(tmp_path)
    jobs = ordered_jobs(args[7])
    pd.DataFrame({"job_type_id": [j.section for j in jobs], "weights": args[2].weights}).to_csv(
        tmp_path / "base_weights.csv", index=False
    )
    table = pd.DataFrame(
        {
            "job_type_id": [j.index for j in jobs],
            "arrival_time": [1] * len(jobs),
            "end_time": [1 + j.descriptors[2] for j in jobs],
        }
    )
    table.to_csv(tmp_path / "job_table.csv", index=False)
    raw = pd.read_csv(args[0])
    # Distinct from the exact validation value zero, but inside the declared tolerance.
    raw["QoS_Delay_Probabilities"] = "[0.0000000000001,0,0,0]"
    raw.to_csv(args[0], index=False)
    metrics, reported = parse_output(*args)
    assert metrics.pj == (1e-13, 0, 0, 0)
    assert reported["qos_evidence"][0]["pj"] == metrics.pj[0]
    assert reported["qos_evidence"][0]["estimator_numerator"] == 0
    assert reported["reported_pj_validation"] == "PASS"
    assert reported["pj_source"] == "grid_search_results.csv:QoS_Delay_Probabilities"
    table.loc[0, "end_time"] = 1 + jobs[0].descriptors[2] * (jobs[0].descriptors[4] + 2)
    table.to_csv(tmp_path / "job_table.csv", index=False)
    with pytest.raises(ValueError, match="reported Pj mismatch"):
        parse_output(*args)
    assert pd.read_csv(args[0]).iloc[0]["QoS_Delay_Probabilities"] == "[0.0000000000001,0,0,0]"


def observation(tmp_path, p90=0.2, empty=False):
    workload = tmp_path / "workload.ini"
    workload.write_text(
        "[job]\nmin_job_power_watts=1\nmax_job_power_watts=2\nmin_time_seconds=10\nmax_time_seconds=20\nqos_constraint=1\njob_size=1\n"
    )
    table = pd.DataFrame(
        {
            "job_type_id": [] if empty else [0],
            "arrival_time": [] if empty else [1],
            "end_time": [] if empty else [11],
        }
    )
    evidence = validate_reported_qos_evidence(table, ordered_jobs(workload), [0])
    return FlexDCObservation(
        Candidate("test", 0.4, 0.1, (1,), "test"),
        20,
        "confirmation",
        1,
        True,
        Metrics(0.1, p90, (0,), 42),
        "PARSED",
        0,
        "test",
        qos_evidence=evidence,
    )


def test_dual_failure_preserves_execution_and_both_assessments(tmp_path):
    result = assessment(observation(tmp_path, p90=0.5, empty=True))
    assert result["execution_status"] == "PARSED" and result["execution_valid"]
    assert result["numerical_feasible"] is False
    assert result["evidence_status"] == "INSUFFICIENT"
    assert result["evidence_sufficient"] is False
    assert result["evidence_qualified_feasible"] is False


@pytest.mark.parametrize(
    "runs,passes,expected",
    [(0, 0, "NOT_RUN"), (2, 0, "NONE_PASS"), (2, 1, "PARTIAL_PASS"), (2, 2, "ALL_PASS")],
)
def test_confirmation_executions_not_plans(tmp_path, runs, passes, expected):
    valid = observation(tmp_path)
    insufficient = observation(tmp_path, empty=True)
    observations = [valid if i < passes else insufficient for i in range(runs)]
    assert confirmation_status(observations) == "CONFIRMATION_" + expected
    assert all(assessment(o)["numerical_feasible"] for o in observations)


def test_reporting_no_confirmations_and_dual_failure(tmp_path):
    from argos.config import Config
    from argos.controller.argos_controller import SearchState
    from argos.reporting.report import report

    o = replace(observation(tmp_path, p90=0.5, empty=True), phase="search")
    state = SearchState("test", phase="NO_BID", observations=[o])
    summary = report(tmp_path, Config(), state)
    assert summary["confirmation_status"] == "CONFIRMATION_NOT_RUN"
    assert summary["assessments"]["test"]["execution_status"] == "PARSED"
    row = pd.read_csv(tmp_path / "search/all_observations.csv").iloc[0]
    assert not row.numerical_feasible and not row.evidence_sufficient and row.status == "PARSED"


def test_doctor_package_collection_without_dev_tools(monkeypatch):
    def version(name):
        if name in {"pytest", "ruff"}:
            raise metadata.PackageNotFoundError(name)
        return "1.2.3"

    monkeypatch.setattr(metadata, "version", version)
    result = package_versions()
    assert result["pytest"] == result["ruff"] == "NOT_INSTALLED"
    assert all(result[name] == "1.2.3" for name in RUNTIME_PACKAGES)


def test_missing_runtime_dependency_remains_an_error(monkeypatch):
    def missing(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", missing)
    with pytest.raises(metadata.PackageNotFoundError):
        package_versions()
