"""Deterministic synthetic checks; no FlexDC subprocesses are started."""

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from argos.oc_basic.core import (
    candidate_aggregate,
    choose_seeds,
    distinct,
    geometry_key,
    next_batch,
    result_status,
    select_final,
    select_initial,
)
from argos.search.candidates import Domain
from argos.types import Candidate, Metrics


def domain():
    return Domain(0.25, 0.75, 1.0, 0.01, 0.6, (0.15,) * 4, (0.45,) * 4)


def panel(candidate_id, passes, objective):
    return [
        {
            "candidate_id": candidate_id,
            "arrival_seed": 100 + i,
            "execution_status": "COMPLETE",
            "evidence_valid": True,
            "p90": 0.2 if i < passes else 0.4,
            "Pj": [0.0, 0.02, 0.03, 0.04],
            "objective": objective,
        }
        for i in range(10)
    ]


class OCBasicTest(unittest.TestCase):
    def test_seed_freeze_and_disjointness(self):
        excluded = {1, 2, 3, 4, 20260926}
        search = range(101, 111)
        a = choose_seeds(excluded, search)
        self.assertEqual(a, choose_seeds(excluded, search))
        values = [*search, a["search_runtime_seed"]]
        for pair in a["assessment_pairs"]:
            values.extend([pair["arrival_seed"], pair["runtime_seed"]])
        self.assertEqual(len(values), len(set(values)))
        self.assertFalse(set(values) & excluded)

    def test_failed_execution_never_becomes_infeasible_observation(self):
        rows = panel("x", 9, 3)
        rows[0]["execution_status"] = "ERROR"
        with self.assertRaises(ValueError):
            candidate_aggregate(rows)

    def test_incomplete_evidence_never_counts_as_pass(self):
        rows = panel("x", 10, 3)
        rows[0]["evidence_valid"] = False
        self.assertFalse(result_status(rows[0]))
        aggregate = candidate_aggregate(rows)
        self.assertEqual(aggregate["arrival_pass_count"], 9)
        self.assertGreaterEqual(aggregate["worst_normalized_violation"], 1)

    def test_measured_selection_uses_all_ten_objectives_and_threshold(self):
        bad_cheap = candidate_aggregate(panel("bad", 7, 1))
        good = candidate_aggregate(panel("good", 8, 10))
        better = candidate_aggregate(panel("better", 9, 9))
        self.assertEqual(select_final([bad_cheap, good, better])["candidate_id"], "better")
        self.assertIsNone(select_final([bad_cheap]))
        self.assertEqual(good["mean_objective_all_ten"], 10)

    def test_domain_cloud_and_measured_anchor_quota(self):
        d = domain()
        rng = np.random.default_rng(12)
        cloud = []
        for i in range(100):
            c = d.independent(rng, f"cloud-{i}")
            c = Candidate(c.candidate_id, c.Pbar, c.R, c.weights, "independent" if i < 50 else "V3 endpoint", prediction=Metrics(0.1, 0.2, (0.01,) * 4, float(i + 1)))
            cloud.append(c)
        initial = select_initial(cloud, d)
        self.assertEqual(len(initial), 10)
        self.assertEqual(len({geometry_key(c) for c in initial}), 10)
        self.assertGreaterEqual(sum(c.source == "independent" for c in initial), 2)
        for c in initial:
            d.validate(c)
            self.assertAlmostEqual(sum(c.weights), 1.0, places=9)
        candidates = {c.candidate_id: c for c in initial}
        aggregates = [candidate_aggregate(panel(c.candidate_id, i % 10, 100 + i)) for i, c in enumerate(initial)]
        batch = next_batch(batch=2, candidates=candidates, aggregates=aggregates, cloud=cloud, domain=d, rng=np.random.default_rng(3))
        self.assertEqual(len(batch), 6)
        self.assertEqual([c.source for c in batch].count("measured_local"), 4)
        self.assertEqual([c.source for c in batch].count("independent"), 2)
        self.assertTrue(all(c.provenance.get("anchor") in candidates for c in batch[:4]))
        self.assertEqual(len({geometry_key(c) for c in batch}), 6)
        self.assertTrue(all(distinct(c, initial, d) for c in batch))
        for c in batch:
            d.validate(c)

    def test_ten_table_scheduler_respects_worker_limit_and_geometry(self):
        from argos.oc_basic import runner

        c = domain().independent(np.random.default_rng(4), "x")
        active = 0
        peak = 0
        lock = threading.Lock()

        def fake(_root, episode, candidate, _number, _seed, _role):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.01)
            with lock:
                active -= 1
            return {"arrival_seed": int(episode.name.split("_")[-1]), "geometry_key": geometry_key(candidate)}

        with tempfile.TemporaryDirectory() as temp, patch.object(runner, "one_execution", side_effect=fake):
            seed_plan = {"search_arrival_seeds": list(range(100, 110)), "search_runtime_seed": 999}
            rows, wall = runner.run_panel(Path(temp), Path(temp), c, 1, seed_plan, 3)
        self.assertEqual([r["arrival_seed"] for r in rows], list(range(100, 110)))
        self.assertEqual(len({r["geometry_key"] for r in rows}), 1)
        self.assertLessEqual(peak, 3)
        self.assertGreater(peak, 1)
        self.assertGreater(wall, 0)

    def test_held_out_candidate_freeze_cannot_be_reselected(self):
        from argos.oc_basic import runner

        d = domain()
        c1 = d.independent(np.random.default_rng(4), "one")
        c2 = d.independent(np.random.default_rng(5), "two")
        pairs = [{"arrival_seed": 1000 + i, "runtime_seed": 2000 + i} for i in range(30)]

        def fake_table(_root, output, _spec, seed):
            return output / "final" / f"assessment_{seed}", {"initial_job_table_hash": str(seed), "initial_file_sha256": str(seed), "prefill": 0}

        def fake_execution(_root, episode, candidate, _number, runtime_seed, _role):
            return {"arrival_seed": int(episode.name.split("_")[-1]), "runtime_seed": runtime_seed,
                    "candidate_id": candidate.candidate_id, "Pj": [0.0] * 4,
                    "evidence_counts": [100] * 4, "feasible": True}

        with tempfile.TemporaryDirectory() as temp, \
             patch.object(runner, "ensure_assessment_table", side_effect=fake_table), \
             patch.object(runner, "table_statistics", return_value={}), \
             patch.object(runner, "one_execution", side_effect=fake_execution):
            output = Path(temp)
            rows, timing = runner.run_assessment(output, output, {}, c1, {"assessment_pairs": pairs}, 10)
            self.assertEqual(len(rows), 30)
            self.assertEqual(timing["passes"], 30)
            with self.assertRaises(ValueError):
                runner.run_assessment(output, output, {}, c2, {"assessment_pairs": pairs}, 10)

    def test_compact_figures_from_synthetic_measured_rows(self):
        from argos.oc_basic import runner

        with tempfile.TemporaryDirectory() as temp:
            aggregates = []
            search_rows = []
            for i, passes in enumerate((7, 8)):
                one = candidate_aggregate(panel(f"c{i}", passes, 10 - i))
                one.update({"Pbar": 0.4 + i * 0.05, "R": 0.08 + i * 0.01,
                            "weights": "[0.25, 0.25, 0.25, 0.25]", "cumulative_search_wall_seconds": 30 + i * 30})
                aggregates.append(one)
                for row in panel(f"c{i}", passes, 10 - i):
                    search_rows.append({**row, "Pbar": one["Pbar"], "R": one["R"], "feasible": result_status(row)})
            held_out = [{"p90": 0.2 + i * 0.01, "Pj": [0.01, 0.02, 0.03, 0.04], "feasible": i < 2} for i in range(3)]
            runner.make_figures(Path(temp), search_rows, aggregates, held_out)
            self.assertEqual(len(list((Path(temp) / "figures").glob("*.png"))), 6)

    def test_search_hard_cap_and_resume_skip_completed_panels(self):
        from argos.oc_basic import runner

        d = domain()
        rng = np.random.default_rng(7)
        cloud = []
        for i in range(100):
            c = d.independent(rng, f"cloud-{i}")
            cloud.append(Candidate(c.candidate_id, c.Pbar, c.R, c.weights,
                                   "independent" if i < 50 else "V3 endpoint",
                                   prediction=Metrics(0.1, 0.2, (0.01,) * 4, float(i + 1))))
        calls = []

        def fake_panel(_root, _output, candidate, number, seed_plan, _workers):
            calls.append(number)
            return [
                {**row, "candidate_id": candidate.candidate_id,
                 "arrival_seed": seed_plan["search_arrival_seeds"][i],
                 "elapsed_seconds": 0.01, "evidence_counts": [100] * 4}
                for i, row in enumerate(panel(candidate.candidate_id, 8, 10))
            ], 0.02

        with tempfile.TemporaryDirectory() as temp, \
             patch.object(runner, "build_cloud", return_value=(cloud, d, {"smoke": True})), \
             patch.object(runner, "run_panel", side_effect=fake_panel):
            output = Path(temp)
            seed_plan = {"search_arrival_seeds": list(range(500, 510)), "search_runtime_seed": 900}
            rows, aggregates, timing = runner.run_search(output, output, seed_plan, output, {}, 10, 0.001, 100)
            self.assertEqual(len(rows), 100)
            self.assertEqual(len(aggregates), 10)
            self.assertEqual(timing["search_simulator_executions"], 100)
            self.assertEqual(calls, list(range(1, 11)))
            runner.run_search(output, output, seed_plan, output, {}, 10, 0.001, 100)
            self.assertEqual(calls, list(range(1, 11)))

    def test_report_builds_from_frozen_and_synthetic_results(self):
        import json

        import pandas as pd

        from argos.oc_basic import runner

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            frozen = base / runner.OLD_EXPERIMENT
            frozen.mkdir(parents=True)
            pd.DataFrame([{"workload": runner.WORKLOAD, "server_count": 1000,
                           "utilization": 0.6, "search_status": "SEARCH_OBSERVED_FEASIBLE",
                           "runtime_checks_passed": 3, "runtime_checks_total": 3,
                           "search_objective": 90.0}]).to_csv(frozen / "context_summary.csv", index=False)
            baseline = base / "v3"
            baseline.mkdir()
            (baseline / "timing.json").write_text(json.dumps({"simulator_confirmed_contexts": 5,
                                                               "runtime_checks_passed": 14,
                                                               "runtime_checks_total": 15}))
            pd.DataFrame([{"context": f"{runner.WORKLOAD}/N1000_U0.6",
                           "V3_final_bid_actually_feasible": False,
                           "V3_runtime_checks": "N/A", "V3_actual_objective": 95.0}]).to_csv(
                baseline / "head_to_head.csv", index=False)
            aggregate = candidate_aggregate(panel("b01-initial-00", 8, 91))
            aggregate.update({"candidate_source": "V3 snapshot", "Pbar": 0.45,
                              "R": 0.08, "weights": "[0.25, 0.25, 0.25, 0.25]"})
            rows = [{**r, "Pj": r["Pj"], "feasible": result_status(r),
                     "failure_constraints": "none" if result_status(r) else "tracking"}
                    for r in panel("b01-initial-00", 8, 91)]
            timing = {"search_wall_seconds_this_invocation": 100.0,
                      "search_wall_seconds_total": 100.0,
                      "stop_reason": "HARD_CALL_CAP",
                      "aggregate_simulator_seconds": 150.0,
                      "job_table_generation_seconds_this_invocation": 2.0,
                      "assessment": {"assessment_wall_seconds": 5.0},
                      "v3_timing": {"bank_original_generation_seconds": 300.0,
                                    "v3_model_load_seconds": 1.0,
                                    "v3_independent_scoring_seconds": 2.0}}
            held_out = [{"p90": 0.2, "Pj": [0.01, 0.02, 0.03, 0.04],
                         "feasible": True, "failure_constraints": "none"},
                        {"p90": 0.31, "Pj": [0.01, 0.02, 0.03, 0.04],
                         "feasible": False, "failure_constraints": "tracking"}]
            runner.write_report(base, base / "report_output", rows, [aggregate], held_out, timing, baseline)
            self.assertTrue((base / "report_output" / "report.md").exists())
            self.assertEqual(json.loads((base / "report_output" / "summary.json").read_text())["best_search_arrival_pass_count"], 8)


if __name__ == "__main__":
    unittest.main()
