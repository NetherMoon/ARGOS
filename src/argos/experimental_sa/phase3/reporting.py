"""Compact Phase 3 summaries, presentation figures, report, and upload ZIP."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

JOBS = ["ResNet", "GPT2", "Llama", "Bloom"]


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf8"))


def _rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]


def _write_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _flatten_assessment(value: dict) -> dict:
    raw = value["raw"]
    obj = value["objective"]
    feasibility = value["feasibility"]
    row = {
        "cell_id": value["cell_id"],
        "case": value["case"],
        "candidate_source": value["candidate_source"],
        "selection": value["selection"],
        "sa_success": value["sa_success"],
        "seed": int(value["seed"]),
        "Pbar": value["params"][0],
        "R": value["params"][1],
        "weights": json.dumps(value["params"][2:], separators=(",", ":")),
        "p90": raw["p90"],
        "M_RSR": obj["M_RSR"],
        "Ctrack": obj["Ctrack"],
        "CQoS": obj["CQoS"],
        "Cfull": obj["Cfull"],
        "max_Pj": max(raw["Pj"]),
        "Bloom_Pj": raw["Pj"][3],
        "evidence_counts": json.dumps(raw["evidence_counts"], separators=(",", ":")),
        "pass": feasibility["feasible"],
        "initial_job_table_hash": raw["initial_job_table_hash"],
        "grid_signal_hash": raw["grid_signal_hash"],
        "target_trace_hash": raw["target_trace_hash"],
    }
    for index, name in enumerate(JOBS):
        row[f"{name}_Pj"] = raw["Pj"][index]
    failures = []
    if raw["p90"] > 0.30:
        failures.append("tracking")
    failures.extend(name for name, pj in zip(JOBS, raw["Pj"], strict=True) if pj > 0.10)
    row["failure_reasons"] = "+".join(failures) if failures else "NONE"
    return row


def _optimization_summary(experiment: Path) -> tuple[list[dict], list[dict]]:
    summaries = []
    selected = []
    for name in ["A_fixed", "A_varying", "B_fixed", "B_varying"]:
        rows = _rows(experiment / "optimization" / name / "iterations.jsonl")
        result = _read(experiment / "optimization" / name / "result.json")
        valid = [x for x in rows if x["feasibility"]["valid"]]
        feasible = [x for x in valid if x["feasibility"]["feasible"]]
        accepted = [x for x in rows[1:] if x["accepted"]]
        summary = {
            "trajectory": name,
            "case": name[0],
            "method": name.split("_", 1)[1],
            "status": result["status"],
            "evaluations_completed": len(rows),
            "simulator_calls": result["simulator_calls"],
            "valid_count": len(valid),
            "valid_fraction": len(valid) / len(rows),
            "feasible_count": len(feasible),
            "feasible_fraction": len(feasible) / len(rows),
            "first_feasible_iteration": min((x["iteration"] for x in feasible), default=None),
            "best_feasible_objective": None
            if result["best_feasible"] is None
            else result["best_feasible"]["objective"]["Cfull"],
            "best_feasible_iteration": None
            if result["best_feasible"] is None
            else int(result["best_feasible"]["candidate_id"].rsplit(":", 1)[1]),
            "best_scalar_objective": result["best_scalar"]["objective"]["Cfull"],
            "best_scalar_iteration": int(result["best_scalar"]["candidate_id"].rsplit(":", 1)[1]),
            "final_current_objective": result["current"]["objective"]["Cfull"],
            "acceptance_count": len(accepted),
            "acceptance_rate": len(accepted) / max(1, len(rows) - 1),
            "feasible_acceptance_count": sum(
                x["accepted"] and x["feasibility"]["feasible"] for x in rows[1:]
            ),
            "tracking_failure_count": sum(x["raw"]["p90"] > 0.30 for x in valid),
            "Bloom_failure_count": sum(x["raw"]["Pj"][3] > 0.10 for x in valid),
            "distinct_arrival_seeds": len({x["scenario"]["arrival_seed"] for x in rows}),
            "distinct_initial_hashes": len({x["raw"]["initial_job_table_hash"] for x in valid}),
        }
        for index, job in enumerate(JOBS):
            summary[f"{job}_failure_count"] = sum(x["raw"]["Pj"][index] > 0.10 for x in valid)
        summaries.append(summary)
        item = result["best_feasible"] or result["best_violation"]
        selected.append(
            {
                "trajectory": name,
                "case": name[0],
                "method": name.split("_", 1)[1],
                "selection": "best_feasible"
                if result["best_feasible"]
                else "best_violation_diagnostic",
                "sa_success": result["best_feasible"] is not None,
                "candidate_id": item["candidate_id"],
                "Pbar": item["params"][0],
                "R": item["params"][1],
                "weights": json.dumps(item["params"][2:], separators=(",", ":")),
                "optimization_objective": item["objective"]["Cfull"],
            }
        )
    return summaries, selected


def _assessment_summary(data: pd.DataFrame) -> list[dict]:
    rows = []
    for (case, source), group in data.groupby(["case", "candidate_source"], sort=False):
        item = {
            "case": case,
            "candidate_source": source,
            "tested_scenarios": len(group),
            "pass_count": int(group["pass"].sum()),
            "tracking_failure_count": int((group["p90"] > 0.30).sum()),
            "mean_p90": group["p90"].mean(),
            "median_p90": group["p90"].median(),
            "min_p90": group["p90"].min(),
            "max_p90": group["p90"].max(),
            "mean_Cfull": group["Cfull"].mean(),
            "median_Cfull": group["Cfull"].median(),
            "min_Cfull": group["Cfull"].min(),
            "max_Cfull": group["Cfull"].max(),
        }
        for job in JOBS:
            values = group[f"{job}_Pj"]
            item[f"{job}_failure_count"] = int((values > 0.10).sum())
            for statistic in ["mean", "median", "min", "max"]:
                item[f"{statistic}_{job}_Pj"] = getattr(values, statistic)()
        rows.append(item)
    return rows


def _paired(data: pd.DataFrame) -> list[dict]:
    rows = []
    for case in data["case"].unique():
        subset = data[data.case == case]
        wide = subset.pivot(
            index="seed", columns="candidate_source", values=["pass", "p90", "Bloom_Pj", "Cfull"]
        )
        for seed, row in wide.iterrows():
            fixed = bool(row[("pass", "fixed-SA")])
            varying = bool(row[("pass", "varying-SA")])
            rows.append(
                {
                    "case": case,
                    "seed": int(seed),
                    "fixed_pass": fixed,
                    "varying_pass": varying,
                    "classification": "V_PASS_F_FAIL"
                    if varying and not fixed
                    else "F_PASS_V_FAIL"
                    if fixed and not varying
                    else "BOTH_PASS"
                    if fixed
                    else "BOTH_FAIL",
                    "delta_varying_minus_fixed_p90": row[("p90", "varying-SA")]
                    - row[("p90", "fixed-SA")],
                    "delta_varying_minus_fixed_Bloom_Pj": row[("Bloom_Pj", "varying-SA")]
                    - row[("Bloom_Pj", "fixed-SA")],
                    "delta_varying_minus_fixed_Cfull": row[("Cfull", "varying-SA")]
                    - row[("Cfull", "fixed-SA")],
                    "delta_varying_minus_starting_p90": row[("p90", "varying-SA")]
                    - row[("p90", "starting")],
                    "delta_fixed_minus_starting_p90": row[("p90", "fixed-SA")]
                    - row[("p90", "starting")],
                    "delta_varying_minus_starting_Bloom_Pj": row[("Bloom_Pj", "varying-SA")]
                    - row[("Bloom_Pj", "starting")],
                    "delta_fixed_minus_starting_Bloom_Pj": row[("Bloom_Pj", "fixed-SA")]
                    - row[("Bloom_Pj", "starting")],
                    "delta_varying_minus_starting_Cfull": row[("Cfull", "varying-SA")]
                    - row[("Cfull", "starting")],
                    "delta_fixed_minus_starting_Cfull": row[("Cfull", "fixed-SA")]
                    - row[("Cfull", "starting")],
                }
            )
    return rows


def _plots(experiment: Path, assessment: pd.DataFrame) -> None:
    plots = experiment / "plots"
    colors = {"fixed-SA": "#4472C4", "varying-SA": "#ED7D31", "starting": "#777777"}
    for case, assessment_case in [("A", "c005"), ("B", "c007")]:
        plt.figure(figsize=(8, 4.5))
        for method in ["fixed", "varying"]:
            rows = _rows(experiment / "optimization" / f"{case}_{method}" / "iterations.jsonl")
            best = []
            value = np.nan
            for row in rows:
                if row["feasibility"]["feasible"]:
                    candidate = row["objective"]["Cfull"]
                    value = candidate if np.isnan(value) else min(value, candidate)
                best.append(value)
            plt.plot(range(len(best)), best, label=method)
        plt.xlabel("Iteration")
        plt.ylabel("Best feasible objective")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plots / f"{case}_best_feasible_objective.png", dpi=160)
        plt.close()
        fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
        for method in ["fixed", "varying"]:
            rows = _rows(experiment / "optimization" / f"{case}_{method}" / "iterations.jsonl")
            axes[0].plot(
                [x["iteration"] for x in rows], [x["raw"]["p90"] for x in rows], label=method
            )
            axes[1].plot(
                [x["iteration"] for x in rows], [x["raw"]["Pj"][3] for x in rows], label=method
            )
        axes[0].axhline(0.30, color="red", linestyle="--")
        axes[1].axhline(0.10, color="red", linestyle="--")
        axes[0].set_ylabel("p90")
        axes[1].set_ylabel("Bloom Pj")
        axes[1].set_xlabel("Iteration")
        axes[0].legend()
        fig.tight_layout()
        fig.savefig(plots / f"{case}_constraint_trajectory.png", dpi=160)
        plt.close(fig)
        subset = assessment[assessment.case == assessment_case]
        for metric, limit in [("Bloom_Pj", 0.10), ("p90", 0.30)]:
            fig, ax = plt.subplots(figsize=(9, 4.5))
            for source in ["starting", "fixed-SA", "varying-SA"]:
                group = subset[subset.candidate_source == source].sort_values("seed")
                ax.plot(range(1, 11), group[metric], marker="o", label=source, color=colors[source])
            ax.axhline(limit, color="red", linestyle="--")
            ax.set_xlabel("Predeclared assessment scenario")
            ax.set_ylabel(metric)
            ax.legend()
            fig.tight_layout()
            fig.savefig(plots / f"{case}_assessment_{metric}.png", dpi=160)
            plt.close(fig)
    pivot = assessment.pivot_table(
        index=["case", "seed"], columns="candidate_source", values="pass", aggfunc="first"
    )
    fig, ax = plt.subplots(figsize=(7, 7))
    image = ax.imshow(
        pivot[["starting", "fixed-SA", "varying-SA"]].astype(int),
        aspect="auto",
        cmap="RdYlGn",
        vmin=0,
        vmax=1,
    )
    ax.set_xticks(range(3), ["starting", "fixed-SA", "varying-SA"])
    ax.set_yticks(range(len(pivot)), [f"{a}-{b}" for a, b in pivot.index])
    ax.set_title("Independent assessment pass/fail")
    fig.colorbar(image, ax=ax, ticks=[0, 1])
    fig.tight_layout()
    fig.savefig(plots / "assessment_pass_fail.png", dpi=160)
    plt.close(fig)
    selected = pd.read_csv(experiment / "selected_candidates.csv")
    fig, ax = plt.subplots(figsize=(6.5, 5))
    for _, row in selected.iterrows():
        ax.scatter(row["Pbar"], row["R"], label=row["trajectory"], s=65)
    assessment_points = assessment[assessment.candidate_source == "starting"].drop_duplicates(
        ["case", "Pbar", "R"]
    )
    for _, row in assessment_points.iterrows():
        label = "A_starting" if row["case"] == "c005" else "B_starting"
        ax.scatter(row["Pbar"], row["R"], marker="x", s=80, label=label)
    ax.set_xlabel("Pbar (kW/server)")
    ax.set_ylabel("R (kW/server)")
    ax.set_title("Starting and selected candidate locations")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plots / "selected_candidate_PR_locations.png", dpi=160)
    plt.close(fig)


def build_final_outputs(root: Path, experiment: Path, rebuild_zip: bool = False) -> None:
    optimization, selected = _optimization_summary(experiment)
    _write_csv(experiment / "optimization_summary.csv", optimization)
    _write_csv(experiment / "selected_candidates.csv", selected)
    results = []
    for path in sorted((experiment / "assessment/cells").glob("*/result.json")):
        results.append(_flatten_assessment(_read(path)))
    if len(results) != 60:
        raise ValueError(f"Expected 60 assessment results, found {len(results)}")
    _write_csv(experiment / "assessment_results.csv", results)
    frame = pd.DataFrame(results)
    summaries = _assessment_summary(frame)
    _write_csv(experiment / "assessment_summary.csv", summaries)
    paired = _paired(frame)
    _write_csv(experiment / "paired_assessment_comparison.csv", paired)
    failures = []
    for (case, source), group in frame.groupby(["case", "candidate_source"]):
        counts = Counter(group["failure_reasons"])
        failures.extend(
            {
                "case": case,
                "candidate_source": source,
                "failure_combination": reason,
                "count": count,
            }
            for reason, count in counts.items()
        )
    _write_csv(experiment / "failure_summary.csv", failures)
    arrivals = []
    for name in ["A_fixed", "A_varying", "B_fixed", "B_varying"]:
        for row in _rows(experiment / "optimization" / name / "iterations.jsonl"):
            for summary in row["raw"]["arrival_summary"]:
                arrivals.append(
                    {
                        "trajectory": name,
                        "iteration": row["iteration"],
                        "arrival_seed": row["scenario"]["arrival_seed"],
                        **summary,
                    }
                )
    _write_csv(experiment / "arrival_generation_summary.csv", arrivals)
    _plots(experiment, frame)
    lines = [
        "# Phase 3 — Fixed-arrival vs arrival-uncertainty SA",
        "",
        "This report describes a predeclared proof-of-concept experiment. X/10 values are tested-scenario pass counts, not certified reliability probabilities.",
        "",
        "## Independent assessment",
        "",
    ]
    for row in summaries:
        lines.append(
            f"- {row['case']} {row['candidate_source']}: passed {row['pass_count']} of 10 predeclared fresh assessment scenarios; tracking failures {row['tracking_failure_count']}; Bloom failures {row['Bloom_failure_count']}."
        )
    lines += ["", "## Paired varying-SA versus fixed-SA", ""]
    paired_frame = pd.DataFrame(paired)
    for case, group in paired_frame.groupby("case"):
        counts = Counter(group["classification"])
        lines.append(
            f"- {case}: V pass/F fail {counts['V_PASS_F_FAIL']}; F pass/V fail {counts['F_PASS_V_FAIL']}; both pass {counts['BOTH_PASS']}; both fail {counts['BOTH_FAIL']}."
        )
    lines += [
        "",
        "The optimization-training feasibility rate is not interpreted as reliability. Candidates were frozen before the independent panel was evaluated, and the panel did not alter candidate selection.",
    ]
    (experiment / "report.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    if rebuild_zip:
        build_zip(experiment)


def build_zip(experiment: Path) -> Path:
    zip_path = experiment.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(
        str(experiment), "zip", root_dir=experiment.parent, base_dir=experiment.name
    )
    if not zip_path.exists():
        raise RuntimeError("ZIP construction failed")
    return zip_path
