"""Reproduce the pinned V3 contract failure; exit 1 on illegal weights.

This diagnostic changes no optimizer source and performs no FlexDC evaluations.
Run with the pinned paper Python from the ARGOS repository.
"""

import json
from pathlib import Path

import torch

from argos.surrogate.v3_adapter import V3Adapter


def main():
    root = Path(__file__).resolve().parents[2]
    adapter = V3Adapter(root, threads=4, device="cpu")
    logits = torch.tensor(
        [
            [-4.956484794616699, 3.278822898864746, -5.34633207321167, 2.506721258163452],
            [10.0, 10.0, -10.0, -10.0],
            [20.0, 20.0, -20.0, -20.0],
        ],
        dtype=torch.float32,
    )
    weights = adapter.api.parameterize_weights(logits, 0.15, 0.45)
    sums = weights.double().sum(dim=1)
    legal = (
        torch.isfinite(weights).all(dim=1)
        & ((sums - 1.0).abs() <= 1e-6)
        & (weights >= 0.15 - 1e-6).all(dim=1)
        & (weights <= 0.45 + 1e-6).all(dim=1)
    )
    print(
        json.dumps(
            {
                "logits": logits.tolist(),
                "weights": weights.tolist(),
                "sums": sums.tolist(),
                "legal_rows": legal.tolist(),
                "simulator_calls": 0,
            },
            indent=2,
        )
    )
    return 0 if bool(legal.all()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
