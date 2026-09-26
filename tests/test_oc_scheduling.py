"""No-simulator checks for deterministic OC1.3 wave planning."""

import threading
import time
import unittest

import numpy as np

from argos.oc_basic.scheduling import execute_fanout_batch, plan_wave
from argos.search.candidates import Domain


class OCSchedulingTest(unittest.TestCase):
    def setUp(self):
        self.domain = Domain(0.25, 0.75, 1.0, 0.01, 0.6, (0.15,) * 4, (0.45,) * 4)
        self.batch = [self.domain.independent(np.random.default_rng(i), f"c{i}") for i in range(15)]
        self.panel = tuple(range(101, 111))

    def row(self, candidate_id, seed, failed=False):
        return {"candidate_id": candidate_id, "arrival_seed": seed,
                "execution_status": "COMPLETE", "evidence_valid": True,
                "p90": 0.4 if failed else 0.2, "Pj": [0.0] * 4}

    def test_starts_with_ten_distinct_candidates_on_same_first_seed(self):
        wave = plan_wave(self.batch, [], self.panel, 10)
        self.assertEqual(len(wave), 10)
        self.assertEqual({cell.arrival_seed for cell in wave}, {101})
        self.assertEqual(len({cell.candidate_id for cell in wave}), 10)

    def test_least_measured_candidate_priority_and_fanout(self):
        rows = [self.row(f"c{i}", 101) for i in range(10)]
        wave = plan_wave(self.batch, rows, self.panel, 10)
        self.assertEqual(len(wave), 10)
        self.assertEqual({cell.candidate_id for cell in wave[:5]}, {f"c{i}" for i in range(10, 15)})
        single = plan_wave(self.batch[:1], [self.row("c0", 101)], self.panel, 10)
        self.assertEqual([c.arrival_seed for c in single], [102, 103, 104, 105])

    def test_three_failures_stop_future_launches(self):
        rows = [self.row("c0", s, failed=True) for s in self.panel[:3]]
        self.assertEqual(plan_wave(self.batch[:1], rows, self.panel, 10), [])

    def test_duplicate_cells_are_rejected(self):
        rows = [self.row("c0", 101), self.row("c0", 101)]
        with self.assertRaises(ValueError):
            plan_wave(self.batch[:1], rows, self.panel, 10)

    def test_fanout_execution_bound_identity_and_resume(self):
        rows = []
        active = peak = calls = 0
        lock = threading.Lock()

        def evaluate(candidate, seed):
            nonlocal active, peak, calls
            with lock:
                active += 1
                calls += 1
                peak = max(peak, active)
            time.sleep(.001)
            with lock:
                active -= 1
            return self.row(candidate.candidate_id, seed, failed=seed <= 103)

        result = execute_fanout_batch(batch=self.batch[:4], rows=rows, seed_order=self.panel, workers=3,
                                      call_room=lambda: 100-len(rows), deadline_reached=lambda: False,
                                      evaluate=evaluate, record=rows.append)
        self.assertLessEqual(peak, 3)
        self.assertEqual(result["launches"], calls)
        self.assertTrue(all(len([r for r in rows if r["candidate_id"] == c.candidate_id]) >= 3
                            for c in self.batch[:4]))
        prior = calls
        execute_fanout_batch(batch=self.batch[:4], rows=rows, seed_order=self.panel, workers=3,
                             call_room=lambda: 100-len(rows), deadline_reached=lambda: False,
                             evaluate=evaluate, record=rows.append)
        self.assertEqual(calls, prior)


if __name__ == "__main__":
    unittest.main()
