"""Reject mismatched or incomplete evidence; independently reconstruct objective."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from argos.config import Config
from argos.contracts import Costs, validate_metrics
from argos.types import Candidate, Metrics


def parse_output(
    results: Path,
    diagnostics: Path,
    candidate: Candidate,
    config: Config,
    seed: int,
    execution_id: str,
    context_id: str,
    workload: Path,
    costs: Costs,
) -> tuple[Metrics, dict]:
    frames = [pd.read_csv(results), pd.read_csv(diagnostics)]
    if any(len(f) != 1 for f in frames):
        raise ValueError("Expected exactly one result and one diagnostic row")
    raw, diag = (f.iloc[0] for f in frames)
    for row in (raw, diag):
        exact = {
            "Plan_Row_ID": execution_id,
            "Context_ID": context_id,
            "Workload_Name": workload.stem,
        }
        for key, value in exact.items():
            if str(row[key]) != value:
                raise ValueError(f"Reported {key} mismatch")
        if Path(str(row["Workload_Config"])).resolve() != workload.resolve():
            raise ValueError("Workload config path mismatch")
        numbers = {
            "Pbar_kw_per_server": candidate.Pbar,
            "R_kw_per_server": candidate.R,
            "server_count": config.server_count,
            "utilization": config.utilization,
            "Simulation_Seed": seed,
        }
        for key, value in numbers.items():
            if not np.isfinite(float(row[key])) or not np.isclose(
                float(row[key]), value, rtol=1e-9, atol=1e-9
            ):
                raise ValueError(f"Reported {key} mismatch")
    if raw["Policy_Name"] != config.policy or str(raw["Node_Count_Control"]).lower() != "true":
        raise ValueError("Policy contract mismatch")
    if int(raw["workload_mix_size"]) != len(candidate.weights):
        raise ValueError("Job count mismatch")
    for j, w in enumerate(candidate.weights):
        if not np.isclose(raw[f"Weight_{j}"], w, rtol=1e-9, atol=1e-9):
            raise ValueError("Reported weight mismatch")
    for key, value in [("P_actual_watts", candidate.Pbar), ("R_actual_watts", candidate.R)]:
        if float(raw[key]) != round(value * 1000 * config.server_count):
            raise ValueError("Physical watt conversion mismatch")
    probs = tuple(float(x) for x in json.loads(raw["QoS_Delay_Probabilities"]))
    p90 = float(diag["Ctrack_Epsilon_90th"])
    objective = costs.objective(float(raw["Simulator_RSR_Total_Cost"]), p90, probs)
    if not np.isclose(
        objective, float(diag["Diagnostic_FullPaperObjective_Cost"]), rtol=1e-6, atol=1e-8
    ):
        raise ValueError("Reconstructed/logged objective mismatch")
    for key, value in [
        ("Ctrack_Gamma", costs.tracking_error_constraint),
        ("Ctrack_Mu", costs.psi2),
        ("Ctrack_Psi", costs.psi1),
    ]:
        if not np.isclose(float(diag[key]), value, rtol=0, atol=1e-12):
            raise ValueError(f"Logged cost constant mismatch: {key}")
    metrics = Metrics(float(raw["Mtrack_Error_MeanAbs_Normalized"]), p90, probs, objective)
    validate_metrics(metrics, len(candidate.weights))
    reported = {
        k: raw[k].item() if hasattr(raw[k], "item") else raw[k]
        for k in [
            "Plan_Row_ID",
            "Context_ID",
            "Workload_Name",
            "Workload_Config",
            "Pbar_kw_per_server",
            "R_kw_per_server",
            "P_actual_watts",
            "R_actual_watts",
            "server_count",
            "utilization",
            "Simulation_Seed",
            "Policy_Name",
            "workload_mix",
        ]
    }
    reported["weights"] = [float(raw[f"Weight_{j}"]) for j in range(len(candidate.weights))]
    return metrics, reported
