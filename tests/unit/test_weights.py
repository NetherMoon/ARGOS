"""Numerical contracts and independent finite-difference checks for corrected V3 weights."""

import pytest
import torch

from argos.surrogate.weights import parameterize_weights

BAD = [-4.956484794616699, 3.278822898864746, -5.34633207321167, 2.506721258163452]


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
@pytest.mark.parametrize("j", [3, 4, 5, 6, 8])
def test_legal_weights_across_supported_jobs_and_extreme_logits(dtype, j):
    generator = torch.Generator().manual_seed(197)
    inputs = torch.cat(
        [torch.randn(64, j, generator=generator, dtype=dtype) * s for s in [1, 10, 1000]]
    )
    lo, hi = 0.6 / j, 1.8 / j
    weights = parameterize_weights(inputs, lo, hi)
    assert weights.dtype == dtype
    assert torch.isfinite(weights).all()
    torch.testing.assert_close(
        weights.double().sum(1), torch.ones(len(inputs), dtype=torch.float64), atol=1e-6, rtol=0
    )
    assert (weights >= lo - 1e-7).all() and (weights <= hi + 1e-7).all()


def test_actual_failure_and_saturated_reproductions_are_legal():
    logits = torch.tensor([BAD, [10, 10, -10, -10], [20, 20, -20, -20]], dtype=torch.float64)
    weights = parameterize_weights(logits, 0.15, 0.45)
    torch.testing.assert_close(
        weights.sum(1), torch.ones(3, dtype=torch.float64), atol=1e-12, rtol=0
    )
    assert (weights >= 0.15).all() and (weights <= 0.45).all()


@pytest.mark.parametrize("j", [3, 4, 5, 6, 8])
def test_implicit_gradient_matches_finite_differences(j):
    logits = torch.linspace(-3, 3, j, dtype=torch.float64).reshape(1, j).requires_grad_()
    assert torch.autograd.gradcheck(
        lambda x: parameterize_weights(x, 0.6 / j, 1.8 / j), (logits,), atol=1e-6, rtol=1e-4
    )


def test_actual_failure_gradient_matches_finite_differences():
    logits = torch.tensor([BAD], dtype=torch.float64, requires_grad=True)
    assert torch.autograd.gradcheck(
        lambda x: parameterize_weights(x, 0.15, 0.45), (logits,), atol=1e-6, rtol=1e-4
    )


def test_shift_permutation_and_zero_sum_gradient():
    logits = torch.tensor([BAD], dtype=torch.float64, requires_grad=True)
    weights = parameterize_weights(logits, 0.15, 0.45)
    permutation = [3, 1, 0, 2]
    torch.testing.assert_close(
        parameterize_weights(logits + 100, 0.15, 0.45), weights, atol=1e-12, rtol=0
    )
    torch.testing.assert_close(
        parameterize_weights(logits[:, permutation], 0.15, 0.45),
        weights[:, permutation],
        atol=1e-12,
        rtol=0,
    )
    gradient = torch.autograd.grad((weights * torch.tensor([[1, 2, 3, 4]])).sum(), logits)[0]
    assert torch.isfinite(gradient).all() and gradient.abs().max() > 0
    assert abs(gradient.sum()) < 1e-12
    sum_gradient = torch.autograd.grad(parameterize_weights(logits, 0.15, 0.45).sum(), logits)[0]
    torch.testing.assert_close(sum_gradient, torch.zeros_like(logits), atol=1e-12, rtol=0)


@pytest.mark.parametrize("bounds", [(0, None), (0.1, 1), (0.25, 0.45), (0.1, 0.25)])
def test_affine_and_singleton_simplex_branches(bounds):
    logits = torch.tensor([BAD], dtype=torch.float64, requires_grad=True)
    w = parameterize_weights(logits, *bounds)
    torch.testing.assert_close(w.sum(1), torch.ones(1, dtype=torch.float64), atol=1e-12, rtol=0)
    assert torch.isfinite(torch.autograd.grad(w.sum(), logits)[0]).all()


@pytest.mark.parametrize("bounds", [(-0.1, 0.5), (0.3, 0.5), (0, 0.2), (0.5, 0.4)])
def test_infeasible_bounds_rejected(bounds):
    with pytest.raises(ValueError):
        parameterize_weights(torch.zeros(1, 4), *bounds)


def test_nonfinite_rejected():
    with pytest.raises(ValueError, match="Non-finite"):
        parameterize_weights(torch.tensor([[float("nan"), 0, 0, 0]]), 0.15, 0.45)
