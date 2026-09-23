"""Phase 3C planning and shared-panel engine tests; no FlexDC simulation."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from argos.experimental_sa.phase3.planning import EXPECTED_SHAS
from argos.experimental_sa.phase3c.engine import aggregate_panel, run_shared3_trajectory
from argos.experimental_sa.phase3c.planning import (
    BLOCK_SIZE,
    NAIVE_CALLS_PER_TRAJECTORY,
    PANEL_SIZE,
    PANELS,
    SHARED_CALLS_PER_TRAJECTORY,
    TRANSITIONS,
    _generate_seed_plan,
    create_plan,
    validate_seed_plan,
)
from argos.experimental_sa.phase3c.reporting import build_zip, report
from argos.provenance import git

ROOT = Path(__file__).resolve().parents[2]
JOBS = ["ResNet", "GPT2", "Llama", "Bloom"]


class Domain:
    def validate(self, _value):
        pass

    def project(self, value):
        x = np.asarray(value, dtype=float)
        x[0] = np.clip(x[0], 0.4, 0.6)
        x[1] = np.clip(x[1], 0.01, 0.2)
        x[2:] = np.maximum(x[2:], 0.01)
        x[2:] /= x[2:].sum()
        return tuple(x)


class Contract:
    def evaluate(self, monetary, p90, pj):
        value = float(monetary + p90 + sum(pj))
        return SimpleNamespace(
            to_dict=lambda: {
                "M_RSR": monetary,
                "Ctrack": p90,
                "CQoS": sum(pj),
                "Cfull": value,
                "qos_terms": tuple(pj),
            }
        )


class PanelEvaluator:
    def __init__(self, fail_once=None, infeasible=False, increasing=False):
        self.fail_once = set(fail_once or [])
        self.failed = set()
        self.calls = []
        self.infeasible = infeasible
        self.increasing = increasing

    def evaluate_panel(self, *, params, evaluation_id, panel_index, panel_seeds, runtime_seed):
        self.calls.append((evaluation_id, panel_index, tuple(panel_seeds), tuple(params)))
        if evaluation_id in self.fail_once and evaluation_id not in self.failed:
            self.failed.add(evaluation_id)
            raise RuntimeError("synthetic interruption")
        raws = []
        for seed in panel_seeds:
            p90 = 0.4 if self.infeasible else 0.2
            raws.append(
                {
                    "status": "COMPLETE",
                    "arrival_seed": seed,
                    "runtime_seed": runtime_seed,
                    "p90": p90,
                    "mean_tracking": p90,
                    "M_RSR": 1.0 + (10.0 * evaluation_id if self.increasing else 0.0),
                    "Pj": [0.01] * 4,
                    "evidence_counts": [10] * 4,
                    "grid_signal_hash": "grid",
                    "initial_job_table_hash": f"jobs-{seed}",
                    "target_trace_hash": "target",
                }
            )
        return {"raw_results": raws, "performed_calls": 3}


def draws(count):
    return [
        {
            "iteration": i,
            "p_standard_normal": 0.1,
            "r_standard_normal": 0.1,
            "weight_standard_normals": [0.0, 0.0, 0.0, 0.0],
            "metropolis_uniform": 0.99,
        }
        for i in range(1, count + 1)
    ]


def run_small(tmp_path, evaluator, transitions=4, block_size=2):
    panels = [
        [100 + i * 3 + j for j in range(3)]
        for i in range((transitions + block_size - 1) // block_size)
    ]
    return run_shared3_trajectory(
        initial=(0.47, 0.08, 0.25, 0.25, 0.25, 0.25),
        domain=Domain(),
        evaluator=evaluator,
        contract=Contract(),
        job_names=JOBS,
        output=tmp_path,
        run_id="test",
        panel_schedule=panels,
        runtime_seed=999,
        search_draws=draws(transitions),
        transitions=transitions,
        block_size=block_size,
        temperature=10,
        cooling_rate=0.95,
        steps=(0.01, 0.01, 0.02),
    )


def test_seed_plan_is_deterministic_unique_and_disjoint():
    prior = {1, 2, 3}
    first = _generate_seed_plan(prior)
    second = _generate_seed_plan(prior)
    assert first == second
    validate_seed_plan(first, prior)
    assert len(first["search_roots"]) == 2
    assert len(first["naive_arrival_seeds"]) == 401
    assert len(first["shared_panel_seeds"]) == 40
    assert all(len(x) == 3 for x in first["shared_panel_seeds"])
    assert len(first["assessment_seeds"]) == 20


def test_full_plan_has_exact_frozen_budgets(tmp_path):
    if git(ROOT, "rev-parse", "HEAD") != EXPECTED_SHAS["ARGOS"]:
        pytest.skip("Phase 3C plan creation requires its archived Phase 3 ARGOS commit")
    experiment = create_plan(ROOT, tmp_path / "phase3c")
    import csv

    def read(name):
        with (experiment / name).open(newline="", encoding="utf8") as stream:
            return list(csv.DictReader(stream))

    calls = read("optimization_call_plan.csv")
    assessment = read("assessment_run_plan.csv")
    assert len(calls) == 6884
    assert sum(x["method"] == "naive" for x in calls) == 1604
    assert sum(x["method"] == "shared3" for x in calls) == 5280
    assert len(assessment) == 200
    assert len(read("shared_panel_schedule.csv")) == 120


def test_shared_engine_uses_three_scenarios_cache_and_switch_reevaluation(tmp_path):
    evaluator = PanelEvaluator()
    result = run_small(tmp_path, evaluator)
    assert result.simulator_calls == 18
    assert result.panel_evaluations == 6
    rows = [json.loads(x) for x in (tmp_path / "iterations.jsonl").read_text().splitlines()]
    assert len(rows) == 5
    assert len(list((tmp_path / "panel_events").glob("*.json"))) == 1
    assert all(len(x["panel_evaluation"]["scenario_observations"]) == 3 for x in rows)
    assert rows[1]["panel_seeds"] == rows[2]["panel_seeds"]
    assert rows[3]["panel_seeds"] == rows[4]["panel_seeds"]
    assert rows[2]["panel_seeds"] != rows[3]["panel_seeds"]
    assert result.best_panel_feasible is not None


def test_panel_all_feasible_requires_three_valid_feasible_scenarios():
    evaluator = PanelEvaluator(infeasible=True)
    response = evaluator.evaluate_panel(
        params=[1], evaluation_id=0, panel_index=0, panel_seeds=[1, 2, 3], runtime_seed=9
    )
    item = aggregate_panel(
        params=[1],
        candidate_id="x",
        evaluation_id=0,
        panel_index=0,
        panel_seeds=[1, 2, 3],
        raw_results=response["raw_results"],
        contract=Contract(),
        job_names=JOBS,
    )
    assert item["panel_pass_count"] == 0
    assert not item["panel_all_feasible"]


def test_no_panel_feasible_is_explicit(tmp_path):
    result = run_small(tmp_path, PanelEvaluator(infeasible=True))
    assert result.status == "NO_PANEL_FEASIBLE_CANDIDATE_FOUND"
    assert result.best_panel_feasible is None and result.best_violation is not None


def test_rejected_proposal_preserves_cached_current(tmp_path):
    result = run_small(tmp_path, PanelEvaluator(increasing=True), transitions=2, block_size=2)
    rows = [json.loads(x) for x in (tmp_path / "iterations.jsonl").read_text().splitlines()]
    assert not rows[1]["accepted"] and not rows[2]["accepted"]
    assert rows[1]["current_state_id"] == rows[0]["candidate_id"]
    assert rows[2]["current_state_id"] == rows[0]["candidate_id"]
    assert result.current["candidate_id"] == rows[0]["candidate_id"]


def test_resume_inside_panel_is_deterministic(tmp_path):
    evaluator = PanelEvaluator(fail_once={2})
    try:
        run_small(tmp_path, evaluator)
    except RuntimeError:
        pass
    resumed = run_small(tmp_path, evaluator)
    clean = run_small(tmp_path / "clean", PanelEvaluator())
    assert resumed.current["params"] == clean.current["params"]
    assert resumed.best_scalar["params"] == clean.best_scalar["params"]


def test_resume_at_panel_boundary_preserves_new_panel_cache(tmp_path):
    evaluator = PanelEvaluator(fail_once={4})  # boundary reevaluation is id 3, proposal is id 4
    try:
        run_small(tmp_path, evaluator)
    except RuntimeError:
        pass
    checkpoint = json.loads((tmp_path / "checkpoint.json").read_text())
    assert checkpoint["current_panel_index"] == 1 and checkpoint["next_transition"] == 3
    resumed = run_small(tmp_path, evaluator)
    assert resumed.simulator_calls == 18 and resumed.panel_evaluations == 6


def test_nominal_call_arithmetic():
    assert TRANSITIONS == 400 and BLOCK_SIZE == 10 and PANELS == 40 and PANEL_SIZE == 3
    assert NAIVE_CALLS_PER_TRAJECTORY == 401
    assert SHARED_CALLS_PER_TRAJECTORY == 3 + 400 * 3 + 39 * 3 == 1320
    assert 4 * NAIVE_CALLS_PER_TRAJECTORY == 1604
    assert 4 * SHARED_CALLS_PER_TRAJECTORY == 5280
    assert 1604 + 5280 == 6884 and 6884 + 200 == 7084


def test_compact_zip_excludes_scratch(tmp_path):
    experiment = tmp_path / "phase3c"
    experiment.mkdir()
    (experiment / "manifest.json").write_text("{}")
    scratch = experiment / "assessment/cells/x/scratch"
    scratch.mkdir(parents=True)
    (scratch / "big.csv").write_text("x")
    (scratch.parent / "result.json").write_text("{}")
    target = build_zip(experiment)
    import zipfile

    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
    assert any(x.endswith("result.json") for x in names)
    assert not any(x.endswith("big.csv") for x in names)


def test_report_constructs_final_pre_argos_decision(tmp_path):
    import pandas as pd

    rows = []
    for case in ["c005", "c007"]:
        for role in [
            "starting",
            "replicate_1_naive",
            "replicate_1_shared3",
            "replicate_2_naive",
            "replicate_2_shared3",
        ]:
            method = "starting" if role == "starting" else role.rsplit("_", 1)[1]
            replicate = 0 if role == "starting" else int(role.split("_")[1])
            for panel, count in [("A", 6), ("B", 7), ("COMBINED", 13)]:
                item = {
                    "case": case,
                    "candidate_role": role,
                    "replicate": replicate,
                    "method": method,
                    "panel": panel,
                    "pass_count": count,
                    "proposed_8_of_10_scenario_criterion": False,
                    "average_metric_feasible": True,
                    "mean_p90": 0.25,
                    "mean_Bloom_Pj": 0.03,
                    "mean_Cfull": 88.0,
                }
                rows.append(item)
    summary = pd.DataFrame(rows)
    pairs = pd.DataFrame(
        [
            {"case": case, "replicate": rep, "classification": "BOTH_PASS"}
            for case in ["c005", "c007"]
            for rep in [1, 2]
        ]
    )
    stable = pd.DataFrame(
        [
            {"case": case, "method": method, "s3_wins": 1, "naive_wins": 0, "ties": 1}
            for case in ["c005", "c007"]
            for method in ["naive", "shared3"]
        ]
    )
    optimization = pd.DataFrame(
        [
            {
                "method": method,
                "simulator_calls": 401 if method == "naive" else 1320,
                "wall_clock_seconds": 1.0,
            }
            for _case in ["c005", "c007"]
            for _rep in [1, 2]
            for method in ["naive", "shared3"]
        ]
    )
    report(tmp_path, summary, pairs, stable, optimization)
    text = (tmp_path / "report.md").read_text()
    assert "# Final Pre-ARGOS Recommendation" in text
    assert "candidate + collection of scenario outcomes" in text
    assert "next work item is ARGOS implementation" in text
