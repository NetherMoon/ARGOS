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
