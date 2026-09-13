import json
from pathlib import Path

import pandas as pd
import pytest

from argos.config import Config
from argos.contracts import Costs
from argos.simulator.output_parser import parse_output
from argos.types import candidate_from_dict

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def inputs(tmp_path):
    fixture = json.loads((FIXTURES / "flexdc_observation.json").read_text())
    workload = tmp_path / "W1-train-qos3333.ini"
    mix = json.loads(pd.read_csv(FIXTURES / "flexdc_results.csv").iloc[0]["workload_mix"])
    fields = [
        "min_job_power_watts",
        "max_job_power_watts",
        "min_time_seconds",
        "max_time_seconds",
        "qos_constraint",
        "job_size",
    ]
    workload.write_text(
        "\n".join(
            f"[job{i}]\n" + "\n".join(f"{k}={v}" for k, v in zip(fields, values))
            for i, values in enumerate(mix)
        )
    )
    files = []
    for kind in ["results", "diagnostics"]:
        frame = pd.read_csv(FIXTURES / f"flexdc_{kind}.csv")
        frame["Workload_Config"] = str(workload)
        p = tmp_path / f"{kind}.csv"
        frame.to_csv(p, index=False)
        files.append(p)
    args = [
        *files,
        candidate_from_dict(fixture["candidate"]),
        Config(),
        fixture["seed"],
        fixture["execution_id"],
        fixture["context_id"],
        workload,
        Costs(1, 10, 0.3, 20, 2, 0.1),
    ]
    return args, fixture


def test_real_one_row_fixture(tmp_path):
    args, fixture = inputs(tmp_path)
    metrics, reported = parse_output(*args)
    assert metrics.objective == pytest.approx(fixture["metrics"]["objective"])
    assert metrics.p90 == pytest.approx(fixture["metrics"]["p90"])
    assert reported["weights"] == pytest.approx(args[2].weights)


@pytest.mark.parametrize(
    "file_index,column,value",
    [
        (0, "Simulation_Seed", 99),
        (0, "Pbar_kw_per_server", 0.9),
        (0, "Weight_0", 0.9),
        (0, "QoS_Delay_Probabilities", "[0, 0]"),
        (0, "QoS_Delay_Probabilities", "[0, 0, 0, NaN]"),
        (1, "Ctrack_Epsilon_90th", float("nan")),
        (1, "Diagnostic_FullPaperObjective_Cost", 1),
    ],
)
def test_rejects_bad_evidence(tmp_path, file_index, column, value):
    args, _ = inputs(tmp_path)
    path = args[file_index]
    frame = pd.read_csv(path)
    frame[column] = value
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError):
        parse_output(*args)


def test_rejects_cartesian_rows(tmp_path):
    args, _ = inputs(tmp_path)
    frame = pd.read_csv(args[0])
    pd.concat([frame, frame]).to_csv(args[0], index=False)
    with pytest.raises(ValueError, match="exactly one"):
        parse_output(*args)
