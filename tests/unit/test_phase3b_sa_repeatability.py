"""Phase 3B planning/reporting tests; no FlexDC simulation is executed."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest

from argos.experimental_sa.phase3.planning import EXPECTED_SHAS, collect_prior_seeds
from argos.experimental_sa.phase3b.planning import (
    EVALUATIONS,
    PHASE3_ARRIVAL_SCHEDULE_SHA256,
    _collect_seed_values,
    _generate_seed_plan,
    create_plan,
    generate_replicate_search_draws,
    verify_phase3_provenance,
)
from argos.experimental_sa.phase3b.reporting import (
    JOBS,
    _assessment_summaries,
    _build_report,
    _paired,
    _plots,
    _repeatability,
    build_zip,
)
from argos.provenance import git

ROOT = Path(__file__).resolve().parents[2]


def require_archived_phase3_head():
    if git(ROOT, "rev-parse", "HEAD") != EXPECTED_SHAS["ARGOS"]:
        pytest.skip("Phase 3B plan creation requires its archived Phase 3 ARGOS commit")


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf8") as stream:
        return list(csv.DictReader(stream))


def test_phase3_artifacts_load_and_schedule_hash_matches():
    require_archived_phase3_head()
    value = verify_phase3_provenance(ROOT)
    assert value["phase3_manifest"]["status"] == "COMPLETE"
    assert (
        value["phase3_manifest"]["repo_shas"]["ARGOS"] == "6c95e4b77eebbf25f32522c5836d69759f225963"
    )
    assert value["phase3_contract"]["simulator_policy_contract"] == "normal_v3_argos_aqa"
    assert value["phase3_seed_plan"]["training_runtime_seed"] == 3609882979
    assert len(value["arrival_schedule"]) == EVALUATIONS
    assert (
        PHASE3_ARRIVAL_SCHEDULE_SHA256
        == "464225850c667f6566da4719661d91e9f96cd0c007c6a8b012e7bad1430db349"
    )


def test_new_seed_plan_is_deterministic_new_and_frozen():
    require_archived_phase3_head()
    phase3 = verify_phase3_provenance(ROOT)
    prior = collect_prior_seeds(ROOT) | _collect_seed_values(phase3["phase3_seed_plan"])
    first = _generate_seed_plan(prior)
    second = _generate_seed_plan(prior)
    assert first == second
    roots = set(first["replicate_search_root_seeds"].values())
    assessment = set(first["assessment_seeds"])
    assert len(roots) == 2
    assert len(assessment) == 20
    assert not roots & prior
    assert not assessment & prior
    assert not roots & assessment
    assert first["panel_A"] == first["assessment_seeds"][:10]
    assert first["panel_B"] == first["assessment_seeds"][10:]


def test_search_draws_are_matched_by_reference_and_distinct_by_replicate():
    first = generate_replicate_search_draws(123)
    repeated = generate_replicate_search_draws(123)
    second = generate_replicate_search_draws(124)
    assert first == repeated
    assert len(first["A"]) == len(first["B"]) == 400
    assert first["A"] != first["B"]
    assert first != second


def test_full_plan_has_exact_budget_and_no_replicate1_optimization(tmp_path):
    require_archived_phase3_head()
    experiment = create_plan(ROOT, tmp_path / "phase3b")
    replicates = read_csv(experiment / "replicate_plan.csv")
    optimization = read_csv(experiment / "optimization_run_plan.csv")
    assessment = read_csv(experiment / "assessment_run_plan.csv")
    seeds = read_csv(experiment / "assessment_seed_panel.csv")
    assert len(replicates) == 12
    assert len(optimization) == 3208
    assert {int(x["replicate"]) for x in optimization} == {2, 3}
    assert len(assessment) == 280
    assert len(seeds) == 20
    assert sum(x["candidate_role"] == "starting" for x in assessment) == 40
    assert sum(x["candidate_role"].startswith("replicate_1") for x in assessment) == 80
    assert {x["runtime_seed"] for x in optimization} == {"3609882979"}
    varying = [x for x in optimization if x["method"] == "varying"]
    fixed = [x for x in optimization if x["method"] == "fixed"]
    assert len({x["arrival_seed"] for x in varying}) == 401
    assert len({x["arrival_seed"] for x in fixed}) == 1
    for replicate in [2, 3]:
        for label in ["A", "B"]:
            rows = [
                x
                for x in replicates
                if int(x["replicate"]) == replicate and x["case_label"] == label
            ]
            assert len(rows) == 2
            assert rows[0]["search_draw_schedule"] == rows[1]["search_draw_schedule"]
            assert rows[0]["search_draw_schedule_sha256"] == rows[1]["search_draw_schedule_sha256"]


def synthetic_assessment() -> pd.DataFrame:
    rows = []
    for case in ["c005", "c007"]:
        for role in ["starting"] + [
            f"replicate_{r}_{m}" for r in (1, 2, 3) for m in ("fixed", "varying")
        ]:
            replicate = 0 if role == "starting" else int(role.split("_")[1])
            method = "starting" if role == "starting" else role.rsplit("_", 1)[1]
            for seed in range(20):
                p90 = 0.2 + (0.11 if seed == 0 else 0)
                pjs = [0.01, 0.02, 0.03, 0.04]
                rows.append(
                    {
                        "case": case,
                        "candidate_role": role,
                        "replicate": replicate,
                        "method": method,
                        "panel": "A" if seed < 10 else "B",
                        "panel_index": seed + 1 if seed < 10 else seed - 9,
                        "seed": seed,
                        "complete_scenario_pass": p90 <= 0.30,
                        "valid": True,
                        "p90": p90,
                        "Cfull": 80 + p90,
                        "failure_reasons": "tracking" if p90 > 0.30 else "NONE",
                        **{f"{job}_Pj": pjs[index] for index, job in enumerate(JOBS)},
                    }
                )
    return pd.DataFrame(rows)


def test_reporting_shapes_and_distinct_criteria():
    data = synthetic_assessment()
    summaries = _assessment_summaries(data)
    assert len(summaries) == 42
    paired = _paired(data)
    assert len(paired) == 120
    repeatability = _repeatability(pd.DataFrame(summaries))
    assert len(repeatability) == 6
    combined = [x for x in summaries if x["panel"] == "COMBINED"]
    assert all(x["proposed_8_of_10_scenario_criterion"] == "NOT_APPLICABLE" for x in combined)
    assert all(x["average_metric_feasible"] for x in summaries)


def test_compact_zip_excludes_simulator_scratch(tmp_path):
    experiment = tmp_path / "phase3b"
    experiment.mkdir()
    (experiment / "manifest.json").write_text("{}", encoding="utf8")
    scratch = experiment / "assessment" / "cells" / "x" / "scratch"
    scratch.mkdir(parents=True)
    (scratch / "large.csv").write_text("do not archive", encoding="utf8")
    result = scratch.parent / "result.json"
    result.write_text("{}", encoding="utf8")
    path = build_zip(experiment)
    assert path.exists()
    import zipfile

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    assert any(name.endswith("manifest.json") for name in names)
    assert any(name.endswith("result.json") for name in names)
    assert not any(name.endswith("large.csv") for name in names)


def test_plots_and_report_generate_from_synthetic_results(tmp_path):
    experiment = tmp_path / "phase3b_reporting"
    (experiment / "plots").mkdir(parents=True)
    data = synthetic_assessment()
    summary = pd.DataFrame(_assessment_summaries(data))
    paired = pd.DataFrame(_paired(data))
    repeatability = pd.DataFrame(_repeatability(summary))
    candidate_rows = []
    for case in ["c005", "c007"]:
        for replicate in (1, 2, 3):
            for method in ("fixed", "varying"):
                candidate_rows.append(
                    {
                        "case": case,
                        "replicate": replicate,
                        "method": method,
                        "Pbar": 0.47 + replicate / 10000,
                        "R": 0.06 + replicate / 1000,
                        "weights": "[0.25,0.25,0.25,0.25]",
                    }
                )
    candidates = pd.DataFrame(candidate_rows)
    _plots(experiment, summary, candidates)
    _build_report(experiment, summary, paired, repeatability, candidates)
    assert len(list((experiment / "plots").glob("*.png"))) == 8
    report = (experiment / "report.md").read_text(encoding="utf8")
    assert "Cross-replicate findings" in report
    assert "Average metric feasibility and complete-scenario pass frequency" in report
    assert "Suggested next experiment" in report
