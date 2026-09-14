"""Frozen V3 scenario invariance and original selection regressions."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from argos.config import Config
from argos.provenance import ARTIFACT
from argos.surrogate.v3_adapter import V3Adapter

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    not (ROOT / ARTIFACT).is_dir() or not (ROOT / ".deps/CONDOR-FLEXDC").is_dir(),
    reason="Pinned artifact required",
)


def test_scenario_seed_invariance_features_predictions_and_search():
    a = V3Adapter(ROOT)
    c = Config()
    w, e = a.context(
        ROOT / ".deps/FlexDC" / c.workload, ROOT / ".deps/FlexDC" / c.experiment, 1000, 0.6, 20
    )
    other = replace(e, random_seed=21)
    features = []
    differentiable = []
    predictions = []
    searches = []
    settings = a.api.OptimizationSettings(
        starts=4, iterations=4, random_seed=37, weight_min=0.15, weight_max=0.45, r_over_p_max=0.6
    )
    for experiment in [e, other]:
        features.append(
            a.api.make_feature_row(
                pbar_kw_per_server=0.4,
                r_kw_per_server=0.1,
                weights=[0.25] * 4,
                workload=w,
                experiment=experiment,
            )
        )
        differentiable.append(
            a.api.build_differentiable_features(
                pbar=torch.tensor([0.4]),
                reserve=torch.tensor([0.1]),
                weights=torch.tensor([[0.25] * 4]),
                workload=w,
                experiment=experiment,
                metadata=a.loaded.metadata,
            )
        )
        predictions.append(a.predict(w, experiment, 0.4, 0.1, [0.25] * 4))
        searches.append(
            a.optimize(workload=w, experiment=experiment, settings=settings, snapshot_every=2)
        )
    pd.testing.assert_series_equal(features[0][0], features[1][0], check_exact=True)
    for i in [1, 2]:
        np.testing.assert_array_equal(features[0][i], features[1][i])
    assert features[0][3] == features[1][3]
    for x, y in zip(*differentiable):
        torch.testing.assert_close(x, y, rtol=0, atol=0)
    for key in [
        "Predicted_Mean_Tracking",
        "Predicted_P90_Tracking",
        "Predicted_QoS_Probabilities",
        "Predicted_Full_Objective",
    ]:
        np.testing.assert_array_equal(predictions[0][key], predictions[1][key])
    for x, y in zip(*searches):
        pd.testing.assert_frame_equal(x, y, check_exact=True)


def test_corrected_optimizer_survives_original_failing_snapshot():
    from argos.campaign.candidate_bank import setup
    from argos.search.regions import from_snapshot

    a = V3Adapter(ROOT)
    c = replace(Config(), starts=512, iterations=200, candidate_seed=300001)
    w, e, settings, _, domain, _ = setup(a, ROOT, c)
    endpoints, snapshots, _ = a.optimize(
        workload=w, experiment=e, settings=settings, snapshot_every=50
    )
    assert len(snapshots) == 512 * 5
    assert 150 in set(snapshots.Iteration)
    for row in snapshots.to_dict("records") + endpoints.to_dict("records"):
        domain.validate(
            from_snapshot(
                dict(row, Iteration=row.get("Iteration", settings.iterations)), settings.iterations
            )
        )
    # The pinned dependency stays untouched; the correction belongs to ARGOS.
    bad = torch.tensor(
        [[-4.956484794616699, 3.278822898864746, -5.34633207321167, 2.506721258163452]]
    )
    assert abs(float(a.api.parameterize_weights(bad, 0.15, 0.45).sum()) - 1) > 0.1
