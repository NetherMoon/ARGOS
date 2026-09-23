"""Scientific contracts for single-table ARGOS search, without private run artifacts."""

from __future__ import annotations

from dataclasses import asdict, replace

import pandas as pd
import pytest

from argos.config import Config
from argos.contracts import assessment, qualified
from argos.fixed_table.protocol import GRID_TRACE_HASH, ROOT, config_for, load_plan
from argos.fixed_table.runner import archive, collect, new_experiment, run
from argos.fixed_table.simulator import FixedTableSimulator, geometry
from argos.provenance import sha256, write_json
from argos.search.candidates import Domain
from argos.types import Candidate, FlexDCObservation, JobIdentity, Metrics, QoSEvidence
from argos.vnext.controller import NextController


def candidate(number=1, source="synthetic"):
    return Candidate(
        f"candidate-{number}",
        0.45 + number * 0.001,
        0.08,
        (0.25, 0.25, 0.25, 0.25),
        source,
        prediction=Metrics(0.1, 0.2, (0.01,) * 4, 100.0),
    )


def observation(c, *, feasible=True, objective=100.0, seed=101, phase="search", evidence=True):
    pj = (0.01,) * 4 if feasible else (0.01, 0.01, 0.01, 0.2)
    metrics = Metrics(0.1, 0.2, pj, objective)
    support = tuple(
        QoSEvidence(
            JobIdentity(i, name, (1.0,) * 6),
            0.0,
            observation_count=10,
            finished_count=10,
            unfinished_count=0,
            exceedance_count=0,
            estimator_numerator=0,
            estimator_denominator=9,
        )
        for i, (name, p) in enumerate(zip(("Resnet", "GPT2", "Llama", "Bloom"), pj))
    )
    # Synthetic Pj values above are chosen for ranking; support can be absent to test
    # evidence exclusion without mirroring the estimator implementation.
    if evidence:
        support = tuple(replace(e, pj=0.0) for e in support)
        metrics = replace(metrics, pj=tuple(e.pj for e in support))
        if not feasible:
            metrics = replace(metrics, p90=0.4)
    else:
        support = None
    return FlexDCObservation(
        c,
        seed,
        phase,
        1,
        True,
        metrics,
        "PARSED",
        1.0,
        f"execution-{c.candidate_id}",
        qos_evidence=support,
    )


def controller(tmp_path, *, single=True):
    config = replace(
        Config(),
        search_seed=101,
        candidate_seed=202,
        confirmation_seeds=(303, 404, 505),
        max_workers=2,
    )
    domain = Domain(0.4, 0.55, 0.7, 0.01, 0.6, (0.15,) * 4, (0.45,) * 4)
    return NextController(
        tmp_path,
        config,
        domain,
        [],
        None,
        lambda c: replace(c, prediction=c.prediction or Metrics(0.1, 0.2, (0.01,) * 4, 100.0)),
        [candidate()],
        [] if single else (606, 707, 808),
        fixed_table_single_seed=single,
    )


def test_plan_has_six_independent_episodes_and_frozen_budget():
    seeds, rows = load_plan(ROOT)
    assert len(rows) == 6
    assert {row["workload"] for row in rows} == {"W2-short-qos5_4.5_4_3.5", "W2-short-qos5555"}
    assert {int(row["arrival_seed"]) for row in rows} == set(seeds["arrival_seeds"])
    assert sum(int(row["max_search_calls"]) for row in rows) == 192
    assert sum(int(row["max_final_checks"]) for row in rows) == 18
    assert (
        len({*seeds["arrival_seeds"], seeds["search_runtime_seed"], *seeds["final_runtime_seeds"]})
        == 7
    )
    assert (
        config_for(rows[0]["workload"], seeds, 10).starts,
        config_for(rows[0]["workload"], seeds, 10).iterations,
    ) == (512, 1500)


def test_manifest_freezes_small_plan_and_recovery_rejects_changes(tmp_path, monkeypatch):
    from argos.fixed_table import runner

    monkeypatch.setattr(
        runner,
        "verify_environment",
        lambda _root, *_plans: {
            "spec": {"fixed": {"duration_seconds": 3600}},
            "dependencies": {"FlexDC": "pinned", "CONDOR-FLEXDC": "pinned"},
            "checkpoint_sha256": "pinned",
            "artifact_manifest_sha256": "pinned",
            "v3_contexts": {},
        },
    )
    directory = tmp_path / "prepared"
    first = new_experiment(ROOT, directory, 10)
    assert first["budget"]["max_total"] == 210
    assert (directory / "seed_plan.json").is_file()
    assert (directory / "episode_plan.csv").is_file()
    assert new_experiment(ROOT, directory, 10) == first
    (directory / "seed_plan.json").write_text("changed", encoding="utf8")
    with pytest.raises(ValueError, match="integrity"):
        new_experiment(ROOT, directory, 10)

    validation = tmp_path / "fresh-validation"
    custom = new_experiment(
        ROOT,
        validation,
        10,
        "configs/fixed_table/validation_seed_plan.json",
        "configs/fixed_table/validation_episode_plan.csv",
    )
    assert custom["plan_paths"]["seed_plan"] == "configs/fixed_table/validation_seed_plan.json"
    assert new_experiment(
        ROOT,
        validation,
        10,
        "configs/fixed_table/validation_seed_plan.json",
        "configs/fixed_table/validation_episode_plan.csv",
    ) == custom
    with pytest.raises(ValueError, match="source or plan changed"):
        new_experiment(ROOT, validation, 10)


def test_six_episode_orchestration_shares_two_banks_without_sharing_search_state(
    tmp_path, monkeypatch
):
    from argos.fixed_table import runner

    seeds, rows = load_plan(ROOT)
    directory = tmp_path / "experiment"
    bank_calls, episode_calls = [], []

    def fake_manifest(_root, output, _workers, *_plans):
        output.mkdir()
        write_json(output / "seed_plan.json", seeds)
        return {"seed_plan": seeds}

    class FakeAdapter:
        def __init__(self, *_args):
            self.device_metadata = {"resolved": "cpu"}

    def fake_bank(_root, _directory, workload, _seeds, _manifest, _adapter, _workers):
        bank_calls.append(workload)
        return (None, None, None, None, None, {"wall_seconds": 5}, False, workload)

    def fake_episode(_root, output, row, _manifest, bank, _workers):
        episode_calls.append((row["workload"], row["arrival_seed"], bank[6]))
        episode = output / row["episode_path"]
        episode.mkdir(parents=True)
        write_json(episode / "selection.json", {"candidate": None, "status": "NO_BID"})
        write_json(episode / "vnext_state.json", {"observations": []})
        return {
            "workload": row["workload"],
            "arrival_seed": int(row["arrival_seed"]),
            "search_status": "NO_FEASIBLE_BID_FOUND_WITHIN_SEARCH_BUDGET",
            "runtime_check_status": "RUNTIME_CHECKS_NOT_RUN",
            "search_calls": 32,
            "runtime_checks_executed": 0,
            "selected_candidate_source": None,
            "initial_job_table_hash": f"table-{row['workload']}-{row['arrival_seed']}",
            "episode_seconds": 1.0,
        }

    monkeypatch.setattr(runner, "new_experiment", fake_manifest)
    monkeypatch.setattr(runner, "V3Adapter", FakeAdapter)
    monkeypatch.setattr(runner, "bank_for", fake_bank)
    monkeypatch.setattr(runner, "episode_result", fake_episode)
    zipped = run(ROOT, directory, 10)
    assert zipped.exists()
    assert bank_calls == list(dict.fromkeys(row["workload"] for row in rows))
    assert len(episode_calls) == 6
    assert [reused for _, _, reused in episode_calls] == [False, True, True, False, True, True]
    assert len({(workload, seed) for workload, seed, _ in episode_calls}) == 6
    assert len(pd.read_csv(directory / "summary.csv")) == 6


def test_single_seed_search_selects_one_feasible_observation_without_repeats(tmp_path):
    ctl = controller(tmp_path)
    cheap_fail = observation(candidate(2), feasible=False, objective=1)
    feasible = observation(candidate(3), objective=20)
    costly_feasible = observation(candidate(4), objective=30)
    ctl.state["batch"] = 4
    ctl.state["observations"] = [asdict(o) for o in (cheap_fail, costly_feasible, feasible)]
    ctl.save()
    result = ctl.run()
    assert result["phase"] == "DONE"
    assert result["incumbent"]["candidate_id"] == "candidate-3"
    assert result["confirmation_index"] == 0
    assert all(row["status"] != "SEARCH_ROBUST_FEASIBLE" for row in result["search_statuses"])
    assert qualified(feasible) and not qualified(cheap_fail)


def test_missing_evidence_never_becomes_incumbent(tmp_path):
    ctl = controller(tmp_path)
    no_support = observation(candidate(3), objective=1, evidence=False)
    ctl.state["batch"] = 4
    ctl.state["observations"] = [asdict(no_support)]
    result = ctl.run()
    assert result["phase"] == "NO_BID"
    assert result["incumbent"] is None
    assert assessment(no_support)["evidence_status"] == "UNKNOWN"


def test_proposals_have_eight_distinct_geometries_and_no_repeat_seeds(tmp_path):
    ctl = controller(tmp_path)
    first = ctl.propose()
    assert len(first["entries"]) == 8
    assert (
        len(
            {
                (e["candidate"]["Pbar"], e["candidate"]["R"], *e["candidate"]["weights"])
                for e in first["entries"]
            }
        )
        == 8
    )
    assert {e["seed"] for e in first["entries"]} == {101}
    assert not any(e["repeat"] for e in first["entries"])
    with pytest.raises(ValueError, match="no repeats"):
        NextController(
            tmp_path / "bad",
            ctl.config,
            ctl.domain,
            [],
            None,
            ctl.predictor,
            [],
            [606],
            fixed_table_single_seed=True,
        )


def test_full_synthetic_search_spends_32_distinct_calls_without_runtime_repeats(tmp_path):
    class FakeSimulator:
        def __init__(self):
            self.calls = []

        def evaluate_batch(self, candidates, seed, phase, batch):
            self.calls.extend((geometry(c), seed, phase) for c in candidates)
            return [
                observation(c, objective=100.0 + i, seed=seed) for i, c in enumerate(candidates)
            ]

        def search_attempts(self):
            return len(self.calls)

    ctl = controller(tmp_path)
    fake = FakeSimulator()
    ctl.simulator = fake
    result = ctl.run()
    assert result["phase"] == "DONE"
    assert result["search_calls"] == 32
    assert result["repeats"] == 0
    assert len({x[0] for x in fake.calls}) == 32
    assert {x[1:] for x in fake.calls} == {(101, "search")}
    assert result["confirmation_index"] == 0


def test_cell_identity_is_table_seed_geometry_and_phase_specific(tmp_path, monkeypatch):
    import argos.fixed_table.simulator as module

    monkeypatch.setattr(module, "FixedEvaluator", lambda *args: None)
    monkeypatch.setattr(module, "ObjectiveContract", lambda *args: None)
    monkeypatch.setattr(module, "ordered_jobs", lambda *args: ())
    episode = tmp_path / "episode"
    episode.mkdir()
    table = episode / "initial_jobs.csv.gz"
    table.write_bytes(b"synthetic immutable table")
    root = tmp_path
    workload = root / "workload.ini"
    workload.write_text("synthetic")
    experiment = root / "experiment.ini"
    experiment.write_text("synthetic")
    context = {
        "root": str(root),
        "output": str(episode),
        "case": {"workload": "synthetic", "workload_path": "workload.ini"},
        "spec": {
            "files": {"workload.ini": sha256(workload), "experiment.ini": sha256(experiment)},
            "experiment_path": "experiment.ini",
            "policy": "AQA",
        },
        "arrival_seed": 1,
        "initial_job_table_hash": "table-one",
        "initial_file_sha256": sha256(table),
        "grid_signal_hash": GRID_TRACE_HASH,
    }
    write_json(episode / "fixed_context.json", context)
    simulator = FixedTableSimulator(
        root,
        episode,
        replace(Config(), search_seed=101, confirmation_seeds=(303, 404, 505)),
        context,
        2,
    )
    one = simulator._identity(candidate(1), 101, "search", 1)
    assert one != simulator._identity(candidate(1), 303, "confirmation", 1)
    assert one != simulator._identity(candidate(2), 101, "search", 1)
    with pytest.raises(ValueError, match="Search runtime seed"):
        simulator.evaluate_batch([candidate()], 999, "search", 1)
    simulator.context = {**context, "initial_job_table_hash": "table-two"}
    assert one != simulator._identity(candidate(1), 101, "search", 1)
    with pytest.raises(ValueError, match="32.*3"):
        simulator._index("search", 5, 0)


def test_compact_report_and_zip_handle_no_bid_and_partial_checks(tmp_path):
    directory = tmp_path / "experiment"
    rows = []
    for i, status in enumerate(
        ("NO_FEASIBLE_BID_FOUND_WITHIN_SEARCH_BUDGET", "SEARCH_OBSERVED_FEASIBLE"), 1
    ):
        row = {"workload": f"W2-{i}", "arrival_seed": str(i), "episode_path": f"W2-{i}/arrival_{i}"}
        rows.append(row)
        episode = directory / row["episode_path"]
        episode.mkdir(parents=True)
        write_json(
            episode / "result.json",
            {
                "workload": row["workload"],
                "arrival_seed": i,
                "search_status": status,
                "search_calls": 32,
                "runtime_check_status": "RUNTIME_CHECKS_NOT_RUN"
                if i == 1
                else "RUNTIME_CHECKS_1_OF_3_PASS",
                "selected_candidate_source": None if i == 1 else "protected_v3_elite",
                "initial_job_table_hash": str(i),
            },
        )
        write_json(episode / "selection.json", {"status": status, "candidate": None})
        write_json(episode / "vnext_state.json", {"observations": []})
    write_json(directory / "seed_plan.json", {"final_runtime_seeds": [303, 404, 505]})
    result = collect(directory, rows)
    assert len(result) == 2
    report = (directory / "report.md").read_text()
    assert "NO_FEASIBLE_BID_FOUND" in report and "RUNTIME_CHECKS_1_OF_3_PASS" in report
    zipped = archive(directory)
    assert zipped.exists()
    import zipfile

    with zipfile.ZipFile(zipped) as z:
        assert "report.md" in z.namelist()
        assert "W2-1/arrival_1/result.json" in z.namelist()


def test_fresh_validation_plan_is_distinct_and_keeps_the_fixed_budget():
    prior, _ = load_plan(ROOT)
    fresh, rows = load_plan(
        ROOT,
        "configs/fixed_table/validation_seed_plan.json",
        "configs/fixed_table/validation_episode_plan.csv",
    )
    assert len(rows) == 6
    assert len(set(fresh["arrival_seeds"])) == 3
    assert not set(fresh["arrival_seeds"]) & set(prior["arrival_seeds"])
    assert not set(fresh["final_runtime_seeds"]) & set(prior["final_runtime_seeds"])
    assert fresh["search_runtime_seed"] == prior["search_runtime_seed"]
    assert fresh["controller_seeds"] == prior["controller_seeds"]
    assert sum(int(row["max_search_calls"]) for row in rows) == 192
    assert sum(int(row["max_final_checks"]) for row in rows) == 18


def test_bank_identity_uses_json_stable_weight_bounds(monkeypatch, tmp_path):
    from argos.fixed_table import runner

    class Adapter:
        device_metadata = {"backend": "CPU"}

    monkeypatch.setattr(runner, "setup", lambda *_args: (None, None, None, None, None, None))
    captured = {}

    def fake_get_bank(_directory, case, *_args):
        captured.update(case)
        raise RuntimeError("identity captured")

    monkeypatch.setattr(runner, "get_bank", fake_get_bank)
    seeds, _ = load_plan(ROOT)
    manifest = {
        "specification": {
            "files": {
                f".deps/FlexDC/configs/workload/{name}.ini": "workload"
                for name in ("W2-short-qos5_4.5_4_3.5", "W2-short-qos5555")
            }
            | {"experiment.ini": "experiment", "cluster.ini": "cluster"},
            "experiment_path": "experiment.ini",
            "cluster_path": "cluster.ini",
        },
        "checkpoint_sha256": "checkpoint",
        "v3_contexts": {"W2-short-qos5555": {"label": "REVIEWED_V3_CONTEXT"}},
        "source_hashes": {
            "src/argos/surrogate/v3_adapter.py": "v3",
            "src/argos/campaign/candidate_bank.py": "bank",
            "configs/v3_context_contract.json": "context",
        },
    }
    with pytest.raises(RuntimeError, match="identity captured"):
        runner.bank_for(ROOT, tmp_path, "W2-short-qos5555", seeds, manifest, Adapter(), 10)
    assert captured["bank_identity"]["weight_bounds"] == [0.15, 0.45]
