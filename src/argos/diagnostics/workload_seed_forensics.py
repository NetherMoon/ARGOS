"""Pinned FlexDC workload-generator forensics; never imports/runs the simulator."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import random
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "1.0"
WINDOWS = (1, 10, 30, 60)
ARRIVAL_COLUMNS = ["job_id", "job_type_id", "submit_time"]
GENERATOR_FILES = (
    "create_tables.py",
    "parsing/experiment_config_reader.py",
    "parsing/job_profile_reader.py",
    "parsing/parsing_utils.py",
)


def safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or any(x.startswith(".env") for x in path.parts):
        raise ValueError(f"Unsafe diagnostic input path: {relative}")
    return path


def sha(path):
    if any(x.startswith(".env") for x in path.parts):
        raise ValueError("Environment files are excluded")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


def validate_lineage(root, specification):
    """Small input/source checks only; never traverses historical runtime trees."""
    spec = read_json(specification)
    for name in ("FlexDC", "CONDOR-FLEXDC"):
        dep = root / ".deps" / name
        if git(dep, "rev-parse", "HEAD") != spec["setup_repositories"][name]["sha"]:
            raise ValueError(f"Pinned {name} HEAD mismatch; stop for lineage review")
        if git(dep, "status", "--porcelain"):
            raise ValueError(f"Pinned {name} is modified; stop for lineage review")
    for relative, expected in spec["files"].items():
        if sha(safe_path(root, relative)) != expected:
            raise ValueError(f"Lineage hash mismatch: {relative}")
    history_path = safe_path(root, spec["historical_csv"])
    if sha(history_path) != spec["historical_csv_sha256"]:
        raise ValueError("Recovered historical mapping changed")
    unavailable = []
    for relative, expected in spec["historical_sources"].items():
        path = safe_path(root, relative)
        if not path.exists():
            unavailable.append(relative)
        elif sha(path) != expected:
            raise ValueError(f"Historical outcome source changed: {relative}")
    if {"python": platform.python_version(), "numpy": np.__version__} != spec["runtime"]:
        raise ValueError("Use the recorded paper Python/NumPy runtime for exact regeneration")
    seeds = spec["seed_panel"]
    if len(seeds) != 10 or len(set(seeds)) != 10 or any(not 0 <= s < 2**32 for s in seeds):
        raise ValueError("Expected exactly ten distinct recorded diagnostic seeds")
    history = pd.read_csv(history_path, float_precision="round_trip")
    if set(seeds) != set(history.seed) or len(history) != 10:
        raise ValueError("Panel no longer equals the recovered ten-seed historical union")
    return spec, history, unavailable


def load_generator(root):
    source = root / ".deps/FlexDC/src"
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    tables = importlib.import_module("peacsim.create_tables")
    exp = importlib.import_module("peacsim.parsing.experiment_config_reader")
    jobs = importlib.import_module("peacsim.parsing.job_profile_reader")
    for module in (tables, exp, jobs):
        if not Path(module.__file__).resolve().is_relative_to(source.resolve()):
            raise ValueError("Imported a different FlexDC installation")
    return tables, exp.ExperimentConfigReader, jobs.JobProfileReader


def generate(tables, experiment, jobs, seed):
    """Exactly the wizard's two seed calls and real init_job_table call, serially."""
    py_state, np_state = random.getstate(), np.random.get_state()
    try:
        experiment._random_seed = int(seed)
        np.random.seed(experiment.random_seed)
        random.seed(experiment.random_seed)
        table = tables.init_job_table(experiment, jobs)
    finally:
        random.setstate(py_state)
        np.random.set_state(np_state)
    duration = experiment.simulation_duration
    if table.ndim != 2 or table.shape[0] != 10 or not np.isfinite(table).all():
        raise ValueError("Unexpected generator job-table schema")
    count = table.shape[1]
    if not np.array_equal(table[0], np.arange(count)):
        raise ValueError("Unexpected job IDs")
    if not np.array_equal(table[:3], np.rint(table[:3])):
        raise ValueError("Expected integer IDs and rounded-second submit times")
    if np.any(table[2] < 0) or np.any(table[2] > duration):
        raise ValueError("Generated arrivals outside the pinned rounded-time domain")
    if not (
        np.all(table[3:5] == -1)
        and np.all(table[5] == 0)
        and np.array_equal(table[2], table[6])
        and np.all(table[7] == 0)
    ):
        raise ValueError("Generator defaults changed")
    sizes = list(jobs.all_job_size.values())
    prefill = int(experiment.server_count / (2 * sum(sizes)) * (2 * len(sizes)))
    trace = pd.DataFrame(table[:3].T.astype(np.int64), columns=ARRIVAL_COLUMNS)
    trace["job_type"] = trace.job_type_id.map(jobs.all_jobs)
    trace["is_prefill"] = trace.job_id < prefill
    trace["min_execution_time"] = table[8]
    trace["qos_constraint"] = table[9]
    if not np.all(table[2, :prefill] == 0):
        raise ValueError("Prefill no longer occupies the first zero-time rows")
    return trace, table, prefill


def arrival_hash(trace):
    """Canonical LF UTF-8 CSV, exact integer job ID/type/rounded submit time."""
    canonical = (
        trace[ARRIVAL_COLUMNS].sort_values("job_id").to_csv(index=False, lineterminator="\n")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def table_hash(table):
    return hashlib.sha256(np.asarray(table, dtype="<f8").tobytes(order="C")).hexdigest()


def interarrival_stats(times):
    gaps = np.diff(np.sort(np.asarray(times, dtype=float)))
    if not len(gaps):
        return dict.fromkeys(("mean", "median", "std", "cv", "p90", "p99"))
    mean = float(gaps.mean())
    std = float(gaps.std(ddof=0))
    return {
        "mean": mean,
        "median": float(np.median(gaps)),
        "std": std,
        "cv": std / mean if mean else None,
        "p90": float(np.quantile(gaps, 0.9)),
        "p99": float(np.quantile(gaps, 0.99)),
    }


def max_window(counts, width):
    """All sliding half-open integer-second windows, including the T endpoint."""
    counts = np.pad(np.asarray(counts, dtype=np.int64), (0, width - 1))
    prefix = np.concatenate(([0], np.cumsum(counts)))
    return int(np.max(prefix[width:] - prefix[:-width]))


def summarize(trace, workload, seed, rates, duration, prefill_total, job_names):
    summaries, bins = [], {w: [] for w in WINDOWS}
    for job_id, name in job_names.items():
        subset = trace[trace.job_type_id == job_id]
        times = subset.submit_time.to_numpy(dtype=int)
        pois = subset.loc[~subset.is_prefill, "submit_time"].to_numpy(dtype=int)
        counts = np.bincount(times, minlength=duration + 1)
        poisson_counts = np.bincount(pois, minlength=duration + 1)
        expected = rates[job_id] * duration
        expected_total = expected + prefill_total / len(job_names)
        row = {
            "workload": workload,
            "seed": seed,
            "job_type_id": job_id,
            "job_type": name,
            "total_count": len(times),
            "prefill_count": len(times) - len(pois),
            "poisson_count": len(pois),
            "rate_per_second": rates[job_id],
            "expected_poisson_count": expected,
            "poisson_count_difference": len(pois) - expected,
            "poisson_count_z": (len(pois) - expected) / np.sqrt(expected),
            "expected_prefill_count": prefill_total / len(job_names),
            "expected_total_count": expected_total,
            "total_count_difference": len(times) - expected_total,
            "total_count_z_style": (len(times) - expected_total) / np.sqrt(expected_total),
            "min_submit_time": int(times.min()) if len(times) else None,
            "max_submit_time": int(times.max()) if len(times) else None,
            "poisson_rounded_to_zero": int(np.sum(pois == 0)),
            "poisson_rounded_to_duration": int(np.sum(pois == duration)),
        }
        for prefix, values in (("interarrival_", times), ("poisson_interarrival_", pois)):
            row.update({prefix + k: v for k, v in interarrival_stats(values).items()})
        for width in WINDOWS:
            row[f"max_window_{width}s"] = max_window(counts, width)
            row[f"poisson_max_window_{width}s"] = max_window(poisson_counts, width)
            for start in range(0, duration + 1, width):
                stop = min(start + width, duration + 1)
                bins[width].append(
                    {
                        "workload": workload,
                        "seed": seed,
                        "job_type": name,
                        "bin_start": start,
                        "bin_end_exclusive": stop,
                        "count": int(counts[start:stop].sum()),
                        "poisson_count": int(poisson_counts[start:stop].sum()),
                        "prefill_count": int(
                            (counts[start:stop] - poisson_counts[start:stop]).sum()
                        ),
                    }
                )
        for tail in (60, 300):
            n = int(np.sum(times >= duration - tail))
            row[f"final_{tail}s_count"] = n
            row[f"final_{tail}s_fraction"] = n / len(times) if len(times) else None
        summaries.append(row)
    return summaries, bins


def write_csv(path, frame):
    compression = {"method": "gzip", "mtime": 0} if path.suffix == ".gz" else None
    frame.to_csv(path, index=False, lineterminator="\n", compression=compression)


def make_plots(out, summary, bins, joined):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_dir = out / "plots"
    plot_dir.mkdir()
    first = summary.workload.iloc[0]
    bloom = bins[(bins.workload == first) & bins.job_type.str.startswith("Bloom")]
    fig, ax = plt.subplots(figsize=(10, 4))
    for seed, frame in bloom.groupby("seed"):
        ax.plot(frame.bin_start, frame.poisson_count, label=str(seed), alpha=0.75)
    ax.set(
        xlabel="Submit time (s); 60-second fixed bins",
        ylabel="Bloom Poisson arrivals",
        title="Bloom arrivals across seeds (prefill excluded)",
    )
    ax.legend(ncol=5, fontsize=7)
    fig.tight_layout()
    fig.savefig(plot_dir / "bloom_arrivals.png", dpi=140)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(10, 6))
    for ax, (job, frame) in zip(axes.flat, summary[summary.workload == first].groupby("job_type")):
        ax.plot(frame.seed.astype(str), frame.total_count, "o-")
        ax.axhline(frame.expected_total_count.iloc[0], color="gray", linestyle="--")
        ax.set_title(job)
        ax.tick_params(axis="x", labelrotation=90, labelsize=7)
        ax.set_ylabel("Total arrivals including prefill")
    fig.tight_layout()
    fig.savefig(plot_dir / "per_job_counts.png", dpi=140)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4))
    for job, frame in summary[summary.workload == first].groupby("job_type"):
        ax.plot(frame.seed.astype(str), frame.poisson_max_window_60s, "o-", label=job)
    ax.set(
        ylabel="Maximum sliding 60s Poisson arrivals",
        xlabel="Seed",
        title="Burstiness (prefill excluded)",
    )
    ax.tick_params(axis="x", labelrotation=45)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / "burstiness.png", dpi=140)
    plt.close(fig)
    if not joined.empty:
        fig, axes = plt.subplots(1, 3, figsize=(12, 4))
        for ax, metric in zip(
            axes, ("poisson_count_z", "poisson_max_window_60s", "final_300s_fraction")
        ):
            for workload, frame in joined.groupby("workload"):
                ax.scatter(frame[metric], frame.Bloom_Pj, label=workload)
            ax.axhline(0.1, color="gray", linestyle="--")
            ax.set(xlabel=metric, ylabel="Historical Bloom Pj")
        axes[0].legend(fontsize=6)
        fig.suptitle("Historical associations only; arrivals and runtime scheduling share the seed")
        fig.tight_layout()
        fig.savefig(plot_dir / "bloom_outcome_linkage.png", dpi=140)
        plt.close(fig)


def make_report(out, summary, comparisons, joined, hashes, smoke):
    lines = [
        "# W2 workload-generator seed forensics",
        "",
        "SMOKE TEST ONLY: two seeds, not the full panel."
        if smoke
        else "Generator-only diagnostic: ten shared historical seeds, two fixed W2 contexts.",
        "",
        "No simulator, optimizer, controller, policy execution or grid-signal randomization was run.",
        "",
        "## What the seed changes",
        "",
        "Python random chooses the type of each of the 1,000 time-zero prefill jobs, then draws exponential inter-arrivals sequentially for each job type. The generator sorts unrounded arrivals, rounds submit times to integer seconds and assigns job IDs. Counts, type ordering and submit times therefore change. Type-specific execution-time and QoS values are copied from fixed profiles; runtime fields start at fixed defaults.",
        "",
        "NumPy is also seeded to mirror the wizard, but this Poisson path consumes Python random. The simulator later reseeds both RNGs and the AQA scheduler shuffles queue order. Historical seed sensitivity combines arrival and scheduling changes; these arrival-only diagnostics cannot separate their causal effects.",
        "",
        "## Controls and measurement definitions",
        "",
        "An identical first seed/context was generated twice; both arrival and full-table hashes matched. Distinct seeds produced distinct arrival hashes in each workload.",
        f"Shared-seed arrival equality: {int(comparisons.arrivals_identical.sum())}/{len(comparisons)}. Full job tables differ because the GPT2/Llama/Bloom QoS column differs; the two profiles otherwise have identical arrival inputs.",
        "The actual rate is U*N/J/min_time_seconds/job_size. QoS, max execution time, power, configured arrival_rate, P/R/weights and ISO inputs do not enter it. Generator input comparison is in workload_input_comparison.json; exact source references are in source_audit.md.",
        "",
        "All count/min/max/inter-arrival summaries include prefill unless explicitly prefixed poisson_. Poisson-count expectation excludes prefill; total expectation adds 1000/4. Prefill by type is multinomial, not Poisson. z-style values use sqrt(expectation) only as diagnostics, not certifications.",
        "Inter-arrivals use adjacent rounded submit times, population standard deviation (ddof=0), and NumPy linear quantiles. Ties/zero gaps are retained. Raw continuous exponential draws are not exposed by the pinned generator and are not reconstructed.",
        "Fixed and sliding windows are half-open [start,start+width); fixed bins start at zero. All integer-second sliding starts are evaluated. Rounded arrivals at T=3600 are retained in an explicit endpoint bin, never dropped. Final tails use [T-L,T], including the endpoint. Prefill and Poisson-only burstiness are both reported to avoid confusing the deterministic startup burst with steady arrivals.",
        "",
        "## How much counts and burstiness vary",
        "",
        "| Job | Total count range | Poisson z range | Poisson inter-arrival CV range | Max sliding 60s Poisson count range |",
        "|---|---|---|---|---|",
    ]
    first = summary[summary.workload == summary.workload.iloc[0]]
    for job, frame in first.groupby("job_type"):
        lines.append(
            f"| {job} | {frame.total_count.min()}--{frame.total_count.max()} | {frame.poisson_count_z.min():.3f}--{frame.poisson_count_z.max():.3f} | {frame.poisson_interarrival_cv.min():.3f}--{frame.poisson_interarrival_cv.max():.3f} | {frame.poisson_max_window_60s.min()}--{frame.poisson_max_window_60s.max()} |"
        )
    z = first.loc[first.poisson_count_z.abs().idxmax()]
    lines += [
        "",
        "Bloom has the lowest arrival rate because its minimum execution time is 44 seconds (the others are 25,28,36), not because of a Bloom-specific stochastic rule. Compare deviations to each type's expectation; raw counts and rounded inter-arrival CVs are not directly interchangeable across rates.",
        f"Largest absolute Poisson count deviation is {abs(z.poisson_count_z):.3f} for {z.job_type}, seed {z.seed}. "
        + (
            "This exceeds the descriptive |z|>4 flag and merits inspection, not a bug verdict."
            if abs(z.poisson_count_z) > 4
            else "No count exceeds the descriptive |z|>4 flag."
        ),
        "",
        "## Previously good/bad Bloom seeds",
        "",
        "| Workload | Seed | Phase | Bloom Pj | Qualified | Bloom count z | Max60s Poisson | Final300s fraction |",
        "|---|---|---|---:|---|---:|---:|---:|",
    ]
    for row in joined.itertuples():
        lines.append(
            f"| {row.workload} | {row.seed} | {row.phase} | {row.Bloom_Pj:.6f} | {row.evidence_qualified_pass} | {row.poisson_count_z:.3f} | {row.poisson_max_window_60s} | {row.final_300s_fraction:.6f} |"
        )
    for workload, frame in joined.groupby("workload"):
        bad = frame[frame.Bloom_Pj > 0.1]
        good = frame[frame.Bloom_Pj <= 0.1]
        if len(bad) and len(good):
            lines.append(
                f"\n{workload}: observed bad/good Bloom subsets have mean count-z {bad.poisson_count_z.mean():.3f}/{good.poisson_count_z.mean():.3f}, mean max60s arrivals {bad.poisson_max_window_60s.mean():.1f}/{good.poisson_max_window_60s.mean():.1f}, and mean final300s fraction {bad.final_300s_fraction.mean():.4f}/{good.final_300s_fraction.mean():.4f}. These are small descriptive subsets of one exact candidate, not causal estimates."
            )
        else:
            lines.append(
                f"\n{workload}: this executed panel lacks both bad and good Bloom outcomes, so a within-candidate contrast is unavailable."
            )
    lines += [
        "",
        "## Interpretation and flags",
        "",
        "Prefill consumes the same Python RNG before arrivals, and types consume it sequentially: changing earlier types or their order changes later types' draws. Rounding creates ties and can place arrivals at the simulation endpoint. These are documented implementation properties, not newly demonstrated bugs. Runtime completion/evidence counts are not generated-arrival counts and need not match them.",
        "Reproducibility failures stop this tool. Cross-workload mismatches with identical arrival inputs also stop it. Passing controls and ordinary count deviations do not rule out scheduler/QoS or simulator issues. Do not infer causation or certify robustness from ten selected historical seeds. No optimizer or simulator repair is proposed by this diagnostic.",
        "",
        "The first three plots use one workload because arrivals are shared; cross-workload equality is checked explicitly. Full historical outcomes (including every Pj, evidence count, objective and source) and arrival-only trace data are included. No full runtime trees are retained.",
        "",
    ]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")


def execute(root, specification, output_parent, smoke=False):
    start = time.perf_counter()
    spec, history, missing_now = validate_lineage(root, specification)
    tables, Experiment, Jobs = load_generator(root)
    experiment = Experiment(str(safe_path(root, spec["experiment_path"])))
    actual = {
        "duration_seconds": experiment.simulation_duration,
        "N": experiment.server_count,
        "U": experiment.utilization,
        "iso_start_hour": experiment.iso_signal_start_hour,
        "randomize_iso_start": experiment.randomize_iso_start,
        "time_granularity": experiment.time_granularity,
        "workload_trace": experiment.workload_trace,
    }
    if actual != spec["fixed"]:
        raise ValueError("Physical experiment differs from the recent W2 lineage")
    seeds = spec["seed_panel"][:2] if smoke else spec["seed_panel"]
    profiles = [Jobs(str(safe_path(root, c["workload_path"]))) for c in spec["contexts"]]
    for j in profiles:
        if list(j.all_jobs.values()) != [
            "Resnet.infer.4",
            "GPT2.infer.4",
            "Llama.infer.4",
            "Bloom.infer.4",
        ]:
            raise ValueError("Unexpected ordered W2 job types")
    arrival_inputs = [
        {
            "job_order": j.all_jobs,
            "minimum_times": j.all_min_execution_time,
            "job_sizes": j.all_job_size,
            "rates": tables.generate_arrival_rates(experiment, j),
        }
        for j in profiles
    ]
    if arrival_inputs[0] != arrival_inputs[1]:
        raise ValueError("W2 arrival-driving inputs differ from audited profiles")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = output_parent / ("w2_workload_seed_forensics_" + stamp + ("_smoke" if smoke else ""))
    out.mkdir(parents=True, exist_ok=False)
    (out / "traces").mkdir()
    (out / "inputs").mkdir()
    manifest = {
        "tool": "argos.workload_seed_forensics",
        "version": VERSION,
        "created_utc": stamp,
        "mode": "two-seed-smoke" if smoke else "full-ten-seed-panel",
        "status": "RUNNING",
        "repo_shas": {
            "ARGOS": git(root, "rev-parse", "HEAD"),
            **{k: spec["setup_repositories"][k]["sha"] for k in ("FlexDC", "CONDOR-FLEXDC")},
        },
        "argos_working_tree_status": git(root, "status", "--porcelain"),
        "runtime": spec["runtime"],
        "pandas": pd.__version__,
        "seed_panel": seeds,
        "fixed_context": actual,
        "specification": spec,
        "specification_sha256": sha(specification),
        "historical_sources_missing_at_run": missing_now,
        "simulator_executions": 0,
        "arrival_hash_format": "LF UTF-8 CSV job_id,job_type_id,submit_time sorted by job_id",
        "full_table_hash_format": "10 x n C-order little-endian float64 bytes",
        "expected_generation_calls": len(seeds) * 2 + 1,
    }
    write_json(out / "manifest.json", manifest)
    write_csv(out / "historical_outcomes.csv", history)
    write_csv(
        out / "seed_panel.csv",
        pd.DataFrame(
            [
                {
                    "seed": s,
                    "origin": "recovered historical outcome",
                    "known_contexts_and_phases": ";".join(
                        history.loc[history.seed == s, "workload"]
                        + ":"
                        + history.loc[history.seed == s, "phase"]
                    ),
                }
                for s in seeds
            ]
        ),
    )
    write_json(
        out / "workload_input_comparison.json",
        {
            "arrival_inputs_equal": True,
            "arrival_inputs": arrival_inputs,
            "full_profiles": [j.to_dict() for j in profiles],
            "difference": "Only GPT2/Llama/Bloom qos_constraint values differ; they affect job-table QoS column, not arrival generation.",
        },
    )
    for c in spec["contexts"]:
        shutil.copyfile(
            safe_path(root, c["workload_path"]), out / "inputs" / (c["workload"] + ".ini")
        )
    shutil.copyfile(safe_path(root, spec["experiment_path"]), out / "inputs/experiment.ini")
    shutil.copyfile(specification, out / "inputs/diagnostic_specification.json")
    shutil.copyfile(root / "docs/WORKLOAD_SEED_FORENSICS.md", out / "source_audit.md")
    source_dir = out / "generator_source"
    for relative in GENERATOR_FILES:
        target = source_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / ".deps/FlexDC/src/peacsim" / relative, target)
    shutil.copyfile(Path(__file__), out / "diagnostic_source.py")
    summaries, hash_rows, comparisons, first_hashes = [], [], [], {}
    all_bins = {w: [] for w in WINDOWS}
    for index, (context, jobs) in enumerate(zip(spec["contexts"], profiles)):
        for seed in seeds:
            trace, table, prefill = generate(tables, experiment, jobs, seed)
            h, full = arrival_hash(trace), table_hash(table)
            if index == 0 and seed == seeds[0]:
                duplicate, duplicate_table, _ = generate(tables, experiment, jobs, seed)
                control = {
                    "seed": seed,
                    "workload": context["workload"],
                    "first_arrival_hash": h,
                    "repeat_arrival_hash": arrival_hash(duplicate),
                    "first_table_hash": full,
                    "repeat_table_hash": table_hash(duplicate_table),
                }
                write_json(out / "reproducibility_control.json", control)
                if h != control["repeat_arrival_hash"] or full != control["repeat_table_hash"]:
                    raise RuntimeError(
                        "Reproducibility failure: identical inputs did not regenerate identical table"
                    )
            if index == 0:
                first_hashes[seed] = (h, full)
            else:
                same = h == first_hashes[seed][0]
                comparisons.append(
                    {
                        "seed": seed,
                        "arrivals_identical": same,
                        "full_tables_identical": full == first_hashes[seed][1],
                        "first_arrival_sha256": first_hashes[seed][0],
                        "second_arrival_sha256": h,
                        "explained_difference": "qos_constraint column only",
                    }
                )
                if not same:
                    raise RuntimeError(
                        "Same seed and audited-equal arrival inputs produced different traces"
                    )
            hash_rows.append(
                {
                    "workload": context["workload"],
                    "seed": seed,
                    "arrival_sha256": h,
                    "full_table_sha256": full,
                    "generated_jobs": len(trace),
                }
            )
            write_csv(out / "traces" / f"{context['case']}_{seed}.csv.gz", trace)
            stats, bins = summarize(
                trace,
                context["workload"],
                seed,
                tables.generate_arrival_rates(experiment, jobs),
                experiment.simulation_duration,
                prefill,
                jobs.all_jobs,
            )
            summaries.extend(stats)
            for w in WINDOWS:
                all_bins[w].extend(bins[w])
            print(f"Generated {context['case']} seed {seed}: {len(trace)} jobs", flush=True)
    summary, hashes, comparison = (
        pd.DataFrame(summaries),
        pd.DataFrame(hash_rows),
        pd.DataFrame(comparisons),
    )
    if any(g.arrival_sha256.nunique() != len(seeds) for _, g in hashes.groupby("workload")):
        raise RuntimeError("Different seeds produced an identical arrival trace; investigate")
    write_csv(out / "per_seed_per_job_summary.csv", summary)
    write_csv(out / "trace_hashes.csv", hashes)
    write_csv(out / "cross_workload_same_seed_comparison.csv", comparison)
    for w in WINDOWS:
        write_csv(out / f"arrival_bins_{w}s.csv.gz", pd.DataFrame(all_bins[w]))
    bloom = summary[summary.job_type.str.startswith("Bloom")]
    joined = history[history.seed.isin(seeds)].merge(
        bloom, on=["workload", "seed"], how="left", validate="one_to_one"
    )
    if joined.total_count.isna().any():
        raise ValueError("Historical outcome linkage failed")
    write_csv(out / "historical_outcome_join.csv", joined)
    make_plots(out, summary, pd.DataFrame(all_bins[60]), joined)
    make_report(out, summary, comparison, joined, hashes, smoke)
    manifest.update(
        status="COMPLETE",
        elapsed_seconds=time.perf_counter() - start,
        controls={
            "reproducibility": "PASS",
            "different_seeds": "PASS",
            "same_seed_cross_workload": "IDENTICAL_ARRIVALS",
            "historical_linked_rows": len(joined),
        },
        output_file_hashes={
            p.relative_to(out).as_posix(): sha(p)
            for p in sorted(out.rglob("*"))
            if p.is_file() and p.name != "manifest.json"
        },
    )
    manifest["diagnostic_source_sha256"] = sha(Path(__file__))
    write_json(out / "manifest.json", manifest)
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    if size > 100 * 1024**2:
        raise RuntimeError("Unexpected output exceeds 100 MiB; no ZIP created")
    archive = out.with_suffix(".zip")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(out))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
    print(f"COMPLETE: {archive} ({archive.stat().st_size / 1024**2:.2f} MiB)", flush=True)
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Generate only the pinned W2 arrival tables and a compact forensic ZIP. Never runs FlexDC simulation or ARGOS optimization."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="ARGOS repository root (default: current directory)",
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("configs/diagnostics/w2_seed_forensics.json"),
        help="Audited lineage and deterministic ten-seed panel, relative to root",
    )
    parser.add_argument(
        "--output-parent",
        type=Path,
        default=Path("runs/diagnostics"),
        help="New timestamped outputs under this repository-relative directory",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Only the first two shared seeds, plus one identical-input repetition",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    execute(root, safe_path(root, args.spec), safe_path(root, args.output_parent), args.smoke)


if __name__ == "__main__":
    main()
