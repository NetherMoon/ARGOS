"""Finite-panel Phase 2B summaries, presentation figures and compact packaging."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from argos.contracts import QOS_LIMIT, TRACKING_LIMIT
from argos.diagnostics.seed_factorization_reporting import archive
from argos.diagnostics.seed_factorization_worker import atomic_json
from argos.diagnostics.workload_seed_forensics import read_json, write_csv

JOBS = ["Resnet", "GPT2", "Llama", "Bloom"]
LABEL = "descriptive variance decomposition for this selected finite matrix; no p-values or population causal percentages"


def matrix_effects(matrix):
    a = np.asarray(matrix, dtype=float)
    if a.ndim != 2 or min(a.shape) < 2 or not np.isfinite(a).all():
        raise ValueError("A complete finite rectangular matrix is required")
    grand = a.mean()
    rows = a.mean(axis=1)
    cols = a.mean(axis=0)
    residual = a - rows[:, None] - cols[None, :] + grand
    total = float(((a - grand) ** 2).sum())
    arrival = float(a.shape[1] * ((rows - grand) ** 2).sum())
    runtime = float(a.shape[0] * ((cols - grand) ** 2).sum())
    interaction = float((residual**2).sum())
    return {
        "arrival_rows": a.shape[0],
        "runtime_columns": a.shape[1],
        "grand_mean": float(grand),
        "row_means": json.dumps(rows.tolist()),
        "column_means": json.dumps(cols.tolist()),
        "runtime_ranges_at_fixed_arrival": json.dumps(np.ptp(a, axis=1).tolist()),
        "arrival_ranges_at_fixed_runtime": json.dumps(np.ptp(a, axis=0).tolist()),
        "maximum_runtime_range": float(np.ptp(a, axis=1).max()),
        "maximum_arrival_range": float(np.ptp(a, axis=0).max()),
        "range_all": float(np.ptp(a)),
        "ss_total": total,
        "ss_arrival": arrival,
        "ss_runtime": runtime,
        "ss_interaction": interaction,
        "ss_arrival_fraction": arrival / total if total else None,
        "ss_runtime_fraction": runtime / total if total else None,
        "ss_interaction_fraction": interaction / total if total else None,
        "interpretation": LABEL,
    }


def flat(record, manifest):
    row = dict(record)
    if "Pj" in row and row["Pj"] is not None:
        values = json.loads(row["Pj"]) if isinstance(row["Pj"], str) else row["Pj"]
        for i, v in enumerate(values):
            row[f"Pj_{i}"] = v
        row["max_Pj"] = max(values)
        row["Bloom_Pj"] = values[3]
        failures = ["tracking"] if row["p90"] > TRACKING_LIMIT else []
        failures += [JOBS[i] for i, v in enumerate(values) if v > QOS_LIMIT]
        counts = row["evidence_counts"]
        if isinstance(counts, str):
            counts = json.loads(counts)
        failures += [
            f"insufficient_evidence:{JOBS[i]}" for i, n in enumerate(counts) if n is None or n < 1
        ]
        row["failure_reason"] = ";".join(failures) or "NONE"
    else:
        row.update({f"Pj_{i}": None for i in range(4)})
        row.update(
            p90=None,
            objective=None,
            max_Pj=None,
            Bloom_Pj=None,
            evidence_qualified_pass=None,
            evidence_counts=None,
            failure_reason=row.get("status", "NOT_RUN"),
        )
    row["repo_shas"] = manifest["repo_shas"]
    row["configuration_sha256"] = manifest["configuration_sha256"]
    row.pop("assessment", None)
    for k, v in list(row.items()):
        if isinstance(v, (dict, list, tuple)):
            row[k] = json.dumps(v, separators=(",", ":"))
    return row


def merged_results(output, manifest, results):
    actual = {r["cell_id"]: r for r in results}
    planned = []
    for row in manifest["new_run_plan"]:
        if row["cell_id"] in actual:
            item = actual[row["cell_id"]]
        else:
            status = (
                "EXECUTION_ERROR"
                if (output / "cells" / row["cell_id"] / "execution_error.json").exists()
                else "NOT_RUN"
            )
            item = {**row, "origin": "NEW", "status": status}
        planned.append(flat(item, manifest))
    new = pd.DataFrame(planned)
    original = read_json(output / "inputs/old_fresh_confirmations.json")
    fixed = pd.DataFrame(
        [*[flat(r, manifest) for r in original], *new[new.role == "COUPLED_NEW"].to_dict("records")]
    )
    fixed["seed"] = fixed.arrival_seed
    old = read_json(output / "inputs/old_matrix_results.json")
    factor = pd.DataFrame(
        [
            *[
                flat(
                    {
                        **r,
                        "origin": "PHASE2_REUSED",
                        "role": "FACTORIZATION_OLD",
                        "initial_hash_evidence": "actual pilot initial state verified",
                        "grid_hash_evidence": "actual pilot grid/target verified",
                    },
                    manifest,
                )
                for r in old
            ],
            *new[new.role == "FACTORIZATION_NEW"].to_dict("records"),
        ]
    )
    for case in manifest["specification"]["cases"]:
        c = case["case"]
        expected_fixed = (
            manifest["configuration"]["old_fixed_confirmation_seeds"][c]
            + manifest["configuration"]["new_seeds"]
        )
        selected = fixed[fixed.case == c]
        if (
            len(selected) != 10
            or set(selected.seed) != set(expected_fixed)
            or not (selected.arrival_seed == selected.runtime_seed).all()
        ):
            raise ValueError(
                "Goal A merge is not the original three fresh plus seven new coupled scenarios"
            )
        selected = factor[factor.case == c]
        expected = {
            (a, r) for a in manifest["arrival_axes"][c] for r in manifest["frozen_runtime_axes"][c]
        }
        if (
            len(selected) != 30
            or set(zip(selected.arrival_seed, selected.runtime_seed)) != expected
        ):
            raise ValueError("Goal B merge is not the preserved 10x3 matrix")
    if new.cell_id.nunique() != 56 or len(fixed) != 20 or len(factor) != 60:
        raise ValueError("Expanded result cardinality mismatch")
    return new, fixed, factor


def fixed_summary(fixed):
    rows = []
    for case, planned in fixed.groupby("case"):
        frame = planned[planned.status == "COMPLETE"]
        n = len(frame)
        passed = int(frame.evidence_qualified_pass.astype(bool).sum())
        row = {
            "case": case,
            "tested_count": n,
            "planned_count": 10,
            "passed_tested_scenarios": passed,
            "characterization_complete": n == 10,
            "statement": f"candidate passed {passed} of the 10 tested fresh scenarios"
            if n == 10
            else f"INCOMPLETE: {passed}/{n} available scenarios passed; 10 planned",
        }
        for metric in ["p90", *[f"Pj_{i}" for i in range(4)], "Bloom_Pj"]:
            for stat in ["mean", "median", "min", "max"]:
                row[metric + "_" + stat] = float(getattr(frame[metric], stat)()) if n else None
        row["tracking_failures"] = int((frame.p90 > TRACKING_LIMIT).sum())
        for i, name in enumerate(JOBS):
            row[name + "_qos_failures"] = int((frame[f"Pj_{i}"] > QOS_LIMIT).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def compact_tables(output, results):
    tables = {}
    for name in ["per_job_run_summary", "qos_accounting", "queue_summary"]:
        old = pd.read_csv(
            output / "inputs" / ("phase2_" + name + ".csv"), float_precision="round_trip"
        )
        old["origin"] = "PHASE2_REUSED"
        old["role"] = "FACTORIZATION_OLD"
        frames = [old]
        for r in results:
            table = pd.read_csv(
                output / "cells" / r["cell_id"] / (name + ".csv"), float_precision="round_trip"
            )
            for key in ["cell_id", "case", "workload", "arrival_seed", "runtime_seed", "role"]:
                table[key] = r[key]
            table["origin"] = "NEW"
            frames.append(table)
        table = pd.concat(frames, ignore_index=True)
        if table.duplicated(["cell_id", "job_type_id"]).any():
            raise ValueError("Duplicate reused compact job evidence")
        write_csv(output / (name + ".csv"), table)
        tables[name] = table
    return tables


def factor_summary(output, manifest, factor, tables):
    effects = []
    row_states = []
    matrix_dir = output / "crossed_matrices"
    matrix_dir.mkdir(exist_ok=True)
    extras = [
        ("queue_summary", "queue_after_policy_mean"),
        ("per_job_run_summary", "waiting_started_seconds_p90"),
        ("per_job_run_summary", "unfinished"),
    ]
    for case in manifest["specification"]["cases"]:
        c = case["case"]
        arrivals = manifest["arrival_axes"][c]
        runtimes = manifest["frozen_runtime_axes"][c]
        frame = factor[factor.case == c].copy()
        for name, metric in extras:
            bloom = tables[name][(tables[name].case == c) & (tables[name].job_type_id == 3)][
                ["cell_id", metric]
            ]
            frame = frame.merge(bloom, on="cell_id", how="left", validate="one_to_one")
        for metric in [
            "Bloom_Pj",
            "p90",
            "Pj_0",
            "Pj_1",
            "Pj_2",
            "objective",
            "evidence_qualified_pass",
            *[m for n, m in extras],
        ]:
            mat = frame.pivot(index="arrival_seed", columns="runtime_seed", values=metric).reindex(
                index=arrivals, columns=runtimes
            )
            mat.index.name = "arrival_seed"
            mat.to_csv(matrix_dir / (c + "_" + metric + ".csv"))
            if mat.notna().all().all():
                effects.append(
                    {"case": c, "metric": metric, **matrix_effects(mat.to_numpy(dtype=float))}
                )
        for arrival in arrivals:
            row = frame[(frame.arrival_seed == arrival) & (frame.status == "COMPLETE")]
            n = len(row)
            passes = int(row.evidence_qualified_pass.astype(bool).sum())
            state = (
                "INCOMPLETE"
                if n != 3
                else "ALWAYS_FEASIBLE"
                if passes == 3
                else "ALWAYS_INFEASIBLE"
                if passes == 0
                else "MIXED_FRAGILE"
            )
            row_states.append(
                {
                    "case": c,
                    "arrival_seed": arrival,
                    "complete_runtime_cells": n,
                    "passes": passes,
                    "classification": state,
                    "Bloom_Pj_mean": row.Bloom_Pj.mean() if n else None,
                    "Bloom_Pj_min": row.Bloom_Pj.min() if n else None,
                    "Bloom_Pj_max": row.Bloom_Pj.max() if n else None,
                    "Bloom_Pj_runtime_range": row.Bloom_Pj.max() - row.Bloom_Pj.min()
                    if n
                    else None,
                    "queue_mean_over_runtime_seeds": row.queue_after_policy_mean.mean()
                    if n
                    else None,
                    "waiting_p90_mean_over_runtime_seeds": row.waiting_started_seconds_p90.mean()
                    if n
                    else None,
                    "unfinished_mean_over_runtime_seeds": row.unfinished.mean() if n else None,
                }
            )
    effect_frame = (
        pd.DataFrame(effects)
        if effects
        else pd.DataFrame(
            columns=[
                "case",
                "metric",
                "ss_arrival_fraction",
                "ss_runtime_fraction",
                "ss_interaction_fraction",
            ]
        )
    )
    states = pd.DataFrame(row_states)
    write_csv(output / "factorization_descriptive_effects.csv", effect_frame)
    write_csv(output / "arrival_runtime_classification.csv", states)
    return effect_frame, states


def arrival_associations(output, states):
    path = output / "arrival_diagnostics.csv"
    arrivals = (
        pd.read_csv(path, float_precision="round_trip")
        if path.exists()
        else pd.read_csv(output / "inputs/phase1_arrival_summary.csv", float_precision="round_trip")
    )
    if "case" not in arrivals:
        arrivals["case"] = arrivals.workload.map(
            {"W2-short-qos5_4.5_4_3.5": "c005", "W2-short-qos5555": "c007"}
        )
    joined = states.merge(
        arrivals,
        left_on=["case", "arrival_seed"],
        right_on=["case", "seed"],
        how="left",
        validate="one_to_many",
    )
    write_csv(output / "arrival_outcome_join.csv", joined)
    correlations = []
    for (case, job), frame in joined[joined.complete_runtime_cells == 3].groupby(
        ["case", "job_type"]
    ):
        for metric in [
            "poisson_count",
            "prefill_count",
            "poisson_max_window_60s",
            "final_300s_fraction",
        ]:
            values = frame[[metric, "Bloom_Pj_mean"]].dropna()
            corr = (
                values[metric].corr(values.Bloom_Pj_mean)
                if len(values) >= 3 and values[metric].std() > 0 and values.Bloom_Pj_mean.std() > 0
                else None
            )
            correlations.append(
                {
                    "case": case,
                    "job_type": job,
                    "arrival_metric": metric,
                    "n_arrival_realizations": len(values),
                    "pearson_r_with_runtime_mean_Bloom_Pj": corr,
                    "interpretation": "descriptive association only; fixed feature list; no p-values or causal/explanatory sufficiency claim",
                }
            )
    result = pd.DataFrame(correlations)
    write_csv(output / "arrival_correlations.csv", result)
    return result


def plots(output, manifest, fixed, factor, states):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, TwoSlopeNorm
    from matplotlib.patches import Rectangle

    directory = output / "plots"
    directory.mkdir(exist_ok=True)
    cases = manifest["specification"]["cases"]
    fixed_bloom_top = max(0.11, float(pd.to_numeric(fixed.Bloom_Pj, errors="coerce").max()) * 1.08)
    for metric, title in [
        ("Bloom_Pj", "Ten fresh scenarios: Bloom Pj"),
        ("evidence_qualified_pass", "Ten fresh scenarios: overall qualified outcome"),
    ]:
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True)
        for ax, case in zip(axes, cases):
            c = case["case"]
            order = (
                manifest["configuration"]["old_fixed_confirmation_seeds"][c]
                + manifest["configuration"]["new_seeds"]
            )
            data = fixed[fixed.case == c].set_index("seed").reindex(order)
            for i, (_, row) in enumerate(data.iterrows()):
                if row.status == "COMPLETE":
                    ax.scatter(
                        i,
                        float(row[metric]),
                        color="#087f5b" if row.evidence_qualified_pass else "#c92a2a",
                        marker="o" if row.evidence_qualified_pass else "x",
                        s=65,
                    )
            ax.axvline(2.5, color="gray", linestyle=":")
            if metric == "Bloom_Pj":
                ax.set_ylim(0, fixed_bloom_top)
                ax.axhline(QOS_LIMIT, color="black", linestyle="--", label="0.10 QoS limit")
                ax.legend(fontsize=8)
            else:
                ax.set_yticks([0, 1], ["FAIL", "PASS"])
                ax.set_ylim(-0.2, 1.2)
            ax.set_xticks(range(10), [str(s) for s in order], rotation=65, ha="right", fontsize=7)
            ax.set_title(case["workload"], fontsize=11)
            ax.set_xlabel("First 3: original confirmations | Next 7: predeclared new seeds")
        fig.suptitle(title + " (green PASS; red FAIL; blank = not run)")
        fig.savefig(directory / ("fixed_" + metric + ".png"), dpi=170)
        plt.close(fig)
    for metric, title in [
        ("Bloom_Pj", "10x3 Bloom Pj; black outline = exceeds 0.10"),
        ("evidence_qualified_pass", "10x3 qualified outcome: green PASS, red FAIL"),
    ]:
        fig, axes = plt.subplots(1, 2, figsize=(12, 9), constrained_layout=True)
        maximum = max(0.100001, float(pd.to_numeric(factor[metric], errors="coerce").max()))
        for ax, case in zip(axes, cases):
            c = case["case"]
            arrivals = manifest["arrival_axes"][c]
            runtime = manifest["frozen_runtime_axes"][c]
            matrix = (
                factor[factor.case == c]
                .pivot(index="arrival_seed", columns="runtime_seed", values=metric)
                .reindex(index=arrivals, columns=runtime)
                .to_numpy(dtype=float)
            )
            if metric == "Bloom_Pj":
                im = ax.imshow(
                    np.ma.masked_invalid(matrix),
                    cmap="RdYlGn_r",
                    norm=TwoSlopeNorm(vmin=0, vcenter=0.1, vmax=maximum),
                    aspect="auto",
                )
            else:
                im = ax.imshow(
                    np.ma.masked_invalid(matrix),
                    cmap=ListedColormap(["#c92a2a", "#087f5b"]),
                    vmin=0,
                    vmax=1,
                    aspect="auto",
                )
            ax.set_xticks(range(3), [str(s) for s in runtime], rotation=25, ha="right", fontsize=8)
            ax.set_yticks(range(10), [str(s) for s in arrivals], fontsize=8)
            ax.axhline(2.5, color="black", linestyle="--", linewidth=1)
            ax.set_xlabel("Preserved runtime seeds")
            ax.set_ylabel("Arrival seeds: original 3, then new 7")
            ax.set_title(case["workload"], fontsize=11)
            for i in range(10):
                for j in range(3):
                    v = matrix[i, j]
                    label = (
                        (f"{v:.3f}" if metric == "Bloom_Pj" else "PASS" if v else "FAIL")
                        if np.isfinite(v)
                        else "pending"
                    )
                    ax.text(
                        j,
                        i,
                        label,
                        ha="center",
                        va="center",
                        fontsize=9,
                        color="white"
                        if np.isfinite(v)
                        and (metric != "Bloom_Pj" or v < 0.025 or v > 0.1 + (maximum - 0.1) * 0.7)
                        else "black",
                    )
                    if metric == "Bloom_Pj" and v > 0.1:
                        ax.add_patch(
                            Rectangle(
                                (j - 0.49, i - 0.49),
                                0.98,
                                0.98,
                                fill=False,
                                edgecolor="black",
                                linewidth=1,
                            )
                        )
            fig.colorbar(im, ax=ax, shrink=0.6)
        fig.suptitle(title)
        fig.savefig(directory / ("matrix_" + metric + ".png"), dpi=170)
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for ax, case in zip(axes, cases):
        data = states[(states.case == case["case"]) & (states.complete_runtime_cells == 3)]
        for row in data.itertuples():
            color = {
                "ALWAYS_FEASIBLE": "#087f5b",
                "ALWAYS_INFEASIBLE": "#c92a2a",
                "MIXED_FRAGILE": "#e67700",
            }[row.classification]
            ax.scatter(
                row.queue_mean_over_runtime_seeds,
                row.waiting_p90_mean_over_runtime_seeds,
                color=color,
                s=60,
            )
            index = manifest["arrival_axes"][case["case"]].index(row.arrival_seed) + 1
            ax.annotate(
                f"A{index}",
                (row.queue_mean_over_runtime_seeds, row.waiting_p90_mean_over_runtime_seeds),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=8,
            )
        ax.set_title(case["workload"], fontsize=11)
        ax.set_xlabel("Mean Bloom queue, averaged over runtime seeds")
        ax.set_ylabel("Mean Bloom p90 started-job wait (seconds)")
    fig.suptitle("Arrival realizations: green always feasible; red always infeasible; orange mixed")
    fig.savefig(directory / "Bloom_queue_waiting.png", dpi=170)
    plt.close(fig)


def report(output, manifest, status, summary, factor, effects, states, correlations, error):
    complete = status == "COMPLETE"
    lines = [
        "# Phase 2B — Expanded W2 Seed Characterization",
        "",
        f"Status: {status}. New successful cells: {manifest['new_completed']}/56.",
        "Existing six fresh confirmations and 18 pilot cells are reused; none were rerun. Coupled new S,S cells are outside the 10x3 matrices.",
        "X/10 is a fixed-candidate pass count across ten tested fresh scenarios, not a certified reliability probability. The original three pilot arrivals were deliberately selected, while the new seven seeds were fixed before trace generation.",
        "",
    ]
    if error:
        lines += ["Execution/integrity error: " + error, ""]
    if not complete:
        lines += [
            "INCOMPLETE: pending cells are unknown, not failures. No expanded-panel or Phase 3 conclusion is available yet.",
            "",
        ]
    conclusions = []
    for c in manifest["specification"]["cases"]:
        case = c["case"]
        s = summary[summary.case == case].iloc[0]
        rows = states[states.case == case]
        lines += [
            "## " + c["workload"],
            "",
            s.statement + ".",
            f"Tracking failures in available coupled scenarios: {int(s.tracking_failures)}. Per-job QoS failures: "
            + ", ".join(f"{j}={int(s[j + '_qos_failures'])}" for j in JOBS)
            + ".",
        ]
        known = factor[(factor.case == case) & (factor.status == "COMPLETE")]
        lines += [
            f"Available matrix cells: {len(known)}/30; tracking failures: {int((known.p90 > TRACKING_LIMIT).sum())}.",
            "Arrival classifications: "
            + ", ".join(
                f"{label}={int((rows.classification == label).sum())}"
                for label in ["ALWAYS_FEASIBLE", "ALWAYS_INFEASIBLE", "MIXED_FRAGILE", "INCOMPLETE"]
            )
            + ".",
        ]
        matrix_failures = {
            name: int((known[f"Pj_{i}"] > QOS_LIMIT).sum()) for i, name in enumerate(JOBS)
        }
        most = max(matrix_failures.values(), default=0)
        dominant_jobs = (
            ", ".join(name for name, count in matrix_failures.items() if count == most)
            if most
            else "none"
        )
        lines += [
            "Per-job matrix QoS failures: "
            + ", ".join(f"{name}={count}" for name, count in matrix_failures.items())
            + ". Most frequent QoS failure type(s): "
            + dominant_jobs
            + "."
        ]
        e = effects[(effects.case == case) & (effects.metric == "Bloom_Pj")]
        if len(e):
            e = e.iloc[0]
            dominant = e.ss_arrival >= max(e.ss_runtime, e.ss_interaction)
            conclusions.append(bool(dominant))
            lines += [
                f"Bloom Pj finite-matrix SS shares: arrival {100 * e.ss_arrival_fraction:.2f}%, runtime {100 * e.ss_runtime_fraction:.2f}%, residual/interaction {100 * e.ss_interaction_fraction:.2f}%. Largest runtime-only Pj range at fixed arrivals: {e.maximum_runtime_range:.6f}.",
                LABEL + ".",
                f"Arrival is the largest descriptive component: {dominant}. Runtime-seed pass/fail flips occurred in {int((rows.classification == 'MIXED_FRAGILE').sum())} of ten arrival rows.",
            ]
        corr = correlations[
            (correlations.case == case) & correlations.job_type.str.startswith("Bloom")
        ]
        if len(corr):
            lines += [
                "Bloom arrival associations with runtime-averaged Bloom Pj: "
                + "; ".join(
                    f"{r.arrival_metric}: r={r.pearson_r_with_runtime_mean_Bloom_Pj:.3f}, n={r.n_arrival_realizations}"
                    for r in corr.itertuples()
                    if pd.notna(r.pearson_r_with_runtime_mean_Bloom_Pj)
                )
                + ".",
                "These count/burst correlations describe association, not explanatory sufficiency. A stronger correlation alone does not establish that simple counts explain the workload effect. The complete workload includes prefill and all competing job types; use arrival_outcome_join.csv and queue histories to inspect mechanisms.",
            ]
        lines += [""]
    lines += ["## Interpretation and limits", ""]
    if complete:
        lines += [
            "The pilot conclusion survives as the largest descriptive component for both candidates."
            if all(conclusions) and len(conclusions) == 2
            else "The pilot's arrival-dominance conclusion is not uniformly supported by the expanded matrix; inspect the component and conditional ranges before generalizing.",
            "Existing replay controls remain exact and all new successful cells passed prepared-initial-state and actual grid/target invariants. This adds no detected replay/identity bug; it does not prove the generator or simulator is bug-free.",
            "This completed characterization is sufficient to inform a proposal for uncertainty-aware simulated annealing. Any next-phase design should follow the observed arrival/runtime sensitivity and finite-horizon accounting; this does not certify a candidate or prescribe an 8/10 feasibility rule. Phase 3 has NOT been started.",
        ]
    lines += [
        "Runtime streams can be consumed at different event times under different arrivals. Residual/interaction is unreplicated, not an inferential error variance. No ANOVA p-values are reported.",
        "Started-job waiting times and completed-job sojourns exclude censored observations, which are separately retained. Upstream Pj uses its existing (m-1)/(n-1) estimator and horizon exclusions; QoS accounting and evidence requirements are unchanged.",
        "Original confirmation hashes are explicitly labeled Phase1/fixed-context references where original runtime traces were not retained. The c007 seed144392579 confirmation has no pilot runtime detail, so only its real metrics and existing arrival reconstruction are reused.",
        "Do not compare these two candidates as a QoS-threshold-only intervention: their bids/weights and original seed panels also differ.",
        "Five figures are included. Per-cell new gzip data, merged old summaries and source links preserve compact evidence; no old full simulator trees, grid copies, per-node traces or automatic retries are retained.",
    ]
    (output / "report.md").write_text("\n\n".join(lines) + "\n", encoding="utf8")


def export(output, manifest, results, status, error=None):
    new, fixed, factor = merged_results(output, manifest, results)
    write_csv(output / "new_run_results.csv", new)
    write_csv(output / "fixed_candidate_10seed_results.csv", fixed)
    write_csv(output / "factorization_10x3_results.csv", factor)
    summary = fixed_summary(fixed)
    write_csv(output / "fixed_candidate_10seed_summary.csv", summary)
    for case, table in fixed.groupby("case"):
        write_csv(output / (case + "_fixed_candidate_10seed_results.csv"), table)
    tables = compact_tables(output, results)
    effects, states = factor_summary(output, manifest, factor, tables)
    correlations = arrival_associations(output, states)
    combined = pd.concat([fixed, factor], ignore_index=True).drop_duplicates("cell_id")
    for filename, fields in [
        (
            "initial_job_table_hashes.csv",
            ["initial_job_table_hash", "arrival_hash", "initial_hash_evidence"],
        ),
        ("grid_signal_hashes.csv", ["grid_signal_hash", "target_trace_hash", "grid_hash_evidence"]),
    ]:
        for field in fields:
            if field not in combined:
                combined[field] = None
        write_csv(
            output / filename,
            combined[
                ["cell_id", "case", "arrival_seed", "runtime_seed", "origin", "status", *fields]
            ],
        )
    plots(output, manifest, fixed, factor, states)
    manifest.update(status=status, new_completed=len(results), error=error)
    report(output, manifest, status, summary, factor, effects, states, correlations, error)
    atomic_json(output / "manifest.json", manifest)
    return archive(output)
