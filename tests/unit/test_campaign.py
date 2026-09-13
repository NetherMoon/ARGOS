"""Campaign controls tested independently of model/simulator expense."""

from dataclasses import asdict, replace

import numpy as np
import pytest

from argos.campaign.cache import EarlyReplay, SimulatorCache, physical_key, scheduled_seconds
from argos.campaign.identity import digest, immutable_json, verify_files
from argos.campaign.ledger import validate_case_seeds, validate_ledger
from argos.campaign.methods import FixedController, fixed_probes
from argos.campaign.reporting import campaign_report
from argos.campaign.runner import run_v3_only, seal_method
from argos.config import Config
from argos.controller.argos_controller import Controller
from argos.provenance import read_json, sha256, write_json
from argos.search.candidates import Domain
from argos.types import (
    Candidate,
    FlexDCObservation,
    JobIdentity,
    Metrics,
    QoSEvidence,
    Region,
    observation_from_dict,
)


class FakeRunner:
    calls = 0

    def __init__(self, root, episode, config):
        self.episode = episode

    def evaluate(self, c, seed, phase, batch):
        path = self.episode / "fake.json"
        if path.exists():
            return observation_from_dict(read_json(path))
        FakeRunner.calls += 1
        m = Metrics(0.1, 0.2, (0.0,) * len(c.weights), 1.0)
        evidence = tuple(
            QoSEvidence(JobIdentity(i, f"job{i}", (1, 2, 3, 4, 5, 1)), 0.0, 2, 2, 0, 0, 0, 1)
            for i in range(len(c.weights))
        )
        o = FlexDCObservation(
            c, seed, phase, batch, True, m, "PARSED", 1.0, c.candidate_id, qos_evidence=evidence
        )
        write_json(path, asdict(o))
        return o


def environment(tmp_path):
    config = replace(
        Config(),
        search_seed=101,
        confirmation_seeds=(102, 103),
        starts=4,
        iterations=4,
        max_workers=2,
        batch_size=4,
        independent_per_batch=1,
        max_search_batches=4,
        max_search_calls=16,
    )
    domain = Domain(0.18, 0.76, 0.912, 0.01, 0.6, (0.15,) * 4, (0.45,) * 4)
    candidate = Candidate(
        "v3-4-0",
        0.5,
        0.15,
        (0.25,) * 4,
        "V3 endpoint",
        0,
        4,
        "region-1",
        Metrics(0.1, 0.2, (0.0,) * 4, 1.0),
    )
    regions = [
        Region(
            "region-1", candidate, (candidate.candidate_id,), tuple(domain.encode(candidate)), (4,)
        )
    ]
    predict = lambda c: replace(c, prediction=candidate.prediction)
    case = {
        "case_id": "c000",
        "phase": 0,
        "tier": "ENGINEERING_SMOKE",
        "category": "test",
        "workload": "test",
        "workload_sha256": "abc",
        "context": {"x": 1},
        "context_hash": "context",
        "J": 4,
        "bank_id": "bank",
        "methods": [
            "v3_only",
            "v3_fixed_probing",
            "simulator_only_adaptive",
            "argos_fixed_budget",
            "argos_early_stop",
        ],
        "settings": asdict(config),
    }
    cache = SimulatorCache(tmp_path, tmp_path, {"frozen": "yes"}, FakeRunner)
    return config, domain, candidate, regions, predict, case, cache


def test_exact_keys_and_context_invalidation(tmp_path):
    _, _, c, _, _, _, _ = environment(tmp_path)
    key = physical_key(c, 1, {"x": 1})
    assert key == physical_key(
        replace(c, candidate_id="other", prediction=None, source="independent"), 1, {"x": 1}
    )
    assert key != physical_key(replace(c, Pbar=np.nextafter(c.Pbar, 1)), 1, {"x": 1})
    assert key != physical_key(c, 2, {"x": 1})
    assert key != physical_key(c, 1, {"x": 2})
    assert key != physical_key(replace(c, weights=(0.2, 0.3, 0.25, 0.25)), 1, {"x": 1})


def test_cross_method_cache_keeps_logical_counts_and_resume(tmp_path):
    config, _, c, _, _, case, cache = environment(tmp_path)
    FakeRunner.calls = 0
    a = cache.method(case, "a", tmp_path / "a", config)
    b = cache.method(case, "b", tmp_path / "b", config)
    x = a.evaluate_batch([c], 101, "search", 1)
    y = b.evaluate_batch([replace(c, candidate_id="other")], 101, "search", 1)
    assert FakeRunner.calls == 1
    assert x[0].execution_id == y[0].execution_id
    assert x[0].candidate != y[0].candidate
    assert a.evaluate_batch([c], 101, "search", 1) == x
    assert FakeRunner.calls == 1
    assert len(list((tmp_path / "a/logical_queries").glob("*.json"))) == 1
    assert read_json(next((tmp_path / "b/logical_queries").glob("*.json")))[
        "physical_execution_reused"
    ]
    b.evaluate_batch([c], 102, "confirmation", 1)
    assert FakeRunner.calls == 2


def test_fixed_full_set_frozen_and_independent_of_results(tmp_path):
    config, domain, _, regions, predict, case, cache = environment(tmp_path)
    ep = tmp_path / "fixed"
    probes = fixed_probes(ep, config, domain, regions, predict)
    assert len(probes) == 16
    before = sha256(ep / "frozen_probes.json")
    assert sum(c.source == "independent" for c in probes) >= 4
    state = FixedController(
        ep,
        config,
        domain,
        regions,
        cache.method(case, "fixed", ep, config),
        predict,
        proposals=probes,
    ).run()
    assert [o.candidate for o in state.observations if o.phase == "search"] == probes
    assert sha256(ep / "frozen_probes.json") == before
    assert fixed_probes(ep, config, domain, regions, predict) == probes


def test_exact_early_replay_matches_independent_core_run(tmp_path):
    config, domain, _, regions, predict, case, cache = environment(tmp_path)
    ep = tmp_path / "fixed"
    fixed = Controller(
        ep, config, domain, regions, cache.method(case, "fixed", ep, config), predict
    ).run()
    early_config = replace(config, search_mode="early_stop")
    ep = tmp_path / "early"
    early = Controller(
        ep,
        early_config,
        domain,
        regions,
        EarlyReplay(cache.method(case, "early", ep, early_config), fixed.observations),
        predict,
    ).run()
    ep = tmp_path / "independent"
    independent = Controller(
        ep,
        early_config,
        domain,
        regions,
        cache.method(case, "independent", ep, early_config),
        predict,
    ).run()
    assert early.observations == independent.observations
    assert early.incumbent == independent.incumbent
    assert early.search_calls == 8 < fixed.search_calls
    assert early.stop_reason == "EARLY_STOP_QUALIFIED_LOCAL_PATIENCE"


def test_early_prefix_mismatch_rejected(tmp_path):
    config, _, c, _, _, case, cache = environment(tmp_path)
    delegate = cache.method(case, "fixed", tmp_path / "fixed", config)
    observations = delegate.evaluate_batch([c], 101, "search", 1)
    replay = EarlyReplay(delegate, observations)
    with pytest.raises(ValueError, match="proposals"):
        replay.evaluate_batch([replace(c, Pbar=0.6)], 101, "search", 1)


def test_simulator_only_never_receives_v3_predictions(tmp_path):
    config, domain, _, _, _, case, cache = environment(tmp_path)
    ep = tmp_path / "sim"
    state = Controller(
        ep, config, domain, [], cache.method(case, "sim", ep, config), lambda c: c
    ).run()
    assert all(o.candidate.prediction is None for o in state.observations)
    assert all(
        o.candidate.source == "independent"
        for o in state.observations
        if o.batch == 1 and o.phase == "search"
    )
    assert any(o.candidate.source == "local" for o in state.observations)


def test_v3_selection_frozen_before_validation_and_no_safe_endpoint(tmp_path):
    config, _, c, _, _, case, cache = environment(tmp_path)
    ep = tmp_path / "v3"
    state = run_v3_only(ep, config, c, cache.method(case, "v3", ep, config))
    assert state.search_calls == 1 and state.incumbent == c and state.confirmation_index == 2
    assert (
        run_v3_only(ep, config, c, cache.method(case, "v3", ep, config)).observations
        == state.observations
    )
    ep = tmp_path / "none"
    state = run_v3_only(ep, config, None, cache.method(case, "none", ep, config))
    assert state.phase == "NO_BID" and state.search_calls == 0 and state.observations == []


def test_seal_rejects_corruption(tmp_path):
    p = tmp_path / "record.json"
    immutable_json(p, {"value": 1})
    with pytest.raises(ValueError, match="Immutable"):
        immutable_json(p, {"value": 2})
    expected = sha256(p)
    p.write_text("changed")
    with pytest.raises(ValueError, match="integrity"):
        verify_files(tmp_path, {"record.json": expected})


def test_ledger_redaction_and_overlap(tmp_path):
    groups = {
        "historical_or_training": [20],
        "engineering_smoke": [1, 2, 3],
        "campaign_development_search": [4],
        "campaign_development_confirmation": [5, 6],
        "reserved_final_benchmark_search": [7],
        "reserved_final_benchmark_confirmation": [8],
    }
    p = tmp_path / "ledger.json"
    write_json(p, {"groups": groups})
    ledger = validate_ledger(p, sha256(p))
    assert all(not k.startswith("reserved") for k in ledger["development"])
    case = {
        "tier": "SERIOUS_DEVELOPMENT",
        "settings": {"search_seed": 4, "confirmation_seeds": [5, 6]},
    }
    validate_case_seeds(case, ledger)
    case["settings"]["search_seed"] = 7
    with pytest.raises(ValueError, match="Unallocated"):
        validate_case_seeds(case, ledger)
    groups["reserved_final_benchmark_search"] = [4]
    write_json(p, {"groups": groups})
    with pytest.raises(ValueError, match="overlap"):
        validate_ledger(p, sha256(p))


def test_batch_time_is_resource_matched():
    assert scheduled_seconds([5, 4, 3, 2], 2) == 7
    assert scheduled_seconds([5, 4], 4) == 5


def test_mock_campaign_all_methods_reporting(tmp_path):
    config, domain, c, regions, predict, case, cache = environment(tmp_path)
    manifest = {
        "campaign_id": "mock",
        "identity": {
            "core": {"commit": "frozen"},
            "checkpoint_sha256": "checkpoint",
            "dependencies": {},
        },
        "protocol_sha256": "protocol",
        "ledger_sha256": "ledger",
        "seed_group_counts": {},
        "cases": [case],
    }
    write_json(tmp_path / "campaign_manifest.json", manifest)
    fixed = None
    for method in case["methods"]:
        ep = tmp_path / "cases/c000" / method
        ep.mkdir(parents=True)
        config.save(ep / "resolved_config.yaml")
        simulator = cache.method(case, method, ep, config)
        if method == "v3_only":
            state = run_v3_only(ep, config, c, simulator)
        elif method == "v3_fixed_probing":
            probes = fixed_probes(ep, config, domain, regions, predict)
            state = FixedController(
                ep, config, domain, regions, simulator, predict, proposals=probes
            ).run()
        else:
            cfg = (
                replace(config, search_mode="early_stop")
                if method == "argos_early_stop"
                else config
            )
            if method == "argos_early_stop":
                simulator = EarlyReplay(simulator, fixed.observations)
            state = Controller(
                ep,
                cfg,
                domain,
                [] if method == "simulator_only_adaptive" else regions,
                simulator,
                (lambda c: c) if method == "simulator_only_adaptive" else predict,
            ).run()
            if method == "argos_fixed_budget":
                fixed = state
        seal_method(ep, {"v3_logical_seconds": 0 if method == "simulator_only_adaptive" else 10})
    summary = campaign_report(tmp_path)
    assert summary["completed"] == 5
    import pandas as pd

    rows = pd.read_csv(tmp_path / "campaign_results.csv")
    argos = rows[rows.method == "argos_fixed_budget"].iloc[0]
    assert argos.first_feasible_batch == 1
    assert argos.queries_launched_through_first_feasible_batch == 4
    assert "ENGINEERING_SMOKE" in (tmp_path / "REPORT.md").read_text(encoding="utf-8")


def test_cached_observation_corruption_rejected(tmp_path):
    config, _, c, _, _, case, cache = environment(tmp_path)
    simulator = cache.method(case, "a", tmp_path / "a", config)
    simulator.evaluate_batch([c], 101, "search", 1)
    p = next((tmp_path / "cache/flexdc").glob("*/fake.json"))
    d = read_json(p)
    d["runtime_seconds"] = 500
    write_json(p, d)
    with pytest.raises(ValueError, match="Physical observation changed"):
        simulator.evaluate_batch([c], 101, "search", 1)


def test_fixed_set_corruption_rejected_before_execution(tmp_path):
    config, domain, _, regions, predict, _, _ = environment(tmp_path)
    ep = tmp_path / "fixed"
    fixed_probes(ep, config, domain, regions, predict)
    p = ep / "frozen_probes.json"
    d = read_json(p)
    d["candidates"][0]["Pbar"] += 0.01
    write_json(p, d)
    with pytest.raises(ValueError, match="corrupted"):
        fixed_probes(ep, config, domain, regions, predict)


def test_bank_reuse_and_corruption(tmp_path):
    from dataclasses import dataclass
    from types import SimpleNamespace

    import pandas as pd

    from argos.campaign.candidate_bank import get_bank

    config, domain, candidate, _, _, _, _ = environment(tmp_path)
    row = {
        "Start_Index": 0,
        "Iteration": 4,
        "Pbar_kw_per_server": candidate.Pbar,
        "R_kw_per_server": candidate.R,
        "weights": list(candidate.weights),
        "Predicted_Mean_Tracking": 0.1,
        "Predicted_P90_Tracking": 0.2,
        "Predicted_QoS_Probabilities": [0.0] * 4,
        "Predicted_Full_Objective": 1.0,
    }
    snapshots = pd.DataFrame([dict(row, Iteration=0), row])

    @dataclass
    class Settings:
        starts: int = 1
        iterations: int = 4
        top_k: int = 5
        candidate_distance: float = 0.03
        mode: str = "margin_constrained"

    calls = []

    def optimize(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame([row]), snapshots, pd.DataFrame([{"loss": 1.0}])

    api = SimpleNamespace(select_distinct_top_k=lambda endpoints, **kwargs: endpoints)
    adapter = SimpleNamespace(api=api, optimize=optimize)
    identity = {"frozen": "model", "starts": 1}
    case = {"bank_identity": identity, "bank_id": digest(identity)}
    values = (SimpleNamespace(job_count=4), None, Settings(), None, domain, None)
    first, manifest, reused = get_bank(tmp_path, case, adapter, config, values)
    assert not reused and manifest["snapshot_count"] == 2
    second, _, reused = get_bank(tmp_path, case, adapter, config, values)
    assert reused and first == second and len(calls) == 1
    bank = tmp_path / "cache/v3_banks" / case["bank_id"]
    (bank / manifest["completed_attempt"] / "endpoints.csv").write_text("corrupt")
    with pytest.raises(ValueError, match="integrity"):
        get_bank(tmp_path, case, adapter, config, values)


def test_no_bid_retained_in_report_denominator(tmp_path):
    config, _, _candidate, _, _, case, _ = environment(tmp_path)
    case["methods"] = ["v3_only"]
    manifest = {
        "campaign_id": "mock",
        "identity": {"core": {"commit": "core"}, "checkpoint_sha256": "cp", "dependencies": {}},
        "protocol_sha256": "p",
        "ledger_sha256": "l",
        "seed_group_counts": {},
        "cases": [case],
    }
    write_json(tmp_path / "campaign_manifest.json", manifest)
    ep = tmp_path / "cases/c000/v3_only"
    state = run_v3_only(ep, config, None, None)
    assert state.phase == "NO_BID"
    seal_method(ep, {"v3_logical_seconds": 10})
    campaign_report(tmp_path)
    import pandas as pd

    summary = pd.read_csv(tmp_path / "method_comparison.csv").iloc[0]
    assert summary.attempted == 1 and summary.qualified_bids == 0
    assert summary.success_fraction_descriptive == 0
    failures = pd.read_csv(tmp_path / "campaign_failures.csv")
    assert failures.iloc[0].kind == "NO_BID"
