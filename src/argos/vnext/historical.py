"""Diagnostic historical evidence, deliberately unavailable to the online controller."""

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from argos.contracts import qualified
from argos.provenance import write_json
from argos.search.candidates import Domain
from argos.types import Candidate, candidate_from_dict, observation_from_dict
from argos.vnext.offline import OLD, OUT, ROOT, SOURCES, read, record


def main():
    refs = ROOT.parent / "condor_flexdc_v4"
    report = read(refs / "reports/trackS_v6_summary.json")
    hu = next(r for r in report if r["short"] == "W2HU")
    point = hu["verdict"]["best_sim_feasible_seed20"]
    historical = Candidate(
        "historical-diagnostic-only",
        point["Pbar_kw_per_server"],
        point["R_kw_per_server"],
        tuple(point["weights"]),
        "historical diagnostic",
    )
    manifest = read(OLD / "campaign_manifest.json")
    cases = [c for c in manifest["cases"] if c["case_id"] in ["c005", "c006", "c007", "c008"]]
    dense_path = record(
        refs / "traditional_iso16_newqos_plus_w2dense_AQA_combined_grid_search_results.csv"
    )
    counts = {
        c["case_id"]: {"rows": 0, "numerical_feasible": 0, "best_objective": None} for c in cases
    }
    for chunk in pd.read_csv(dense_path, chunksize=10000):
        for case in cases:
            sub = chunk[
                (chunk.Workload_Name == case["workload"])
                & (chunk.server_count == 1000)
                & np.isclose(chunk.utilization, case["settings"]["utilization"])
            ]
            for row in sub.to_dict("records"):
                value = counts[case["case_id"]]
                value["rows"] += 1
                if (
                    row["Ctrack_Epsilon_90th"] <= 0.3
                    and max(json.loads(row["QoS_Delay_Probabilities"])) <= 0.1
                ):
                    value["numerical_feasible"] += 1
                    obj = row["Diagnostic_FullPaperObjective_Cost"]
                    value["best_objective"] = min(value["best_objective"] or float("inf"), obj)
    provenance = read(ROOT / "configs/campaigns/provenance_v1.json")
    splits = []
    for split in provenance["v3_splits"]:
        path = record(ROOT / split["path"])
        frame = pd.read_csv(path, nrows=0)
        splits.append(
            {
                "split": split["split"],
                "path": str(path),
                "matches_pinned_hash": SOURCES[str(path)]["sha256"] == split["sha256"],
                "rows": split["rows"],
                "seed_counts": split["seed_counts"],
                "columns": list(frame),
                "original_W2_counts": {
                    c["case_id"]: {"rows": 0, "numerical_feasible": 0} for c in cases
                },
            }
        )
    for split in splits:
        for frame in pd.read_csv(split["path"], chunksize=10000):
            for c in cases:
                sub = frame[
                    (frame.Workload_Name == c["workload"])
                    & (frame.server_count == 1000)
                    & np.isclose(frame.utilization, c["settings"]["utilization"])
                ]
                split["original_W2_counts"][c["case_id"]]["rows"] += len(sub)
                split["original_W2_counts"][c["case_id"]]["numerical_feasible"] += int(
                    ((sub.Actual_P90_Tracking <= 0.3) & (sub.Actual_Max_Pj <= 0.1)).sum()
                )
    c8 = next(c for c in cases if c["case_id"] == "c008")
    bank = OLD / "cache/v3_banks" / c8["bank_id"]
    meta = read(bank / "manifest.json")
    domain = Domain(**meta["domain"])
    selected = candidate_from_dict(read(bank / meta["completed_attempt"] / "selection.json"))
    physical = np.array(
        [
            selected.Pbar - historical.Pbar,
            selected.R - historical.R,
            *np.subtract(selected.weights, historical.weights),
        ]
    )
    distance = {
        "current_candidate": asdict(selected),
        "historical_point": asdict(historical),
        "signed_difference_P_R_weights": physical.tolist(),
        "P_R_l2_kw_per_server": float(np.linalg.norm(physical[:2])),
        "weight_l2": float(np.linalg.norm(physical[2:])),
        "normalized_domain_distance": domain.distance(selected, historical),
        "normalized_coordinate_difference": (
            domain.encode(selected) - domain.encode(historical)
        ).tolist(),
        "historical_verdict": hu["verdict"],
        "provenance_limit": "Different historical model/search, includes anchors and known feasible rows; not a fair V3/H1 baseline. Numerical historical feasibility; original per-job count evidence is not asserted from this summary.",
    }
    racing = []
    for case in cases:
        for method in ["v3_only", "argos_fixed_budget"]:
            state = read(OLD / "cases" / case["case_id"] / method / "state.json")
            winner = state.get("incumbent")
            if not winner:
                continue
            c = candidate_from_dict(winner)
            obs = [observation_from_dict(o) for o in state["observations"]]
            same = [
                o
                for o in obs
                if (o.candidate.Pbar, o.candidate.R, o.candidate.weights)
                == (c.Pbar, c.R, c.weights)
            ]
            rows = [
                {
                    "phase": o.phase,
                    "seed": o.seed,
                    "qualified": qualified(o),
                    "metrics": asdict(o.metrics),
                    "execution_id": o.execution_id,
                }
                for o in same
            ]
            outcomes = [qualified(o) for o in same]
            racing.append(
                {
                    "case": case["case_id"],
                    "method": method,
                    "observations": rows,
                    "retrospective_state_after_all": "SCENARIO_FRAGILE"
                    if not all(outcomes)
                    else "SEARCH_ROBUST_FEASIBLE"
                    if len({o.seed for o in same}) >= 2
                    else "PROVISIONAL_FEASIBLE",
                    "diagnostic_only": True,
                    "confirmation_not_available_to_historical_controller": True,
                    "order_dependence": "With two passes and one fail, two-pass screening accepts if failure comes third, rejects if it comes first/second. Full observed record is fragile."
                    if sum(outcomes) == 2 and len(outcomes) == 3
                    else None,
                }
            )
    record(refs / "run_trackS_v6.py")
    record(refs / "sim_plan_v6.py")
    record(refs / "sim_validation/plans/plan_W2HU_r2.csv")
    record(refs / "sim_validation/plans/plan_W2HU_verify.csv")
    record(Path(__file__))
    write_json(
        OUT / "historical_geometry.json",
        {
            "c008_distance": distance,
            "dense_W2": counts,
            "training_provenance": splits,
            "racing": racing,
            "dense_evidence_limit": "Counts are numerical feasibility from historical aggregate CSV; no claim of new H1-contract-qualified replications; no warm starts.",
        },
    )
    write_json(OUT / "historical_inputs.json", SOURCES)
    print(
        json.dumps(
            {
                "distance": distance["normalized_domain_distance"],
                "physical_difference": physical.tolist(),
                "dense_counts": counts,
                "training_hashes_match": all(s["matches_pinned_hash"] for s in splits),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
