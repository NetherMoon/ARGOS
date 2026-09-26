"""Synthetic OC1.1 rules and scheduler tests; no FlexDC calls."""

import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np

from argos.oc_basic.core import geometry_key
from argos.oc_basic.runner_v1_1 import _race_batch, _read_rows
from argos.oc_basic.v1_1 import (
    axis_probe,
    candidate_state,
    complete_rank,
    next_batch,
    select_final,
    signed_scenario_violation,
    weight_transfer,
)
from argos.search.candidates import Domain
from argos.types import Candidate, Metrics


def domain():
    return Domain(0.25, 0.75, 1.0, 0.01, 0.6, (0.15,) * 4, (0.45,) * 4)


PANEL = tuple(range(101, 111))


def row(candidate_id, seed, g, objective=99.0):
    return {
        "candidate_id": candidate_id, "arrival_seed": seed,
        "execution_status": "COMPLETE", "evidence_valid": True,
        "p90": 0.3 * (1 + g), "Pj": [0.0, 0.0, 0.0, 0.0],
        "objective": objective, "evidence_counts": [100] * 4,
        "runtime_seed": 999, "initial_job_table_hash": str(seed),
        "grid_signal_hash": "grid", "elapsed_seconds": 0.01,
    }


class OC11Test(unittest.TestCase):
    def test_signed_violation_multiple_constraints(self):
        passing = row("a", 101, -0.2)
        self.assertAlmostEqual(signed_scenario_violation(passing), -0.2)
        passing["Pj"] = [0.11, 0.21, 0, 0]
        self.assertAlmostEqual(signed_scenario_violation(passing), 1.1)
        passing["evidence_valid"] = False
        self.assertIsNone(signed_scenario_violation(passing))

    def test_g8_repair_sum_and_final_selection(self):
        five = [row("five", s, -0.1 if i < 5 else [0.4, 0.1, 0.3, 2.0, 3.0][i-5])
                for i, s in enumerate(PANEL)]
        state = candidate_state("five", five, PANEL)
        self.assertEqual(state.passes, 5)
        self.assertAlmostEqual(state.g8, 0.4)
        self.assertAlmostEqual(state.repair_sum, 0.8)
        self.assertEqual(state.critical_failure_seeds, (PANEL[6], PANEL[7], PANEL[5]))
        self.assertIsNone(select_final([state]))
        eight = candidate_state("eight", [row("eight", s, -0.1 if i < 8 else 0.5, 100+i)
                                           for i, s in enumerate(PANEL)], PANEL)
        seven = candidate_state("seven", [row("seven", s, -0.1 if i < 7 else 0.01, 1)
                                           for i, s in enumerate(PANEL)], PANEL)
        self.assertLessEqual(eight.g8, 0)
        self.assertEqual(eight.critical_failure_seeds, PANEL[8:])
        self.assertGreater(seven.g8, 0)
        self.assertEqual(select_final([state, seven, eight]).candidate_id, "eight")
        self.assertAlmostEqual(eight.mean_objective_all_ten, 104.5)
        self.assertLess(complete_rank(seven), complete_rank(state))
        partial = candidate_state("partial", [row("partial", s, -0.5) for s in PANEL[:8]], PANEL)
        self.assertIsNone(select_final([partial]))

    def test_early_rejection_and_legal_probes(self):
        state = candidate_state("x", [row("x", s, 0.1) for s in PANEL[:3]], PANEL)
        self.assertEqual(state.maximum_possible_passes, 7)
        self.assertTrue(state.early_rejected)
        d = domain()
        anchor = Candidate("anchor", 0.45, 0.1, (0.25,) * 4, "measured")
        moved = weight_transfer(anchor, d, 3, 0, 0.04, "transfer")
        d.validate(moved)
        self.assertAlmostEqual(sum(moved.weights), 1)
        self.assertGreater(moved.weights[3], anchor.weights[3])
        self.assertEqual(moved.provenance["receiver"], "Bloom")
        self.assertEqual(moved.provenance["donor"], "ResNet")
        for axis in ("P", "conditional_R"):
            for offset in (-0.04, -0.02, 0.02, 0.04):
                probe = axis_probe(anchor, d, axis, offset, f"{axis}-{offset}")
                d.validate(probe)
                self.assertEqual(probe.provenance["anchor"], "anchor")

    def test_structured_batch_keeps_two_anchors_and_independents(self):
        d = domain()
        rng = np.random.default_rng(9)
        one = Candidate("a", 0.43, 0.08, (0.25,) * 4, "measured")
        two = Candidate("b", 0.55, 0.16, (0.25,) * 4, "measured")
        candidates = {c.candidate_id: c for c in (one, two)}
        rows_by = {"a": [row("a", s, -0.1 if i < 5 else 0.2) for i, s in enumerate(PANEL)],
                   "b": [row("b", s, -0.1 if i < 4 else 0.4) for i, s in enumerate(PANEL)]}
        states = [candidate_state(k, v, PANEL) for k, v in rows_by.items()]
        cloud = []
        for i in range(100):
            c = d.independent(rng, f"ind-{i}")
            cloud.append(replace(c, prediction=Metrics(0.1, 0.2, (0.01,) * 4, i)))
        batch = next_batch(batch=2, candidates=candidates, rows_by_candidate=rows_by,
                           states=states, cloud=cloud, domain=d, rng=np.random.default_rng(10))
        self.assertEqual(len(batch), 8)
        self.assertEqual(len({geometry_key(c) for c in batch}), 8)
        self.assertEqual(sum(c.source == "independent" for c in batch), 2)
        self.assertEqual(sum(c.provenance.get("anchor") == "a" for c in batch), 3)
        self.assertEqual(sum(c.provenance.get("anchor") == "b" for c in batch), 3)
        self.assertTrue(any(c.source == "targeted_axis" and c.provenance.get("axis") == "P" for c in batch))
        self.assertTrue(any(c.source == "targeted_axis" and c.provenance.get("axis") == "conditional_R" for c in batch))
        for c in batch:
            d.validate(c)

    def test_racing_does_not_launch_after_third_failure_or_exceed_workers(self):
        d = domain()
        candidates = {f"b01-screen-{i:02d}": d.independent(np.random.default_rng(i+2), f"b01-screen-{i:02d}")
                      for i in range(4)}
        batch = list(candidates.values())
        active = peak = calls = 0
        lock = threading.Lock()

        def fake(_root, episode, candidate, _number, runtime_seed, _role):
            nonlocal active, peak, calls
            with lock:
                active += 1
                peak = max(peak, active)
                calls += 1
            time.sleep(0.001)
            with lock:
                active -= 1
            seed = int(episode.name.split("_")[-1])
            return row(candidate.candidate_id, seed, 0.1)

        with tempfile.TemporaryDirectory() as temp, patch("argos.oc_basic.runner.one_execution", side_effect=fake):
            output = Path(temp)
            (output / "search").mkdir()
            all_rows = []
            new_rows = []
            stats = _race_batch(output, output, batch, candidates, all_rows, new_rows, PANEL,
                                999, {s: str(s) for s in PANEL}, 3, 100, 99, time.monotonic())
            self.assertEqual(calls, 12)
            self.assertEqual(len(all_rows), 12)
            self.assertLessEqual(peak, 3)
            self.assertEqual(stats["peak_workers"], 3)
            self.assertEqual(len(_read_rows(output / "search" / "new_scenario_executions.csv")), 12)
            _race_batch(output, output, batch, candidates, all_rows, new_rows, PANEL,
                        999, {s: str(s) for s in PANEL}, 3, 100, 99, time.monotonic())
            self.assertEqual(calls, 12)


if __name__ == "__main__":
    unittest.main()
