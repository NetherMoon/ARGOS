"""Exercise actual recovery normalization without starting a simulator."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from argos.config import Config
from argos.contracts import Costs
from argos.provenance import read_json, write_json
from argos.simulator.flexdc_adapter import FlexDCRunner
from argos.types import (
    Candidate,
    FlexDCObservation,
    JobIdentity,
    Metrics,
    QoSEvidence,
    observation_from_dict,
)


def cached_runner(tmp_path, monkeypatch):
    import argos.simulator.flexdc_adapter as adapter

    candidate = Candidate("cached", 0.4, 0.1, (0.25,) * 4, "test")
    metrics = Metrics(0.1, 0.2, (0.0,) * 4, 42.0)
    evidence = tuple(
        QoSEvidence(
            JobIdentity(i, f"job{i}", (100.0, 200.0, 10.0, 20.0, 1.0, 1.0)), 0.0, 1, 1, 0, 0, 0, 1
        )
        for i in range(4)
    )
    identity = {
        "candidate": asdict(candidate),
        "seed": 20,
        "phase": "search",
        "batch": 1,
        "context": "context",
    }
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    reported = {
        "qos_evidence": [asdict(e) for e in evidence],
        "input_hashes": {},
        "output_hashes": {},
    }
    observation = FlexDCObservation(
        candidate,
        20,
        "search",
        1,
        True,
        metrics,
        "EVIDENCE_QUALIFIED_FEASIBLE",
        0.0,
        key,
        reported,
        {"results": "results.csv", "diagnostics": "diagnostics.csv"},
        qos_evidence=evidence,
    )
    cache = tmp_path / "flexdc_raw" / key / "observation.json"
    write_json(cache, asdict(observation))
    runner = object.__new__(FlexDCRunner)
    runner.episode = tmp_path
    runner.config = Config()
    runner.context_id = "context"
    runner.workload = Path("workload.ini")
    runner.costs = Costs(1, 10, 0.3, 20, 2, 0.1)
    monkeypatch.setattr(adapter, "parse_output", lambda *args: (metrics, reported))
    return runner, cache, candidate


def test_actual_recovery_accepts_json_list_tuple_roundtrip(tmp_path, monkeypatch):
    runner, cache, candidate = cached_runner(tmp_path, monkeypatch)
    result = runner.evaluate(candidate, 20, "search", 1)
    assert result == observation_from_dict(read_json(cache))
    assert not list(tmp_path.glob("flexdc_raw/*/attempt-*"))


@pytest.mark.parametrize("field", ["reported", "qos_evidence"])
def test_actual_recovery_still_rejects_evidence_tampering(tmp_path, monkeypatch, field):
    runner, cache, candidate = cached_runner(tmp_path, monkeypatch)
    data = read_json(cache)
    rows = data["reported"]["qos_evidence"] if field == "reported" else data["qos_evidence"]
    rows[0]["job"]["section"] = "swapped"
    write_json(cache, data)
    with pytest.raises(ValueError, match="QoS evidence changed"):
        runner.evaluate(candidate, 20, "search", 1)
    assert not list(tmp_path.glob("flexdc_raw/*/attempt-*"))
