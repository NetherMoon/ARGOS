"""Two-call, non-scientific fixed-table integration smoke; refuses a second launch."""

from __future__ import annotations

import json
from dataclasses import replace

from argos.contracts import assessment
from argos.experimental_sa.paper_consistent.evaluator import prepare
from argos.fixed_table.protocol import (
    GRID_TRACE_HASH,
    ROOT,
    WORKLOADS,
    config_for,
    load_plan,
    load_source,
)
from argos.fixed_table.simulator import FixedTableSimulator
from argos.provenance import write_json
from argos.types import Candidate

ARRIVAL = 1841060571
RUNTIME_ONLY = 2381098110
OUTPUT = ROOT / "runs/diagnostics/fixed_table_argos_smoke_20260922"
PARAMETERS = (
    0.473702073097229,
    0.10366622393131254,
    (0.26254186034202576, 0.2516586482524872, 0.2489594668149948, 0.23684002459049225),
)
EXPECTED = {
    "p90": 0.285,
    "Pj": (0.0, 0.06880049400504296, 0.0, 0.011801861702127714),
    "objective": 87.67387938485652,
}


def main():
    if OUTPUT.exists():
        raise FileExistsError(
            "The bounded two-call smoke has already started; inspect its preserved results"
        )
    seeds, _ = load_plan(ROOT)
    spec = load_source(ROOT)
    case = spec["cases"][WORKLOADS[0]]
    context, _, _ = prepare(ROOT, OUTPUT, spec, case, ARRIVAL, GRID_TRACE_HASH)
    config = replace(
        config_for(WORKLOADS[0], seeds, 2),
        search_seed=ARRIVAL,
        confirmation_seeds=(RUNTIME_ONLY, 2495920665, 144392579),
    )
    config.validate()
    simulator = FixedTableSimulator(ROOT, OUTPUT, config, context, 2)
    candidate = Candidate(
        "historical-smoke-only",
        PARAMETERS[0],
        PARAMETERS[1],
        PARAMETERS[2],
        "historical_parity_smoke",
    )
    first = simulator.evaluate_batch([candidate], ARRIVAL, "search", 1)[0]
    if not first.valid:
        raise RuntimeError(
            "First fixed-table replay failed; inspect preserved smoke cell: " + str(first.error)
        )
    actual = first.metrics
    if (
        abs(actual.p90 - EXPECTED["p90"]) > 1e-12
        or any(abs(a - b) > 1e-12 for a, b in zip(actual.pj, EXPECTED["Pj"]))
        or abs(actual.objective - EXPECTED["objective"]) > 1e-12
    ):
        raise ValueError("Historical same-seed replay differs; second smoke call blocked")
    second = simulator.evaluate_batch([candidate], RUNTIME_ONLY, "confirmation", 1)[0]
    if not second.valid:
        raise RuntimeError("Runtime-only seed-change smoke failed: " + str(second.error))
    if (
        first.reported["raw"]["initial_job_table_hash"]
        != second.reported["raw"]["initial_job_table_hash"]
        or first.reported["raw"]["grid_signal_hash"] != second.reported["raw"]["grid_signal_hash"]
        or first.reported["raw"]["target_trace_hash"] != second.reported["raw"]["target_trace_hash"]
    ):
        raise ValueError("Fixed table, grid or same-bid target changed during runtime-only smoke")
    write_json(
        OUTPUT / "smoke_result.json",
        {
            "full_flexdc_calls": 2,
            "role": "NON_SCIENTIFIC_HISTORICAL_PARITY_SMOKE",
            "arrival_seed": ARRIVAL,
            "runtime_seeds": [ARRIVAL, RUNTIME_ONLY],
            "initial_job_table_hash": context["initial_job_table_hash"],
            "historical_replay": {
                "p90": actual.p90,
                "Pj": actual.pj,
                "objective": actual.objective,
                "assessment": assessment(first),
            },
            "runtime_only_check": {
                "p90": second.metrics.p90,
                "Pj": second.metrics.pj,
                "objective": second.metrics.objective,
                "assessment": assessment(second),
            },
            "fixed_table_hash_match": True,
            "fixed_grid_hash_match": True,
            "same_bid_target_hash_match": True,
        },
    )
    print(json.dumps({"status": "PASS", "calls": 2, "output": str(OUTPUT)}))


if __name__ == "__main__":
    main()
