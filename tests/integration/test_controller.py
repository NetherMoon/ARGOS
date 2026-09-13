from dataclasses import replace

import pytest

from argos.config import Config
from argos.contracts import feasible
from argos.controller.argos_controller import Controller, SearchState
from argos.reporting.report import report
from argos.search.candidates import Domain
from argos.types import Candidate, FlexDCObservation, Metrics, Region


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
            assert summary["confirmation_passes"] == 0 and summary["status"] == "CONFIRMATION_MIXED"
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
