"""Phase 3B compact summaries, repeatability analysis, figures, report, and ZIP."""

from __future__ import annotations

import csv
import json
import zipfile
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .planning import CASES, METHODS, PHASE3, REPLICATES

JOBS = ["ResNet", "GPT2", "Llama", "Bloom"]
PANELS = ["A", "B", "COMBINED"]


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf8"))


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line]


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf8") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _failure_reasons(p90: float, pjs: list[float]) -> str:
    failures = []
    if p90 > 0.30:
        failures.append("tracking")
    failures.extend(name for name, value in zip(JOBS, pjs, strict=True) if value > 0.10)
    return "+".join(failures) if failures else "NONE"


def _flatten_assessment(value: dict) -> dict:
    raw = value["raw"]
    objective = value["objective"]
    feasibility = value["feasibility"]
    row = {
        "cell_id": value["cell_id"],
        "case_label": value["case_label"],
        "case": value["case"],
        "candidate_role": value["candidate_role"],
        "replicate": int(value["replicate"]),
        "method": value["method"],
        "selection": value["selection"],
        "sa_success": bool(value["sa_success"]),
        "optimization_candidate_id": value["optimization_candidate_id"],
        "panel": value["panel"],
        "panel_index": int(value["panel_index"]),
        "seed": int(value["seed"]),
        "arrival_seed": int(raw["arrival_seed"]),
        "runtime_seed": int(raw["runtime_seed"]),
        "Pbar": value["params"][0],
        "R": value["params"][1],
        "weights": json.dumps(value["params"][2:], separators=(",", ":")),
        "p90": raw["p90"],
        "M_RSR": objective["M_RSR"],
        "Ctrack": objective["Ctrack"],
        "CQoS": objective["CQoS"],
        "Cfull": objective["Cfull"],
        "max_Pj": max(raw["Pj"]),
        "evidence_counts": json.dumps(raw["evidence_counts"], separators=(",", ":")),
        "valid": bool(feasibility["valid"]),
        "complete_scenario_pass": bool(feasibility["feasible"]),
        "initial_job_table_hash": raw["initial_job_table_hash"],
        "grid_signal_hash": raw["grid_signal_hash"],
        "target_trace_hash": raw["target_trace_hash"],
        "failure_reasons": _failure_reasons(raw["p90"], raw["Pj"]),
    }
    for index, job in enumerate(JOBS):
        row[f"{job}_Pj"] = raw["Pj"][index]
    return row


def _with_combined(data: pd.DataFrame) -> pd.DataFrame:
    combined = data.copy()
    combined["panel"] = "COMBINED"
    combined["panel_index"] = combined.groupby(["case", "candidate_role"]).cumcount() + 1
    return pd.concat([data, combined], ignore_index=True)


def _average_feasible(group: pd.DataFrame) -> bool:
    return bool(
        group["p90"].mean() <= 0.30
        and all(group[f"{job}_Pj"].mean() <= 0.10 for job in JOBS)
    )


def _assessment_summaries(data: pd.DataFrame) -> list[dict]:
    rows = []
    expanded = _with_combined(data)
    for (case, role, replicate, method, panel), group in expanded.groupby(
        ["case", "candidate_role", "replicate", "method", "panel"], sort=False
    ):
        item = {
            "case": case,
            "candidate_role": role,
            "replicate": int(replicate),
            "method": method,
            "panel": panel,
            "tested_scenarios": len(group),
            "pass_count": int(group["complete_scenario_pass"].sum()),
            "proposed_8_of_10_scenario_criterion": (
                bool(group["complete_scenario_pass"].sum() >= 8)
                if panel in {"A", "B"}
                else "NOT_APPLICABLE"
            ),
            "average_metric_feasible": _average_feasible(group),
            "tracking_failure_count": int((group["p90"] > 0.30).sum()),
            "valid_count": int(group["valid"].sum()),
        }
        for metric in ["p90", "Cfull", *[f"{job}_Pj" for job in JOBS]]:
            values = group[metric]
            for statistic in ["mean", "median", "min", "max"]:
                item[f"{statistic}_{metric}"] = getattr(values, statistic)()
        for job in JOBS:
            item[f"{job}_failure_count"] = int((group[f"{job}_Pj"] > 0.10).sum())
        rows.append(item)
    return rows


def _optimization_summary(root: Path, experiment: Path) -> list[dict]:
    seed_plan = _read(experiment / "seed_plan.json")
    phase3_seed_plan = _read(root / PHASE3 / "seed_plan.json")
    items = []
    for replicate in (1, 2, 3):
        for label, case_id in CASES:
            for method in METHODS:
                if replicate == 1:
                    path = root / PHASE3 / "optimization" / f"{label}_{method}"
                    search_seed = phase3_seed_plan["search_seeds"][label]
                    search_root = ""
                    source = "historical_phase3_reused"
                else:
                    path = experiment / "optimization" / f"replicate_{replicate}" / f"{label}_{method}"
                    search_seed = ""
                    search_root = seed_plan["replicate_search_root_seeds"][f"replicate_{replicate}"]
                    source = "new_phase3b"
                rows = _rows(path / "iterations.jsonl")
                result = _read(path / "result.json")
                valid = [x for x in rows if x["feasibility"]["valid"]]
                feasible = [x for x in valid if x["feasibility"]["feasible"]]
                accepted = [x for x in rows[1:] if x["accepted"]]
                selected = result["best_feasible"] or result["best_violation"]
                item = {
                    "replicate": replicate,
                    "case_label": label,
                    "case": case_id,
                    "method": method,
                    "source": source,
                    "search_seed_phase3": search_seed,
                    "search_root_seed_phase3b": search_root,
                    "status": result["status"],
                    "evaluations_completed": len(rows),
                    "simulator_calls_recorded": result["simulator_calls"],
                    "accepted_transitions": len(accepted),
                    "acceptance_rate": len(accepted) / max(1, len(rows) - 1),
                    "feasible_evaluations": len(feasible),
                    "first_feasible_iteration": min((x["iteration"] for x in feasible), default=None),
                    "selected_best_feasible_iteration": (
                        int(result["best_feasible"]["candidate_id"].rsplit(":", 1)[1])
                        if result["best_feasible"]
                        else None
                    ),
                    "best_feasible_training_objective": (
                        result["best_feasible"]["objective"]["Cfull"]
                        if result["best_feasible"]
                        else None
                    ),
                    "best_scalar_objective": result["best_scalar"]["objective"]["Cfull"],
                    "final_current_objective": result["current"]["objective"]["Cfull"],
                    "selected_candidate_id": selected["candidate_id"],
                    "selection": "best_feasible" if result["best_feasible"] else "diagnostic_best_violation",
                    "Pbar": selected["params"][0],
                    "R": selected["params"][1],
                    "weights": json.dumps(selected["params"][2:], separators=(",", ":")),
                    "tracking_failure_count": sum(x["raw"]["p90"] > 0.30 for x in valid),
                    "distinct_arrival_seeds": len({x["scenario"]["arrival_seed"] for x in rows}),
                    "distinct_initial_hashes": len({x["raw"]["initial_job_table_hash"] for x in valid}),
                }
                for index, job in enumerate(JOBS):
                    item[f"{job}_failure_count"] = sum(x["raw"]["Pj"][index] > 0.10 for x in valid)
                items.append(item)
    return items


def _paired(data: pd.DataFrame) -> list[dict]:
    rows = []
    for case, _label_group in data.groupby("case"):
        for replicate in (1, 2, 3):
            fixed_role = f"replicate_{replicate}_fixed"
            varying_role = f"replicate_{replicate}_varying"
            subset = data[(data.case == case) & data.candidate_role.isin([fixed_role, varying_role])]
            wide = subset.pivot(index="seed", columns="candidate_role")
            for seed, row in wide.iterrows():
                fixed_pass = bool(row[("complete_scenario_pass", fixed_role)])
                varying_pass = bool(row[("complete_scenario_pass", varying_role)])
                item = {
                    "case": case,
                    "replicate": replicate,
                    "seed": int(seed),
                    "panel": row[("panel", fixed_role)],
                    "fixed_pass": fixed_pass,
                    "varying_pass": varying_pass,
                    "classification": (
                        "VARYING_ONLY_PASS"
                        if varying_pass and not fixed_pass
                        else "FIXED_ONLY_PASS"
                        if fixed_pass and not varying_pass
                        else "BOTH_PASS"
                        if fixed_pass
                        else "BOTH_FAIL"
                    ),
                    "delta_varying_minus_fixed_p90": row[("p90", varying_role)] - row[("p90", fixed_role)],
                    "delta_varying_minus_fixed_Cfull": row[("Cfull", varying_role)] - row[("Cfull", fixed_role)],
                }
                for job in JOBS:
                    item[f"delta_varying_minus_fixed_{job}_Pj"] = (
                        row[(f"{job}_Pj", varying_role)] - row[(f"{job}_Pj", fixed_role)]
                    )
                rows.append(item)
    return rows


def _repeatability(summary: pd.DataFrame) -> list[dict]:
    rows = []
    for case in summary.case.unique():
        for panel in PANELS:
            classifications = []
            averages = []
            for replicate in (1, 2, 3):
                fixed = summary[
                    (summary.case == case)
                    & (summary.panel == panel)
                    & (summary.candidate_role == f"replicate_{replicate}_fixed")
                ].iloc[0]
                varying = summary[
                    (summary.case == case)
                    & (summary.panel == panel)
                    & (summary.candidate_role == f"replicate_{replicate}_varying")
                ].iloc[0]
                classifications.append(
                    "varying_win"
                    if varying.pass_count > fixed.pass_count
                    else "fixed_win"
                    if fixed.pass_count > varying.pass_count
                    else "tie"
                )
                averages.append(
                    "varying_only"
                    if varying.average_metric_feasible and not fixed.average_metric_feasible
                    else "fixed_only"
                    if fixed.average_metric_feasible and not varying.average_metric_feasible
                    else "both"
                    if fixed.average_metric_feasible and varying.average_metric_feasible
                    else "neither"
                )
            pass_counts = Counter(classifications)
            average_counts = Counter(averages)
            rows.append(
                {
                    "case": case,
                    "panel": panel,
                    "varying_more_scenario_passes": pass_counts["varying_win"],
                    "fixed_more_scenario_passes": pass_counts["fixed_win"],
                    "scenario_pass_ties": pass_counts["tie"],
                    "average_feasible_varying_only": average_counts["varying_only"],
                    "average_feasible_fixed_only": average_counts["fixed_only"],
                    "average_feasible_both": average_counts["both"],
                    "average_feasible_neither": average_counts["neither"],
                    "replicate_count": 3,
                    "interpretation": "descriptive_repeatability_under_one_training_arrival_schedule",
                }
            )
    return rows


def _plots(experiment: Path, summary: pd.DataFrame, candidates: pd.DataFrame) -> None:
    plots = experiment / "plots"
    colors = {"fixed": "#4472C4", "varying": "#ED7D31", "starting": "#777777"}
    combined = summary[(summary.panel == "COMBINED") & (summary.method.isin(METHODS))]
    for case in ["c005", "c007"]:
        subset = combined[combined.case == case]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        x = np.arange(3)
        fixed = [subset[subset.candidate_role == f"replicate_{r}_fixed"].pass_count.iloc[0] for r in (1, 2, 3)]
        varying = [subset[subset.candidate_role == f"replicate_{r}_varying"].pass_count.iloc[0] for r in (1, 2, 3)]
        ax.bar(x - 0.18, fixed, 0.36, label="Fixed", color=colors["fixed"])
        ax.bar(x + 0.18, varying, 0.36, label="Varying", color=colors["varying"])
        ax.set_xticks(x, ["Rep 1", "Rep 2", "Rep 3"])
        ax.set_ylabel("Complete scenarios passed (of 20)")
        ax.set_title(f"{case}: fixed vs varying pass count")
        ax.legend()
        fig.tight_layout()
        fig.savefig(plots / f"{case}_pass_count_by_replicate.png", dpi=160)
        plt.close(fig)

    panel = summary[(summary.panel.isin(["A", "B"])) & (summary.method.isin(METHODS))]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, case in zip(axes, ["c005", "c007"], strict=True):
        subset = panel[panel.case == case]
        labels, values, bar_colors = [], [], []
        for replicate in (1, 2, 3):
            for method in METHODS:
                for panel_name in ["A", "B"]:
                    row = subset[(subset.candidate_role == f"replicate_{replicate}_{method}") & (subset.panel == panel_name)].iloc[0]
                    labels.append(f"R{replicate}{method[0].upper()}-{panel_name}")
                    values.append(row.pass_count)
                    bar_colors.append(colors[method])
        ax.bar(range(len(values)), values, color=bar_colors)
        ax.axhline(8, color="red", linestyle="--", label="proposed 8/10")
        ax.set_xticks(range(len(labels)), labels, rotation=60, ha="right", fontsize=8)
        ax.set_title(case)
        ax.set_ylabel("Panel pass count (of 10)")
        ax.legend()
    fig.tight_layout()
    fig.savefig(plots / "panel_A_B_pass_counts.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4.5))
    comp = summary[summary.panel == "COMBINED"].copy()
    labels = [f"{r.case}:{r.candidate_role}" for r in comp.itertuples()]
    ax.bar(range(len(comp)), comp.pass_count, color=[colors.get(x, "#777777") for x in comp.method])
    ax.set_xticks(range(len(comp)), labels, rotation=65, ha="right", fontsize=8)
    ax.set_ylabel("Complete scenarios passed (of 20)")
    ax.set_title("Combined fresh 20-seed assessment")
    fig.tight_layout()
    fig.savefig(plots / "combined_pass_counts.png", dpi=160)
    plt.close(fig)

    for metric, limit, filename, ylabel in [
        ("mean_p90", 0.30, "mean_p90_by_replicate.png", "Mean p90"),
        ("mean_Bloom_Pj", 0.10, "mean_Bloom_Pj_by_replicate.png", "Mean Bloom Pj"),
    ]:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
        for ax, case in zip(axes, ["c005", "c007"], strict=True):
            subset = combined[combined.case == case]
            for method in METHODS:
                values = [subset[subset.candidate_role == f"replicate_{r}_{method}"][metric].iloc[0] for r in (1, 2, 3)]
                ax.plot([1, 2, 3], values, marker="o", label=method, color=colors[method])
            ax.axhline(limit, color="red", linestyle="--")
            ax.set_xticks([1, 2, 3])
            ax.set_title(case)
            ax.set_xlabel("Replicate")
            ax.set_ylabel(ylabel)
            ax.legend()
        fig.tight_layout()
        fig.savefig(plots / filename, dpi=160)
        plt.close(fig)

    criteria = summary[summary.panel.isin(["A", "B", "COMBINED"])].copy()
    labels = [f"{r.case}:{r.candidate_role}:{r.panel}" for r in criteria.itertuples()]
    values = np.column_stack(
        [
            criteria.proposed_8_of_10_scenario_criterion.astype(str).eq("True").astype(int),
            criteria.average_metric_feasible.astype(int),
        ]
    )
    fig, ax = plt.subplots(figsize=(8, max(5, len(criteria) * 0.18)))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks([0, 1], ["Proposed 8/10", "Average feasible"])
    ax.set_yticks(range(len(labels)), labels, fontsize=6)
    ax.set_title("Scenario and average-metric criteria")
    fig.colorbar(image, ax=ax, ticks=[0, 1])
    fig.tight_layout()
    fig.savefig(plots / "criterion_summary.png", dpi=160)
    plt.close(fig)

    selected = candidates[candidates.method.isin(METHODS)]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    for case in ["c005", "c007"]:
        subset = selected[selected.case == case]
        marker = "o" if case == "c005" else "s"
        for method in METHODS:
            rows = subset[subset.method == method].sort_values("replicate")
            axes[0].plot(rows.Pbar, rows.R, marker=marker, label=f"{case}-{method}", color=colors[method])
            weights = np.array([json.loads(x) for x in rows.weights])
            axes[1].plot(rows.replicate, weights[:, 3], marker=marker, label=f"{case}-{method}", color=colors[method])
            axes[2].plot(rows.replicate, weights[:, 0], marker=marker, label=f"{case}-{method}", color=colors[method])
    axes[0].set_xlabel("Pbar"); axes[0].set_ylabel("R"); axes[0].set_title("Selected P/R")
    axes[1].set_xlabel("Replicate"); axes[1].set_ylabel("Bloom weight"); axes[1].set_title("Selected Bloom weight")
    axes[2].set_xlabel("Replicate"); axes[2].set_ylabel("ResNet weight"); axes[2].set_title("Selected ResNet weight")
    for ax in axes: ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(plots / "selected_parameters_across_replicates.png", dpi=160)
    plt.close(fig)


def _build_report(
    experiment: Path,
    summary: pd.DataFrame,
    paired: pd.DataFrame,
    repeatability: pd.DataFrame,
    candidates: pd.DataFrame,
) -> None:
    lines = [
        "# Phase 3B — Repeatability of fixed-arrival vs varying-arrival SA",
        "",
        "Phase 3B changes SA search randomness while holding the training-arrival schedule, optimization runtime seed, grid, starting candidates, simulator contract, and scientific objective/feasibility rules fixed.",
        "",
        "X/10 and X/20 values are tested-scenario pass counts, not certified reliability probabilities. The proposed 8/10 criterion is diagnostic and is not an official project requirement. Average metric feasibility and complete-scenario pass frequency answer different questions.",
        "",
        "## Candidate assessment",
        "",
    ]
    for case in ["c005", "c007"]:
        lines.append(f"### {case}")
        for role in ["starting", *[f"replicate_{r}_{m}" for r in (1, 2, 3) for m in METHODS]]:
            rows = summary[(summary.case == case) & (summary.candidate_role == role)]
            a = rows[rows.panel == "A"].iloc[0]
            b = rows[rows.panel == "B"].iloc[0]
            c = rows[rows.panel == "COMBINED"].iloc[0]
            lines.append(
                f"- {role}: Panel A {a.pass_count}/10 (8/10: {'YES' if a.proposed_8_of_10_scenario_criterion else 'NO'}, average feasible: {'YES' if a.average_metric_feasible else 'NO'}); "
                f"Panel B {b.pass_count}/10 (8/10: {'YES' if b.proposed_8_of_10_scenario_criterion else 'NO'}, average feasible: {'YES' if b.average_metric_feasible else 'NO'}); "
                f"combined {c.pass_count}/20 (average feasible: {'YES' if c.average_metric_feasible else 'NO'})."
            )
        lines.append("")
    lines += ["## Matched repeatability", ""]
    for case in ["c005", "c007"]:
        combined = repeatability[(repeatability.case == case) & (repeatability.panel == "COMBINED")].iloc[0]
        lines.append(
            f"- {case}: varying wins {combined.varying_more_scenario_passes}, fixed wins {combined.fixed_more_scenario_passes}, ties {combined.scenario_pass_ties} across three matched replicates on combined pass count."
        )
        for replicate in (1, 2, 3):
            fixed = summary[(summary.case == case) & (summary.panel == "COMBINED") & (summary.candidate_role == f"replicate_{replicate}_fixed")].iloc[0]
            varying = summary[(summary.case == case) & (summary.panel == "COMBINED") & (summary.candidate_role == f"replicate_{replicate}_varying")].iloc[0]
            pair = paired[(paired.case == case) & (paired.replicate == replicate)]
            counts = Counter(pair.classification)
            lines.append(
                f"  - Replicate {replicate}: fixed {fixed.pass_count}/20, varying {varying.pass_count}/20; "
                f"varying-only passes {counts['VARYING_ONLY_PASS']}, fixed-only passes {counts['FIXED_ONLY_PASS']}, both pass {counts['BOTH_PASS']}, both fail {counts['BOTH_FAIL']}; "
                f"mean deltas V-F: p90 {varying.mean_p90-fixed.mean_p90:+.6f}, Bloom Pj {varying.mean_Bloom_Pj-fixed.mean_Bloom_Pj:+.6f}, Cfull {varying.mean_Cfull-fixed.mean_Cfull:+.6f}."
            )
    lines += ["", "## Cross-replicate findings", ""]
    combined_summary = summary[summary.panel == "COMBINED"]
    total_varying_wins = 0
    total_fixed_wins = 0
    for case in ["c005", "c007"]:
        row = repeatability[(repeatability.case == case) & (repeatability.panel == "COMBINED")].iloc[0]
        total_varying_wins += int(row.varying_more_scenario_passes)
        total_fixed_wins += int(row.fixed_more_scenario_passes)
        lines.append(
            f"- {case}: varying had more combined scenario passes in {row.varying_more_scenario_passes}/3 replicates, fixed in {row.fixed_more_scenario_passes}/3, with {row.scenario_pass_ties}/3 ties. "
            f"Average-feasibility classifications were varying-only {row.average_feasible_varying_only}, fixed-only {row.average_feasible_fixed_only}, both {row.average_feasible_both}, neither {row.average_feasible_neither}."
        )
        selected_case = combined_summary[(combined_summary.case == case) & combined_summary.method.isin(METHODS)]
        tracking_failures = int(selected_case.tracking_failure_count.sum())
        bloom_failures = int(selected_case.Bloom_failure_count.sum())
        varying_bloom_failures = int(selected_case[selected_case.method == "varying"].Bloom_failure_count.sum())
        lines.append(
            f"  - Across the six selected SA candidates on the combined panel: tracking failures {tracking_failures}; Bloom failures {bloom_failures}; varying-candidate Bloom failures {varying_bloom_failures}."
        )
        for method in METHODS:
            points = candidates[(candidates.case == case) & (candidates.method == method)]
            weights = np.array([json.loads(x) for x in points.weights])
            weight_ranges = [float(weights[:, index].max() - weights[:, index].min()) for index in range(4)]
            lines.append(
                f"  - {method} selected-parameter ranges across replicates: Pbar {points.Pbar.min():.9f}–{points.Pbar.max():.9f}; R {points.R.min():.9f}–{points.R.max():.9f}; weight ranges {weight_ranges}."
            )
    panel_rows = summary[summary.panel.isin(["A", "B"])]
    criterion_disagreements = int(
        (panel_rows.proposed_8_of_10_scenario_criterion.astype(bool) != panel_rows.average_metric_feasible.astype(bool)).sum()
    )
    lines.append(
        f"- The proposed scenario criterion and average-metric feasibility disagreed in {criterion_disagreements} candidate-panel comparisons. Average metric feasibility and complete-scenario pass frequency answer different questions."
    )
    if total_varying_wins >= 4 and total_fixed_wins == 0:
        recommendation = "The descriptive pattern supports a next controlled experiment that introduces runtime uncertainty while preserving matched arrival panels."
    elif total_varying_wins > total_fixed_wins:
        recommendation = "The varying-arrival method is promising but not uniform; shared multi-scenario candidate evaluation is the safer next experiment before adding another randomness source."
    else:
        recommendation = "Search-path results are mixed; shared multi-scenario candidate evaluation or additional matched search replicates should precede vary-both experiments."
    lines += ["", "## Suggested next experiment", "", recommendation]
    lines += [
        "",
        "## Interpretation boundaries",
        "",
        "Optimization feasible-evaluation frequency is not interpreted as reliability. This design measures repeatability across SA search trajectories under one fixed 401-entry training-arrival schedule and one fixed optimization runtime seed. It does not establish robustness to a different training-arrival panel or different optimization runtime seeds.",
        "",
        "The next experimental choice should be based on the observed replicate pattern: repeatable varying-arrival wins support broader runtime/arrival uncertainty tests; mixed wins support shared multi-scenario candidate evaluation or additional matched search replicates. No next experiment is started automatically.",
    ]
    (experiment / "report.md").write_text("\n".join(lines) + "\n", encoding="utf8")


def build_final_outputs(root: Path, experiment: Path, rebuild_zip: bool = False) -> None:
    optimization = _optimization_summary(root, experiment)
    _write_csv(experiment / "optimization_replicate_summary.csv", optimization)
    result_paths = sorted((experiment / "assessment" / "cells").glob("*/result.json"))
    if len(result_paths) != 280:
        raise ValueError(f"Expected 280 assessment results, found {len(result_paths)}")
    results = [_flatten_assessment(_read(path)) for path in result_paths]
    _write_csv(experiment / "assessment_results.csv", results)
    frame = pd.DataFrame(results)
    if not (frame.arrival_seed == frame.runtime_seed).all() or not (frame.seed == frame.arrival_seed).all():
        raise ValueError("Assessment coupled-seed contract changed")
    summaries = _assessment_summaries(frame)
    _write_csv(experiment / "assessment_summary_by_panel.csv", summaries)
    summary = pd.DataFrame(summaries)
    scenario_columns = [
        "case", "candidate_role", "replicate", "method", "panel", "tested_scenarios",
        "pass_count", "proposed_8_of_10_scenario_criterion",
    ]
    _write_csv(experiment / "scenario_pass_summary.csv", summary[scenario_columns].to_dict("records"))
    average_columns = [
        "case", "candidate_role", "replicate", "method", "panel", "tested_scenarios",
        "mean_p90", *[f"mean_{job}_Pj" for job in JOBS], "average_metric_feasible",
    ]
    _write_csv(experiment / "average_metric_feasibility.csv", summary[average_columns].to_dict("records"))
    paired_rows = _paired(frame)
    _write_csv(experiment / "paired_fixed_varying.csv", paired_rows)
    repeatability_rows = _repeatability(summary)
    _write_csv(experiment / "method_repeatability_summary.csv", repeatability_rows)
    failures = []
    for (case, role, panel), group in _with_combined(frame).groupby(["case", "candidate_role", "panel"], sort=False):
        for reason, count in Counter(group.failure_reasons).items():
            failures.append({"case": case, "candidate_role": role, "panel": panel, "failure_combination": reason, "count": count})
    _write_csv(experiment / "failure_summary.csv", failures)
    candidates = pd.read_csv(experiment / "all_selected_candidates.csv")
    _plots(experiment, summary, candidates)
    _build_report(
        experiment,
        summary,
        pd.DataFrame(paired_rows),
        pd.DataFrame(repeatability_rows),
        candidates,
    )
    if rebuild_zip:
        build_zip(experiment)


def build_zip(experiment: Path) -> Path:
    zip_path = experiment.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    selected = []
    for path in experiment.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(experiment)
        parts = relative.parts
        include = len(parts) == 1
        include |= parts[0] in {"plots", "search_draw_schedule"}
        include |= parts[0] == "optimization" and path.name in {
            "checkpoint.json", "iterations.jsonl", "result.json", "trajectory.log"
        }
        include |= parts[:2] == ("assessment", "cells") and path.name == "result.json"
        if include and not path.name.endswith(".tmp"):
            selected.append(path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(selected):
            archive.write(path, Path(experiment.name) / path.relative_to(experiment))
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        raise RuntimeError("Phase 3B ZIP construction failed")
    return zip_path

