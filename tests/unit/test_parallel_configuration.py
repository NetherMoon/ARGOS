"""Concurrent overlays import once and preserve deterministic pinned helper behavior."""

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

from argos.provenance import import_file, read_json, sha256
from argos.simulator import configuration

ROOT = Path(__file__).resolve().parents[2]


def exercise(root, tmp_path, monkeypatch):
    source = tmp_path / "source.ini"
    source.write_text("; preserve comment\n[system]\nserver_count = 1000\nutilization=0.6\n")
    dependency = root / ".deps/FlexDC/am_generate_paper_iso_experiment_configs.py"
    before = sha256(dependency)
    configuration._REPLACERS.pop(dependency.resolve(), None)
    reference = import_file("_argos_serial_reference", dependency).replace_ini_values
    loaded = Mock(wraps=import_file)
    monkeypatch.setattr(configuration, "import_file", loaded)
    barrier = threading.Barrier(8)
    original_bytecode = sys.dont_write_bytecode

    def worker(i):
        if i < 8:
            barrier.wait(timeout=10)
        changes = {("system", "server_count"): str(100 + i)}
        path = tmp_path / "outputs" / f"{i}.ini"
        record = configuration.overlay(root, source, path, changes)
        expected = reference(source.read_text(), changes, source)
        assert path.read_text() == expected
        assert record == read_json(path.with_suffix(".audit.json"))
        assert record["source_sha256"] == sha256(source)
        assert record["generated_sha256"] == sha256(path)
        assert record["changes"] == [
            {"section": "system", "key": "server_count", "old": "1000", "new": str(100 + i)}
        ]
        return path.read_bytes()

    with ThreadPoolExecutor(max_workers=8) as pool:
        outputs = list(pool.map(worker, range(32)))
    assert len(set(outputs)) == 32
    loaded.assert_called_once()
    name = loaded.call_args.args[0]
    assert sys.modules[name].replace_ini_values is configuration.load_ini_replacer(root)
    assert sys.dont_write_bytecode == original_bytecode
    assert sha256(dependency) == before
    assert not list(dependency.parent.glob("__pycache__/*"))


def test_concurrent_overlay_single_import_portable(tmp_path, monkeypatch):
    dependency = tmp_path / ".deps/FlexDC/am_generate_paper_iso_experiment_configs.py"
    dependency.parent.mkdir(parents=True)
    dependency.write_text(
        "def replace_ini_values(text, changes, source):\n    return text.replace('server_count = 1000', 'server_count = ' + changes[('system', 'server_count')])\n"
    )
    exercise(tmp_path, tmp_path, monkeypatch)


def test_concurrent_overlay_pinned_helper_parity(tmp_path, monkeypatch):
    if not (ROOT / ".deps/FlexDC/am_generate_paper_iso_experiment_configs.py").is_file():
        pytest.skip("Pinned FlexDC required")
    exercise(ROOT, tmp_path, monkeypatch)
