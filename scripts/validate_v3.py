"""Reproduce saved predictions from original deterministic plan inputs."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from argos.provenance import ARTIFACT, CHECKPOINT, sha256, write_json
from argos.surrogate.v3_adapter import V3Adapter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root
    adapter = V3Adapter(root)
    api = adapter.api
    plan = pd.read_csv(root / "runs/audit/known_plan.csv")
    saved = pd.read_csv(root / ARTIFACT / CHECKPOINT.replace(".pt", "_test_predictions.csv"))
    merged = plan.merge(saved, left_on="plan_row_id", right_on="Plan_Row_ID")
    if len(merged) < 32:
        raise ValueError("Insufficient original plan rows for saved prediction parity")
    print("Plan columns", list(plan.columns), flush=True)
    workload, experiment = adapter.context(
        root / ".deps/FlexDC/configs/workload/W1-train-qos3333.ini",
        root
        / ".deps/FlexDC/configs/experiment/new_iso/traditional_signal/generated_server_counts/exp_traditional_iso16_servers_1000.ini",
        1000,
        0.6,
        20,
    )
    errors = []
    fixture = []
    sample = merged.iloc[np.linspace(0, len(merged) - 1, 32, dtype=int)]
    for _, row in sample.iterrows():
        weights = json.loads(row["weights"])
        p, r = float(row["Pbar_kw_per_server"]), float(row["R_kw_per_server"])
        prediction = adapter.predict(workload, experiment, p, r, weights)
        cols = [
            "Predicted_Mean_Tracking",
            "Predicted_P90_Tracking",
            "Predicted_Max_Pj",
            "Predicted_M_RSR",
            "Predicted_Full_Objective",
        ]
        observed = np.array([prediction[c] for c in cols])
        expected = np.array([row[c] for c in cols])
        np.testing.assert_allclose(observed, expected, rtol=5e-4, atol=1e-4)
        errors.append(dict(zip(cols, abs(observed - expected).tolist())))
        fixture.append(
            {
                "plan_row_id": row["plan_row_id"],
                "Pbar": p,
                "R": r,
                "weights": weights,
                "expected": dict(zip(cols, expected.tolist())),
            }
        )
    settings = api.OptimizationSettings(
        starts=8, iterations=20, random_seed=37, weight_min=0.15, weight_max=0.45, r_over_p_max=0.6
    )
    original, _, _ = adapter.optimize(
        workload=workload, experiment=experiment, settings=settings, snapshot_every=5, capture=False
    )
    captured, snapshots, _ = adapter.optimize(
        workload=workload, experiment=experiment, settings=settings, snapshot_every=5
    )
    pd.testing.assert_frame_equal(original, captured, check_exact=True)
    # Autograd against central finite differences on physical P, R and simplex tangent.
    x = torch.tensor([0.45, 0.12, 0.25, 0.25, 0.25, 0.25], dtype=torch.float32, requires_grad=True)

    def objective(z):
        g, t, m = api.build_differentiable_features(
            pbar=z[:1],
            reserve=z[1:2],
            weights=z[2:].unsqueeze(0),
            workload=workload,
            experiment=experiment,
            metadata=adapter.loaded.metadata,
        )
        out = adapter.loaded.model(g, t, m)
        return api.reconstruct_differentiable_outputs(
            loaded=adapter.loaded,
            pbar=z[:1],
            reserve=z[1:2],
            model_output=out,
            experiment=experiment,
        )["objective"].sum()

    gradient = torch.autograd.grad(objective(x), x)[0]
    checks = []
    for direction in [
        torch.tensor([1.0, 0, 0, 0, 0, 0]),
        torch.tensor([0.0, 1, 0, 0, 0, 0]),
        torch.tensor([0.0, 0, 1, -1, 0, 0]),
    ]:
        h = 1e-3
        finite = float(
            (objective(x.detach() + h * direction) - objective(x.detach() - h * direction))
            / (2 * h)
        )
        exact = float(gradient @ direction)
        np.testing.assert_allclose(finite, exact, rtol=0.04, atol=0.05)
        checks.append({"autograd": exact, "finite_difference": finite})
    write_json(root / "tests/fixtures/known_v3_predictions.json", fixture)
    report = {
        "status": "PASS",
        "checkpoint_sha256": sha256(root / ARTIFACT / CHECKPOINT),
        "epoch": adapter.loaded.checkpoint["epoch"],
        "saved_prediction_rows": len(errors),
        "absolute_errors": errors,
        "prediction_tolerance": {"rtol": 5e-4, "atol": 1e-4},
        "endpoint_parity": "bitwise identical DataFrames",
        "optimizer_settings": asdict(settings),
        "snapshots": len(snapshots),
        "iterations_saved": sorted(snapshots.Iteration.unique().tolist()),
        "gradient_checks": checks,
        "architecture": "immutable artifact-bundled source",
        "inference": "pinned generic inference with artifact import bindings",
    }
    write_json(root / "reports/v3_parity.json", report)
    snapshots.to_csv(root / "runs/audit/parity_snapshots.csv", index=False)
    print("V3 parity PASS", flush=True)


if __name__ == "__main__":
    main()
