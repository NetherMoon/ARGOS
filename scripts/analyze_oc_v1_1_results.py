"""Build compact, read-only scientific summaries from completed OC1.x runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from argos.oc_basic import runner as v1
from argos.oc_basic.runner_v1_1 import _existence_prior, _read_rows, _states, _v1_prior
from argos.oc_basic.v1_1 import signed_scenario_violation
from argos.provenance import read_json


def _all_rows(source: Path, output: Path, mode: str) -> tuple[list[dict], list[dict]]:
    new = _read_rows(output / "search" / "new_scenario_executions.csv")
    prior = (_v1_prior(source)[1] if mode == "development" else
             _existence_prior(source)[1] if mode == "existence" else [])
    return prior + new, new


def _plot_progress(figures: Path, events: pd.DataFrame, summary: dict) -> None:
    if events.empty:
        return
    x = events.wall_seconds.to_numpy(dtype=float) / 60
    for column, ylabel, filename, target in (
        ("best_g8", "Best complete-panel g8", "best_g8_vs_time.png", 0),
        ("best_support", "Best complete-panel support / 10", "best_support_vs_time.png", 8),
        ("best_eligible_objective", "Lowest eligible mean objective", "best_eligible_objective_vs_time.png", None),
        ("new_calls", "New FlexDC calls completed", "simulator_calls_vs_time.png", None),
    ):
        y = pd.to_numeric(events[column], errors="coerce")
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.step(x, y, where="post", color="#215e91", linewidth=1.8)
        if target is not None:
            ax.axhline(target, color="#b93535", linestyle="--", linewidth=1)
        ax.set(xlabel="New search wall time (minutes)", ylabel=ylabel,
               title=f"{summary['mode']}: {ylabel}")
        ax.grid(alpha=0.2)
        fig.tight_layout()
        fig.savefig(figures / filename, dpi=160)
        plt.close(fig)


def _plot_geometry(figures: Path, candidates: pd.DataFrame, states: pd.DataFrame, mode: str) -> None:
    frame = candidates.merge(states, on="candidate_id", how="left")
    frame = frame[frame.scenarios_evaluated.fillna(0) > 0].copy()
    if frame.empty:
        return
    for column, filename, label in (
        ("passes", "pbar_r_pass_count.png", "Observed passes (partial or full)"),
        ("g8", "pbar_r_g8.png", "g8 on complete panels"),
    ):
        fig, ax = plt.subplots(figsize=(8, 5))
        color = pd.to_numeric(frame[column], errors="coerce")
        points = ax.scatter(frame.Pbar, frame.R, c=color, cmap="viridis", s=55, vmin=0 if column == "passes" else None)
        fig.colorbar(points, ax=ax, label=label)
        ax.set(xlabel="Pbar (kW/server)", ylabel="R (kW/server)", title=f"{mode}: measured bids")
        fig.tight_layout()
        fig.savefig(figures / filename, dpi=160)
        plt.close(fig)
    weights = np.array([json.loads(w) for w in frame.weights])
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, w in enumerate(weights):
        alpha = .85 if frame.complete_panel.iloc[i] else .3
        ax.plot(range(4), w, alpha=alpha, color=plt.cm.viridis(min(1, float(frame.passes.iloc[i]) / 10)))
    ax.set_xticks(range(4), v1.JOB_NAMES)
    ax.set(ylabel="Scheduling weight", title=f"{mode}: measured bid weights")
    fig.tight_layout()
    fig.savefig(figures / "weight_space.png", dpi=160)
    plt.close(fig)


def _plot_matrix(figures: Path, rows: list[dict], panel: list[int], mode: str) -> None:
    ids = list(dict.fromkeys(r["candidate_id"] for r in rows))
    if not ids:
        return
    score = np.full((len(ids), len(panel)), np.nan)
    for r in rows:
        score[ids.index(r["candidate_id"]), panel.index(int(r["arrival_seed"]))] = signed_scenario_violation(r)
    fig, ax = plt.subplots(figsize=(11, min(13, max(4, .28 * len(ids) + 2))))
    ax.imshow(np.where(np.isnan(score), 0.5, np.where(score <= 0, 0, 1)), aspect="auto", cmap="RdYlGn_r", vmin=0, vmax=1)
    ax.set_xticks(range(10), [str(s) for s in panel], rotation=60, ha="right", fontsize=7)
    ax.set_yticks(range(len(ids)), ids, fontsize=5 if len(ids) > 35 else 7)
    ax.set(xlabel="Search arrival seed", ylabel="Measured candidate", title=f"{mode}: green pass, red fail, yellow unmeasured")
    fig.tight_layout()
    fig.savefig(figures / "candidate_arrival_pass_matrix.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, min(13, max(4, .28 * len(ids) + 2))))
    bounded = np.clip(score, -0.5, 5)
    image = ax.imshow(bounded, aspect="auto", cmap="coolwarm", vmin=-0.5, vmax=5)
    fig.colorbar(image, ax=ax, label="Signed normalized worst-constraint violation")
    ax.set_xticks(range(10), [str(s) for s in panel], rotation=60, ha="right", fontsize=7)
    ax.set_yticks(range(len(ids)), ids, fontsize=5 if len(ids) > 35 else 7)
    ax.set(xlabel="Search arrival seed", ylabel="Measured candidate", title=f"{mode}: critical-seed violations")
    fig.tight_layout()
    fig.savefig(figures / "critical_seed_violation_heatmap.png", dpi=180)
    plt.close(fig)


def analyze(source: Path, output: Path) -> dict:
    identity = read_json(output / "manifest.json")
    status = read_json(output / "run_status.json")
    if not status["status"].startswith("COMPLETE"):
        raise ValueError("OC stage has not completed")
    summary = read_json(output / "summary.json")
    panel = [int(s) for s in identity["seed_order"]]
    all_rows, new_rows = _all_rows(source, output, identity["mode"])
    candidates = v1.read_candidate_batches(output)
    if identity["mode"] in ("development", "existence"):
        prior_candidates = (_v1_prior(source)[0] if identity["mode"] == "development"
                            else _existence_prior(source)[0])
        candidates = {**prior_candidates, **candidates}
    states = _states(candidates, all_rows, panel)
    state_frame = pd.DataFrame([s.__dict__ for s in states])
    candidate_frame = pd.DataFrame([v1.candidate_row(c) for c in candidates.values()])
    events = []
    prior = [r for r in all_rows if r not in new_rows]
    for i, current in enumerate(sorted(new_rows, key=lambda r: r["cumulative_search_wall_seconds"]), 1):
        observed = prior + sorted(new_rows, key=lambda r: r["cumulative_search_wall_seconds"])[:i]
        current_states = _states(candidates, observed, panel)
        full = [s for s in current_states if s.g8 is not None]
        eligible = [s for s in full if s.passes >= 8]
        events.append({"wall_seconds": current["cumulative_search_wall_seconds"], "new_calls": i,
                       "best_g8": min((s.g8 for s in full), default=None),
                       "best_support": max((s.passes for s in full), default=0),
                       "best_eligible_objective": min((s.mean_objective_all_ten for s in eligible), default=None),
                       "candidate_id": current["candidate_id"]})
    event_frame = pd.DataFrame(events)
    prior_eligible = any(s.complete_panel and s.passes >= 8 for s in _states(candidates, prior, panel))
    first = next((e for e in events if e["best_support"] >= 8), None)
    failure_counts = {name: sum(name in str(r.get("failure_constraints", "")).split(",") for r in new_rows)
                      for name in ("tracking", *v1.JOB_NAMES, "evidence")}
    analysis = {"first_8of10_new_call": 0 if prior_eligible else first["new_calls"] if first else None,
                "first_8of10_seconds": 0.0 if prior_eligible else first["wall_seconds"] if first else None,
                "prior_eligible_candidate_reused": prior_eligible,
                "new_failure_constraint_counts": failure_counts,
                "new_calls": len(new_rows), "complete_candidate_count": sum(s.complete_panel for s in states),
                "eligible_candidate_count": sum(s.passes >= 8 and s.complete_panel for s in states)}
    v1.atomic_json(output / "analysis_summary.json", analysis)
    v1.atomic_csv(output / "search" / "progress_events.csv", events)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    _plot_progress(figures, event_frame, summary)
    _plot_geometry(figures, candidate_frame, state_frame, identity["mode"])
    _plot_matrix(figures, all_rows, panel, identity["mode"])
    return analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a completed OC1.x run without FlexDC")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    print(json.dumps(analyze(source, args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
