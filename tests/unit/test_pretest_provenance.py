"""Offline per-dimension audit identity and pinned cost-source regressions."""

import re
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from argos import audit_provenance as provenance
from argos.audit import audit_episode
from argos.config import Config
from argos.controller.argos_controller import SearchState
from argos.provenance import read_json, sha256, write_json
from argos.search.integrity import FILES, write_search_manifest
from argos.simulator.configuration import canonical_cost_provenance, canonical_costs

ROOT = Path(__file__).resolve().parents[2]


def manifest_fixture():
    return {
        "argos_git_head": "head",
        "argos_dirty": False,
        "input_identity": {
            "source_files": {"src/argos/a.py": "source"},
            "dependencies": {
                name: {"commit": "commit", "dirty": False, "url": "url"}
                for name in ("FlexDC", "CONDOR-FLEXDC")
            },
            "checkpoint_sha256": "checkpoint",
            "artifact_manifest_sha256": "artifact",
            "canonical_cost_provenance": {
                "sha256": "cost",
                "metadata_sha256": "metadata",
                "upstream_repository": "repo",
                "upstream_commit": "upstream",
                "upstream_path": "path",
            },
            "context_contract": {"contract_sha256": "context"},
        },
    }


def install_current(monkeypatch, manifest):
    current = {
        name: {"value": deepcopy(value), "error": None}
        for name, value in provenance.recorded_provenance(manifest).items()
    }
    monkeypatch.setattr(provenance, "current_provenance", lambda root: current)
    return current


def test_all_provenance_dimensions_match(monkeypatch, tmp_path):
    manifest = manifest_fixture()
    install_current(monkeypatch, manifest)
    result = provenance.audit_provenance(tmp_path, manifest)
    assert result["exact_match"] and result["status"] == "MATCH"
    assert set(result["dimensions"]) == {
        "argos_source",
        "flexdc",
        "condor_flexdc",
        "checkpoint",
        "artifact_manifest",
        "canonical_cost_source",
        "context_contract",
    }
    assert all(d["status"] == "MATCH" for d in result["dimensions"].values())


@pytest.mark.parametrize(
    "dimension,key",
    [
        ("argos_source", "head"),
        ("argos_source", "files"),
        ("flexdc", "commit"),
        ("condor_flexdc", "commit"),
        ("checkpoint", None),
        ("artifact_manifest", "files_match"),
        ("canonical_cost_source", "sha256"),
        ("canonical_cost_source", "metadata_sha256"),
        ("context_contract", None),
    ],
)
def test_each_mismatch_is_explicit(monkeypatch, tmp_path, dimension, key):
    manifest = manifest_fixture()
    current = install_current(monkeypatch, manifest)
    if key:
        current[dimension]["value"][key] = "changed"
    else:
        current[dimension]["value"] = "changed"
    result = provenance.audit_provenance(tmp_path, manifest)
    assert not result["exact_match"] and result["status"] == "MISMATCH"
    assert result["dimensions"][dimension]["status"] == "MISMATCH"
    historical = provenance.audit_provenance(tmp_path, manifest, True)
    assert historical["status"] == "HISTORICAL"
    assert historical["dimensions"][dimension]["status"] == "MISMATCH"


def test_missing_record_and_unavailable_environment_distinct(monkeypatch, tmp_path):
    manifest = manifest_fixture()
    current = install_current(monkeypatch, manifest)
    del manifest["input_identity"]["context_contract"]
    current["checkpoint"] = {"value": None, "error": "FileNotFoundError"}
    result = provenance.audit_provenance(tmp_path, manifest, True)
    assert result["dimensions"]["context_contract"]["status"] == "HISTORICAL"
    assert result["dimensions"]["checkpoint"]["status"] == "UNAVAILABLE"
    assert not result["exact_match"]


def test_actual_audit_fails_current_mismatch_allows_explicit_history(tmp_path, monkeypatch):
    episode = tmp_path / "episode"
    directory = episode / "v3"
    directory.mkdir(parents=True)
    config = Config()
    config.save(episode / "resolved_config.yaml")
    for name in FILES:
        (directory / name).write_text(
            "a\n1\n"
            if name.endswith(".csv")
            else "[]"
            if name in {"candidate_pool.json", "regions.json"}
            else "{}"
        )
    manifest = manifest_fixture()
    manifest.update(
        resolved_config_sha256=sha256(episode / "resolved_config.yaml"),
        v3_search_manifest_sha256=write_search_manifest(directory, config),
    )
    write_json(episode / "manifest.json", manifest)
    write_json(episode / "state.json", asdict(SearchState("episode", phase="NO_BID")))
    current = install_current(monkeypatch, manifest)
    before = {str(p): sha256(p) for p in episode.rglob("*") if p.is_file()}
    assert audit_episode(tmp_path, episode)["status"] == "PASS"
    current["flexdc"]["value"]["commit"] = "different"
    result = audit_episode(tmp_path, episode)
    assert result["status"] == "FAIL" and result["raw_data_validity"] == "PASS"
    assert result["provenance_failures"] == ["flexdc"]
    result = audit_episode(tmp_path, episode, True)
    assert result["status"] == result["raw_data_validity"] == "PASS"
    assert result["current_environment_identity"]["dimensions"]["flexdc"]["status"] == "MISMATCH"
    assert result["confirmation_status"] == "CONFIRMATION_NOT_RUN"
    assert before == {str(p): sha256(p) for p in episode.rglob("*") if p.is_file()}


def test_pinned_canonical_source_metadata_offline():
    metadata = read_json(ROOT / "configs/canonical_cost_source.json")
    digest = sha256(ROOT / "configs/canonical_cost_source.ini")
    assert metadata["sha256"] == metadata["upstream_file_sha256"] == digest
    assert re.fullmatch("[0-9a-f]{40}", metadata["upstream_commit"])
    assert metadata["upstream_repository"] == "https://github.com/peaclab/flexdc-sim"
    assert metadata["url"] == (
        "https://raw.githubusercontent.com/peaclab/flexdc-sim/"
        + metadata["upstream_commit"]
        + "/"
        + metadata["upstream_path"]
    )
    assert metadata["used_sections"] == ["cost_function", "dr_program"]
    assert canonical_cost_provenance(ROOT)["sha256"] == digest


def test_sa_sections_do_not_affect_costs(tmp_path):
    import shutil

    (tmp_path / "configs").mkdir()
    for name in ("canonical_cost_source.ini", "canonical_cost_source.json"):
        shutil.copyfile(ROOT / "configs" / name, tmp_path / "configs" / name)
    expected = canonical_costs(tmp_path)
    path = tmp_path / "configs/canonical_cost_source.ini"
    path.write_text(
        path.read_text()
        .replace("temperature     = 1000", "temperature     = 999999")
        .replace("w_low   = 0.1", "w_low   = 0.99")
    )
    metadata_path = path.with_suffix(".json")
    metadata = read_json(metadata_path)
    metadata["sha256"] = metadata["upstream_file_sha256"] = sha256(path)
    write_json(metadata_path, metadata)
    assert canonical_costs(tmp_path) == expected
    metadata["used_sections"].append("simulated_annealing")
    write_json(metadata_path, metadata)
    with pytest.raises(ValueError, match="allows only"):
        canonical_costs(tmp_path)


def test_real_collector_reports_changed_cost_bytes(tmp_path):
    import shutil

    (tmp_path / "configs").mkdir()
    for name in ("canonical_cost_source.ini", "canonical_cost_source.json"):
        shutil.copyfile(ROOT / "configs" / name, tmp_path / "configs" / name)
    before = provenance._canonical_cost(tmp_path)
    assert before["metadata_valid"]
    path = tmp_path / "configs/canonical_cost_source.ini"
    path.write_bytes(path.read_bytes() + b"\n; changed\n")
    changed = provenance._canonical_cost(tmp_path)
    assert not changed["metadata_valid"] and changed["sha256"] != before["sha256"]
