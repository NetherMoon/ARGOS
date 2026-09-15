"""Hard-crash safety and nominal equivalence to the frozen W2 implementation."""

import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from test_vnext import D, Synthetic, setup

from argos.campaign.identity import digest
from argos.provenance import read_json
from argos.vnext.cli import gate_path


def test_no_overreservation_after_abandoned_attempts(tmp_path):
    controller, simulator = setup(tmp_path)
    controller.state["batch"] = 3
    controller.state["search_calls"] = 28
    state = controller.run()
    assert state["phase"] == "ERROR" and state["search_calls"] == 28
    assert state["pending"] is None and not simulator.calls
    assert "insufficient budget" in state["stop_reason"]
    assert read_json(controller.path)["search_calls"] <= 32


def test_pending_crash_budget_exhaustion_is_explicit(tmp_path):
    controller, simulator = setup(tmp_path)
    frozen = controller.propose()
    frozen["sha256"] = digest(frozen)
    controller.state["pending"] = frozen
    controller.state["search_calls"] = 8
    simulator.search_attempts = lambda: 32

    def fail(*args):
        raise RuntimeError("Insufficient remaining budget to retry interrupted batch")

    simulator.evaluate_batch = fail
    state = controller.run()
    assert state["phase"] == "ERROR" and state["search_calls"] == 32
    assert state["pending"] == frozen and not simulator.calls
    assert "Hard-crash retries" in state["stop_reason"]


@pytest.mark.parametrize("kind", ["accurate", "elite", "fragile", "none"])
def test_nominal_queries_identical_to_frozen_w2(tmp_path, kind):
    root = Path(__file__).resolve().parents[2]
    source = subprocess.check_output(
        ["git", "show", "4f2fc8e:src/argos/vnext/controller.py"], cwd=root
    )
    previous = ModuleType("vnext_before_recovery_guard")
    exec(compile(source, "<frozen-W2-controller>", "exec"), previous.__dict__)  # noqa: S102 - trusted pinned repository code
    current, current_sim = setup(tmp_path / "current", kind)
    previous_sim = Synthetic(kind)
    before = previous.NextController(
        tmp_path / "previous",
        current.config,
        D,
        current.regions,
        previous_sim,
        current.predictor,
        current.elites,
        (101, 102, 103),
        "ERT",
    )
    old_state = before.run()
    new_state = current.run()
    assert previous_sim.calls == current_sim.calls
    for field in ["phase", "batch", "search_calls", "repeats", "incumbent", "observations"]:
        assert old_state[field] == new_state[field]


def test_verification_gate_preserves_development_gate():
    assert gate_path("development").name == "execution_gate.json"
    assert gate_path("verification").name == "verification_gate.json"
    assert gate_path("development") != gate_path("verification")
    with pytest.raises(ValueError):
        gate_path("mixed")
