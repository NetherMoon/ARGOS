"""Seed separation, replay barrier and compact observer tests; no full simulations."""

import io
import json
import random
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from argos.diagnostics import seed_factorization as sf
from argos.diagnostics.seed_factorization_reporting import archive, factor_effects
from argos.diagnostics.seed_factorization_worker import (
    JOB_COLUMNS,
    atomic_json,
    create_initial,
    job_summaries,
    observed_simulator,
)
from argos.diagnostics.workload_seed_forensics import load_generator, read_json, sha, table_hash
from argos.simulator.evidence import validate_reported_qos_evidence
from argos.types import JobIdentity

ROOT = Path(__file__).resolve().parents[2]


def test_real_generator_runtime_seed_does_not_change_initial_state():
    spec = read_json(ROOT / sf.DEFAULT_SPEC)
    case = spec["cases"][0]
    _, exp, _, _, initial, _ = create_initial(ROOT, spec, case, case["seeds"][0])
    expected = table_hash(initial)
    initial.setflags(write=False)
    copies, draws = [], []
    for runtime_seed in case["seeds"][:2]:
        mutable = initial.copy()
        exp._random_seed = runtime_seed
        random.seed(exp.random_seed)
        np.random.seed(exp.random_seed)
        draws.append((random.random(), np.random.random()))
        assert table_hash(mutable) == expected
        mutable[3, 0] = 10
        copies.append(mutable)
    assert draws[0] != draws[1]
    assert table_hash(initial) == expected
    assert not np.shares_memory(copies[0], copies[1])
    _, _, _, _, different, _ = create_initial(ROOT, spec, case, case["seeds"][1])
    assert table_hash(different) != expected


def test_observer_preserves_upstream_precision_and_does_not_consume_rng_or_mutate():
    load_generator(ROOT)
    from peacsim.simulator import Simulator

    base = object.__new__(Simulator)
    compact = object.__new__(observed_simulator(Simulator))
    jobs = np.zeros((10, 3))
    jobs[1] = [0, 1, 0]
    jobs[2] = [0, 5, 10]
    jobs[3] = [-1, 1, -1]
    nodes = np.zeros((12, 2))
    nodes[1] = [1, -1]
    nodes[2] = [1, -1]
    nodes[3] = [500, 120]
    nodes[11] = [450, -1]
    for obj in [base, compact]:
        obj._job_table = jobs.copy()
        obj._node_table = nodes.copy()
        obj._job_type_count = 2
        obj._server_count = 2
    rows = []
    compact.queue_writer = SimpleNamespace(writerow=rows.append)
    before = (random.getstate(), np.random.get_state())
    args = (5, True, 620.234, 600.123, 1, 3, 0.12345678, 620.234, 0)
    original_stream, compact_stream = io.StringIO(), io.StringIO()
    base.record_state(*args, original_stream)
    compact.record_state(*args, compact_stream)
    assert (
        compact_stream.getvalue().strip().split(",")
        == original_stream.getvalue().strip().split(",")[:9]
    )
    assert random.getstate() == before[0]
    after = np.random.get_state()
    assert (
        after[0] == before[1][0]
        and np.array_equal(after[1], before[1][1])
        and after[2:] == before[1][2:]
    )
    assert np.array_equal(compact._job_table, jobs) and np.array_equal(compact._node_table, nodes)
    assert rows[0][2] == 1 and rows[1][3:5] == [1, 1]
    assert observed_simulator(Simulator).run is Simulator.run


def test_qos_accounting_and_censoring_boundaries():
    # Prefill excluded; equality to QoS threshold does not violate; exact late boundary excluded.
    table = pd.DataFrame(
        [
            [0, 0, 0, 0, 100, 1, 100, 0, 10, 1],
            [1, 0, 1, 2, 21, 1, 21, 0, 10, 1],
            [2, 0, 2, 3, 23, 1, 23, 0, 10, 1],
            [3, 0, 10, -1, -1, 0, 100, 0, 10, 1],
            [4, 0, 90, -1, -1, 0, 100, 0, 10, 1],
            [5, 0, 80, 81, -1, 0, 100, 0, 10, 1],
        ],
        columns=JOB_COLUMNS,
    )
    # Use real one-hour support with shifted horizon boundaries for the two late jobs.
    table.loc[4, "arrival_time"] = 3590
    table.loc[5, ["arrival_time", "start_time"]] = [3580, 3581]
    job = JobIdentity(0, "Bloom", (100, 500, 10, 20, 1, 1))
    evidence = validate_reported_qos_evidence(table, [job], [1 / 3])
    summary, accounting = job_summaries(table, evidence, 1)
    row = accounting.iloc[0]
    assert row.qos_observations == 4 and row.violation_count == 2
    assert row.estimator_numerator == 1 and row.estimator_denominator == 3
    assert row.violating_completed == 1 and row.violating_unfinished == 1
    assert row.excluded_zero_submit == 1 and row.excluded_late_unfinished == 1
    assert row.empirical_exceedance_fraction == 0.5
    assert summary.iloc[0].never_started == 2 and summary.iloc[0].started_unfinished == 1


def mock_spec():
    return {
        "replay_absolute_tolerance": 1e-12,
        "cases": [
            {
                "case": case,
                "seeds": [11, 22, 33],
                "historical": [
                    {
                        "seed": s,
                        "p90": 0.2,
                        "Pj": [0.0, 0.0, 0.0, 0.2 if s == 22 else 0.01],
                        "objective": 10.0,
                        "initial_job_table_hash": f"hash{s}",
                        "arrival_hash": f"arrival{s}",
                        "evidence_counts": [10] * 4,
                        "evidence_qualified_pass": s != 22,
                    }
                    for s in [11, 22, 33]
                ],
            }
            for case in ["c005", "c007"]
        ],
    }


def mock_result(spec, case_id, arrival, runtime):
    case = next(c for c in spec["cases"] if c["case"] == case_id)
    ref = next(r for r in case["historical"] if r["seed"] == arrival)
    return {
        **ref,
        "case": case_id,
        "cell_id": sf.cell_name(case_id, arrival, runtime),
        "arrival_seed": arrival,
        "runtime_seed": runtime,
    }


@pytest.mark.parametrize("mismatch", [False, True])
def test_hard_replay_barrier_counts_diagonals_once(monkeypatch, tmp_path, mismatch):
    spec = mock_spec()
    manifest = {"specification": spec, "input_fingerprint": "test"}
    stages, exports = [], []

    def execute(root, output, manifest, cells, workers):
        stages.append(cells)
        results = [mock_result(spec, *cell) for cell in cells]
        if mismatch and len(stages) == 1:
            results[0]["Pj"] = [0.0, 0.0, 0.0, 0.25]
        return results

    monkeypatch.setattr(sf, "execute_stage", execute)
    monkeypatch.setattr(sf, "invariants", lambda *args: None)
    monkeypatch.setattr(
        sf, "export", lambda output, results, checks, status, error=None: exports.append(status)
    )
    code = sf.run_stages(ROOT, tmp_path, manifest, 10)
    assert len(stages[0]) == 6 and all(a == r for c, a, r in stages[0])
    if mismatch:
        assert code == 2 and len(stages) == 1 and exports[-1] == "REPLAY_FAILED"
        assert not (tmp_path / "replay_gate.json").exists()
    else:
        assert code == 0 and len(stages[1]) == 12
        assert len(set(stages[0] + stages[1])) == 18
        assert read_json(tmp_path / "replay_gate.json")["passed"]


def test_replay_tolerates_only_small_roundoff_and_exact_counts():
    spec = mock_spec()
    ref = spec["cases"][0]["historical"][0]
    result = mock_result(spec, "c005", 11, 11)
    result["objective"] += 5e-13
    assert all(r["passed"] for r in sf.replay_check(spec, "c005", ref, result))
    result["evidence_counts"] = [10, 10, 10, 11]
    assert not all(r["passed"] for r in sf.replay_check(spec, "c005", ref, result))


def test_resume_skips_complete_cells_and_rejects_corruption(monkeypatch, tmp_path):
    name = sf.cell_name("c005", 11, 11)
    cell = tmp_path / "cells" / name
    cell.mkdir(parents=True)
    result = {"cell_id": name, "status": "COMPLETE"}
    atomic_json(cell / "result.json", result)
    atomic_json(
        cell / "completion.json",
        {"input_fingerprint": "test", "files": {"result.json": sha(cell / "result.json")}},
    )
    monkeypatch.setattr(sf, "invariants", lambda *args: None)
    monkeypatch.setattr(
        sf.subprocess, "run", lambda *args, **kwargs: pytest.fail("Completed cell rerun")
    )
    assert sf.execute_stage(
        ROOT, tmp_path, {"input_fingerprint": "test"}, [("c005", 11, 11)], 10
    ) == [result]
    (cell / "result.json").write_text("{}")
    with pytest.raises(ValueError, match="seal mismatch"):
        sf.completed_cell(tmp_path, name, "test")


def test_incomplete_cell_is_not_silently_retried(tmp_path):
    (tmp_path / "cells" / "x").mkdir(parents=True)
    with pytest.raises(ValueError, match="Incomplete/interrupted"):
        sf.completed_cell(tmp_path, "x", "test")


def test_factor_decomposition_has_no_false_interaction_for_additive_data():
    a = np.array([0, 2, 4])[:, None] + np.array([0, 1, 3])[None, :]
    result = factor_effects(a)
    assert result["ss_interaction"] == pytest.approx(0, abs=1e-25)
    assert result["ss_total"] == pytest.approx(result["ss_arrival"] + result["ss_runtime"])
    assert result["runtime_ranges_at_fixed_arrival"] == [3, 3, 3]
    assert result["arrival_ranges_at_fixed_runtime"] == [4, 4, 4]
    assert not any("p_value" in key for key in result)


def test_archive_excludes_scratch_and_verifies_compact_contents(tmp_path):
    import zipfile

    atomic_json(tmp_path / "manifest.json", {"status": "TEST"})
    scratch = tmp_path / "cells/x/scratch"
    scratch.mkdir(parents=True)
    (scratch / "node.csv").write_text("not scientific retained evidence")
    (tmp_path / "report.md").write_text("test")
    target = archive(tmp_path)
    with zipfile.ZipFile(target) as z:
        assert "report.md" in z.namelist() and not any("scratch" in n for n in z.namelist())
        hashes = json.loads(z.read("artifact_hashes.json"))
        assert hashes["report.md"] == sha(tmp_path / "report.md")


def test_complete_synthetic_matrix_export(tmp_path):
    # Synthetic summaries only: verify the all-cells reporting branch without simulations.
    from argos.diagnostics.seed_factorization_reporting import export

    spec = mock_spec()
    for case in spec["cases"]:
        case["workload"] = "synthetic_" + case["case"]
    atomic_json(tmp_path / "manifest.json", {"specification": spec, "status": "SYNTHETIC_TEST"})
    (tmp_path / "source_audit.md").write_text("synthetic test, no simulator executions")
    results = []
    for case in spec["cases"]:
        for i, a in enumerate(case["seeds"]):
            for j, r in enumerate(case["seeds"]):
                result = mock_result(spec, case["case"], a, r)
                result.update(
                    workload=case["workload"],
                    grid_signal_hash="grid",
                    target_trace_hash="target",
                    logged_target_hash="logged",
                    P_watts=1,
                    R_watts=1,
                )
                cell = tmp_path / "cells" / result["cell_id"]
                cell.mkdir(parents=True)
                pd.DataFrame(
                    [
                        {
                            "job_type_id": 3,
                            "unfinished": 10 + i + j,
                            "waiting_started_seconds_p90": i * 2 + j,
                        }
                    ]
                ).to_csv(cell / "per_job_run_summary.csv", index=False)
                pd.DataFrame([{"job_type_id": 3, "Pj": result["Pj"][3]}]).to_csv(
                    cell / "qos_accounting.csv", index=False
                )
                pd.DataFrame([{"job_type_id": 3, "queue_after_policy_mean": i + j}]).to_csv(
                    cell / "queue_summary.csv", index=False
                )
                results.append(result)
    target = export(tmp_path, results, [], "SYNTHETIC_TEST_COMPLETE")
    assert target.exists()
    assert len(pd.read_csv(tmp_path / "all_runs.csv")) == 18
    assert len(list((tmp_path / "plots").glob("*.png"))) == 4
    effects = pd.read_csv(tmp_path / "descriptive_factor_effects.csv")
    assert len(effects) == 22 and effects.ss_interaction.notna().all()
    matrix = pd.read_csv(tmp_path / "crossed_matrices/c005_Bloom_Pj.csv", index_col=0)
    assert matrix.shape == (3, 3) and matrix.notna().all().all()
