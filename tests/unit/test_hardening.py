import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from argos.config import Config
from argos.context import check_context
from argos.provenance import sha256
from argos.search.candidates import Domain, FixedRadius, interval_sample
from argos.search.integrity import FILES, verify_search_manifest, write_search_manifest
from argos.search.regions import promising
from argos.surrogate.v3_adapter import resolve_device
from argos.types import Candidate, Metrics


@pytest.mark.parametrize("j", [3, 4, 5, 6, 8])
def test_variable_j_relative_simplex(j):
    config = replace(Config(), weight_policy="relative_to_equal")
    lo, hi = config.weight_bounds(j)
    d = Domain(0.2, 0.7, 0.9, 0, 0.6, (lo,) * j, (hi,) * j)
    rng = np.random.default_rng(j)
    for i in range(40):
        a = d.independent(rng, str(i))
        d.validate(a)
        d.validate(d.local(a, rng, 0.12, "local"))
        projected = d.project(rng.normal(0, 10, j))
        assert sum(projected) == pytest.approx(1, abs=1e-12)
        assert min(projected) >= lo and max(projected) <= hi


def test_fixed_j8_invalid_and_no_silent_switch():
    with pytest.raises(ValueError, match="simplex"):
        Config().weight_bounds(8)
    assert Config().weight_bounds(4) == (0.15, 0.45)
    assert replace(Config(), weight_policy="relative_to_equal").weight_bounds(8) == (0.075, 0.225)


def test_interval_and_reserve_boundaries():
    rng = np.random.default_rng(1)
    with pytest.raises(ValueError, match="interval"):
        interval_sample(rng, 0.5, 0.4)
    assert interval_sample(rng, 0.5, 0.5) == 0.5
    assert interval_sample(rng, 0.5, 0.5 - 1e-14) == pytest.approx(0.5)
    d = Domain(0.2, 0.8, 0.8, 0, 0.6, (0.25,) * 4, (0.25,) * 4)
    a = Candidate("edge", 0.8, 0, (0.25,) * 4, "test")
    assert np.isfinite(d.encode(a)).all() and d.encode(a)[1] == 0
    assert d.distance(a, a) == 0
    for i in range(30):
        d.validate(d.local(a, rng, 0.12, str(i)))
        d.validate(d.independent(rng, str(i)))
    with pytest.raises(ValueError, match="reserve"):
        replace(d, pr_upper=0.79)
    assert FixedRadius(0.12).radius(batch=99, observations=()) == 0.12


def test_retention_keeps_infeasible_despite_feasible_group():
    d = Domain(0.2, 0.8, 0.95, 0.01, 0.6, (0.25,) * 4, (0.25,) * 4)
    rows = [
        Candidate(
            str(i),
            0.22 + i * 0.02,
            0.02,
            (0.25,) * 4,
            "test",
            iteration=0,
            prediction=Metrics(0.1, 0.1 + i * 0.001, (0.02,) * 4, 10 + i),
        )
        for i in range(20)
    ]
    bad = replace(
        rows[0],
        candidate_id="low-violation",
        Pbar=0.79,
        prediction=Metrics(0.1, 0.3001, (0.02,) * 4, 1),
    )
    rows.append(bad)
    chosen = promising(rows, 6, d)
    assert bad in chosen and rows[0] in chosen
    assert len({c.candidate_id for c in chosen}) == 6
    assert chosen == promising(list(reversed(rows)), 6, d)


@pytest.mark.parametrize("name", FILES)
def test_search_manifest_tamper(tmp_path, name):
    for f in FILES:
        p = tmp_path / f
        p.write_text(
            "a\n1\n"
            if f.endswith(".csv")
            else "[]"
            if f in {"candidate_pool.json", "regions.json"}
            else "{}"
        )
    config = Config()
    digest = write_search_manifest(tmp_path, config)
    verify_search_manifest(tmp_path, config, digest)
    p = tmp_path / name
    p.write_text(p.read_text() + " ")
    with pytest.raises(ValueError, match="integrity"):
        verify_search_manifest(tmp_path, config, digest)
    import shutil

    from argos.episode import run_episode
    from argos.provenance import write_json

    episode = tmp_path / "episode"
    (episode / "v3").mkdir(parents=True)
    for filename in (*FILES, "search_manifest.json"):
        shutil.copyfile(tmp_path / filename, episode / "v3" / filename)
    config.save(episode / "resolved_config.yaml")
    write_json(
        episode / "manifest.json",
        {
            "resolved_config_sha256": sha256(episode / "resolved_config.yaml"),
            "v3_search_manifest_sha256": digest,
        },
    )
    with pytest.raises(ValueError, match="integrity"):
        run_episode(tmp_path, resume=episode)


def test_manifest_policy_and_legacy_rejected(tmp_path):
    with pytest.raises(ValueError, match="LEGACY_UNTRUSTED"):
        verify_search_manifest(tmp_path)
    for f in FILES:
        (tmp_path / f).write_text(
            "a\n1\n"
            if f.endswith(".csv")
            else "[]"
            if f in {"candidate_pool.json", "regions.json"}
            else "{}"
        )
    digest = write_search_manifest(tmp_path, Config())
    p = tmp_path / "search_manifest.json"
    record = json.loads(p.read_text())
    record["policies"]["schema"] = 999
    p.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="hash changed"):
        verify_search_manifest(tmp_path, Config(), digest)
    with pytest.raises(ValueError, match="policy"):
        verify_search_manifest(tmp_path)


def context_fixture(tmp_path):
    contract = json.loads(
        (Path(__file__).resolve().parents[2] / "configs/v3_context_contract.json").read_text()
    )
    flex = tmp_path / ".deps/FlexDC"
    (flex / "src/peacsim").mkdir(parents=True)
    (tmp_path / "configs").mkdir()
    signal = flex / "signal.csv"
    signal.write_text("signal")
    cluster = flex / "cluster.ini"
    cluster.write_text("cluster")
    contract["iso_sha256"] = sha256(signal)
    contract["cluster_sha256"] = sha256(cluster)
    (tmp_path / "configs/v3_context_contract.json").write_text(json.dumps(contract))
    sections = {}
    for name, value in contract["locked_experiment"].items():
        section, key = name.split(".", 1)
        sections.setdefault(section, {})[key] = value
    sections["iso"]["iso_file_path"] = "../../signal.csv"
    sections["system"].update(server_count="1000", utilization="0.6", random_seed="20")
    path = flex / "experiment.ini"
    path.write_text(
        "\n".join(
            f"[{section}]\n" + "\n".join(f"{k}={v}" for k, v in values.items())
            for section, values in sections.items()
        )
    )
    return replace(Config(), experiment="experiment.ini", cluster="cluster.ini"), path


@pytest.mark.parametrize(
    "old,new",
    [
        ("idle_watts = 120.0", "idle_watts = 121.0"),
        ("iso_signal_start_hour = 16", "iso_signal_start_hour = 17"),
        ("normalize_iso_signal = True", "normalize_iso_signal = False"),
        ("time_granularity = 1", "time_granularity = 2"),
    ],
)
def test_context_mismatch_and_ood(tmp_path, old, new):
    config, path = context_fixture(tmp_path)
    assert not check_context(tmp_path, config)["context_ood"]
    path.write_text(path.read_text().replace(old.replace(" = ", "="), new.replace(" = ", "=")))
    with pytest.raises(ValueError, match="context mismatch"):
        check_context(tmp_path, config)
    assert (
        check_context(tmp_path, replace(config, allow_context_ood=True))["label"]
        == "CONTEXT_OOD_OVERRIDE"
    )


def test_context_policy_hash_and_unsupported_duration(tmp_path):
    config, path = context_fixture(tmp_path)
    with pytest.raises(ValueError):
        check_context(tmp_path, replace(config, policy="FIFO"))
    signal = tmp_path / ".deps/FlexDC/signal.csv"
    signal.write_text("changed")
    with pytest.raises(ValueError):
        check_context(tmp_path, config)
    path.write_text(
        path.read_text().replace("simulation_duration=3600", "simulation_duration=7200")
    )
    with pytest.raises(ValueError, match="even in OOD"):
        check_context(tmp_path, replace(config, allow_context_ood=True))


def test_device_resolution_and_explicit_cuda_failure(monkeypatch):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert resolve_device("auto", 4)[0] == "cpu"
    assert resolve_device("cpu", 4)[1]["dtype"] == "float32"
    with pytest.raises(RuntimeError, match="explicitly requested"):
        resolve_device("cuda", 4)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_device_name", lambda i: "mock-gpu")
    assert resolve_device("auto", 4)[0] == "cuda"
    assert resolve_device("cuda", 4)[1]["gpu_name"] == "mock-gpu"


def test_paper_mode_rejects_dirty_tree_before_artifact_access(tmp_path, monkeypatch):
    from argos import episode

    monkeypatch.setattr(episode, "git", lambda *args: " M src/argos/config.py")
    with pytest.raises(ValueError, match="clean ARGOS"):
        episode.doctor(tmp_path, replace(Config(), run_mode="paper"))


def test_resume_rejects_legacy_before_simulator(tmp_path):
    from argos.episode import run_episode
    from argos.provenance import write_json

    Config().save(tmp_path / "resolved_config.yaml")
    write_json(
        tmp_path / "manifest.json",
        {"resolved_config_sha256": sha256(tmp_path / "resolved_config.yaml")},
    )
    with pytest.raises(ValueError, match="LEGACY_UNTRUSTED"):
        run_episode(tmp_path, resume=tmp_path)
