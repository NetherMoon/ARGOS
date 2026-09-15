"""Mechanistic synthetic tests: no FlexDC processes or historical labels."""

from dataclasses import asdict, replace
from types import SimpleNamespace

import numpy as np
import pytest

from argos.config import Config
from argos.provenance import read_json
from argos.search.candidates import Domain
from argos.types import Candidate, FlexDCObservation, JobIdentity, Metrics, QoSEvidence, Region
from argos.vnext.controller import EliteController, NextController
from argos.vnext.correction import Correction, CorrectionSpec, behaviors, coordinates
from argos.vnext.mechanisms import (
    TrustRegion,
    protected_elites,
    robust_rank,
    scenario_status,
    targeted_probes,
)

D = Domain(0.18, 0.76, 0.912, 0.01, 0.6, (0.15,) * 4, (0.45,) * 4)
C = Candidate(
    "elite", 0.5, 0.12, (0.25,) * 4, "V3 endpoint", prediction=Metrics(0.1, 0.2, (0.02,) * 4, 80)
)


def observation(c=C, seed=100, p90=0.2, pj=(0.02,) * 4, phase="search", batch=1):
    m = Metrics(0.1, p90, tuple(pj), 80)
    evidence = tuple(
        QoSEvidence(
            JobIdentity(i, f"job{i}", (1, 2, 3, 4, 5, 1)),
            p,
            101,
            101,
            0,
            round(p * 100) + 1,
            round(p * 100),
            100,
        )
        for i, p in enumerate(pj)
    )
    return FlexDCObservation(
        c,
        seed,
        phase,
        batch,
        True,
        m,
        "PARSED",
        0.01,
        f"{c.candidate_id}-{seed}",
        qos_evidence=evidence,
    )


class Synthetic:
    def __init__(self, kind):
        self.kind = kind
        self.calls = {}
        self.interrupt = False

    def evaluate_batch(self, candidates, seed, phase, batch):
        out = []
        for c in candidates:
            key = (c.candidate_id, seed, phase, batch)
            if key not in self.calls:
                good = (
                    self.kind == "accurate"
                    or self.kind == "elite"
                    and c.candidate_id == "elite"
                    or self.kind == "fragile"
                    and seed == 100
                )
                self.calls[key] = observation(
                    c, seed, 0.2 if good else 0.6, phase=phase, batch=batch
                )
            out.append(self.calls[key])
            if self.interrupt:
                self.interrupt = False
                raise RuntimeError("synthetic crash after durable evaluation")
        return out


def setup(tmp_path, kind="accurate", variant="ERT"):
    config = replace(
        Config(), search_seed=100, candidate_seed=200, confirmation_seeds=(104, 105, 106)
    )
    bad = replace(C, candidate_id="medoid", Pbar=0.35)
    regions = [Region("one", bad, ("elite", "medoid"), tuple(D.encode(bad)), (1500,))]
    predict = lambda c: (
        c if c.prediction else replace(c, prediction=Metrics(0.1, 0.2, (0.02,) * 4, c.Pbar * 100))
    )
    sim = Synthetic(kind)
    controller = NextController(
        tmp_path,
        config,
        D,
        regions,
        sim,
        predict,
        [replace(C, source="protected_v3_elite")],
        (101, 102, 103),
        variant,
    )
    return controller, sim


def test_helmert_geometry_metric():
    rng = np.random.default_rng(9)
    cs = [D.independent(rng, str(i)) for i in range(20)]
    x = coordinates(D, cs)
    assert x.shape == (20, 5)
    for i in range(1, 20):
        assert np.linalg.norm(x[i] - x[0]) == pytest.approx(D.distance(cs[i], cs[0]), abs=1e-12)


def test_protected_compression_and_dedup(tmp_path):
    elites = protected_elites(
        C, [C, replace(C, candidate_id="dup"), replace(C, candidate_id="other", Pbar=0.7)], D
    )
    assert len(elites) == 2 and elites[0].candidate_id == "elite"
    assert elites[0].provenance["original_selection"]
    ctrl, _ = setup(tmp_path, "elite")
    batch = ctrl.propose()
    assert batch["entries"][0]["candidate"]["candidate_id"] == "elite"
    assert (
        len(
            {
                tuple(e["candidate"]["weights"]) + (e["candidate"]["Pbar"], e["candidate"]["R"])
                for e in batch["entries"]
            }
        )
        == 8
    )
    assert sum(e["candidate"]["source"] == "independent" for e in batch["entries"]) >= 2


def test_race_repeated_seed_is_not_robust():
    a = observation()
    b = observation(seed=101)
    assert scenario_status([a]) == "PROVISIONAL_FEASIBLE"
    assert scenario_status([a, a]) == "PROVISIONAL_FEASIBLE"
    assert scenario_status([a, b]) == "SEARCH_ROBUST_FEASIBLE"
    assert (
        scenario_status([a, replace(b, metrics=replace(b.metrics, p90=0.4))]) == "SCENARIO_FRAGILE"
    )
    assert robust_rank([a, b]) < robust_rank([a])
    with pytest.raises(ValueError):
        scenario_status([replace(a, phase="confirmation")])


@pytest.mark.parametrize(
    "kind,expected",
    [("accurate", "DONE"), ("elite", "DONE"), ("fragile", "NO_BID"), ("none", "NO_BID")],
)
def test_complete_synthetic_landscapes(tmp_path, kind, expected):
    ctrl, sim = setup(tmp_path, kind)
    state = ctrl.run()
    assert state["phase"] == expected and state["search_calls"] == 32
    assert 0 <= state["repeats"] <= 8
    obs = list(sim.calls.values())
    search = [o for o in obs if o.phase == "search"]
    conf = [o for o in obs if o.phase == "confirmation"]
    assert len(search) == 32 and len(conf) == (3 if expected == "DONE" else 0)
    assert {o.seed for o in search}.isdisjoint({o.seed for o in conf})
    for b in range(1, 5):
        frozen = read_json(tmp_path / "prequery" / f"batch_{b:03d}.json")
        assert sum(e["candidate"]["source"] == "independent" for e in frozen["entries"]) >= 2
        prior = {o.execution_id for o in search if o.batch < b}
        assert set(frozen["training_ids"]) == prior
    if kind == "fragile":
        assert any(s["status"] == "SCENARIO_FRAGILE" for s in state["search_statuses"])
    if kind == "accurate":
        assert read_json(tmp_path / "prequery/batch_003.json")["mode"] == "IMPROVE"


def test_resume_reuses_predictions_and_physical_evaluations(tmp_path):
    ctrl, sim = setup(tmp_path, "accurate")
    sim.interrupt = True
    with pytest.raises(RuntimeError, match="synthetic crash"):
        ctrl.run()
    saved = read_json(ctrl.path)
    frozen = saved["pending"]
    resumed = NextController(
        tmp_path,
        ctrl.config,
        D,
        ctrl.regions,
        sim,
        ctrl.predictor,
        ctrl.elites,
        (101, 102, 103),
        "ERT",
    )
    state = resumed.run()
    assert state["phase"] == "DONE" and len(sim.calls) == 35
    assert read_json(tmp_path / "prequery/batch_001.json") == frozen


def test_pause_and_seed_overlap(tmp_path):
    ctrl, _ = setup(tmp_path)
    pause = tmp_path / "PAUSE"
    pause.touch()
    state = ctrl.run(pause)
    assert state["search_calls"] == 0
    with pytest.raises(ValueError, match="disjoint"):
        NextController(
            tmp_path, ctrl.config, D, [], ctrl.simulator, ctrl.predictor, [], (101, 102, 104)
        )


def test_targeted_qos_and_paired_tracking():
    o = observation(pj=(0.2, 0.01, 0.03, 0.02))
    probes = targeted_probes(o, D, "target")
    transfers = [c for c in probes if c.source == "qos_transfer"]
    assert transfers and all(c.weights[0] > C.weights[0] for c in transfers)
    for c in probes:
        D.validate(c)
        assert sum(c.weights) == pytest.approx(1)
    directions = [c.provenance for c in probes if c.source == "tracking_direction"]
    assert {(d["axis"], np.sign(d["signed_normalized_step"])) for d in directions} == {
        ("P", -1),
        ("P", 1),
        ("conditional_R", -1),
        ("conditional_R", 1),
    }
    # Synthetic bottleneck responds to additional allocation, with no global claim.
    assert min(0.2 - 12 * (c.weights[0] - 0.25) for c in transfers) < 0.1


@pytest.mark.parametrize("model", ["C1", "C2", "C3"])
def test_correction_bias_and_repeated_geometry(model):
    obs = [
        observation(replace(C, candidate_id=f"p{i}", Pbar=0.45 + i * 0.01), seed=100 + i, p90=0.25)
        for i in range(8)
    ]
    fit = Correction(D, CorrectionSpec(model=model)).fit(obs)
    predicted, _ = fit.predict([C])
    assert abs(predicted[0, 1] - 0.25) < 0.03
    fit.fit([obs[0], replace(obs[0], seed=999, execution_id="repeat")])
    assert len(fit.x) == 1
    with pytest.raises(ValueError, match="Confirmation"):
        fit.fit([replace(obs[0], phase="confirmation")])


def test_gp_failure_has_explicit_fallback(monkeypatch):
    import argos.vnext.correction as module

    monkeypatch.setattr(
        module.GaussianProcessRegressor,
        "fit",
        lambda *a: (_ for _ in ()).throw(ValueError("test fit failure")),
    )
    fit = Correction(D, CorrectionSpec(model="C3")).fit([observation(p90=0.25)])
    y, u = fit.predict([C])
    assert u is None and fit.events[0]["kind"] == "gp_failure"
    assert y[0, 1] == pytest.approx(0.25, abs=1e-6)


def test_accurate_v3_correction_stays_accurate():
    fit = Correction(D, CorrectionSpec(model="C2")).fit([observation()])
    y, _ = fit.predict([C])
    assert y[0] == pytest.approx(behaviors(C.prediction))


def test_region_shrink_expand_restart_disconnected_island():
    trust = TrustRegion(C)
    a = observation()
    trust.update(a)
    for _ in range(8):
        trust.update(observation(p90=0.6))
    assert trust.radius == 0.0075
    island = replace(C, candidate_id="disconnected", Pbar=0.7)
    trust.restart(island)
    assert trust.center == island and trust.restarts == 1 and trust.radius == 0.06
    trust.update(observation(island))
    trust.update(
        replace(
            observation(island, p90=0.1, pj=(0.01,) * 4), metrics=Metrics(0.1, 0.1, (0.01,) * 4, 70)
        )
    )
    assert trust.radius == 0.09


@pytest.mark.parametrize(
    "cuda,hip,available,expected",
    [(None, None, False, "CPU"), ("12.1", None, True, "CUDA"), (None, "6.2", True, "HIP")],
)
def test_backend_metadata(monkeypatch, cuda, hip, available, expected):
    import argos.vnext.device as module

    monkeypatch.setattr(module.torch, "version", SimpleNamespace(cuda=cuda, hip=hip))
    monkeypatch.setattr(module.torch.cuda, "is_available", lambda: available)
    monkeypatch.setattr(module.torch.cuda, "current_device", lambda: 1)
    monkeypatch.setattr(module.torch.cuda, "get_device_name", lambda i: f"device-{i}")
    _, meta = module.resolve_device("auto", 4)
    assert meta["backend"] == expected
    if available:
        assert meta["gpu_name"] == "device-1"


def test_original_only_protocol_guard():
    from argos.vnext.protocol import validate_case

    case = {
        "workload": "MIX4-IIIT",
        "J": 4,
        "settings": asdict(replace(Config(), search_seed=100, confirmation_seeds=(104, 105, 106))),
        "repeat_seeds": [101, 102, 103],
        "workload_sha256": "unused",
    }
    with pytest.raises(ValueError, match="eight original"):
        validate_case(case)
    case["workload"] = "W2-short-qos5555"
    case["J"] = 5
    with pytest.raises(ValueError, match="eight original"):
        validate_case(case)


def test_no_fake_correction_ablation(tmp_path):
    ctrl, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="no-correction duplicate"):
        NextController(
            tmp_path,
            ctrl.config,
            D,
            ctrl.regions,
            ctrl.simulator,
            ctrl.predictor,
            ctrl.elites,
            (101, 102, 103),
            "ERTC",
        )


def test_elite_only_ablation_preserves_endpoint(tmp_path):
    ctrl, _ = setup(tmp_path)
    e = EliteController(
        tmp_path / "E",
        ctrl.config,
        D,
        ctrl.regions,
        ctrl.simulator,
        ctrl.predictor,
        elites=ctrl.elites,
    )
    assert e.next_batch()[0].candidate_id == "elite"


def test_completed_search_prediction_cannot_use_current_labels(tmp_path):
    ctrl, sim = setup(tmp_path)
    first = ctrl.propose()
    assert first["training_ids"] == []
    # A read-only proposal contains no simulator calls and no future labels.
    assert not sim.calls and first["mode"] == "DISCOVER"


def test_objective_behavior_reconstruction():
    from argos.contracts import Costs
    from argos.vnext.costs import objective

    y = np.array([0.1, 0.25, 0.01, 0.02, 0.03, 0.04])
    expected = Costs(1, 10, 0.3, 20, 2, 0.1).objective(
        100 * (0.5 - 0.12 + 0.12 * 0.1), 0.25, tuple(y[2:])
    )
    assert objective(C, y) == pytest.approx(expected)
