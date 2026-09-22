"""Exactly four fixed-candidate simulator replays, gated by saved Phase2C parity tests."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from argos.experimental_sa.paper_consistent.domain import load_domain
from argos.experimental_sa.paper_consistent.evaluator import FixedEvaluator, prepare
from argos.experimental_sa.paper_consistent.objective import ObjectiveContract
from argos.experimental_sa.paper_consistent.rng import search_rng, state
from argos.experimental_sa.paper_consistent.simulated_annealing import optimize

ROOT = Path(__file__).resolve().parents[1]


def run():
    out = (
        ROOT
        / json.loads((ROOT / "src/argos/experimental_sa/audit_location.json").read_text())[
            "directory"
        ]
    )
    m = json.loads((out / "manifest.json").read_text())
    assert m["parity"]["passed"]
    tests = ET.parse(out / "unit_tests.xml").getroot()
    assert not tests.findall(".//failure") and not tests.findall(".//error")
    if m["real_simulations"] or (out / "smoke_plan.json").exists():
        raise ValueError("Smoke already started; never automatically rerun")
    p2b = ROOT / m["phase2b_directory"]
    source = json.loads((p2b / "manifest.json").read_text())
    spec = source["specification"]
    p2 = ROOT / source["configuration"]["phase2_directory"]
    contract = ObjectiveContract(ROOT)
    plan = [
        ("c005", 1841060571, 1841060571, p2),
        ("c007", 3463391848, 3514694477, p2b),
        ("c007", 3463391848, 3463391848, p2b),
        ("c007", 3463391848, 3463391848, p2b),
    ]
    (out / "smoke_plan.json").write_text(
        json.dumps(
            [
                {
                    "case": c,
                    "arrival_seed": a,
                    "runtime_seed": r,
                    "source": str(s.relative_to(ROOT)),
                    "role": "exact_replay" if i < 3 else "repeat_control",
                }
                for i, (c, a, r, s) in enumerate(plan)
            ],
            indent=2,
        )
    )
    contexts = {}
    results = []
    raws = []
    rng = search_rng(20260919)
    for i, (case_id, arrival, runtime, oldroot) in enumerate(plan):
        case = next(c for c in spec["cases"] if c["case"] == case_id)
        params = (case["Pbar"], case["R"], *case["weights"])
        runout = out / "real_smoke" / case_id
        if case_id not in contexts:
            context, e, j = prepare(ROOT, runout, spec, case, arrival, source["expected_grid_hash"])
            contexts[case_id] = (context, e, j, FixedEvaluator(ROOT, runout))
        context, e, j, evaluate = contexts[case_id]
        domain = load_domain(ROOT, "argos_v3_physical", j, e)
        m["real_simulations"] += 1
        (out / "manifest.json").write_text(json.dumps(m, indent=2))
        before = state(rng)
        # Zero SA transitions: evaluate only the declared frozen candidate, log through the real SA API.
        result = optimize(
            params,
            domain,
            lambda p, k, r, evaluate=evaluate, i=i: evaluate(p, i, r),
            contract,
            list(j.all_jobs.values()),
            runout / f"evaluation_{i}.jsonl",
            run_id=f"smoke_{i}",
            search_seed=20260919,
            arrival_seed=arrival,
            runtime_seed=runtime,
            iterations=0,
            temperature=1000.0,
            cooling_rate=0.95,
            steps=(0.01, 0.01, 0.02),
        )
        (runout / f"result_{i}.json").write_text(json.dumps(result.to_dict(), indent=2))
        assert result.error is None, result.error
        raw = result.current["raw"]
        raws.append(raw)
        reference = json.loads(
            (oldroot / "cells" / f"{case_id}_a{arrival}_r{runtime}" / "result.json").read_text()
        )
        assert state(rng) == before
        assert raw["p90"] == reference["p90"]
        assert raw["Pj"] == reference["Pj"]
        assert raw["evidence_counts"] == reference["evidence_counts"]
        assert raw["M_RSR"] == reference["monetary_power"] + reference["monetary_tracking"]
        assert result.current["objective"]["Cfull"] == reference["objective"]
        assert result.current["feasibility"]["feasible"] == reference["evidence_qualified_pass"]
        for key in ["initial_job_table_hash", "grid_signal_hash", "target_trace_hash"]:
            assert raw[key] == reference[key]
        results.append(
            {
                "index": i,
                "case": case_id,
                "arrival_seed": arrival,
                "runtime_seed": runtime,
                "p90": raw["p90"],
                "Pj": json.dumps(raw["Pj"]),
                "evidence_counts": json.dumps(raw["evidence_counts"]),
                "M_RSR": raw["M_RSR"],
                "objective": result.current["objective"]["Cfull"],
                "feasible": result.current["feasibility"]["feasible"],
                "initial_job_table_hash": raw["initial_job_table_hash"],
                "grid_signal_hash": raw["grid_signal_hash"],
                "target_trace_hash": raw["target_trace_hash"],
                "search_rng_unchanged": True,
                "reference_match": "EXACT",
                "elapsed_seconds": raw["elapsed_seconds"],
                "passed": True,
            }
        )
        pd.DataFrame(results).to_csv(out / "real_smoke_results.csv", index=False)
        print("Exact replay passed", i + 1, "of4", case_id, arrival, runtime, flush=True)
    compare = [k for k in raws[2] if k != "elapsed_seconds"]
    assert all(raws[2][k] == raws[3][k] for k in compare)
    m["real_smoke_passed"] = True
    m["real_smoke_repeat_exact"] = True
    (out / "manifest.json").write_text(json.dumps(m, indent=2))
    print("Four real calls complete; zero SA transitions; no further simulations needed.")


if __name__ == "__main__":
    run()
