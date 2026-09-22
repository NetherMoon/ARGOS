"""Phase 2B plan/merge/retention tests. No full FlexDC execution."""

import ast
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from argos.diagnostics import seed_characterization as sc
from argos.diagnostics import seed_characterization_reporting as report
from argos.diagnostics.seed_factorization_worker import create_initial, run_cell
from argos.diagnostics.workload_seed_forensics import table_hash

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def inputs():
    return sc.load_inputs(ROOT)


def prepared(tmp_path, inputs):
    config, spec, old, old_results, confirmations, plan = inputs
    identity = sc.run_identity(ROOT, config)
    return sc.setup(ROOT, tmp_path, identity, spec, old, old_results, confirmations, plan)


def test_plan_exact_counts_no_overlap_and_preserved_axes(inputs):
    config, spec, _old, results, confirmations, plan = inputs
    assert len(plan) == 56 and len({r["cell_id"] for r in plan}) == 56
    assert sum(r["role"] == "COUPLED_NEW" for r in plan) == 14
    assert sum(r["role"] == "FACTORIZATION_NEW" for r in plan) == 42
    assert not ({r["cell_id"] for r in results} & {r["cell_id"] for r in plan})
    assert sc.select_seeds(ROOT, config) == config["new_seeds"]
    assert not set(config["new_seeds"]) & set(config["historical_seed_union"])
    for case in spec["cases"]:
        matrix = [r for r in plan if r["case"] == case["case"] and r["role"] == "FACTORIZATION_NEW"]
        assert {r["runtime_seed"] for r in matrix} == set(case["seeds"])
        assert len(matrix) == 21
    b = {r["arrival_seed"] for r in confirmations if r["case"] == "c007"}
    assert b == {624506888, 144392579, 1004088181} and 3514694477 not in b


def test_shared_simulation_and_extraction_body_unchanged(inputs):
    config, *_ = inputs
    before = ast.parse(
        (ROOT / config["phase2_directory"] / "inputs/seed_factorization_worker.py").read_text()
    )
    after = ast.parse((ROOT / sc.SHARED_WORKER).read_text())

    def method(tree, name):
        return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)

    for name in ["observed_simulator", "job_summaries", "stats", "check_context"]:
        assert ast.dump(method(before, name)) == ast.dump(method(after, name))

    def simulation_body(tree):
        body = method(tree, "run_cell").body
        index = next(
            i
            for i, node in enumerate(body)
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "initial_hash" for t in node.targets)
        )
        return [ast.dump(node) for node in body[index:]]

    assert simulation_body(before) == simulation_body(after)


def test_new_seed_generation_requires_reference_and_is_shared_between_workloads(inputs):
    config, spec, *_ = inputs
    seed = config["new_seeds"][0]
    tables = []
    for case in spec["cases"]:
        *_, table, prefill = create_initial(ROOT, spec, case, seed, require_reference=False)
        assert prefill == 1000
        tables.append(table)
    assert np.array_equal(tables[0][:3], tables[1][:3])
    assert table_hash(tables[0]) != table_hash(tables[1])
    with pytest.raises(ValueError, match="Missing frozen initial-state reference"):
        create_initial(ROOT, spec, spec["cases"][0], seed)


def test_old_cell_rejected_before_generation(tmp_path, inputs, monkeypatch):
    manifest = prepared(tmp_path, inputs)
    import argos.diagnostics.seed_factorization_worker as worker

    monkeypatch.setattr(
        worker,
        "create_initial",
        lambda *args, **kwargs: pytest.fail("Historical cell reached generation"),
    )
    seed = manifest["frozen_runtime_axes"]["c005"][0]
    with pytest.raises(ValueError, match="historical reruns prohibited"):
        run_cell(ROOT, tmp_path, "c005", seed, seed)


def test_dry_merge_keeps_unknown_results_and_real_confirmation_population(tmp_path, inputs):
    manifest = prepared(tmp_path, inputs)
    new, fixed, factor = report.merged_results(tmp_path, manifest, [])
    assert len(new) == 56 and len(fixed) == 20 and len(factor) == 60
    assert (new.status == "NOT_RUN").all() and new.evidence_qualified_pass.isna().all()
    assert (fixed.status == "COMPLETE").sum() == 6 and (factor.status == "COMPLETE").sum() == 18
    summary = report.fixed_summary(fixed)
    assert summary.tested_count.tolist() == [3, 3]
    assert summary.passed_tested_scenarios.tolist() == [1, 0]
    assert summary.statement.str.startswith("INCOMPLETE").all()


def test_rectangular_decomposition_uses_ten_row_runtime_multiplier():
    matrix = np.arange(10)[:, None] * 2 + np.array([0.0, 1.0, 4.0])[None, :]
    e = report.matrix_effects(matrix)
    assert e["ss_runtime"] == pytest.approx(10 * np.sum((matrix.mean(axis=0) - matrix.mean()) ** 2))
    assert e["ss_arrival"] == pytest.approx(3 * np.sum((matrix.mean(axis=1) - matrix.mean()) ** 2))
    assert e["ss_interaction"] == pytest.approx(0, abs=1e-25)
    assert e["ss_total"] == pytest.approx(e["ss_arrival"] + e["ss_runtime"])
    assert "selected finite matrix" in e["interpretation"]
    with pytest.raises(ValueError):
        report.matrix_effects(np.full((10, 3), np.nan))


def synthetic_results(manifest):
    results = []
    for row in manifest["new_run_plan"]:
        case = next(c for c in manifest["specification"]["cases"] if c["case"] == row["case"])
        index = manifest["configuration"]["new_seeds"].index(row["arrival_seed"])
        pj = 0.02 + index * 0.025
        results.append(
            {
                **row,
                "weights": case["weights"],
                "Pj": [0.0, 0.0, 0.0, pj],
                "p90": 0.27,
                "objective": 90.0 + index,
                "evidence_counts": [1000] * 4,
                "evidence_qualified_pass": pj <= 0.1,
                "initial_job_table_hash": f"table{row['arrival_seed']}",
                "arrival_hash": f"arrival{row['arrival_seed']}",
                "grid_signal_hash": manifest["expected_grid_hash"],
                "target_trace_hash": manifest["expected_target_hashes"][row["case"]],
                "status": "COMPLETE",
                "origin": "NEW",
            }
        )
    return results


def test_full_synthetic_56_result_export_and_zip(tmp_path, inputs):
    manifest = prepared(tmp_path, inputs)
    results = synthetic_results(manifest)
    # Explicit synthetic CSV fixtures. No generator, simulator or external process is called.
    for result in results:
        cell = tmp_path / "cells" / result["cell_id"]
        cell.mkdir()
        pd.DataFrame(
            [
                {"job_type_id": i, "unfinished": 200 + i, "waiting_started_seconds_p90": 100 + i}
                for i in range(4)
            ]
        ).to_csv(cell / "per_job_run_summary.csv", index=False)
        pd.DataFrame([{"job_type_id": i, "Pj": result["Pj"][i]} for i in range(4)]).to_csv(
            cell / "qos_accounting.csv", index=False
        )
        pd.DataFrame(
            [{"job_type_id": i, "queue_after_policy_mean": 100 + i} for i in range(4)]
        ).to_csv(cell / "queue_summary.csv", index=False)
    archive = report.export(tmp_path, manifest, results, "COMPLETE")
    assert archive.is_file()
    assert len(pd.read_csv(tmp_path / "new_run_results.csv")) == 56
    assert len(pd.read_csv(tmp_path / "fixed_candidate_10seed_results.csv")) == 20
    assert len(pd.read_csv(tmp_path / "factorization_10x3_results.csv")) == 60
    assert len(pd.read_csv(tmp_path / "initial_job_table_hashes.csv")) == 75
    assert len(pd.read_csv(tmp_path / "per_job_run_summary.csv")) == 296
    assert len(list((tmp_path / "plots").glob("*.png"))) == 5
    effects = pd.read_csv(tmp_path / "factorization_descriptive_effects.csv")
    assert (effects.arrival_rows == 10).all() and (effects.runtime_columns == 3).all()
    text = (tmp_path / "report.md").read_text()
    assert "of the 10 tested fresh scenarios" in text and "Phase 3 has NOT been started" in text


def test_resume_reuses_all_valid_cells_without_launching(tmp_path, inputs, monkeypatch):
    manifest = prepared(tmp_path, inputs)
    manifest = deepcopy(manifest)
    results = synthetic_results(manifest)
    for case in manifest["specification"]["cases"]:
        case["initial_references"] = [
            {
                "seed": seed,
                "initial_job_table_hash": f"table{seed}",
                "arrival_hash": f"arrival{seed}",
            }
            for seed in manifest["configuration"]["new_seeds"]
        ]
    indexed = {r["cell_id"]: r for r in results}
    monkeypatch.setattr(sc.pilot, "completed_cell", lambda output, name, fingerprint: indexed[name])
    monkeypatch.setattr(
        sc.subprocess, "run", lambda *args, **kwargs: pytest.fail("Sealed run was rescheduled")
    )
    captured = []
    monkeypatch.setattr(report, "export", lambda *args, **kwargs: captured.append(args))
    sc.execute(ROOT, tmp_path, manifest, 10)
    assert len(captured) == 1 and captured[0][3] == "COMPLETE" and len(captured[0][2]) == 56


def test_prepare_and_resume_initial_references_with_tiny_mock_tables(tmp_path, inputs, monkeypatch):
    from types import SimpleNamespace

    manifest = prepared(tmp_path, inputs)
    calls = []

    def generate(root, spec, case, seed, require_reference):
        assert not require_reference
        calls.append((case["case"], seed))
        table = np.zeros((10, 8))
        table[0] = np.arange(8)
        table[1] = [0, 1, 2, 3, 0, 1, 2, 3]
        table[2] = [0, 0, 0, 0, seed % 100 + 1, seed % 100 + 2, seed % 100 + 3, seed % 100 + 4]
        table[3:5] = -1
        table[6] = table[2]
        table[8] = [25, 28, 36, 44] * 2
        table[9] = 3.5 if case["case"] == "c005" else 5
        trace = pd.DataFrame(
            {
                "job_id": table[0].astype(int),
                "job_type_id": table[1].astype(int),
                "submit_time": table[2].astype(int),
                "is_prefill": np.arange(8) < 4,
            }
        )
        return (
            SimpleNamespace(generate_arrival_rates=lambda e, j: [1.0] * 4),
            None,
            SimpleNamespace(all_jobs=dict(enumerate(["Resnet", "GPT2", "Llama", "Bloom"]))),
            trace,
            table,
            4,
        )

    monkeypatch.setattr(sc, "create_initial", generate)
    manifest = sc.prepare_new_arrivals(ROOT, tmp_path, manifest)
    assert len(calls) == 14 and len(set(calls)) == 14
    assert all(len(c["initial_references"]) == 10 for c in manifest["specification"]["cases"])
    assert (tmp_path / "arrival_diagnostics.csv").is_file()
    monkeypatch.setattr(
        sc,
        "create_initial",
        lambda *a, **kw: pytest.fail("Prepared arrivals regenerated on resume"),
    )
    sc.prepare_new_arrivals(ROOT, tmp_path, manifest)
    (tmp_path / "arrival_diagnostics.csv").write_text("corrupt")
    with pytest.raises(ValueError, match="Prepared initial file changed"):
        sc.prepare_new_arrivals(ROOT, tmp_path, manifest)
