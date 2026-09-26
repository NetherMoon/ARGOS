"""Synthetic generic OC checks; no simulator, model, or network calls."""

import unittest

import numpy as np

from argos.oc_basic.generic import (
    PanelRule,
    choose_anchors,
    critical_bottlenecks,
    panel_state,
    select_final,
    weight_transfer,
)
from argos.oc_basic.scheduling import plan_wave
from argos.search.candidates import Domain


def domain(jobs):
    return Domain(0.25, 0.75, 1.0, 0.01, 0.6, (0.05,) * jobs, (0.9,) * jobs)


def row(candidate, seed, pj, p90=0.2, objective=80):
    return {
        "candidate_id": candidate,
        "arrival_seed": seed,
        "execution_status": "COMPLETE",
        "evidence_valid": True,
        "p90": p90,
        "Pj": list(pj),
        "objective": objective,
    }


class GenericOCBreadthTest(unittest.TestCase):
    def test_every_job_can_be_critical_and_permutation_preserves_identity(self):
        base = ("ResNet", "GPT2", "Llama", "Bloom")
        for critical in base:
            for names in (base, tuple(reversed(base))):
                with self.subTest(critical=critical, names=names):
                    rule = PanelRule(names, 5, 4)
                    pj = [0.01] * 4
                    pj[names.index(critical)] = 0.14
                    values = [row("bid", seed, pj) for seed in range(1, 6)]
                    state = panel_state("bid", values, range(1, 6), rule)
                    self.assertEqual(
                        critical_bottlenecks(values, state, rule)[0]["constraint"], critical
                    )

    def test_configured_job_count_and_order(self):
        for names in (
            ("Alpha", "Beta"),
            ("Gamma", "Alpha", "Delta"),
            ("Delta", "Beta", "Alpha", "Gamma", "Epsilon"),
        ):
            with self.subTest(names=names):
                rule = PanelRule(names, 5, 4)
                values = [row("bid", seed, [0.01] * len(names)) for seed in range(1, 6)]
                values[0]["Pj"][0] = 0.11
                state = panel_state("bid", values, range(1, 6), rule)
                self.assertEqual(state.passes, 4)
                self.assertEqual(state.status, "TARGET_MET_COMPLETE")
                self.assertAlmostEqual(state.g_target, -1 / 3)
                bottlenecks = critical_bottlenecks(values, state, rule)
                self.assertEqual(bottlenecks[0]["constraint"], names[0])

    def test_early_rejection_uses_maximum_possible_passes(self):
        rule = PanelRule(("A", "B", "C"), 5, 4)
        a = domain(3).independent(np.random.default_rng(2), "a")
        failed = [row("a", i, [0, 0, 0], p90=0.4) for i in (1, 2)]
        state = panel_state("a", failed, range(1, 6), rule)
        self.assertTrue(state.early_rejected)
        self.assertEqual(state.maximum_possible_passes, 3)
        self.assertEqual(plan_wave([a], failed, tuple(range(1, 6)), 4, rule=rule), [])

    def test_qualified_bid_beats_cheaper_infeasible_bid(self):
        rule = PanelRule(("A", "B"), 5, 4)
        good = panel_state(
            "good", [row("good", i, [0, 0], objective=100) for i in range(1, 6)], range(1, 6), rule
        )
        bad = panel_state(
            "bad",
            [row("bad", i, [0, 0], 0.4 if i <= 2 else 0.2, 1) for i in range(1, 6)],
            range(1, 6),
            rule,
        )
        self.assertEqual(select_final([good, bad], rule).candidate_id, "good")
        incomplete = panel_state(
            "incomplete",
            [row("incomplete", i, [0, 0], objective=1) for i in range(1, 5)],
            range(1, 6),
            rule,
        )
        self.assertEqual(select_final([good, incomplete], rule).candidate_id, "good")

    def test_weight_transfer_is_legal_and_name_independent(self):
        for count in (2, 3, 4, 5):
            with self.subTest(count=count):
                d = domain(count)
                a = d.independent(np.random.default_rng(count), "a")
                receiver, donor = 0, 1
                rule = PanelRule(tuple(f"job_{i}" for i in range(count)), 5, 4)
                move = weight_transfer(a, d, rule, receiver, donor, 0.02, "moved")
                self.assertIsNotNone(move)
                d.validate(move)
                self.assertAlmostEqual(sum(move.weights), sum(a.weights))
                self.assertGreater(move.weights[receiver], a.weights[receiver])
                self.assertEqual(move.provenance["receiver_job"], "job_0")

    def test_two_measured_anchors_when_available(self):
        rule = PanelRule(("A", "B"), 5, 4)
        d = domain(2)
        bids = {str(i): d.independent(np.random.default_rng(i), str(i)) for i in range(3)}
        states = [
            panel_state(str(i), [row(str(i), 1, [0, 0])], range(1, 6), rule) for i in range(3)
        ]
        anchors = choose_anchors(bids, states, d, rule)
        self.assertEqual(len({c.candidate_id for c in anchors}), 2)


if __name__ == "__main__":
    unittest.main()
