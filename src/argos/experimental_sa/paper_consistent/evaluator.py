"""Fixed-arrival baseline using real pinned FlexDC APIs in isolated subprocesses.
The generator runs once in prepare(). Workers load/copy that table, never regenerate it.
The simulator and compact output observer are the same APIs verified in Phase 2.
"""

import csv
import gzip
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from argos.diagnostics.seed_factorization_worker import (
    JOB_COLUMNS,
    POWER_HEADER,
    QUEUE_COLUMNS,
    array_hash,
    check_context,
    job_summaries,
    observed_simulator,
)
from argos.diagnostics.workload_seed_forensics import generate, load_generator, sha, table_hash
from argos.simulator.evidence import ordered_jobs, validate_reported_qos_evidence


def prepare(root, output, spec, case, arrival_seed, expected_grid_hash):
    root = root.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name, digest in spec["files"].items():
        if sha(root / name) != digest:
            raise ValueError("Pinned input mismatch: " + name)
    tables, Experiment, Jobs = load_generator(root)
    e = Experiment(str(root / spec["experiment_path"]))
    e._utilization = case["U"]
    check_context(e, spec)
    j = Jobs(str(root / case["workload_path"]))
    _trace, initial, prefill = generate(tables, e, j, arrival_seed)
    initial.setflags(write=False)
    path = output / "initial_jobs.csv.gz"
    pd.DataFrame(initial.T, columns=JOB_COLUMNS).to_csv(
        path, index=False, compression="gzip", float_format="%.17g"
    )
    files = {
        str(p.relative_to(root)).replace("\\", "/"): sha(p)
        for p in (root / "src/argos/experimental_sa/paper_consistent").glob("*.py")
    }
    for name in [
        "scripts/run_experimental_sa.py",
        "src/argos/diagnostics/seed_factorization_worker.py",
        "src/argos/diagnostics/workload_seed_forensics.py",
        "src/argos/simulator/evidence.py",
        "src/argos/contracts.py",
        "src/argos/simulator/configuration.py",
        "configs/canonical_cost_source.ini",
        "configs/canonical_cost_source.json",
    ]:
        files[name] = sha(root / name)
    record = {
        "root": str(root),
        "output": str(output),
        "spec": spec,
        "case": case,
        "arrival_seed": arrival_seed,
        "initial_job_table_hash": table_hash(initial),
        "initial_file_sha256": sha(path),
        "prefill": prefill,
        "grid_signal_hash": expected_grid_hash,
        "files": files,
    }
    (output / "fixed_context.json").write_text(json.dumps(record, indent=2), encoding="utf8")
    return record, e, j


class FixedEvaluator:
    def __init__(self, root, output):
        self.root = root.resolve()
        self.output = output.resolve()

    def __call__(self, params, iteration, runtime_seed):
        if (
            isinstance(runtime_seed, bool)
            or not isinstance(runtime_seed, int)
            or not 0 <= runtime_seed < 2**32
        ):
            raise ValueError("Invalid runtime seed")
        cell = self.output / "evaluations" / f"{iteration:06d}"
        cell.mkdir(parents=True, exist_ok=False)
        request = {
            "context": str(self.output / "fixed_context.json"),
            "params": list(params),
            "runtime_seed": runtime_seed,
            "cell": str(cell),
        }
        request_path = cell / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf8")
        env = os.environ.copy()
        for name in ["OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"]:
            env[name] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        with (cell / "worker.log").open("w", encoding="utf8") as log:
            run = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(self.root / "scripts/run_experimental_sa.py"),
                    "--worker",
                    str(request_path),
                ],
                cwd=self.root,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=1800,
                check=False,
            )
        log_path = cell / "worker.log"
        tail = log_path.read_bytes()[-16384:]
        log_path.write_bytes(tail)
        if run.returncode:
            raise RuntimeError(
                "Isolated FlexDC execution failed; inspect " + str(cell / "worker.log")
            )
        return json.loads((cell / "raw_result.json").read_text())


def worker(request_path):
    started = time.monotonic()
    request = json.loads(request_path.read_text())
    context = json.loads(Path(request["context"]).read_text())
    root = Path(context["root"])
    cell = Path(request["cell"])
    spec = context["spec"]
    case = context["case"]
    if not cell.resolve().is_relative_to((Path(context["output"]) / "evaluations").resolve()):
        raise ValueError("Output outside private evaluation area")
    for name, digest in {**spec["files"], **context["files"]}.items():
        if sha(root / name) != digest:
            raise ValueError("Worker input changed: " + name)
    path = Path(context["output"]) / "initial_jobs.csv.gz"
    if sha(path) != context["initial_file_sha256"]:
        raise ValueError("Initial file changed")
    initial = pd.read_csv(path, float_precision="round_trip").to_numpy().T.copy()
    if table_hash(initial) != context["initial_job_table_hash"]:
        raise ValueError("Initial state changed")
    initial.setflags(write=False)
    tables, Experiment, Jobs = load_generator(root)
    sys.path.insert(0, str(root / ".deps/FlexDC/src/peacsim"))
    e = Experiment(str(root / spec["experiment_path"]))
    e._utilization = case["U"]
    e._random_seed = request["runtime_seed"]
    j = Jobs(str(root / case["workload_path"]))
    check_context(e, spec)
    wizard = importlib.import_module("peacsim.am_data_extraction_wizard")
    Policy = importlib.import_module("peacsim.parsing.policy_config_reader").PolicyConfigReader
    Cluster = importlib.import_module("peacsim.parsing.cluster_profile_reader").ClusterProfileReader
    Runtime = importlib.import_module("peacsim.aqa_runtimepolicy").AQARuntimePolicy
    Simulator = importlib.import_module("peacsim.simulator").Simulator
    qos = importlib.import_module("peacsim.calculate_qos_cost").calculate_delay_prob
    p, r, *weights = request["params"]
    weights_path = cell / "weights.csv"
    pd.DataFrame({"job_type_id": list(j.all_jobs.values()), "weights": weights}).to_csv(
        weights_path, index=False
    )
    parameters = wizard.build_policy_parameters(
        SimpleNamespace(
            policy_name="AQA",
            node_count_control=None,
            power_cap_percentage=None,
            probabilities=None,
        ),
        j.job_type_count,
    )
    if parameters != spec["policy_parameters"]:
        raise ValueError("Policy changed")
    parameters["weights_path"] = str(weights_path)
    pr = wizard.convert_kw_per_server_to_flexdc_pr(p, r, e, j)
    policy = Policy.from_parameters(
        policy_name="AQA",
        P=pr["P_actual_watts"],
        R=pr["R_actual_watts"],
        P_ratio=pr["Pbar_ratio"],
        R_ratio=pr["R_ratio"],
        policy_parameters=parameters,
    )
    mutable = initial.copy()
    nodes = tables.init_node_table(e)
    runtime = Runtime(policy, e, j, nodes, mutable)
    os.chdir(root / ".deps/FlexDC/src/peacsim")
    if Path(e.iso_file_path).resolve() != (root / spec["grid_path"]).resolve():
        raise ValueError("Grid path changed")
    scratch = cell / "scratch"
    scratch.mkdir()
    sim = observed_simulator(Simulator)(
        mutable,
        nodes,
        runtime,
        e,
        j,
        Cluster(str(root / spec["cluster_path"])),
        output_dir=str(scratch) + os.sep,
    )
    if table_hash(sim._job_table) != context["initial_job_table_hash"] or np.shares_memory(
        initial, sim._job_table
    ):
        raise ValueError("State copy failed")
    ticks = np.arange(3601)
    grid = np.column_stack([ticks, np.array(sim._iso_signal)[ticks // 2]])
    target = np.column_stack([ticks, np.array(sim._cluster_power_cap_per_signal)[ticks // 2]])
    if array_hash(grid) != context["grid_signal_hash"]:
        raise ValueError("Grid changed")
    if not np.allclose(target[:, 1], policy.P + policy.R * grid[:, 1], rtol=0, atol=1e-9):
        raise ValueError("Target construction mismatch")
    (scratch / "power_trace.csv").write_text(POWER_HEADER + "\n")
    (scratch / "PRtable.csv").write_text(f"phase,P,R\n0,{policy.P},{policy.R}\n")
    with gzip.open(scratch / "queue.csv.gz", "wt", newline="") as stream:
        sim.queue_writer = csv.writer(stream)
        sim.queue_writer.writerow(QUEUE_COLUMNS)
        power_cost, tracking_cost = sim.run()
    if table_hash(initial) != context["initial_job_table_hash"]:
        raise ValueError("Initial state mutated")
    jobs = sim._job_table
    pj = [
        float(x)
        for x in qos(1, j.job_type_count, jobs, j.all_job_qos_constraints, j.all_min_execution_time)
    ]
    evidence = validate_reported_qos_evidence(
        jobs, ordered_jobs(root / case["workload_path"]), tuple(pj)
    )
    power = pd.read_csv(scratch / "power_trace.csv", float_precision="round_trip")
    if (
        len(power) != 3601
        or power.time.tolist() != ticks.tolist()
        or abs(power.trackingError).quantile(0.9) != sim.tracking_error_at_90
    ):
        raise ValueError("Incomplete tracking evidence")
    summaries, accounting = job_summaries(jobs, evidence, context["prefill"])
    pd.DataFrame(summaries).to_csv(cell / "job_summary.csv", index=False)
    pd.DataFrame(accounting).to_csv(cell / "qos_accounting.csv", index=False)
    raw = {
        "status": "COMPLETE",
        "M_RSR": float(power_cost + tracking_cost),
        "monetary_power": float(power_cost),
        "monetary_tracking": float(tracking_cost),
        "mean_tracking": float(power.trackingError.iloc[1:].abs().mean()),
        "p90": float(sim.tracking_error_at_90),
        "Pj": pj,
        "evidence_counts": [int(x.observation_count) for x in evidence],
        "legacy_qos_proxy": float(sim.ratio_of_job_type_qos_violation),
        "arrival_seed": context["arrival_seed"],
        "runtime_seed": request["runtime_seed"],
        "initial_job_table_hash": table_hash(initial),
        "grid_signal_hash": array_hash(grid),
        "target_trace_hash": array_hash(target),
        "P_watts": policy.P,
        "R_watts": policy.R,
        "effective_policy_weights": list(runtime.weights.values()),
        "elapsed_seconds": time.monotonic() - started,
    }
    (cell / "raw_result.json").write_text(json.dumps(raw, indent=2, allow_nan=False))
    if scratch.resolve().parent != cell.resolve():
        raise ValueError("Unsafe scratch path")
    shutil.rmtree(scratch)
