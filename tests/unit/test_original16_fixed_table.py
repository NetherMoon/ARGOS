"""Plan and provenance checks for the original 16-context breadth experiment."""

import json
import zipfile

import pytest

from argos.fixed_table import runner
from argos.fixed_table.original16 import (
    ROOT,
    WORKLOADS,
    config_for,
    load_plan,
    new_experiment,
    spec_for,
    verify_environment,
)


def test_frozen_panel_and_serious_budget():
    seeds, rows, source = load_plan(ROOT)
    assert len(rows) == 16
    assert {r["workload"] for r in rows} == set(WORKLOADS)
    assert {int(r["server_count"]) for r in rows} == {250, 1000}
    assert {float(r["utilization"]) for r in rows} == {0.6, 0.8}
    assert len({int(r["arrival_seed"]) for r in rows}) == 1
    assert sum(int(r["max_search_calls"]) for r in rows) == 512
    assert sum(int(r["max_final_checks"]) for r in rows) == 48
    assert seeds["arrival_seed"] not in {
        3883208862,
        3090083691,
        2888586026,
        1483544252,
        1059155856,
        1258205800,
        20,
        21,
        22,
    }
    assert (
        len({seeds["arrival_seed"], seeds["search_runtime_seed"], *seeds["final_runtime_seeds"]})
        == 5
    )
    assert all(config_for(row, seeds, 10).max_search_calls == 32 for row in rows)
    for row in rows:
        spec = spec_for(ROOT, row, source)
        assert spec["fixed"]["N"] == int(row["server_count"])
        assert spec["fixed"]["U"] == float(row["utilization"])
        assert str(row["server_count"]) in spec["experiment_path"]
        assert spec["cases"][row["workload"]]["workload_path"].endswith(row["workload"] + ".ini")


def test_all_contexts_are_within_frozen_v3_contract():
    assert len(verify_environment(ROOT)["v3_contexts"]) == 16


def test_preparation_receipt_and_resume_guard(tmp_path):
    directory = tmp_path / "prepared"
    manifest = new_experiment(ROOT, directory, 10)
    assert manifest["budget"] == {
        "episodes": 16,
        "search_per_episode": 32,
        "checks_per_selected": 3,
        "max_search": 512,
        "max_checks": 48,
        "max_total": 560,
        "global_worker_limit": 10,
    }
    assert len(json.loads((directory / "resolved_config.json").read_text())["contexts"]) == 16
    assert json.loads((directory / "run_status.json").read_text())["status"] == "PREPARED_NOT_RUN"
    assert new_experiment(ROOT, directory, 10) == manifest
    (directory / "source_plan.json").write_text("changed", encoding="utf8")
    with pytest.raises(ValueError, match="integrity"):
        new_experiment(ROOT, directory, 10)


def test_final_zip_contract_excludes_bulk_bank_data(tmp_path):
    directory = tmp_path / "original16"
    directory.mkdir()
    for name in ("manifest.json", "run_status.json", "report.md", "context_summary.csv"):
        (directory / name).write_text("compact evidence", encoding="utf8")
    bank = directory / "cache/v3_banks/example"
    bank.mkdir(parents=True)
    (bank / "manifest.json").write_text("bank receipt", encoding="utf8")
    (bank / "endpoints.csv").write_text("bulk bank data", encoding="utf8")
    archive = runner.archive(directory)
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        assert {"manifest.json", "run_status.json", "report.md", "context_summary.csv"}.issubset(
            output.namelist()
        )
        assert "cache/v3_banks/example/manifest.json" in output.namelist()
        assert "cache/v3_banks/example/endpoints.csv" not in output.namelist()


def test_bank_key_preserves_exact_historical_w2_identity_and_separates_contexts(
    monkeypatch, tmp_path
):
    from argos.fixed_table import original16

    seeds, rows, source = load_plan(ROOT)
    old = next(
        r
        for r in rows
        if r["workload"] == "W2-short-qos5555"
        and int(r["server_count"]) == 1000
        and float(r["utilization"]) == 0.6
    )
    changed = next(
        r
        for r in rows
        if r["workload"] == "W2-short-qos5555"
        and int(r["server_count"]) == 1000
        and float(r["utilization"]) == 0.8
    )
    prior = original16.read_json(ROOT / original16.PRIOR / "manifest.json")
    captures = []
    monkeypatch.setattr(runner, "setup", lambda *_: (None, None, None, None, None, None))

    def capture(_directory, case, *_):
        captures.append(case)
        raise RuntimeError("captured")

    monkeypatch.setattr(runner, "get_bank", capture)

    class Adapter:
        device_metadata = original16.read_json(
            ROOT
            / original16.PRIOR
            / "cache/v3_banks"
            / original16.HISTORICAL_BANKS["W2-short-qos5555"]
            / "manifest.json"
        )["identity"]["device"]

    for row in (old, changed):
        spec = spec_for(ROOT, row, source)
        manifest = {
            **prior,
            "specification": spec,
            "v3_contexts": {
                row["workload"]: original16.check_context(ROOT, config_for(row, seeds, 10))
            },
        }
        with pytest.raises(RuntimeError, match="captured"):
            runner.bank_for(
                ROOT,
                tmp_path,
                row["workload"],
                seeds,
                manifest,
                Adapter(),
                10,
                config_for(row, seeds, 10),
            )
    assert captures[0]["bank_id"] == original16.HISTORICAL_BANKS["W2-short-qos5555"]
    assert captures[1]["bank_id"] != captures[0]["bank_id"]
    assert captures[1]["bank_identity"]["utilization"] == 0.8
