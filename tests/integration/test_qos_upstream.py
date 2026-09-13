from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from argos.provenance import import_file
from argos.simulator.evidence import validate_reported_qos_evidence
from argos.types import JobIdentity

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".deps/FlexDC/src/peacsim/calculate_qos_cost.py"


@pytest.mark.skipif(
    not SOURCE.is_file(), reason="Pinned FlexDC source required for estimator parity"
)
@pytest.mark.parametrize("hours", [1, 3])
def test_exact_estimator_against_pinned_upstream(hours):
    api = import_file("_argos_qos_parity", SOURCE)
    rng = np.random.default_rng(23)
    arrivals = rng.integers(-100, hours * 3600, 200)
    ends = np.where(rng.random(200) > 0.4, arrivals + rng.integers(1, 3000, 200), -1)
    table = pd.DataFrame(
        {"job_type_id": rng.integers(0, 2, 200), "arrival_time": arrivals, "end_time": ends}
    )
    jobs = [JobIdentity(i, f"job{i}", (100, 200, 10 + 500 * i, 1000, 1, 1)) for i in range(3)]
    pj = api.calculate_delay_prob(
        hours, 3, table, {i: 1 for i in range(3)}, {i: 10 + 500 * i for i in range(3)}
    )
    result = validate_reported_qos_evidence(table, jobs, pj, sim_hour=hours)
    assert [e.pj for e in result] == pj
    assert result[2].observation_count == 0
