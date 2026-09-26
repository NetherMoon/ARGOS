"""Build the declared five-row OC-stage comparison from immutable run artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from argos.provenance import read_json


def _v1_row(path: Path) -> dict:
    summary = read_json(path / "summary.json")
    timing = read_json(path / "search" / "search_timing.json")
    audit = path.parents[1] / "diagnostics" / "oc_basic_v1_forensics_20260926" / "diagnostics" / "current_run_robust_scores.csv"
    if not audit.exists():
        raise FileNotFoundError("Verified v1 robust-score audit is required", audit)
    best_g8 = float(pd.read_csv(audit).g8.min())
    return {
        "stage": "OC-basic v1", "protocol_version": "OC-basic v1",
        "warm_start_or_cold_start": "cold", "search_wall_limit": 1200,
        "measured_candidate_geometries": summary["measured_candidate_count"],
        "full_panels": summary["measured_candidate_count"], "partial_panels": 0,
        "early_rejected_candidates": 0,
        "total_FlexDC_executions": summary["search_simulator_executions"],
        "executions_saved_by_racing": 0, "max_workers": timing["max_workers"],
        "time_to_first_8of10": None, "calls_to_first_8of10": None,
        "best_pass_count": summary["best_search_arrival_pass_count"],
        "best_g8": best_g8,
        "eligible_candidates": summary["eligible_candidate_count"],
        "selected_objective": summary["selected_search_panel_mean_objective"],
        "fresh_assessment_result": None,
        "search_wall_seconds": timing["search_wall_seconds_total"],
        "notes": "Ten full initial panels consumed 100/110 calls; no held-out assessment",
    }


def _new_row(path: Path, stage: str, warm: bool) -> dict:
    summary = read_json(path / "summary.json")
    analysis = read_json(path / "analysis_summary.json")
    manifest = read_json(path / "manifest.json")
    assessment = path / "final" / "fresh_assessment_results.csv"
    outcome = None
    if assessment.exists():
        frame = pd.read_csv(assessment)
        outcome = f"{int(frame.feasible.astype(str).str.lower().eq('true').sum())}/{len(frame)}"
    return {
        "stage": stage, "protocol_version": summary["protocol_version"],
        "warm_start_or_cold_start": "warm development" if warm else "cold",
        "search_wall_limit": manifest["soft_search_seconds"],
        "measured_candidate_geometries": summary["measured_candidates"],
        "full_panels": summary["full_panels"], "partial_panels": summary["partial_panels"],
        "early_rejected_candidates": summary["early_rejected_candidates"],
        "total_FlexDC_executions": summary["new_simulator_executions"],
        "executions_saved_by_racing": summary["executions_saved_by_racing"],
        "max_workers": manifest["max_workers"],
        "time_to_first_8of10": analysis["first_8of10_seconds"],
        "calls_to_first_8of10": analysis["first_8of10_new_call"],
        "best_pass_count": summary["best_pass_count"], "best_g8": summary["best_g8"],
        "eligible_candidates": summary["eligible_candidates"],
        "selected_objective": summary["selected_mean_objective"],
        "fresh_assessment_result": outcome,
        "search_wall_seconds": summary["search_wall_seconds"],
        "notes": f"{summary['prior_simulator_executions_reused']} prior calls reused; {summary['stop_reason']}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Five-stage ARGOS-OC comparison; no FlexDC execution")
    for key in ("v1", "development", "existence", "cold20", "cold10"):
        parser.add_argument(f"--{key}", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = [
        _v1_row(args.v1),
        _new_row(args.development, "OC1.1 development continuation", True),
        _new_row(args.existence, "OC1.2 existence", True),
        _new_row(args.cold20, "OC1.3 20-minute cold start", False),
        _new_row(args.cold10, "OC1.3 10-minute cold start", False),
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)
    print(args.output)


if __name__ == "__main__":
    main()
