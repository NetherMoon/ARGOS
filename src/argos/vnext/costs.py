"""Pinned analytical objective, reconstructed from predicted behavior outputs."""

from argos.contracts import Costs


def objective(candidate, behavior):
    # Same continuous kW convention as the pinned V3 inference routine. Actual
    # simulator objectives remain authoritative and use integer-watt allocations.
    monetary = 0.1 * 1000 * (candidate.Pbar - candidate.R + candidate.R * behavior[0])
    return Costs(1, 10, 0.3, 20, 2, 0.1).objective(
        monetary, float(behavior[1]), tuple(behavior[2:])
    )
