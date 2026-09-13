import configparser
from pathlib import Path

import pytest

from argos.simulator.configuration import canonical_costs, gradient_config, overlay, read_ini

ROOT = Path(__file__).resolve().parents[2]


def test_overlay_preserves_unrelated_settings(tmp_path):
    root = ROOT
    if not (root / ".deps/FlexDC").exists():
        pytest.skip("Pinned FlexDC required")
    p = gradient_config(root, tmp_path / "gradient.ini")
    c = read_ini(p)
    assert c.getfloat("calculate_gradient", "psi1") == 1
    assert c.getfloat("gradient_driver", "beta") == 20
    assert c.getfloat("gradient_driver", "num_iterations") == 200
    assert canonical_costs(root).qos_constraint == 0.1
    source = tmp_path / "bad.ini"
    source.write_text("[system]\nx=1\nx=2\n")
    with pytest.raises(configparser.DuplicateOptionError):
        overlay(root, source, tmp_path / "out.ini", {("system", "x"): "3"})
    source.write_text("[system]\nx=1\n")
    with pytest.raises(ValueError):
        overlay(root, source, tmp_path / "out.ini", {("system", "missing"): "3"})
