"""Read-only numerical audit of the frozen OC-basic v1 experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from argos.search.candidates import Domain
from argos.types import Candidate

JOBS = ("ResNet", "GPT2", "Llama", "Bloom")
LIMITS = (0.30, 0.10, 0.10, 0.10, 0.10)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate(data: dict) -> Candidate:
    return Candidate(
        data["candidate_id"], float(data["Pbar"]), float(data["R"]),
        tuple(float(x) for x in data["weights"]), data["source"],
    )


def score(row: dict) -> tuple[float | None, str, list[float]]:
    if row["execution_status"] != "COMPLETE" or row["evidence_valid"] != "True":
        return None, "invalid_evidence", []
    values = [float(row["p90"]), *json.loads(row["Pj"])]
    signed = [v / limit - 1 for v, limit in zip(values, LIMITS)]
    maximum = max(signed)
    names = ("tracking", *JOBS)
    active = "+".join(name for name, value in zip(names, signed) if value > 0)
    return maximum, active or "none", signed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    run, out = args.run_dir.resolve(), args.output_dir.resolve()
    if out == run or out.is_relative_to(run):
        raise ValueError("Write forensic evidence outside the frozen v1 run")
    status = read_json(run / "run_status.json")
    if status["status"] != "COMPLETE_NO_TARGET_CANDIDATE":
        raise ValueError("Unexpected historical run status")
    manifest = read_json(run / "manifest.json")
    timing = read_json(run / "timing.json")
    summary = read_json(run / "summary.json")
    seed_panel = read_json(run / "arrival_panel" / "seeds.json")
    table_hashes = read_json(run / "arrival_panel" / "table_hashes.json")
    tables = read_csv(run / "arrival_panel" / "table_manifest.csv")
    cloud = read_csv(run / "v3" / "candidate_cloud.csv")
    v3_timing = read_json(run / "v3" / "timing.json")
    aggregates = read_csv(run / "search" / "all_candidate_panels.csv")
    executions = read_csv(run / "search" / "all_scenario_executions.csv")
    search_timing = read_json(run / "search" / "search_timing.json")
    batch1 = read_json(run / "search" / "batch_001_candidates.json")
    batch2 = read_json(run / "search" / "batch_002_candidates.json")
    batch1_csv = read_csv(run / "search" / "batch_001_candidates.csv")
    batch2_csv = read_csv(run / "search" / "batch_002_candidates.csv")
    batch1_results = read_csv(run / "search" / "batch_001_results.csv")
    batch2_results = read_csv(run / "search" / "batch_002_results.csv")
    if (
        len(batch1) != 10
        or len(batch1_csv) != 10
        or len(batch2) != 6
        or len(batch2_csv) != 6
        or len(batch1_results) != 10
        or len(batch2_results) != 1
        or len(aggregates) != 11
        or len(executions) != 110
        or len(tables) != 10
        or len(cloud) < 100
    ):
        raise ValueError("Unexpected v1 artifact counts")
    seeds = [int(x) for x in seed_panel["search_arrival_seeds"]]
    if len(seeds) != 10 or len(set(seeds)) != 10:
        raise ValueError("Invalid frozen seed panel")
    by_seed_table = {int(x["arrival_seed"]): x for x in tables}
    if set(by_seed_table) != set(seeds):
        raise ValueError("Table manifest and seed panel disagree")
    for seed, table in by_seed_table.items():
        if table["initial_job_table_hash"] != table_hashes[str(seed)]:
            raise ValueError("Frozen job-table identity mismatch")
    domain_manifest = read_json(Path(v3_timing["bank_path"]) / "manifest.json")
    domain = Domain(**domain_manifest["domain"])
    candidates = {x["candidate_id"]: candidate(x) for x in [*batch1, *batch2]}
    measured_ids = {x["candidate_id"] for x in aggregates}
    if measured_ids != {x["candidate_id"] for x in batch1} | {batch2[0]["candidate_id"]}:
        raise ValueError("Unexpected v1 measured candidate sequence")
    if [x["candidate_id"] for x in aggregates] != [x["candidate_id"] for x in batch1] + [batch2[0]["candidate_id"]]:
        raise ValueError("Candidate execution order does not match frozen batches")
    for c in candidates.values():
        domain.validate(c)

    matrix = []
    by_candidate: dict[str, list[dict]] = defaultdict(list)
    by_seed: dict[int, list[dict]] = defaultdict(list)
    for row in executions:
        seed, cid = int(row["arrival_seed"]), row["candidate_id"]
        g, bottleneck, signed = score(row)
        if seed not in seeds or cid not in measured_ids or g is None:
            raise ValueError("Unexpected or invalid historical execution")
        if (
            row["runtime_seed"] != str(seed_panel["search_runtime_seed"])
            or row["initial_job_table_hash"] != table_hashes[str(seed)]
            or row["grid_signal_hash"] != manifest["grid_trace_hash"]
        ):
            raise ValueError("Search cell identity mismatch")
        pj = json.loads(row["Pj"])
        feasible = g <= 0
        if feasible != (row["feasible"] == "True"):
            raise ValueError("Archived feasibility disagrees with signed score")
        item = {
            "candidate_id": cid, "candidate_source": row["candidate_source"],
            "batch": next(int(x["batch"]) for x in aggregates if x["candidate_id"] == cid),
            "arrival_seed": seed, "p90": float(row["p90"]),
            **{f"Pj_{name}": float(p) for name, p in zip(JOBS, pj)},
            "objective": float(row["objective"]), "feasible": feasible,
            "active_failing_constraints": bottleneck, "signed_g": g,
            "tracking_normalized_margin": -signed[0],
            **{f"{name}_normalized_margin": -signed[i + 1] for i, name in enumerate(JOBS)},
        }
        matrix.append(item)
        by_candidate[cid].append(item)
        by_seed[seed].append(item)
    if any(len(rows) != 10 or {r["arrival_seed"] for r in rows} != set(seeds) for rows in by_candidate.values()):
        raise ValueError("Incomplete historical candidate panel")
    write_csv(out / "diagnostics" / "current_run_candidate_seed_matrix.csv", matrix)

    robust = []
    for aggregate in aggregates:
        cid = aggregate["candidate_id"]
        rows = by_candidate[cid]
        ordered = sorted(rows, key=lambda r: (r["signed_g"], r["arrival_seed"]))
        passes = sum(r["feasible"] for r in rows)
        repair_count = max(0, 8 - passes)
        required = [r for r in ordered if r["signed_g"] > 0][:repair_count]
        if passes != int(aggregate["arrival_pass_count"]):
            raise ValueError("Archived candidate pass count mismatch")
        robust.append({
            "candidate_id": cid, "candidate_source": aggregate["candidate_source"],
            "batch": int(aggregate["batch"]), "Pbar": float(aggregate["Pbar"]),
            "R": float(aggregate["R"]), "weights": aggregate["weights"],
            "arrival_pass_count": passes, "g8": ordered[7]["signed_g"],
            "g9": ordered[8]["signed_g"], "g10": ordered[9]["signed_g"],
            "worst_violation": ordered[-1]["signed_g"],
            "mean_signed_violation": statistics.mean(r["signed_g"] for r in rows),
            "mean_objective_all_ten": statistics.mean(r["objective"] for r in rows),
            "repair_count": repair_count,
            "repair_sum": sum(r["signed_g"] for r in required),
            "critical_failure_seeds": json.dumps([r["arrival_seed"] for r in required]),
            "pass_vector": "".join("1" if next(r for r in rows if r["arrival_seed"] == s)["feasible"] else "0" for s in seeds),
        })
    write_csv(out / "diagnostics" / "current_run_robust_scores.csv", robust)
    winner = min(robust, key=lambda r: (-r["arrival_pass_count"], r["g8"], r["repair_sum"]))
    winner_id = winner["candidate_id"]
    winner_rows = sorted(by_candidate[winner_id], key=lambda r: (r["signed_g"], r["arrival_seed"]))
    write_csv(out / "diagnostics" / "best_5of10_failure_analysis.csv", winner_rows)

    seed_rows = []
    for seed in seeds:
        rows = by_seed[seed]
        counts = Counter(x for r in rows for x in r["active_failing_constraints"].split("+") if x != "none")
        passed = sum(r["feasible"] for r in rows)
        seed_rows.append({
            "arrival_seed": seed, "passed_candidate_count": passed,
            "minimum_signed_g": min(r["signed_g"] for r in rows),
            "median_signed_g": statistics.median(r["signed_g"] for r in rows),
            "dominant_failing_constraint": counts.most_common(1)[0][0] if counts else "none",
            "minimum_Bloom_Pj": min(r["Pj_Bloom"] for r in rows),
            "minimum_p90": min(r["p90"] for r in rows),
            "winner_passed": next(r for r in rows if r["candidate_id"] == winner_id)["feasible"],
            "descriptive_difficulty": "easier" if passed >= 4 else "intermediate" if passed >= 2 else "difficult",
        })
    write_csv(out / "diagnostics" / "arrival_seed_difficulty.csv", seed_rows)

    pairs = []
    for a, b in combinations(robust, 2):
        av, bv = a["pass_vector"], b["pass_vector"]
        pairs.append({
            "candidate_a": a["candidate_id"], "candidate_b": b["candidate_id"],
            "normalized_domain_distance": domain.distance(candidates[a["candidate_id"]], candidates[b["candidate_id"]]),
            "both_passed": sum(x == y == "1" for x, y in zip(av, bv)),
            "a_only_seeds": json.dumps([s for s, x, y in zip(seeds, av, bv) if x == "1" and y == "0"]),
            "b_only_seeds": json.dumps([s for s, x, y in zip(seeds, av, bv) if x == "0" and y == "1"]),
            "union_coverage": sum(x == "1" or y == "1" for x, y in zip(av, bv)),
            "hamming_distance": sum(x != y for x, y in zip(av, bv)),
        })
    write_csv(out / "diagnostics" / "candidate_complementarity.csv", pairs)

    predictions = {x["candidate_id"]: x.get("prediction") for x in batch1 + batch2}
    missing_predictions = [cid for cid in measured_ids if predictions[cid] is None]
    if missing_predictions:
        # The old controller did not score its local probe. This read-only
        # diagnostic uses the same frozen V3 adapter after all decisions ended.
        from argos.fixed_table.protocol import load_source
        from argos.surrogate.v3_adapter import V3Adapter

        root = Path(manifest["scientific_root"])
        spec = load_source(root)
        adapter = V3Adapter(root, threads=2, device="auto")
        context_seed = v3_timing["bank_v3_context_seed"]
        workload, experiment = adapter.context(
            root / spec["cases"][manifest["workload"]]["workload_path"],
            root / spec["experiment_path"], 1000, 0.6, context_seed,
        )
        for cid in missing_predictions:
            c = candidates[cid]
            p = adapter.predict(workload, experiment, c.Pbar, c.R, list(c.weights))
            predictions[cid] = {
                "mean_tracking": p["Predicted_Mean_Tracking"],
                "p90": p["Predicted_P90_Tracking"],
                "pj": p["Predicted_QoS_Probabilities"],
                "objective": p["Predicted_Full_Objective"],
            }
    prediction_rows = []
    for r in robust:
        cid, actual = r["candidate_id"], by_candidate[r["candidate_id"]]
        p = predictions[cid]
        if p is None:
            raise ValueError("Missing offline V3 prediction")
        values = {"p90": [x["p90"] for x in actual],
                  **{name: [x[f"Pj_{name}"] for x in actual] for name in JOBS},
                  "objective": [x["objective"] for x in actual]}
        prediction_rows.append({
            "candidate_id": cid, "source": r["candidate_source"],
            "prediction_origin": "archived" if cid not in missing_predictions else "posthoc_same_frozen_V3",
            "predicted_mean_tracking": float(p["mean_tracking"]),
            "predicted_p90": float(p["p90"]),
            **{f"predicted_Pj_{name}": float(v) for name, v in zip(JOBS, p["pj"])},
            "predicted_objective": float(p["objective"]),
            **{f"actual_{stat}_{metric}": func(sorted(v)) for metric, v in values.items()
               for stat, func in (("mean", statistics.mean), ("median", statistics.median),
                                  ("worst", max), ("eighth_smallest", lambda seq: seq[7]))},
            "actual_pass_count": r["arrival_pass_count"], "actual_g8": r["g8"],
        })
    write_csv(out / "diagnostics" / "v3_vs_multiarrival_measured.csv", prediction_rows)

    feature_rows = []
    for seed in seeds:
        t = by_seed_table[seed]
        w = next(r for r in by_candidate[winner_id] if r["arrival_seed"] == seed)
        feature_rows.append({
            "arrival_seed": seed,
            **{k: t[k] for k in t if k not in ("arrival_seed", "context_path", "table_file_sha256")},
            "winner_Bloom_Pj": w["Pj_Bloom"], "winner_p90": w["p90"],
            "winner_signed_g": w["signed_g"], "winner_feasible": w["feasible"],
            "pass_count_across_11_candidates": next(x["passed_candidate_count"] for x in seed_rows if x["arrival_seed"] == seed),
        })
    write_csv(out / "diagnostics" / "arrival_table_failure_features.csv", feature_rows)

    parallel_rows = []
    for aggregate in aggregates:
        cid = aggregate["candidate_id"]
        elapsed = [float(r["elapsed_seconds"]) for r in executions if r["candidate_id"] == cid]
        wall = float(aggregate["wave_wall_seconds"])
        parallel_rows.append({
            "candidate_id": cid, "batch": aggregate["batch"],
            "panel_wall_seconds": wall, "sum_individual_elapsed_seconds": sum(elapsed),
            "max_individual_elapsed_seconds": max(elapsed),
            "min_individual_elapsed_seconds": min(elapsed),
            "median_individual_elapsed_seconds": statistics.median(elapsed),
            "estimated_worker_utilization": sum(elapsed) / (10 * wall),
            "straggler_gap_vs_median_seconds": max(elapsed) - statistics.median(elapsed),
        })
    write_csv(out / "diagnostics" / "panel_parallelism.csv", parallel_rows)

    receipt = {
        "historical_manifest_sha256": sha256(run / "manifest.json"),
        "historical_search_csv_sha256": sha256(run / "search" / "all_scenario_executions.csv"),
        "historical_v3_cloud_sha256": sha256(run / "v3" / "candidate_cloud.csv"),
        "historical_status": status,
        "historical_timing": timing,
        "search_timing": search_timing,
        "historical_summary": summary,
        "initial_candidates_evaluated": len(batch1_results),
        "adaptive_candidates_generated": len(batch2),
        "adaptive_candidates_evaluated": len(batch2_results),
        "adaptive_candidates_unevaluated": len(batch2) - len(batch2_results),
        "initial_call_fraction": 100 / 110,
        "best_candidate_id": winner_id,
        "best_pass_count": winner["arrival_pass_count"],
        "best_g8": winner["g8"],
        "best_repair_sum": winner["repair_sum"],
        "v3_posthoc_prediction_ids": missing_predictions,
        "source_files_sha256": {p: sha256(Path(__file__).resolve().parents[1] / p) for p in (
            "src/argos/oc_basic/core.py", "src/argos/oc_basic/runner.py",
            "src/argos/search/candidates.py", "src/argos/vnext/controller.py",
            "src/argos/vnext/mechanisms.py",
        )},
    }
    (out / "diagnostics" / "audit_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("best_candidate_id", "best_pass_count", "best_g8", "best_repair_sum", "initial_call_fraction")}, indent=2))


if __name__ == "__main__":
    main()
