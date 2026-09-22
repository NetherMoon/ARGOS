"""Isolated, output-only observer around the pinned FlexDC Simulator.run."""

from __future__ import annotations

import csv
import gzip
import hashlib
import importlib
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from argos.contracts import assessment
from argos.diagnostics.workload_seed_forensics import (
    arrival_hash,
    generate,
    load_generator,
    read_json,
    sha,
    table_hash,
    write_csv,
)
from argos.simulator.configuration import canonical_costs
from argos.simulator.evidence import ordered_jobs, validate_reported_qos_evidence
from argos.types import Candidate, FlexDCObservation, Metrics

POWER_HEADER = "time,QoSemergency,numNeededForTracking,waitingSum,target,realSum,trackingError,QoSJobSum,standbyPower"
JOB_COLUMNS = [
    "job_id",
    "job_type_id",
    "arrival_time",
    "start_time",
    "end_time",
    "estimate_finished",
    "update_time",
    "realtime_qos",
    "min_execution_time",
    "qos_constraint",
]
QUEUE_COLUMNS = [
    "time",
    "job_type_id",
    "queue_after_policy",
    "running_jobs",
    "active_servers",
    "actual_power_watts",
    "estimated_power_watts",
    "commanded_cap_servers",
    "commanded_cap_sum_watts",
    "cluster_active_servers",
    "cluster_idle_servers",
]


def array_hash(values):
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes(order="C")).hexdigest()


def atomic_json(path, value):
    import json

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf8")
    temporary.replace(path)


def observed_simulator(base):
    """Only change the output sink; preserve upstream run, RNG, scheduling and accounting."""

    class CompactSimulator(base):
        def record_state(
            self,
            t,
            qos_emergency,
            real_power,
            p_target,
            tracking_num,
            waiting_sum,
            tracking_error,
            qos_job_sum,
            standby_power,
            f,
        ):
            # These are exactly the upstream first-nine-column formats. Precision affects p90.
            f.write(
                "%d,%d,%d,%d,%.1f,%.1f,%.3f,%.1f,%.1f\n"  # noqa: UP031 - exact upstream serialization
                % (
                    t,
                    int(qos_emergency),
                    tracking_num,
                    waiting_sum,
                    p_target,
                    real_power,
                    tracking_error,
                    qos_job_sum,
                    standby_power,
                )
            )
            jobs, nodes = self._job_table, self._node_table
            waiting = (jobs[3] == -1) & (jobs[2] <= t)
            queue = np.bincount(jobs[1, waiting].astype(int), minlength=self._job_type_count)
            active = nodes[2] != -1
            total_active = int(active.sum())
            for job_type in range(self._job_type_count):
                selected = active & (nodes[2] == job_type)
                capped = selected & (nodes[11] >= 0)
                self.queue_writer.writerow(
                    [
                        t,
                        job_type,
                        int(queue[job_type]),
                        len(np.unique(nodes[1, selected])),
                        int(selected.sum()),
                        float(nodes[3, selected].sum()),
                        float(nodes[4, selected].sum()),
                        int(capped.sum()),
                        float(nodes[11, capped].sum()),
                        total_active,
                        self._server_count - total_active,
                    ]
                )

    return CompactSimulator


def stats(prefix, values):
    values = np.asarray(values, dtype=float)
    names = ("mean", "median", "p90", "p99", "max")
    numbers = (
        [float(values.mean()), *np.quantile(values, [0.5, 0.9, 0.99]), float(values.max())]
        if len(values)
        else [None] * 5
    )
    return {
        prefix + "_" + name: None if value is None else float(value)
        for name, value in zip(names, numbers)
    }


def job_summaries(table, evidence, prefill, horizon=3600):
    """Separate completed observations, censored lower bounds and upstream Pj support."""
    summaries, accounting = [], []
    for e in evidence:
        rows = table[table.job_type_id == e.job.index]
        arrived = rows.arrival_time <= horizon
        completed = rows.end_time != -1
        started = rows.start_time != -1
        unfinished = arrived & ~completed
        included_complete = completed & (rows.arrival_time > 0)
        included_unfinished = (
            unfinished
            & (rows.arrival_time > 0)
            & (rows.arrival_time + rows.min_execution_time < horizon)
        )
        observed_sojourn = np.where(completed, rows.end_time, horizon) - rows.arrival_time
        threshold = rows.min_execution_time * (1 + rows.qos_constraint)
        exceeds = observed_sojourn > threshold
        m_finished = int((included_complete & exceeds).sum())
        m_unfinished = int((included_unfinished & exceeds).sum())
        if m_finished + m_unfinished != e.exceedance_count:
            raise ValueError("QoS split disagrees with canonical evidence")
        wait_started = rows.loc[started, "start_time"] - rows.loc[started, "arrival_time"]
        wait_censored = horizon - rows.loc[arrived & ~started, "arrival_time"]
        base = {"job_type_id": e.job.index, "job_type": e.job.section}
        summaries.append(
            {
                **base,
                "prefill_count": int((rows.job_id < prefill).sum()),
                "later_generated_count": int((rows.job_id >= prefill).sum()),
                "positive_submit_count": int((rows.arrival_time > 0).sum()),
                "poisson_rounded_zero_count": int(
                    ((rows.job_id >= prefill) & (rows.arrival_time == 0)).sum()
                ),
                "total_jobs": len(rows),
                "completed": int(completed.sum()),
                "unfinished": int(unfinished.sum()),
                "never_started": int((arrived & ~started).sum()),
                "started_unfinished": int((unfinished & started).sum()),
                **stats("waiting_started_seconds", wait_started),
                **stats("waiting_never_started_lower_bound_seconds", wait_censored),
                **stats(
                    "sojourn_completed_seconds",
                    rows.loc[completed, "end_time"] - rows.loc[completed, "arrival_time"],
                ),
                **stats(
                    "sojourn_unfinished_lower_bound_seconds",
                    horizon - rows.loc[unfinished, "arrival_time"],
                ),
            }
        )
        accounting.append(
            {
                **base,
                "Pj": e.pj,
                "qos_observations": e.observation_count,
                "eligible_completed": e.finished_count,
                "eligible_unfinished": e.unfinished_count,
                "violating_completed": m_finished,
                "violating_unfinished": m_unfinished,
                "violation_count": e.exceedance_count,
                "empirical_exceedance_fraction": e.exceedance_count / e.observation_count
                if e.observation_count
                else None,
                "estimator_numerator": e.estimator_numerator,
                "estimator_denominator": e.estimator_denominator,
                "excluded_zero_submit": int((rows.arrival_time == 0).sum()),
                "excluded_late_unfinished": int(
                    (unfinished & (rows.arrival_time > 0) & ~included_unfinished).sum()
                ),
                "threshold_sojourn_seconds": e.threshold_sojourn_seconds,
                "horizon_seconds": horizon,
                "estimator": e.estimator,
            }
        )
    return pd.DataFrame(summaries), pd.DataFrame(accounting)


def check_context(experiment, spec):
    fixed = spec["fixed"]
    values = {
        "duration_seconds": experiment.simulation_duration,
        "N": experiment.server_count,
        "U": experiment.utilization,
        "iso_start_hour": experiment.iso_signal_start_hour,
        "randomize_iso_start": experiment.randomize_iso_start,
        "time_granularity": experiment.time_granularity,
        "workload_trace": experiment.workload_trace,
    }
    if (
        values != fixed
        or experiment.iso_signal_granularity != 2
        or not experiment.normalize_iso_signal
    ):
        raise ValueError("Fixed experiment context changed")


def create_initial(root, spec, case, seed, *, require_reference=True):
    tables, Exp, Jobs = load_generator(root)
    experiment = Exp(str(root / spec["experiment_path"]))
    experiment._utilization = case[
        "U"
    ]  # The same explicit U=.6 overlay as historical exact-plan rows.
    check_context(experiment, spec)
    jobs = Jobs(str(root / case["workload_path"]))
    trace, table, prefill = generate(tables, experiment, jobs, seed)
    references = case.get("initial_references", case["historical"])
    reference = next((r for r in references if r["seed"] == seed), None)
    if require_reference and reference is None:
        raise ValueError("Missing frozen initial-state reference")
    if reference is not None and (
        table_hash(table) != reference["initial_job_table_hash"]
        or arrival_hash(trace) != reference["arrival_hash"]
    ):
        raise ValueError("Initial table disagrees with frozen reconstruction")
    return tables, experiment, jobs, trace, table, prefill


def run_cell(root, output, case_id, arrival_seed, runtime_seed):
    start = time.monotonic()
    manifest = read_json(output / "manifest.json")
    spec = manifest["specification"]
    case = next(c for c in spec["cases"] if c["case"] == case_id)
    if arrival_seed not in case["seeds"] or runtime_seed not in case["seeds"]:
        raise ValueError("Seed outside frozen panel")
    if "new_run_plan" in manifest:
        allowed = {
            (r["case"], r["arrival_seed"], r["runtime_seed"]) for r in manifest["new_run_plan"]
        }
        if (case_id, arrival_seed, runtime_seed) not in allowed:
            raise ValueError(
                "Cell is not in the frozen expansion plan; historical reruns prohibited"
            )
    cell = output / "cells" / f"{case_id}_a{arrival_seed}_r{runtime_seed}"
    if not (cell / "started.json").is_file() or (cell / "completion.json").exists():
        raise ValueError("Worker requires a new, parent-authorized isolated cell")
    # Hash immutable runtime inputs again in each process before generation.
    for rel, digest in {**spec["files"], **manifest["tool_files"]}.items():
        if sha(root / rel) != digest:
            raise ValueError(f"Worker input changed: {rel}")
    sys.path.insert(0, str(root / ".deps/FlexDC/src/peacsim"))
    tables, experiment, jobs, trace, initial, prefill = create_initial(
        root, spec, case, arrival_seed
    )
    initial_hash = table_hash(initial)
    initial.setflags(write=False)
    # Every process owns all three objects. Neither generator nor scheduler is reimplemented.
    mutable_jobs = initial.copy()
    nodes = tables.init_node_table(experiment)
    experiment._random_seed = runtime_seed
    wizard = importlib.import_module("peacsim.am_data_extraction_wizard")
    Cluster = importlib.import_module("peacsim.parsing.cluster_profile_reader").ClusterProfileReader
    Policy = importlib.import_module("peacsim.parsing.policy_config_reader").PolicyConfigReader
    Runtime = importlib.import_module("peacsim.aqa_runtimepolicy").AQARuntimePolicy
    Simulator = importlib.import_module("peacsim.simulator").Simulator
    qos_function = importlib.import_module("peacsim.calculate_qos_cost").calculate_delay_prob
    # Preserve historical CSV serialization and upstream pandas weight parsing exactly.
    weights_path = cell / "base_weights.csv"
    pd.DataFrame({"job_type_id": list(jobs.all_jobs.values()), "weights": case["weights"]}).to_csv(
        weights_path, index=False
    )
    args = SimpleNamespace(
        policy_name="AQA", node_count_control=None, power_cap_percentage=None, probabilities=None
    )
    parameters = wizard.build_policy_parameters(args, jobs.job_type_count)
    if parameters != spec["policy_parameters"]:
        raise ValueError("Historical policy defaults changed")
    parameters["weights_path"] = str(weights_path)
    pr = wizard.convert_kw_per_server_to_flexdc_pr(case["Pbar"], case["R"], experiment, jobs)
    policy = Policy.from_parameters(
        policy_name="AQA",
        P=pr["P_actual_watts"],
        R=pr["R_actual_watts"],
        P_ratio=pr["Pbar_ratio"],
        R_ratio=pr["R_ratio"],
        policy_parameters=parameters,
    )
    runtime = Runtime(policy, experiment, jobs, nodes, mutable_jobs)
    cluster = Cluster(str(root / spec["cluster_path"]))
    # Read-only CWD resolves the unchanged canonical relative ISO path. Outputs are absolute.
    os.chdir(root / ".deps/FlexDC/src/peacsim")
    if Path(experiment.iso_file_path).resolve() != (root / spec["grid_path"]).resolve():
        raise ValueError("Unexpected resolved grid path")
    scratch = cell / "scratch"
    scratch.mkdir()
    sim = observed_simulator(Simulator)(
        mutable_jobs, nodes, runtime, experiment, jobs, cluster, output_dir=str(scratch) + os.sep
    )
    if table_hash(sim._job_table) != initial_hash or np.shares_memory(sim._job_table, initial):
        raise ValueError("Initial state copy failed")
    signal = np.asarray(sim._iso_signal, dtype=float)
    targets = np.asarray(sim._cluster_power_cap_per_signal, dtype=float)
    ticks = np.arange(3601)
    actual_grid = np.column_stack([ticks, signal[ticks // 2]])
    actual_target = np.column_stack([ticks, targets[ticks // 2]])
    grid_hash, target_hash = array_hash(actual_grid), array_hash(actual_target)
    expected_grid = manifest["expected_grid_hash"]
    expected_target = manifest["expected_target_hashes"][case_id]
    if grid_hash != expected_grid or target_hash != expected_target:
        raise ValueError("Actual simulator signal/target disagrees with fixed preflight trace")
    (scratch / "power_trace.csv").write_text(POWER_HEADER + "\n", encoding="utf8")
    (scratch / "PRtable.csv").write_text(f"phase,P,R\n0,{policy.P},{policy.R}\n", encoding="utf8")
    with gzip.open(cell / "queue_resources_1s.csv.gz", "wt", encoding="utf8", newline="") as stream:
        sim.queue_writer = csv.writer(stream, lineterminator="\n")
        sim.queue_writer.writerow(QUEUE_COLUMNS)
        monetary_power, monetary_tracking = (
            sim.run()
        )  # The unchanged upstream run reseeds both RNGs here.
    if table_hash(initial) != initial_hash:
        raise ValueError("Immutable initial state mutated")
    job_table = sim._job_table
    # Validate the normal saved output against the in-memory metric authority.
    saved_jobs = pd.read_csv(scratch / "job_table.csv", float_precision="round_trip")
    if not np.array_equal(saved_jobs[JOB_COLUMNS].to_numpy(), job_table[JOB_COLUMNS].to_numpy()):
        raise ValueError("Saved job table disagrees with simulator state")
    probabilities = tuple(
        float(v)
        for v in qos_function(
            1,
            jobs.job_type_count,
            job_table,
            jobs.all_job_qos_constraints,
            jobs.all_min_execution_time,
        )
    )
    evidence = validate_reported_qos_evidence(
        job_table, ordered_jobs(root / case["workload_path"]), probabilities
    )
    power = pd.read_csv(scratch / "power_trace.csv", float_precision="round_trip")
    if len(power) != 3601 or power.time.tolist() != ticks.tolist():
        raise ValueError("Incomplete power trace")
    if not np.array_equal(power.target.to_numpy(), np.round(actual_target[:, 1], 1)):
        raise ValueError("Logged power target differs from fixed actual trace")
    p90 = float(sim.tracking_error_at_90)
    objective = canonical_costs(root).objective(
        float(monetary_power + monetary_tracking), p90, probabilities
    )
    metrics = Metrics(
        float(power.trackingError.iloc[1:].abs().mean()), p90, probabilities, objective
    )
    candidate = Candidate(
        case["candidate_id"], case["Pbar"], case["R"], tuple(case["weights"]), "historical_exact"
    )
    observation = FlexDCObservation(
        candidate,
        runtime_seed,
        "seed_factorization",
        0,
        True,
        metrics,
        "PARSED",
        time.monotonic() - start,
        cell.name,
        qos_evidence=evidence,
    )
    qualified = assessment(observation)
    summaries, accounting = job_summaries(job_table, evidence, prefill)
    write_csv(cell / "per_job_run_summary.csv", summaries)
    write_csv(cell / "qos_accounting.csv", accounting)
    write_csv(cell / "jobs.csv.gz", saved_jobs[JOB_COLUMNS])
    write_csv(cell / "power_trace.csv.gz", power)
    queue = pd.read_csv(cell / "queue_resources_1s.csv.gz")
    queue_summary = []
    for job_type, rows in queue.groupby("job_type_id"):
        queue_summary.append(
            {
                "job_type_id": int(job_type),
                "job_type": jobs.all_jobs[job_type],
                **stats("queue_after_policy", rows.queue_after_policy),
                "queue_end": int(rows.queue_after_policy.iloc[-1]),
                "queue_job_seconds_sample_sum": int(rows.queue_after_policy.sum()),
                "active_servers_mean": float(rows.active_servers.mean()),
                "running_jobs_mean": float(rows.running_jobs.mean()),
                "actual_power_watts_mean": float(rows.actual_power_watts.mean()),
                "commanded_cap_servers_mean": float(rows.commanded_cap_servers.mean()),
                "commanded_cap_sum_watts_mean": float(rows.commanded_cap_sum_watts.mean()),
            }
        )
    write_csv(cell / "queue_summary.csv", pd.DataFrame(queue_summary))
    result = {
        "cell_id": cell.name,
        "case": case_id,
        "workload": case["workload"],
        "candidate_id": case["candidate_id"],
        "arrival_seed": arrival_seed,
        "runtime_seed": runtime_seed,
        "initial_job_table_hash": initial_hash,
        "arrival_hash": arrival_hash(trace),
        "grid_signal_hash": grid_hash,
        "target_trace_hash": target_hash,
        "logged_target_hash": array_hash(power[["time", "target"]]),
        "Pbar": case["Pbar"],
        "R": case["R"],
        "weights": case["weights"],
        "effective_policy_weights": list(runtime.weights.values()),
        "P_watts": policy.P,
        "R_watts": policy.R,
        "p90": p90,
        "Pj": list(probabilities),
        "objective": objective,
        "monetary_power": float(monetary_power),
        "monetary_tracking": float(monetary_tracking),
        "evidence_counts": qualified["per_job_evidence_counts"],
        "evidence_qualified_pass": qualified["evidence_qualified_feasible"],
        "assessment": qualified,
        "duration_seconds": 3600,
        "elapsed_seconds": time.monotonic() - start,
        "status": "COMPLETE",
    }
    atomic_json(cell / "result.json", result)
    # Only our explicit scratch directory, never dependency or historical paths.
    import shutil

    if scratch.resolve().parent != cell.resolve() or not cell.resolve().is_relative_to(
        (output / "cells").resolve()
    ):
        raise ValueError("Unsafe scratch cleanup path")
    shutil.rmtree(scratch)
    retained = [
        p for p in cell.iterdir() if p.is_file() and p.name not in {"worker.log", "started.json"}
    ]
    atomic_json(
        cell / "completion.json",
        {
            "status": "COMPLETE",
            "input_fingerprint": manifest["input_fingerprint"],
            "files": {p.name: sha(p) for p in retained},
        },
    )
    return result
