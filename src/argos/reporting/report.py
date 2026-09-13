"""Report every observation and distinguish selection from confirmation."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from argos.config import Config
from argos.contracts import QOS_LIMIT, TRACKING_LIMIT, feasible, violations
from argos.controller.argos_controller import SearchState
from argos.provenance import write_json


def report(episode: Path, config: Config, state: SearchState) -> dict:
    searches = [o for o in state.observations if o.phase == "search"]
    confirms = [o for o in state.observations if o.phase == "confirmation"]
    feasible_search = [o for o in searches if o.valid and feasible(o.metrics)]
    passes = sum(o.valid and feasible(o.metrics) for o in confirms)
    if state.phase not in {"DONE", "NO_BID"}:
        status = "INSUFFICIENT_EVIDENCE"
    elif not feasible_search:
        status = "NO_FEASIBLE_BID_FOUND_WITHIN_BUDGET"
    elif not confirms:
        status = "SIMULATOR_OBSERVED_FEASIBLE"
    elif passes == len(confirms) == len(config.confirmation_seeds):
        status = f"CONFIRMATION_{passes}_OF_{len(confirms)}_PASS"
    else:
        status = "CONFIRMATION_MIXED"
    selected = next(
        (
            o
            for o in searches
            if state.incumbent
            and o.candidate.candidate_id == state.incumbent.candidate_id
            and o.valid
        ),
        None,
    )
    summary = {
        "episode_id": episode.name,
        "status": status,
        "phase": state.phase,
        "stop_reason": state.stop_reason,
        "config": asdict(config),
        "search_calls": state.search_calls,
        "completed_search_observations": len(searches),
        "valid_search_observations": sum(o.valid for o in searches),
        "observed_feasible_count": len(feasible_search),
        "confirmation_passes": passes,
        "confirmation_runs": len(confirms),
        "max_workers": config.max_workers,
        "controller_wall_seconds": state.elapsed_seconds,
        "selected_search_observation": asdict(selected) if selected else None,
        "confirmation_observations": [asdict(o) for o in confirms],
        "failures": [
            {"execution_id": o.execution_id, "error": o.error, "status": o.status}
            for o in state.observations
            if not o.valid
        ],
    }
    rows = []
    for o in state.observations:
        row = {
            "candidate_id": o.candidate.candidate_id,
            "execution_id": o.execution_id,
            "Pbar": o.candidate.Pbar,
            "R": o.candidate.R,
            "weights": json.dumps(o.candidate.weights),
            "source": o.candidate.source,
            "region_id": o.candidate.region_id,
            "start_id": o.candidate.start_id,
            "iteration": o.candidate.iteration,
            "seed": o.seed,
            "phase": o.phase,
            "batch": o.batch,
            "worker": o.worker,
            "returncode": o.returncode,
            "runtime_seconds": o.runtime_seconds,
            "evidence_validity": o.valid,
            "status": o.status,
            "error": o.error,
            "raw_paths": json.dumps(o.raw_paths),
            "reported": json.dumps(o.reported),
            "residuals": json.dumps(o.residuals),
        }
        for prefix, metrics in [("predicted", o.candidate.prediction), ("actual", o.metrics)]:
            if metrics:
                worst, total = violations(metrics)
                row.update(
                    {
                        f"{prefix}_mean_tracking": metrics.mean_tracking,
                        f"{prefix}_p90": metrics.p90,
                        f"{prefix}_pj": json.dumps(metrics.pj),
                        f"{prefix}_objective": metrics.objective,
                        f"{prefix}_tracking_pass": metrics.p90 <= TRACKING_LIMIT,
                        f"{prefix}_qos_pass": max(metrics.pj) <= QOS_LIMIT,
                        f"{prefix}_numerical_feasibility": feasible(metrics),
                        f"{prefix}_tracking_margin": TRACKING_LIMIT - metrics.p90,
                        f"{prefix}_qos_margin": QOS_LIMIT - max(metrics.pj),
                        f"{prefix}_worst_violation": worst,
                        f"{prefix}_total_violation": total,
                    }
                )
        rows.append(row)
    (episode / "search").mkdir(exist_ok=True)
    table = pd.DataFrame(rows)
    table.to_csv(episode / "search/all_observations.csv", index=False)
    (episode / "final").mkdir(exist_ok=True)
    if len(table):
        table[table.phase == "confirmation"].to_csv(episode / "final/confirmation.csv", index=False)
    write_json(episode / "summary.json", summary)
    text = [
        f"# ARGOS episode {episode.name}",
        f"\nStatus: **{status}**",
        f"\nContext: {config.workload}; N={config.server_count}, utilization={config.utilization}, policy={config.policy}.",
        f"\nSearch: {state.search_calls} reserved calls, {state.completed_batches} completed batches, {config.max_workers} workers.",
        f"Controller wall time: {state.elapsed_seconds:.3f} s. See v3/search_timing.json for surrogate time.",
        f"\nObserved feasible candidates: {len(feasible_search)}. Independent confirmation: {passes}/{len(confirms)} pass.",
        f"\nStop reason: {state.stop_reason}.",
    ]
    if selected:
        text.extend(
            [
                f"\nFrozen candidate: Pbar={selected.candidate.Pbar:.9g}, R={selected.candidate.R:.9g}, weights={selected.candidate.weights}.",
                f"Selection seed={selected.seed}: p90={selected.metrics.p90}, Pj={selected.metrics.pj}, actual objective={selected.metrics.objective}.",
            ]
        )
    for o in confirms:
        text.append(f"\nConfirmation seed {o.seed}: {o.status}; metrics={o.metrics}.")
    for failure in summary["failures"]:
        text.append(f"\nInvalid observation: {failure}.")
    text.append(
        "\nA finite failed search does not establish mathematical infeasibility. Confirmation pass counts do not prove universal reliability. Search and confirmation observations remain separate. Full evidence and provenance are in the episode files."
    )
    (episode / "report.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    return summary
