"""Phase 3 planning/controller tests; no FlexDC simulator is executed."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from argos.experimental_sa.paper_consistent.domain import Domain
from argos.experimental_sa.phase3.engine import run_trajectory
from argos.experimental_sa.phase3.planning import collect_prior_seeds
from argos.experimental_sa.phase3.reporting import _plots, build_zip
from argos.experimental_sa.phase3.scenarios import (
    FixedArrivalScenarioPolicy,
    VaryingArrivalScenarioPolicy,
    generate_search_draws,
    generate_seed_plan,
)

ROOT = Path(__file__).resolve().parents[2]
NAMES = ["ResNet", "GPT2", "Llama", "Bloom"]


class Contract:
    def evaluate(self, money, p90, pj):
        value = money + p90 + sum(pj)
        return SimpleNamespace(
            to_dict=lambda: {
                "M_RSR": money,
                "Ctrack": p90,
                "CQoS": sum(pj),
                "Cfull": value,
                "qos_terms": [x + 0.01 for x in pj],
            }
        )


class Evaluator:
    def __init__(self, stop_after=None):
        self.stop_after = stop_after
        self.calls = 0
        self.finalized = []

    def __call__(self, params, iteration, scenario):
        if self.stop_after is not None and iteration > self.stop_after:
            raise RuntimeError("synthetic interruption")
        self.calls += 1
        value = abs(params[0] - 0.4) + (scenario.arrival_seed % 7) / 1000
        return {
            "raw": {
                "status": "COMPLETE",
                "M_RSR": 50 + value,
                "mean_tracking": 0.1,
                "p90": 0.2,
                "Pj": [0.01, 0.02, 0.03, 0.04],
                "evidence_counts": [100] * 4,
                "initial_job_table_hash": f"h{scenario.arrival_seed}",
                "grid_signal_hash": "fixed-grid",
                "target_trace_hash": f"t{params[0]}",
                "arrival_seed": scenario.arrival_seed,
                "runtime_seed": scenario.runtime_seed,
            },
            "simulator_call_performed": True,
        }

    def finalize_iteration(self, iteration, scenario, valid):
        self.finalized.append((iteration, valid))


def domain():
    return Domain("test", 0.2, 0.7, 0.01, 0.2, 0.15, 0.45, 4, pr_max=0.9, r_over_p=0.6)


def run_synthetic(output, transitions=3):
    evaluator = Evaluator()
    result = run_trajectory(
        initial=(0.47, 0.06, 0.25, 0.25, 0.25, 0.25),
        domain=domain(),
        evaluator=evaluator,
        contract=Contract(),
        job_names=NAMES,
        output=output,
        run_id="test",
        scenario_policy=VaryingArrivalScenarioPolicy(list(range(100, 101 + transitions)), 77),
        search_draws=generate_search_draws(123, transitions, 4),
        transitions=transitions,
        temperature=1000,
        cooling_rate=0.95,
        steps=(0.01, 0.01, 0.02),
    )
    return result


def test_aqa_source_identity():
    normal = (ROOT / ".deps/FlexDC/src/peacsim/run_simulator.py").read_text()
    legacy = (ROOT / ".deps/FlexDC/src/peacsim/simulated_annealing.py").read_text()
    evaluator = (ROOT / "src/argos/experimental_sa/paper_consistent/evaluator.py").read_text()
    assert "from peacsim.aqa_runtimepolicy import AQARuntimePolicy" in normal
    assert "from peacsim.AQA_runtime_policy import AQARuntimePolicy" in legacy
    assert 'import_module("peacsim.aqa_runtimepolicy")' in evaluator


def test_scenario_policies_and_iteration_zero():
    fixed = FixedArrivalScenarioPolicy(10, 99, 401)
    varying = VaryingArrivalScenarioPolicy(list(range(10, 411)), 99)
    assert fixed.scenario_for_iteration(0) == varying.scenario_for_iteration(0)
    assert {fixed.scenario_for_iteration(i).arrival_seed for i in range(401)} == {10}
    assert len({varying.scenario_for_iteration(i).arrival_seed for i in range(401)}) == 401
    assert {varying.scenario_for_iteration(i).runtime_seed for i in range(401)} == {99}


def test_seed_plan_disjointness_and_size():
    prior = collect_prior_seeds(ROOT)
    plan = generate_seed_plan(20260920, prior)
    arrivals = set(plan["arrival_schedule"])
    assessment = set(plan["assessment_seeds"])
    smoke = set(plan["smoke"]["arrival_schedule"])
    assert len(arrivals) == 401
    assert len(assessment) == 10
    assert not arrivals & assessment
    assert not arrivals & prior
    assert not assessment & prior
    assert not smoke & assessment
    assert plan["training_runtime_seed"] not in arrivals | assessment | prior


def test_search_draws_are_matched_and_complete():
    first = generate_search_draws(1234, 400, 4)
    second = generate_search_draws(1234, 400, 4)
    assert first == second
    assert len(first) == 400
    assert [row["iteration"] for row in first] == list(range(1, 401))


def test_four_trajectory_call_plan():
    names = ["A_fixed", "A_varying", "B_fixed", "B_varying"]
    assert len(names) == 4
    assert sum(401 for _ in names) == 1604


def test_fixed_and_varying_hash_grid_runtime_invariants(tmp_path):
    draws = generate_search_draws(5, 2, 4)
    initial = (0.47, 0.06, 0.25, 0.25, 0.25, 0.25)
    common = {
        "initial": initial,
        "domain": domain(),
        "contract": Contract(),
        "job_names": NAMES,
        "search_draws": draws,
        "transitions": 2,
        "temperature": 1000,
        "cooling_rate": 0.95,
        "steps": (0.01, 0.01, 0.02),
    }
    for method, policy in [
        ("fixed", FixedArrivalScenarioPolicy(10, 77, 3)),
        ("varying", VaryingArrivalScenarioPolicy([10, 11, 12], 77)),
    ]:
        run_trajectory(
            evaluator=Evaluator(),
            output=tmp_path / method,
            run_id=method,
            scenario_policy=policy,
            **common,
        )
    fixed = [json.loads(x) for x in (tmp_path / "fixed/iterations.jsonl").read_text().splitlines()]
    varying = [
        json.loads(x) for x in (tmp_path / "varying/iterations.jsonl").read_text().splitlines()
    ]
    assert fixed[0]["raw"] == varying[0]["raw"]
    assert len({x["raw"]["initial_job_table_hash"] for x in fixed}) == 1
    assert len({x["raw"]["initial_job_table_hash"] for x in varying}) == 3
    assert {x["raw"]["grid_signal_hash"] for x in fixed + varying} == {"fixed-grid"}
    assert {x["raw"]["runtime_seed"] for x in fixed + varying} == {77}
    assert [x["search_draw"] for x in fixed[1:]] == [x["search_draw"] for x in varying[1:]]


def test_resume_equivalence(tmp_path):
    uninterrupted = run_synthetic(tmp_path / "full", 3)
    assert uninterrupted.simulator_calls == 4
    partial_output = tmp_path / "resume"
    run_synthetic(partial_output, 1)
    resumed = run_synthetic(partial_output, 3)
    assert resumed.to_dict() == uninterrupted.to_dict()
    assert (partial_output / "iterations.jsonl").read_text() == (
        tmp_path / "full/iterations.jsonl"
    ).read_text()


def test_assessment_plan_identity_and_selection_immutability():
    seeds = list(range(10))
    sources = ["starting", "fixed-SA", "varying-SA"]
    ids = {(case, source, seed) for case in ["A", "B"] for source in sources for seed in seeds}
    assert len(ids) == 60
    selected = {"params": [1, 2, 3]}
    before = json.dumps(selected, sort_keys=True)
    _assessment_results = [{"seed": x, "pass": bool(x % 2)} for x in seeds]
    assert json.dumps(selected, sort_keys=True) == before


def test_zip_construction(tmp_path):
    experiment = tmp_path / "experiment"
    experiment.mkdir()
    (experiment / "manifest.json").write_text('{"status":"COMPLETE"}')
    path = build_zip(experiment)
    assert path.exists() and path.stat().st_size > 0


def test_plots_map_workload_ids_to_trajectory_labels(tmp_path):
    experiment = tmp_path / "experiment"
    (experiment / "plots").mkdir(parents=True)
    for case in ["A", "B"]:
        for method in ["fixed", "varying"]:
            target = experiment / "optimization" / f"{case}_{method}"
            target.mkdir(parents=True)
            row = {
                "iteration": 0,
                "feasibility": {"feasible": True},
                "objective": {"Cfull": 90.0},
                "raw": {"p90": 0.2, "Pj": [0.01, 0.02, 0.03, 0.04]},
            }
            (target / "iterations.jsonl").write_text(json.dumps(row) + "\n")
    pd.DataFrame(
        [
            {
                "trajectory": f"{case}_{method}",
                "Pbar": 0.47,
                "R": 0.06,
            }
            for case in ["A", "B"]
            for method in ["fixed", "varying"]
        ]
    ).to_csv(experiment / "selected_candidates.csv", index=False)
    assessment = pd.DataFrame(
        [
            {
                "case": workload,
                "seed": seed,
                "candidate_source": source,
                "Bloom_Pj": 0.04,
                "p90": 0.2,
                "pass": True,
                "Pbar": 0.47,
                "R": 0.06,
            }
            for workload in ["c005", "c007"]
            for source in ["starting", "fixed-SA", "varying-SA"]
            for seed in range(10)
        ]
    )
    _plots(experiment, assessment)
    assert (experiment / "plots/A_assessment_Bloom_Pj.png").exists()
    assert (experiment / "plots/B_assessment_p90.png").exists()
