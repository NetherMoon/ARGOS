import pytest

from argos.provenance import read_json, sha256, write_json


def test_atomic_json_and_hash(tmp_path):
    p = tmp_path / "state.json"
    write_json(p, {"budget": 3})
    assert read_json(p) == {"budget": 3}
    assert len(sha256(p)) == 64
    with pytest.raises(ValueError):
        write_json(p, {"metric": float("nan")})


def test_env_rejected_without_reading(tmp_path):
    with pytest.raises(ValueError):
        sha256(tmp_path / ".env")


def test_failed_dynamic_import_restores_module_and_bytecode(tmp_path):
    import sys
    from types import ModuleType

    from argos.provenance import import_file

    path = tmp_path / "broken.py"
    path.write_text("raise RuntimeError('broken helper')")
    name = "_argos_test_broken_helper"
    previous = ModuleType(name)
    sys.modules[name] = previous
    bytecode = sys.dont_write_bytecode
    try:
        with pytest.raises(RuntimeError, match="broken helper"):
            import_file(name, path)
        assert sys.modules[name] is previous
        assert sys.dont_write_bytecode == bytecode
        assert not (tmp_path / "__pycache__").exists()
    finally:
        sys.modules.pop(name, None)
