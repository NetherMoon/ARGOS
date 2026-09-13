import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from argos.provenance import ARTIFACT
from argos.surrogate.v3_adapter import V3Adapter

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    not (ROOT / ARTIFACT).is_dir() or not (ROOT / ".deps/CONDOR-FLEXDC").is_dir(),
    reason="Immutable V3 artifact and pinned dependency required",
)


def test_real_checkpoint_prediction_and_snapshot_parity():
    a = V3Adapter(ROOT)
    w, e = a.context(
        ROOT / ".deps/FlexDC/configs/workload/W1-train-qos3333.ini",
        ROOT
        / ".deps/FlexDC/configs/experiment/new_iso/traditional_signal/generated_server_counts/exp_traditional_iso16_servers_1000.ini",
        1000,
        0.6,
        20,
    )
    rows = json.loads((ROOT / "tests/fixtures/known_v3_predictions.json").read_text())
    for row in rows[:3]:
        p = a.predict(w, e, row["Pbar"], row["R"], row["weights"])
        for key, expected in row["expected"].items():
            np.testing.assert_allclose(p[key], expected, rtol=5e-4, atol=1e-4)
    settings = a.api.OptimizationSettings(
        starts=4, iterations=4, random_seed=37, weight_min=0.15, weight_max=0.45, r_over_p_max=0.6
    )
    original, _, _ = a.optimize(
        workload=w, experiment=e, settings=settings, snapshot_every=2, capture=False
    )
    captured, snapshots, _ = a.optimize(
        workload=w, experiment=e, settings=settings, snapshot_every=2
    )
    pd.testing.assert_frame_equal(original, captured, check_exact=True)
    assert set(snapshots.Iteration) == {0, 2, 4}
    assert len(snapshots) == 12


@pytest.mark.parametrize("j", [3, 4, 5, 6, 8])
def test_relative_bounds_intersect_upstream(j):
    from dataclasses import replace

    from argos.config import Config

    adapter = V3Adapter(ROOT)
    config = replace(Config(), weight_policy="relative_to_equal")
    lo, hi = config.weight_bounds(j)
    settings = adapter.api.OptimizationSettings(weight_min=lo, weight_max=hi)
    bounds = adapter.api.resolve_effective_weight_bounds(settings, job_count=j, server_count=1000)
    assert bounds.final_lower >= max(lo, 1 / 1000)
    assert bounds.final_upper <= hi


def test_cuda_prediction_if_available():
    import torch

    if not torch.cuda.is_available():
        pytest.skip("CUDA unavailable; CPU parity is the release authority")
    cpu = V3Adapter(ROOT, device="cpu")
    gpu = V3Adapter(ROOT, device="cuda")
    from argos.config import Config

    config = Config()
    w, e = cpu.context(
        ROOT / ".deps/FlexDC" / config.workload,
        ROOT / ".deps/FlexDC" / config.experiment,
        1000,
        0.6,
        20,
    )
    a = cpu.predict(w, e, 0.4, 0.1, [0.25] * 4)
    b = gpu.predict(w, e, 0.4, 0.1, [0.25] * 4)
    for key in [
        "Predicted_P90_Tracking",
        "Predicted_QoS_Probabilities",
        "Predicted_Full_Objective",
    ]:
        np.testing.assert_allclose(a[key], b[key], rtol=5e-4, atol=1e-4)
