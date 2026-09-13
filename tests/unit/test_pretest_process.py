"""Deterministic process-race and execution-recovery regressions; no simulator runs."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import psutil
import pytest

from argos.config import Config
from argos.contracts import Costs
from argos.provenance import read_json
from argos.simulator import process_identity as identity
from argos.simulator.flexdc_adapter import FlexDCRunner
from argos.types import Candidate


@pytest.mark.parametrize(
    "case,state",
    [
        ("absent", "ABSENT"),
        ("exists", "LIVE"),
        ("vanish_constructor", "ABSENT"),
        ("vanish_created", "ABSENT"),
        ("zombie", "ABSENT"),
        ("denied", "UNKNOWN"),
        ("other_error", "UNKNOWN"),
    ],
)
def test_process_inspection_races(monkeypatch, case, state):
    monkeypatch.setattr(identity.psutil, "pid_exists", lambda pid: case != "absent")
    error = {
        "vanish_created": psutil.NoSuchProcess(12),
        "zombie": psutil.ZombieProcess(12),
        "denied": psutil.AccessDenied(12),
        "other_error": psutil.Error("unknown"),
    }.get(case)
    process = Mock(create_time=Mock(side_effect=error, return_value=100.0))
    constructor = Mock(
        return_value=process,
        side_effect=psutil.NoSuchProcess(12) if case == "vanish_constructor" else None,
    )
    monkeypatch.setattr(identity.psutil, "Process", constructor)
    result = identity.inspect_process(12)
    assert result.state == state
    if case == "absent":
        constructor.assert_not_called()
    if case == "exists":
        assert result.created == 100.0


@pytest.mark.parametrize("created,live", [(100.0, True), (90.0, False)])
def test_matching_and_reused_pid(monkeypatch, created, live):
    monkeypatch.setattr(
        identity, "inspect_process", lambda pid: identity.ProcessIdentity("LIVE", 100.0)
    )
    assert identity.original_process_running({"pid": 12, "created": created}) is live


@pytest.mark.parametrize(
    "probe,record",
    [
        (identity.ProcessIdentity("UNKNOWN"), {"pid": 12, "created": 100}),
        (identity.ProcessIdentity("LIVE", 100), {"pid": 12, "created": None}),
    ],
)
def test_unknown_identity_blocks_resume(monkeypatch, probe, record):
    monkeypatch.setattr(identity, "inspect_process", lambda pid: probe)
    with pytest.raises(RuntimeError, match="refusing duplicate resume"):
        identity.original_process_running(record)


def prepared_runner(tmp_path, monkeypatch):
    import argos.simulator.flexdc_adapter as adapter

    runner = object.__new__(FlexDCRunner)
    runner.root = tmp_path
    runner.episode = tmp_path / "episode"
    runner.flexdc = tmp_path / ".deps/FlexDC"
    runner.flexdc.mkdir(parents=True)
    runner.config = Config()
    runner.context_id = "context"
    runner.costs = Costs(1, 10, 0.3, 20, 2, 0.1)
    for name in ("workload", "cluster", "gradient", "base_experiment"):
        path = tmp_path / (name + ".ini")
        path.write_text("[iso]\niso_file_path=../../signal.csv\n")
        setattr(runner, name, path)
    (runner.flexdc / "signal.csv").write_text("signal")

    def overlay(root, source, target, changes):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text())

    monkeypatch.setattr(adapter, "overlay", overlay)
    candidate = Candidate("test", 0.4, 0.1, (0.25,) * 4, "test")
    return runner, candidate, adapter


def test_popen_disappears_is_structured_recoverable_failure(tmp_path, monkeypatch):
    runner, candidate, adapter = prepared_runner(tmp_path, monkeypatch)
    process = SimpleNamespace(pid=12, returncode=1, wait=lambda timeout=None: 1)
    popen = Mock(return_value=process)
    monkeypatch.setattr(adapter.subprocess, "Popen", popen)
    monkeypatch.setattr(identity.psutil, "pid_exists", lambda pid: True)
    monkeypatch.setattr(identity.psutil, "Process", Mock(side_effect=psutil.NoSuchProcess(12)))
    result = runner.evaluate(candidate, 20, "search", 1)
    assert not result.valid and result.status == "SIMULATOR_EXECUTION_FAILED"
    assert result.returncode == 1 and "exit status 1" in result.error
    directory = Path(result.raw_paths["execution"]).parent
    assert read_json(directory / "process.json")["state"] == "ABSENT"
    assert runner.evaluate(candidate, 20, "search", 1) == result
    assert runner.search_attempts() == 1
    popen.assert_called_once()


def test_parity_mismatch_becomes_contract_mismatch(tmp_path, monkeypatch):
    runner, candidate, adapter = prepared_runner(tmp_path, monkeypatch)

    def popen(*args, **kwargs):
        output = kwargs["cwd"] / "output/optimization/test"
        output.mkdir(parents=True)
        (output / "grid_search_results.csv").write_text("placeholder")
        return SimpleNamespace(pid=12, returncode=0, wait=lambda timeout=None: 0)

    monkeypatch.setattr(adapter.subprocess, "Popen", popen)
    monkeypatch.setattr(adapter, "inspect_process", lambda pid: identity.ProcessIdentity("ABSENT"))
    monkeypatch.setattr(
        adapter, "parse_output", Mock(side_effect=ValueError("Raw-table/reported Pj mismatch"))
    )
    result = runner.evaluate(candidate, 20, "search", 1)
    assert not result.valid and result.metrics is None and result.status == "CONTRACT_MISMATCH"
    assert "Pj mismatch" in result.error


def test_live_original_blocks_actual_batch_dispatch(tmp_path, monkeypatch):
    import hashlib
    import json
    from dataclasses import asdict

    from argos.provenance import write_json

    runner, candidate, _adapter = prepared_runner(tmp_path, monkeypatch)
    key = hashlib.sha256(
        json.dumps(
            {
                "candidate": asdict(candidate),
                "seed": 20,
                "phase": "search",
                "batch": 1,
                "context": "context",
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:24]
    write_json(
        runner.episode / "flexdc_raw" / key / "attempt-001/process.json",
        {"pid": 12, "created": 100},
    )
    monkeypatch.setattr(
        identity, "inspect_process", lambda pid: identity.ProcessIdentity("LIVE", 100)
    )
    with pytest.raises(RuntimeError, match="still running"):
        runner.evaluate_batch([candidate], 20, "search", 1)
    assert runner.search_attempts() == 0


def test_post_popen_unknown_identity_still_waits_owned_process(tmp_path, monkeypatch):
    runner, candidate, adapter = prepared_runner(tmp_path, monkeypatch)
    process = SimpleNamespace(pid=12, returncode=1, wait=Mock(return_value=1))
    monkeypatch.setattr(adapter.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(
        adapter,
        "inspect_process",
        lambda pid: identity.ProcessIdentity("UNKNOWN", error="AccessDenied"),
    )
    result = runner.evaluate(candidate, 20, "search", 1)
    assert result.status == "SIMULATOR_EXECUTION_FAILED" and not result.valid
    process.wait.assert_called_once_with(timeout=runner.config.simulator_timeout_seconds)
    record = read_json(Path(result.raw_paths["execution"]).parent / "process.json")
    assert record["created"] is None and record["state"] == "UNKNOWN"
