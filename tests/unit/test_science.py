from dataclasses import asdict, replace

import numpy as np
import pytest

from argos.config import Config
from argos.contracts import Costs, feasible, rank, violations
from argos.search.candidates import Domain
from argos.search.regions import extract_regions, promising
from argos.types import Candidate, Metrics, candidate_from_dict


def domain():
    return Domain(0.18, 0.76, 0.912, 0.01, 0.6, (0.15,) * 4, (0.45,) * 4)


def test_joint_feasibility_and_invalid_evidence():
    assert feasible(Metrics(0.1, 0.3, (0.1, 0.1, 0.1, 0.1), 100))
    assert not feasible(Metrics(0.1, 0.3, (0.0, 0.0, 0.0, 0.10001), 1))
    assert not feasible(Metrics(0.1, 0.30001, (0.0,) * 4, 1))
    with pytest.raises(ValueError):
        feasible(Metrics(0.1, float("nan"), (0.1,), 100))
    with pytest.raises(ValueError):
        feasible(Metrics(0.1, 0.2, (), 100))
    assert rank(Metrics(0.1, 0.2, (0.05,) * 4, 200)) < rank(Metrics(0.1, 0.31, (0.05,) * 4, 1))
    assert violations(Metrics(0.1, 0.6, (0.2, 0.3), 1)) == pytest.approx((2.0, 4.0))


def test_objective_stability():
    costs = Costs(1, 10, 0.3, 20, 2, 0.1)
    assert costs.objective(10, 0.3, (0.1, 0.1)) == pytest.approx(10 + 41 * np.log(2))
    assert np.isfinite(costs.objective(10, 1e5, (1.0,)))
    with pytest.raises(ValueError):
        costs.objective(10, 0.2, (float("nan"),))


def test_sampling_geometry_and_projection():
    d = domain()
    rng = np.random.default_rng(43)
    a = d.independent(rng, "a")
    assert d.independent(np.random.default_rng(43), "a") == a
    for i in range(300):
        c = d.independent(rng, str(i))
        d.validate(c)
        local = d.local(c, rng, 0.12, "l")
        d.validate(local)
        assert abs(sum(local.weights) - 1) < 1e-12
        assert d.distance(c, c) == 0
    zero = d.local(a, rng, 0, "z")
    assert d.distance(a, zero) < 1e-12
    projected = d.project(np.array([100.0, -100.0, 0.25, 0.25]))
    assert sum(projected) == pytest.approx(1, abs=1e-12)
    assert min(projected) >= 0.15 and max(projected) <= 0.45
    with pytest.raises(ValueError):
        replace(d, lower=(0.3,) * 4)
    with pytest.raises(ValueError):
        replace(d, upper=(0.2,) * 4)
    with pytest.raises(ValueError):
        d.validate(replace(a, R=0.6 * a.Pbar + 0.01))
    assert candidate_from_dict(asdict(a)) == a


def test_weight_identity_matters():
    d = domain()
    a = Candidate("a", 0.4, 0.1, (0.15, 0.45, 0.2, 0.2), "test")
    b = replace(a, weights=(0.45, 0.15, 0.2, 0.2))
    assert d.distance(a, b) > 0


def test_regions_preserve_tradeoffs_and_dedupe():
    d = domain()
    a = Candidate(
        "a",
        0.3,
        0.05,
        (0.25,) * 4,
        "test",
        iteration=0,
        prediction=Metrics(0.1, 0.29, (0.09,) * 4, 10),
    )
    b = replace(a, candidate_id="b", Pbar=0.7, prediction=Metrics(0.1, 0.1, (0.01,) * 4, 100))
    duplicate = replace(a, candidate_id="duplicate")
    pool = promising([a, b, duplicate], 3)
    unique, regions = extract_regions(pool, d, 6, 0.1, 0.001)
    assert len(unique) == 2 and len(regions) == 2
    assert extract_regions(pool, d, 6, 0.1, 0.001) == (unique, regions)


def test_config_rejects_budget_and_seed_errors(tmp_path):
    for config in [
        replace(Config(), max_search_calls=0),
        replace(Config(), confirmation_seeds=(20,)),
        replace(Config(), confirmation_seeds=(4, 4)),
        replace(Config(), local_radius=float("nan")),
    ]:
        with pytest.raises(ValueError):
            config.validate()
    path = tmp_path / "config.yaml"
    Config().save(path)
    assert Config.load(path) == Config()
