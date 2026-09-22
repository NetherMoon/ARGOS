"""Compact descriptive outputs; no inferential claims from unreplicated cells."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from argos.diagnostics.seed_factorization_worker import atomic_json
from argos.diagnostics.workload_seed_forensics import read_json, sha, write_csv


def factor_effects(matrix):
    """Balanced fixed-panel descriptive decomposition; interaction is not replicated error."""
    a = np.asarray(matrix, dtype=float)
    if a.shape != (3, 3) or not np.isfinite(a).all():
        raise ValueError("Factor summaries require all nine valid cells")
    grand = float(a.mean())
    rows, cols = a.mean(axis=1), a.mean(axis=0)
    interaction = a - rows[:, None] - cols[None, :] + grand
    total = float(((a - grand) ** 2).sum())
    arrival = float(3 * ((rows - grand) ** 2).sum())
    runtime = float(3 * ((cols - grand) ** 2).sum())
    residual = float((interaction**2).sum())
    return {
        "grand_mean": grand,
        "range_all": float(np.ptp(a)),
        "row_means_arrival": rows.tolist(),
        "column_means_runtime": cols.tolist(),
        "runtime_ranges_at_fixed_arrival": np.ptp(a, axis=1).tolist(),
        "arrival_ranges_at_fixed_runtime": np.ptp(a, axis=0).tolist(),
        "runtime_variances_at_fixed_arrival_ddof0": a.var(axis=1).tolist(),
        "arrival_variances_at_fixed_runtime_ddof0": a.var(axis=0).tolist(),
        "ss_total": total,
        "ss_arrival": arrival,
        "ss_runtime": runtime,
        "ss_interaction": residual,
        "ss_arrival_fraction": arrival / total if total else None,
        "ss_runtime_fraction": runtime / total if total else None,
        "ss_interaction_fraction": residual / total if total else None,
        "interpretation": "descriptive selected panel; one observation per cell; no p-values",
    }


def flatten(result):
    row = {k: v for k, v in result.items() if k != "assessment"}
    for i, value in enumerate(result["Pj"]):
        row[f"Pj_{i}"] = value
    row["Bloom_Pj"] = result["Pj"][3]
    for k, v in list(row.items()):
        if isinstance(v, (list, dict)):
            row[k] = json.dumps(v, separators=(",", ":"))
    return row


def export(output, results, replay_checks, status, error=None):
    manifest = read_json(output / "manifest.json")
    all_rows = pd.DataFrame([flatten(r) for r in results])
    if all_rows.empty:
        all_rows = pd.DataFrame(
            columns=[
                "cell_id",
                "case",
                "arrival_seed",
                "runtime_seed",
                "p90",
                "Pj",
                "objective",
                "evidence_counts",
                "evidence_qualified_pass",
            ]
        )
    write_csv(output / "all_runs.csv", all_rows)
    check_columns = [
        "case",
        "seed",
        "field",
        "expected",
        "actual",
        "absolute_difference",
        "tolerance",
        "passed",
    ]
    write_csv(output / "replay_checks.csv", pd.DataFrame(replay_checks, columns=check_columns))
    tables = {}
    for name in ["per_job_run_summary", "qos_accounting", "queue_summary"]:
        frames = []
        for result in results:
            table = pd.read_csv(
                output / "cells" / result["cell_id"] / (name + ".csv"), float_precision="round_trip"
            )
            for key in ["cell_id", "case", "workload", "arrival_seed", "runtime_seed"]:
                table[key] = result[key]
            frames.append(table)
        frame = (
            pd.concat(frames, ignore_index=True)
            if frames
            else pd.DataFrame(
                columns=["cell_id", "case", "arrival_seed", "runtime_seed", "job_type_id"]
            )
        )
        tables[name] = frame
        write_csv(output / (name + ".csv"), frame)
    write_csv(
        output / "initial_job_table_hashes.csv",
        pd.DataFrame(
            [
                {
                    k: r[k]
                    for k in [
                        "case",
                        "arrival_seed",
                        "runtime_seed",
                        "initial_job_table_hash",
                        "arrival_hash",
                    ]
                }
                for r in results
            ],
            columns=[
                "case",
                "arrival_seed",
                "runtime_seed",
                "initial_job_table_hash",
                "arrival_hash",
            ],
        ),
    )
    write_csv(
        output / "grid_signal_hashes.csv",
        pd.DataFrame(
            [
                {
                    k: r[k]
                    for k in [
                        "case",
                        "arrival_seed",
                        "runtime_seed",
                        "grid_signal_hash",
                        "target_trace_hash",
                        "logged_target_hash",
                        "P_watts",
                        "R_watts",
                    ]
                }
                for r in results
            ],
            columns=[
                "case",
                "arrival_seed",
                "runtime_seed",
                "grid_signal_hash",
                "target_trace_hash",
                "logged_target_hash",
                "P_watts",
                "R_watts",
            ],
        ),
    )
    matrices_dir = output / "crossed_matrices"
    matrices_dir.mkdir(exist_ok=True)
    effects, matrices = [], {}
    for case in manifest["specification"]["cases"]:
        case_id, seeds = case["case"], case["seeds"]
        selected = all_rows[all_rows.case == case_id]
        for metric in [
            "p90",
            "Pj_0",
            "Pj_1",
            "Pj_2",
            "Pj_3",
            "Bloom_Pj",
            "objective",
            "evidence_qualified_pass",
        ]:
            if metric in selected and len(selected):
                mat = selected.pivot(
                    index="arrival_seed", columns="runtime_seed", values=metric
                ).reindex(index=seeds, columns=seeds)
            else:
                mat = pd.DataFrame(np.nan, index=seeds, columns=seeds)
            mat.index.name = "arrival_seed"
            mat.to_csv(matrices_dir / f"{case_id}_{metric}.csv")
            matrices[case_id, metric] = mat
            if mat.notna().all().all():
                result = {
                    "case": case_id,
                    "metric": metric,
                    **factor_effects(mat.to_numpy(dtype=float)),
                }
                effects.append(
                    {k: json.dumps(v) if isinstance(v, list) else v for k, v in result.items()}
                )
        for source, metric in [
            ("per_job_run_summary", "unfinished"),
            ("per_job_run_summary", "waiting_started_seconds_p90"),
            ("queue_summary", "queue_after_policy_mean"),
        ]:
            table = tables[source]
            if not table.empty:
                bloom = table[(table.case == case_id) & (table.job_type_id == 3)]
                mat = bloom.pivot(
                    index="arrival_seed", columns="runtime_seed", values=metric
                ).reindex(index=seeds, columns=seeds)
                if mat.notna().all().all():
                    result = {
                        "case": case_id,
                        "metric": "Bloom_" + metric,
                        **factor_effects(mat.to_numpy(dtype=float)),
                    }
                    effects.append(
                        {k: json.dumps(v) if isinstance(v, list) else v for k, v in result.items()}
                    )
    write_csv(
        output / "descriptive_factor_effects.csv",
        pd.DataFrame(effects)
        if effects
        else pd.DataFrame(
            columns=["case", "metric", "grand_mean", "ss_arrival", "ss_runtime", "ss_interaction"]
        ),
    )
    if results:
        make_plots(output, manifest, matrices, tables)
    note = f"""# W2 seed factorization — {status}

Completed cells: {len(results)}/18. Diagonals are included in 18, never extra simulations.
{("Error: " + error) if error else ""}

This is a frozen, deliberately selected 3x3 panel for each exact candidate. No statistical
significance or population reliability is established. Historical FAILs can pass replay
validation when reproduced faithfully. Missing cells are blank, not zero or failed QoS.

Read source_audit.md for exact pinned APIs, seed boundaries, precision and measurement rules.
The initial tables are verified against Phase 1 reconstructions; old simulator job-table
hashes were not retained, so that check is a reconstruction control, not an archived runtime hash.
All runtime variants of an arrival seed must match the same complete initial-table hash.
The actual sampled grid trace is identical globally; power targets are identical within each
candidate. Targets differ across candidates because their fixed physical P/R bids differ.

Waiting summaries describe jobs that started; never-started waiting times are separate censored
lower bounds. Completed sojourns and unfinished lower bounds are separate. The upstream Pj
sample excludes submit_time=0 and some late unfinished jobs. qos_accounting.csv retains both
the exact upstream estimator numerator/denominator and empirical threshold exceedance counts.
Queue/resource observations are post-policy at each integer second, including t=0 and t=3600.
The legacy waitingSum power column is pre-policy and must not be confused with post-policy queues.
Commanded caps are issued for subsequent progress; actual power and estimated power are separate.

Factor effects are descriptive. Row means summarize arrival seeds, column means runtime seeds.
At fixed runtime seed the same pseudorandom stream can be consumed at different event times;
this is part of the observed interaction, not proof of an independent additive cause.
SS_interaction is the unreplicated residual after row/column effects, not an error variance.
No ANOVA p-values are produced. Inspect Bloom queues, unfinished jobs, waiting and QoS support
alongside Pj before attributing changes to a mechanism.
"""
    (output / "report.md").write_text(note, encoding="utf8")
    manifest.update(status=status, completed_cells=len(results), error=error)
    atomic_json(output / "manifest.json", manifest)
    return archive(output)


def make_plots(output, manifest, matrices, tables):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plots = output / "plots"
    plots.mkdir(exist_ok=True)
    cases = manifest["specification"]["cases"]
    for metric, title, vmax in [
        ("Bloom_Pj", "Bloom Pj", None),
        ("evidence_qualified_pass", "Evidence-qualified pass (1) / fail (0)", 1),
        ("p90", "Tracking p90", None),
    ]:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
        finite = [m.to_numpy(dtype=float) for (c, k), m in matrices.items() if k == metric]
        maximum = (
            vmax
            if vmax is not None
            else max(float(np.nanmax(m)) for m in finite if np.isfinite(m).any())
        )
        for ax, case in zip(axes, cases):
            matrix = matrices[case["case"], metric].to_numpy(dtype=float)
            im = ax.imshow(
                np.ma.masked_invalid(matrix), vmin=0, vmax=max(maximum, 0.001), cmap="viridis"
            )
            labels = [str(s) for s in case["seeds"]]
            ax.set_xticks(range(3), labels, rotation=25, ha="right")
            ax.set_yticks(range(3), labels)
            ax.set_xlabel("Runtime seed")
            ax.set_ylabel("Arrival seed")
            ax.set_title(case["workload"])
            for i in range(3):
                for j in range(3):
                    ax.text(
                        j,
                        i,
                        f"{matrix[i, j]:.3f}" if np.isfinite(matrix[i, j]) else "missing",
                        ha="center",
                        va="center",
                        color="red",
                    )
            fig.colorbar(im, ax=ax, shrink=0.75)
        fig.suptitle(title)
        fig.savefig(plots / f"{metric}.png", dpi=140)
        plt.close(fig)
    summary = tables["per_job_run_summary"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    for col, case in enumerate(cases):
        rows = summary[(summary.case == case["case"]) & (summary.job_type_id == 3)]
        labels = [
            f"A{case['seeds'].index(int(a)) + 1}/R{case['seeds'].index(int(r)) + 1}"
            for a, r in zip(rows.arrival_seed, rows.runtime_seed)
        ]
        for ax, field, title in [
            (axes[0, col], "unfinished", "Bloom unfinished at horizon"),
            (axes[1, col], "waiting_started_seconds_p90", "Bloom p90 wait: started jobs (seconds)"),
        ]:
            ax.bar(labels, rows[field])
            ax.tick_params(axis="x", rotation=45)
            ax.set_title(case["case"] + ": " + title)
    fig.savefig(plots / "Bloom_unfinished_waiting.png", dpi=140)
    plt.close(fig)


def archive(output):
    """Compact allowlisted scientific evidence; never archive scratch or arbitrary files."""
    excluded = {"scratch", "__pycache__"}
    paths = []
    for path in output.rglob("*"):
        rel = path.relative_to(output)
        if not path.is_file() or any(
            part in excluded or part.startswith(".env") for part in rel.parts
        ):
            continue
        if path.name.endswith(".tmp") or path.name in {".campaign.lock", ".factorization.lock"}:
            continue
        if path.suffix not in {".json", ".csv", ".gz", ".md", ".png", ".py", ".ini", ".log"}:
            continue
        paths.append(path)
    if sum(p.stat().st_size for p in paths) > 150 * 1024**2:
        raise ValueError(
            "Compact artifact exceeds the 150 MiB safety bound; inspect before archiving"
        )
    integrity = output / "artifact_hashes.json"
    atomic_json(
        integrity, {p.relative_to(output).as_posix(): sha(p) for p in paths if p != integrity}
    )
    if integrity not in paths:
        paths.append(integrity)
    target = Path(str(output) + ".zip")
    temporary = Path(str(target) + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(paths):
            z.write(path, path.relative_to(output).as_posix())
    temporary.replace(target)
    return target
