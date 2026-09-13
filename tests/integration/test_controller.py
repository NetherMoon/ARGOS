from dataclasses import replace

import pytest

from argos.config import Config
from argos.contracts import feasible
from argos.controller.argos_controller import Controller, SearchState
from argos.reporting.report import report
from argos.search.candidates import Domain
from argos.types import Candidate, FlexDCObservation, JobIdentity, Metrics, QoSEvidence, Region


class Synthetic:
    def __init__(self, case):
        self.case = case
        self.calls = []
        self.cache = {}
        self.interrupt = False

    def evaluate_batch(self, candidates, seed, phase, batch):
        result = []
        for c in candidates:
            key = (c.candidate_id, seed, phase)
            if key not in self.cache:
                self.calls.append(key)
                if self.case == "A":
                    good = c.Pbar > 0.65
                elif self.case == "B":
                    good = 0.28 < c.Pbar < 0.32 or 0.68 < c.Pbar < 0.72
                elif self.case == "C":
                    good = False
                elif self.case == "D":
                    good = phase == "search"
                else:
                    good = False
                m = Metrics(0.1, 0.2 if good else 0.5, (0.03, 0.04), c.Pbar * 100)
                valid = self.case != "invalid"
                self.cache[key] = FlexDCObservation(
                    c,
                    seed,
                    phase,
                    batch,
                    valid,
                    m if valid else None,
                    "PASS" if good else "FAIL",
                    0.01,
                    str(key),
                    qos_evidence=tuple(
                        QoSEvidence(
                            JobIdentity(i, f"job{i}", (1, 2, 3, 4, 5, 1)),
                            pj,
                            101,
                            101,
                            0,
                            round(pj * 100) + 1,
                            round(pj * 100),
                            100,
                        )
                        for i, pj in enumerate(m.pj)
                    ),
                )
            result.append(self.cache[key])
            if self.interrupt:
                self.interrupt = False
                raise RuntimeError("synthetic interruption after durable first result")
        return result


def setup(episode, case):
    config = replace(
        Config(),
        batch_size=2,
        independent_per_batch=1,
        max_workers=1,
        max_search_calls=8,
        max_search_batches=4,
    )
    domain = Domain(0.18, 0.76, 0.912, 0.01, 0.6, (0.15, 0.15), (0.85, 0.85))
    a = Candidate(
        "bad-v3-favorite",
        0.3,
        0.05,
        (0.5, 0.5),
        "V3 snapshot",
        region_id="a",
        prediction=Metrics(0.1, 0.1, (0.01, 0.01), 1),
    )
    b = replace(
        a,
        candidate_id="alternative",
        Pbar=0.7,
        region_id="b",
        prediction=Metrics(0.1, 0.2, (0.02, 0.02), 2),
    )
    regions = [
        Region(c.region_id, c, (c.candidate_id,), tuple(domain.encode(c)), (0,)) for c in [a, b]
    ]
    simulator = Synthetic(case)
    predictor = lambda c: (
        replace(c, prediction=Metrics(0.1, 0.1, (0.01, 0.01), c.Pbar * 100))
        if not c.prediction
        else c
    )
    controller = Controller(episode, config, domain, regions, simulator, predictor)
    return controller, simulator


@pytest.mark.parametrize("case", ["A", "B", "C", "D", "invalid"])
def test_complete_landscapes(tmp_path, case):
    controller, _simulator = setup(tmp_path / case, case)
    state = controller.run()
    summary = report(controller.episode, controller.config, state)
    assert state.search_calls <= 8
    if case == "C":
        assert state.phase == "NO_BID" and not state.incumbent
    elif case == "invalid":
        assert state.phase == "ERROR"
    else:
        assert state.incumbent and summary["observed_feasible_count"] > 0
        confirmation = [o for o in state.observations if o.phase == "confirmation"]
        assert len(confirmation) == 2
        assert all(o.candidate == state.incumbent for o in confirmation)
        assert {o.seed for o in confirmation}.isdisjoint({20})
        if case == "D":
            assert (
                summary["confirmation_passes"] == 0
                and summary["status"] == "CONFIRMATION_NONE_PASS"
            )
        if case == "A":
            first = state.observations[0]
            assert first.candidate.candidate_id == "bad-v3-favorite" and not feasible(first.metrics)
            assert any(o.candidate.candidate_id == "alternative" for o in state.observations)
    assert SearchState.load(controller.path) == state


def test_resume_reuses_completed_work_and_candidates(tmp_path):
    controller, simulator = setup(tmp_path / "recover", "A")
    simulator.interrupt = True
    with pytest.raises(RuntimeError):
        controller.run()
    saved = SearchState.load(controller.path)
    assert saved.search_calls == 2 and len(saved.pending) == 2
    resumed = Controller(
        controller.episode,
        controller.config,
        controller.domain,
        controller.regions,
        simulator,
        controller.predictor,
    )
    result = resumed.run()
    assert len(simulator.calls) == len(set(simulator.calls))
    assert result.search_calls == 8 and result.phase == "DONE"
    calls = len(simulator.calls)
    Controller(
        controller.episode,
        controller.config,
        controller.domain,
        controller.regions,
        simulator,
        controller.predictor,
    ).run()
    assert len(simulator.calls) == calls


@pytest.mark.parametrize("mode", ["measured_random", "v3_screened"])
def test_local_proposal_modes_and_fixed_budget(tmp_path, mode):
    controller, simulator = setup(tmp_path / mode, "B")
    controller.config = replace(controller.config, local_proposal_mode=mode)
    state = controller.run()
    assert state.search_calls == 8
    assert any(o.candidate.source == "local" for o in state.observations)
    assert len(simulator.calls) == len(state.observations)
    for o in state.observations:
        controller.domain.validate(o.candidate)


def test_insufficient_evidence_never_selected_or_fatal(tmp_path):
    controller, simulator = setup(tmp_path / "unknown", "B")
    original = simulator.evaluate_batch

    def unknown(*args):
        return [replace(o, qos_evidence=None) for o in original(*args)]

    simulator.evaluate_batch = unknown
    state = controller.run()
    assert state.phase == "NO_BID" and state.search_calls == 8
    assert not any(o.phase == "confirmation" for o in state.observations)


def test_early_stop_and_resume_are_same_decision(tmp_path):
    from argos.controller.stopping import early_stop_details

    controller, simulator = setup(tmp_path / "early", "B")
    controller.config = replace(
        controller.config, search_mode="early_stop", objective_improvement_epsilon=100
    )
    simulator.interrupt = True
    with pytest.raises(RuntimeError):
        controller.run()
    resumed = Controller(
        controller.episode,
        controller.config,
        controller.domain,
        controller.regions,
        simulator,
        controller.predictor,
    )
    state = resumed.run()
    assert state.search_calls == 6 and state.stop_reason == "EARLY_STOP_QUALIFIED_LOCAL_PATIENCE"
    assert early_stop_details(state.observations, controller.config)["subsequent_local_refinement"]
    again = Controller(
        controller.episode,
        controller.config,
        controller.domain,
        controller.regions,
        simulator,
        controller.predictor,
    ).run()
    assert again == state


def test_early_stop_patience_minimum_and_no_qualified(tmp_path):
    from argos.controller.stopping import early_stop_details

    controller, _ = setup(tmp_path / "stopping", "B")
    state = controller.run()
    config = replace(controller.config, objective_improvement_epsilon=100)
    first = [o for o in state.observations if o.phase == "search" and o.batch == 1]
    assert not early_stop_details(first, config)["stop"]
    assert not early_stop_details(
        [replace(o, qos_evidence=None) for o in state.observations], config
    )["stop"]
    two = [o for o in state.observations if o.phase == "search" and o.batch <= 3]
    assert early_stop_details(two, config)["stop"]
    assert not early_stop_details(two, replace(config, early_stop_patience=3))["stop"]
    assert not early_stop_details(two, replace(config, early_stop_min_batches=4))["stop"]
    assert not early_stop_details(
        [replace(o, candidate=replace(o.candidate, source="independent")) for o in two], config
    )["stop"]


@pytest.mark.parametrize(
    "passes,expected",
    [(0, "CONFIRMATION_NONE_PASS"), (1, "CONFIRMATION_PARTIAL_PASS"), (2, "CONFIRMATION_ALL_PASS")],
)
def test_confirmation_summary_semantics(tmp_path, passes, expected):
    controller, _ = setup(tmp_path / str(passes), "B")
    state = controller.run()
    confirmations = [o for o in state.observations if o.phase == "confirmation"]
    replacement = []
    for i, o in enumerate(confirmations):
        # Preserve numerical feasibility while withdrawing evidence for failing seeds.
        metrics = replace(o.metrics, p90=0.2, pj=(0.03, 0.04))
        replacement.append(
            replace(o, metrics=metrics, qos_evidence=o.qos_evidence if i < passes else None)
        )
    state.observations = [o for o in state.observations if o.phase == "search"] + replacement
    summary = report(controller.episode, controller.config, state)
    assert summary["confirmation_status"] == expected
    assert summary["confirmation_passes"] == passes
    assert summary["confirmation_numerical_passes"] == 2
