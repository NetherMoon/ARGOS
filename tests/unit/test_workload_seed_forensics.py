"""Arrival math and pinned-generator controls; no simulator executions."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from argos.diagnostics.workload_seed_forensics import (
    arrival_hash,
    generate,
    interarrival_stats,
    load_generator,
    max_window,
    safe_path,
    summarize,
    table_hash,
    validate_lineage,
)

ROOT = Path(__file__).resolve().parents[2]


def test_sliding_windows_match_brute_force():
    counts = np.array([4, 0, 2, 8, 0, 3, 1])
    for width in [1, 2, 3, 10]:
        assert max_window(counts, width) == max(
            sum(counts[i : i + width]) for i in range(len(counts))
        )


def test_rounding_ties_and_population_gap_statistics():
    result = interarrival_stats([0, 0, 2, 4])
    assert result["mean"] == pytest.approx(4 / 3)
    assert result["median"] == 2
    assert result["std"] == pytest.approx(np.std([0, 2, 2]))
    assert interarrival_stats([1])["mean"] is None
    assert interarrival_stats([0, 0])["cv"] is None


def test_prefill_poisson_expectation_endpoint_and_bins():
    trace = pd.DataFrame(
        {
            "job_id": range(5),
            "job_type_id": [0] * 5,
            "submit_time": [0, 0, 1, 3, 4],
            "is_prefill": [True, True, False, False, False],
        }
    )
    rows, bins = summarize(trace, "toy", 1, [0.5], 4, 2, {0: "Bloom"})
    row = rows[0]
    assert row["total_count"] == 5 and row["poisson_count"] == 3
    assert row["expected_poisson_count"] == 2 and row["expected_total_count"] == 4
    assert row["poisson_count_z"] == pytest.approx(1 / np.sqrt(2))
    assert row["poisson_rounded_to_duration"] == 1
    assert bins[1][-1]["bin_start"] == 4 and bins[1][-1]["count"] == 1
    for width in bins:
        assert sum(b["count"] for b in bins[width]) == 5
        assert sum(b["poisson_count"] for b in bins[width]) == 3


def test_hash_ignores_dataframe_row_order_but_preserves_job_identity():
    trace = pd.DataFrame({"job_id": [0, 1], "job_type_id": [0, 1], "submit_time": [0, 2]})
    assert arrival_hash(trace) == arrival_hash(trace.iloc[::-1])
    changed = trace.copy()
    changed.loc[1, "submit_time"] = 3
    assert arrival_hash(trace) != arrival_hash(changed)


def test_real_pinned_generator_tiny_reproducibility_and_qos_independence():
    tables, _, _ = load_generator(ROOT)
    exp = SimpleNamespace(
        server_count=8,
        utilization=0.6,
        simulation_duration=5,
        workload_trace="poisson",
        random_seed=27,
    )
    jobs = SimpleNamespace(
        all_jobs={0: "a", 1: "b"},
        all_job_size={0: 1, 1: 1},
        all_min_execution_time={0: 1.0, 1: 2.0},
        all_job_qos_constraints={0: 3.0, 1: 4.0},
    )

    # Mirror the read-only random_seed property used by the real parser.
    class Experiment:
        server_count = exp.server_count
        utilization = exp.utilization
        simulation_duration = exp.simulation_duration
        workload_trace = exp.workload_trace

        @property
        def random_seed(self):
            return self._random_seed

    experiment = Experiment()
    first, table, _ = generate(tables, experiment, jobs, 27)
    repeat, same, _ = generate(tables, experiment, jobs, 27)
    assert arrival_hash(first) == arrival_hash(repeat) and table_hash(table) == table_hash(same)
    jobs.all_job_qos_constraints = {0: 5.0, 1: 5.0}
    qos, different_table, _ = generate(tables, experiment, jobs, 27)
    assert arrival_hash(first) == arrival_hash(qos)
    assert table_hash(table) != table_hash(different_table)
    other, _, _ = generate(tables, experiment, jobs, 28)
    assert arrival_hash(first) != arrival_hash(other)


def test_paths_cannot_escape_or_read_environment(tmp_path):
    for name in ["../elsewhere", ".env", "folder/.env.secret"]:
        with pytest.raises(ValueError):
            safe_path(tmp_path, name)


def test_missing_lineage_fails_before_generation(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_lineage(tmp_path, tmp_path / "missing.json")


def test_recovered_history_preserves_full_precision_and_exact_candidates():
    _, history, missing = validate_lineage(
        ROOT, ROOT / "configs/diagnostics/w2_seed_forensics.json"
    )
    assert not missing
    assert len(history) == 10 and history.seed.nunique() == 10
    c007 = history[history["case"] == "c007"]
    assert all(c007.Pbar == 0.47039860486984253)
    assert all(c007.R == 0.06610638229846953)
    assert history[history.phase == "fresh_confirmation"].groupby(
        "case"
    ).evidence_qualified_pass.sum().to_dict() == {"c005": 1, "c007": 0}
