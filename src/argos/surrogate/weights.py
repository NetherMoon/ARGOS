"""Convergent bounded logistic simplex with its implicit first derivative.

This replaces only the faulty scalar solve in the pinned V3 weight transform.
It does not project an optimized candidate or change the model or objective.
"""

import math

import torch
from torch.autograd.function import once_differentiable

WEIGHT_PARAMETERIZATION = "bounded_logistic_bisection_implicit_v1"


class _BoundedLogistic(torch.autograd.Function):
    @staticmethod
    def forward(ctx, logits, lower, upper):
        work = logits.double()
        scale = upper - lower
        count = work.shape[1]
        # At this common sigmoid probability the row sum is exactly one.
        target = (1.0 - count * lower) / (scale * count)
        offset = math.log(target) - math.log1p(-target)
        left = offset - work.amax(dim=1, keepdim=True)
        right = offset - work.amin(dim=1, keepdim=True)
        for _ in range(80):
            middle = left * 0.5 + right * 0.5
            total = lower * count + scale * torch.sigmoid(work + middle).sum(dim=1, keepdim=True)
            below = total < 1.0
            left = torch.where(below, middle, left)
            right = torch.where(below, right, middle)
        sig = torch.sigmoid(work + (left * 0.5 + right * 0.5))
        weights = (lower + scale * sig).to(logits.dtype)
        if not bool(torch.isfinite(weights).all()) or not bool(
            ((weights.double().sum(dim=1) - 1.0).abs() <= 1e-6).all()
        ):
            raise ValueError("Bounded logistic solve failed its weight contract")
        ctx.save_for_backward(scale * sig * (1.0 - sig))
        ctx.input_dtype = logits.dtype
        return weights

    @staticmethod
    @once_differentiable
    def backward(ctx, gradient):
        (slope,) = ctx.saved_tensors
        denominator = slope.sum(dim=1, keepdim=True)
        # dw_i/dz_j = d_i * (delta_ij - d_j / sum(d)).
        # A numerically fully saturated row is locally constant.
        safe_denominator = torch.where(denominator > 0, denominator, 1.0)
        g = gradient.double()
        average = (g * slope).sum(dim=1, keepdim=True) / safe_denominator
        return (slope * (g - average)).to(ctx.input_dtype), None, None


def parameterize_weights(logits, weight_min, weight_max=None):
    """Return legal weights for finite float32/float64 logits and feasible bounds."""
    if logits.ndim != 2 or logits.shape[1] == 0:
        raise ValueError("Logits must be a nonempty-width matrix")
    if logits.dtype not in (torch.float32, torch.float64):
        raise ValueError("Weight parameterization supports float32 and float64")
    if not bool(torch.isfinite(logits).all()):
        raise ValueError("Non-finite weight logits")
    lower = float(weight_min or 0.0)
    upper = float(1.0 if weight_max is None else weight_max)
    count = logits.shape[1]
    if not math.isfinite(lower) or not math.isfinite(upper) or not 0 <= lower <= upper <= 1:
        raise ValueError("Invalid weight bounds")
    if count * lower > 1.0 or count * upper < 1.0:
        raise ValueError("Infeasible weight bounds")
    if count * lower == 1.0 or count * upper == 1.0:
        return logits * 0.0 + 1.0 / count
    if upper >= 1.0 - (count - 1) * lower - 1e-12:
        return lower + (1.0 - count * lower) * torch.softmax(logits, dim=-1)
    return _BoundedLogistic.apply(logits, lower, upper)
