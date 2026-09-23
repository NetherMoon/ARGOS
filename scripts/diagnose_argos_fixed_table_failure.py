"""Bounded, resumable diagnosis of the frozen W2 qos5555/3883208862 miss.

This script never writes to the historical experiment. It reuses its saved job
table and V3 bank, and permits one cross-workload call plus at most 32 new
unchanged-controller search calls. It does not perform runtime checks.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from argos.contracts import assessment, observation_rank, qualified
from argos.fixed_table.runner import bank_for
from argos.fixed_table.simulator import FixedTableSimulator
from argos.provenance import git, read_json, sha256
from argos.types import candidate_from_dict, observation_from_dict
from argos.vnext.controller import NextController
from argos.vnext.correction import CorrectionSpec
from argos.vnext.device import V3Adapter

WORKLOAD = "W2-short-qos5555"
ARRIVAL = 3883208862
HISTORICAL = ROOT / "runs/experiments/argos_fixed_job_table_20260923T005508_888779Z"
OTHER = "W2-short-qos5_4.5_4_3.5"


def atomic_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf8")
    temporary.replace(path)


def verify(historical: Path) -> tuple[dict, dict, Path, dict, list]:
    manifest = read_json(historical / "manifest.json")
    seeds = read_json(historical / "seed_plan.json")
    episode = historical / WORKLOAD / f"arrival_{ARRIVAL}"
    context = read_json(episode / "fixed_context.json")
    state = read_json(episode / "vnext_state.json")
    # Plan wiring and bank JSON serialization were repaired after the historical
    # run; all simulator and scientific-controller sources must remain exact.
    allowed_diagnostic_changes = {
        "src/argos/fixed_table/runner.py",
        "src/argos/fixed_table/protocol.py",
    }
    for name, expected in manifest["source_hashes"].items():
        if name not in allowed_diagnostic_changes and sha256(ROOT / name) != expected:
            raise ValueError("Historical scientific source changed: " + name)
    for name, expected in manifest["specification"]["files"].items():
        if sha256(ROOT / name) != expected:
            raise ValueError("Historical FlexDC/config input changed: " + name)
    artifact = read_json(ROOT / "artifact_manifest.json")
    if sha256(ROOT / artifact["directory"] / artifact["selected_checkpoint"]) != manifest["checkpoint_sha256"]:
        raise ValueError("Pinned V3 checkpoint changed")
    if context["arrival_seed"] != ARRIVAL or context["case"]["workload"] != WORKLOAD:
        raise ValueError("Historical episode identity mismatch")
    if sha256(episode / "initial_jobs.csv.gz") != context["initial_file_sha256"]:
        raise ValueError("Historical table file changed")
    if context["grid_signal_hash"] != manifest["grid_trace_hash"]:
        raise ValueError("Historical grid identity changed")
    if seeds["search_runtime_seed"] != read_json(episode / "result.json")["search_runtime_seed"]:
        raise ValueError("Historical search seed mismatch")
    observations = [observation_from_dict(x) for x in state["observations"]]
    if len(observations) != 32 or state["batch"] != 4 or any(
        not o.valid or o.seed != seeds["search_runtime_seed"] or o.phase != "search"
        for o in observations
    ):
        raise ValueError("Historical 32-call observation state mismatch")
    if any(qualified(o) for o in observations):
        raise ValueError("Historical episode is not the recorded failure")
    for name, expected in manifest["dependency_shas"].items():
        if git(ROOT / ".deps" / name, "rev-parse", "HEAD") != expected:
            raise ValueError(f"Pinned {name} SHA changed")
    return manifest, seeds, episode, state, observations


def create_output(historical: Path, output: Path, manifest: dict, seeds: dict, episode: Path):
    output.mkdir(parents=True, exist_ok=True)
    path = output / "diagnostic_manifest.json"
    identity = {
        "schema": 1,
        "mode": "FAILED_FIXED_TABLE_BUDGET_EXTENSION_DIAGNOSTIC",
        "historical_path": str(historical),
        "historical_manifest_sha256": sha256(historical / "manifest.json"),
        "historical_state_sha256": sha256(episode / "vnext_state.json"),
        "historical_initial_job_table_hash": read_json(episode / "fixed_context.json")[
            "initial_job_table_hash"
        ],
        "historical_initial_file_sha256": sha256(episode / "initial_jobs.csv.gz"),
        "grid_signal_hash": manifest["grid_trace_hash"],
        "historical_repo_head": manifest["repo_head"],
        "dependency_shas": manifest["dependency_shas"],
        "checkpoint_sha256": manifest["checkpoint_sha256"],
        "v3_bank_id": read_json(episode / "result.json")["v3_bank_id"],
        "workload": WORKLOAD,
        "arrival_seed": ARRIVAL,
        "search_runtime_seed": seeds["search_runtime_seed"],
        "original_search_calls": 32,
        "maximum_new_cross_calls": 1,
        "maximum_new_continuation_calls": 32,
        "runtime_checks": 0,
        "continuation_semantics": "Fresh diagnostic batches 5-8 proposed by the unchanged NextController.propose() from the 32 saved search observations; no original call is rerun or retroactively changed.",
    }
    if path.exists():
        if read_json(path) != identity:
            raise ValueError("Diagnostic identity changed on resume")
    else:
        atomic_json(path, identity)


def offline(output: Path, episode: Path, observations: list) -> None:
    rows = []
    for index, o in enumerate(observations, 1):
        p = o.candidate.prediction
        a = assessment(o)
        rows.append({
            "call": index,
            "candidate_id": o.candidate.candidate_id,
            "candidate_source": o.candidate.source,
            "batch": o.batch,
            "Pbar": o.candidate.Pbar,
            "R": o.candidate.R,
            "weights": json.dumps(o.candidate.weights),
            "predicted_p90": p.p90 if p else None,
            "actual_p90": o.metrics.p90,
            "predicted_Pj": json.dumps(p.pj) if p else "",
            "actual_Pj": json.dumps(o.metrics.pj),
            "max_actual_Pj": max(o.metrics.pj),
            "tracking_pass": a["tracking_pass"],
            "qos_pass": a["qos_numerical_pass"],
            "qualified_pass": a["evidence_qualified_feasible"],
            "objective": o.metrics.objective,
            "normalized_tracking_violation": max(0.0, o.metrics.p90 / 0.3 - 1),
            "normalized_worst_qos_violation": max(0.0, max(o.metrics.pj) / 0.1 - 1),
            "p90_residual_actual_minus_predicted": o.metrics.p90 - p.p90 if p else None,
            "Pj_residual_actual_minus_predicted": json.dumps(
                [x - y for x, y in zip(o.metrics.pj, p.pj)]
            ) if p else "",
            "provenance": json.dumps(o.candidate.provenance),
        })
    csv_path = output / "offline_failed_table_analysis.csv"
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    expected_csv = stream.getvalue()
    if not csv_path.exists():
        csv_path.write_text(expected_csv, encoding="utf8", newline="")
    else:
        with csv_path.open("r", encoding="utf8", newline="") as existing:
            if existing.read() != expected_csv:
                raise ValueError("Offline CSV changed on resume")
    best = min(observations, key=observation_rank)
    qos_pass = [o for o in observations if max(o.metrics.pj) <= 0.1]
    track_pass = [o for o in observations if o.metrics.p90 <= 0.3]
    low_p90 = min(qos_pass, key=lambda o: o.metrics.p90)
    low_pj = min(track_pass, key=lambda o: max(o.metrics.pj))
    relevant = []
    for o in observations:
        triple = (
            max(0.0, o.metrics.p90 / 0.3 - 1),
            max(0.0, max(o.metrics.pj) / 0.1 - 1),
            o.metrics.objective,
        )
        if not any(
            all(x <= y + 1e-12 for x, y in zip((
                max(0.0, t.metrics.p90 / 0.3 - 1),
                max(0.0, max(t.metrics.pj) / 0.1 - 1),
                t.metrics.objective,
            ), triple))
            and any(x < y - 1e-12 for x, y in zip((
                max(0.0, t.metrics.p90 / 0.3 - 1),
                max(0.0, max(t.metrics.pj) / 0.1 - 1),
                t.metrics.objective,
            ), triple))
            for t in observations if t is not o
        ):
            relevant.append(o.candidate.candidate_id)
    from collections import Counter
    src = Counter(o.candidate.source for o in observations)
    weights = list(zip(*(o.candidate.weights for o in observations)))
    near = [o for o in observations if 0.46 < o.candidate.Pbar < 0.48]
    lines = [
        "# Frozen failed-table offline analysis", "",
        "32/32 calls parsed with sufficient QoS evidence. Tracking passed "
        f"{len(track_pass)}/32; all QoS constraints passed {len(qos_pass)}/32; both passed 0/32.", "",
        f"- Minimum normalized worst violation: {best.candidate.candidate_id}; p90={best.metrics.p90}, Pj={list(best.metrics.pj)}, objective={best.metrics.objective}.",
        f"- Lowest p90 among QoS-pass bids: {low_p90.candidate.candidate_id}; p90={low_p90.metrics.p90}, max Pj={max(low_p90.metrics.pj)}.",
        f"- Lowest max Pj among tracking-pass bids: {low_pj.candidate.candidate_id}; p90={low_pj.metrics.p90}, max Pj={max(low_pj.metrics.pj)}.",
        f"- Three-axis Pareto-relevant IDs (tracking violation, worst QoS violation, objective): {', '.join(relevant)}.",
        f"- Pbar range: {min(o.candidate.Pbar for o in observations)} to {max(o.candidate.Pbar for o in observations)}; R range: {min(o.candidate.R for o in observations)} to {max(o.candidate.R for o in observations)}.",
        f"- Weight ranges: {[(min(x), max(x)) for x in weights]}.",
        f"- {len(near)}/32 bids lie in Pbar (0.46, 0.48); their R range is {min(o.candidate.R for o in near)} to {max(o.candidate.R for o in near)}.",
        f"- Proposal sources: {dict(src)}.",
        "- V3 prediction residuals for every bid, including the near misses, are in the companion CSV. The nearest violation bid underpredicted both p90 and Bloom Pj substantially.",
        "", "No feasibility or controller conclusion follows from objective alone: infeasible low-cost bids cannot be selected.", "",
    ]
    text = "\n".join(lines)
    path = output / "offline_failed_table_analysis.md"
    if path.exists() and path.read_text(encoding="utf8") != text:
        raise ValueError("Offline Markdown changed on resume")
    path.write_text(text, encoding="utf8")


def copied_context(source: Path, destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    source_context = read_json(source / "fixed_context.json")
    table = destination / "initial_jobs.csv.gz"
    if not table.exists():
        shutil.copyfile(source / "initial_jobs.csv.gz", table)
    if sha256(table) != source_context["initial_file_sha256"]:
        raise ValueError("Diagnostic table copy differs from historical file")
    context = {**source_context, "output": str(destination.resolve())}
    context_path = destination / "fixed_context.json"
    if context_path.exists() and read_json(context_path) != context:
        raise ValueError("Diagnostic fixed context changed")
    if not context_path.exists():
        atomic_json(context_path, context)
    return context


def cross(output: Path, source: Path, seeds: dict):
    from argos.experimental_sa.paper_consistent.evaluator import FixedEvaluator
    from argos.experimental_sa.paper_consistent.objective import ObjectiveContract

    dest = output / "cross_workload"
    context = copied_context(source, dest)
    old = read_json(HISTORICAL / OTHER / f"arrival_{ARRIVAL}" / "selection.json")
    candidate = candidate_from_dict(old["candidate"])
    if candidate.candidate_id != "b4-target-0-003":
        raise ValueError("Cross-workload candidate identity changed")
    result = output / "cross_workload_diagnostic.json"
    if result.exists():
        return read_json(result)
    cell = dest / "evaluations/000001"
    if cell.exists():
        raise RuntimeError("Partial cross-workload cell requires review; no automatic retry")
    raw = FixedEvaluator(ROOT, dest)(
        (candidate.Pbar, candidate.R, *candidate.weights), 1, seeds["search_runtime_seed"]
    )
    if (raw["initial_job_table_hash"], raw["grid_signal_hash"], raw["arrival_seed"], raw["runtime_seed"]) != (
        context["initial_job_table_hash"], context["grid_signal_hash"], ARRIVAL, seeds["search_runtime_seed"]
    ):
        raise ValueError("Cross-workload scientific identity mismatch")
    objective = ObjectiveContract(ROOT).evaluate(raw["M_RSR"], raw["p90"], raw["Pj"])
    passed = raw["p90"] <= 0.3 and max(raw["Pj"]) <= 0.1 and min(raw["evidence_counts"]) >= 1
    record = {
        "role": "CROSS_WORKLOAD_DIAGNOSTIC_ONLY",
        "candidate": asdict(candidate),
        "workload": WORKLOAD,
        "arrival_seed": ARRIVAL,
        "runtime_seed": seeds["search_runtime_seed"],
        "initial_job_table_hash": raw["initial_job_table_hash"],
        "initial_file_sha256": context["initial_file_sha256"],
        "grid_signal_hash": raw["grid_signal_hash"],
        "target_trace_hash": raw["target_trace_hash"],
        "p90": raw["p90"], "Pj": raw["Pj"],
        "objective": objective.Cfull,
        "evidence_counts": raw["evidence_counts"],
        "tracking_pass": raw["p90"] <= 0.3,
        "qos_pass": max(raw["Pj"]) <= 0.1,
        "evidence_qualified_pass": passed,
        "failure_reason": "" if passed else "+".join(x for x, ok in [
            ("tracking", raw["p90"] <= 0.3), ("QoS", max(raw["Pj"]) <= 0.1),
            ("evidence", min(raw["evidence_counts"]) >= 1)] if not ok),
    }
    atomic_json(result, record)
    return record


def proposer(state: dict, config, domain, predictor, regions, elites) -> NextController:
    controller = object.__new__(NextController)
    controller.state = state
    controller.config = config
    controller.domain = domain
    controller.predictor = predictor
    controller.regions = regions
    controller.elites = elites
    controller.repeat_seeds = []
    controller.fixed_table_single_seed = True
    controller.variant = "ERT"
    controller.correction_spec = CorrectionSpec()
    return controller


def continue_search(output: Path, historical: Path, source: Path, seeds: dict, manifest: dict, state: dict, workers: int):
    from argos.fixed_table.protocol import GRID_TRACE_HASH
    from argos.types import observation_from_dict

    if not 1 <= workers <= 10:
        raise ValueError("--max-workers must be in [1,10]")
    dest = output / "continuation"
    context = copied_context(source, dest)
    adapter = V3Adapter(ROOT, 4, "cpu")
    config, domain, predictor, regions, elites, bank_meta, reused, bank_id = bank_for(
        ROOT, historical, WORKLOAD, seeds, manifest, adapter, workers
    )
    if not reused or bank_id != read_json(source / "result.json")["v3_bank_id"]:
        raise ValueError("Frozen V3 bank was not reused")
    simulator = FixedTableSimulator(ROOT, dest, config, context, workers)
    state_path = output / "continuation_state.json"
    if state_path.exists():
        current = read_json(state_path)
        if current["observations"][:32] != state["observations"]:
            raise ValueError("Saved first 32 observations changed")
    else:
        current = {**state, "phase": "DIAGNOSTIC_SEARCH", "pending": None}
        atomic_json(state_path, current)
    if current["batch"] not in range(4, 9) or len(current["observations"]) != 8 * current["batch"]:
        raise ValueError("Continuation batch/count mismatch")
    while current["batch"] < 8 and not any(
        qualified(observation_from_dict(o)) for o in current["observations"][32:]
    ):
        batch = current["batch"] + 1
        frozen = dest / "prequery" / f"batch_{batch:03d}.json"
        frozen.parent.mkdir(parents=True, exist_ok=True)
        if frozen.exists():
            query = read_json(frozen)
        else:
            query = proposer(current, config, domain, predictor, regions, elites).propose()
            if query["batch"] != batch or len(query["entries"]) != 8 or any(
                e["seed"] != seeds["search_runtime_seed"] or e["repeat"] for e in query["entries"]
            ):
                raise ValueError("Unexpected diagnostic proposal plan")
            old_geometry = {
                (o["candidate"]["Pbar"], o["candidate"]["R"], tuple(o["candidate"]["weights"]))
                for o in current["observations"]
            }
            geometry = [
                (e["candidate"]["Pbar"], e["candidate"]["R"], tuple(e["candidate"]["weights"]))
                for e in query["entries"]
            ]
            if len(set(geometry)) != 8 or any(g in old_geometry for g in geometry):
                raise ValueError("Duplicate diagnostic geometry")
            atomic_json(frozen, query)
        candidates = [candidate_from_dict(e["candidate"]) for e in query["entries"]]
        with ThreadPoolExecutor(max_workers=min(workers, 8)) as pool:
            futures = [
                pool.submit(simulator._evaluate, c, seeds["search_runtime_seed"], "search", batch, 32 + (batch - 5) * 8 + i + 1)
                for i, c in enumerate(candidates)
            ]
            observations = [f.result() for f in futures]
        if any(not o.valid for o in observations):
            raise RuntimeError("Invalid continuation observation; inspect diagnostic cell")
        current["observations"].extend(asdict(o) for o in observations)
        current["batch"] = batch
        current["search_calls"] = batch * 8
        current["pending"] = None
        atomic_json(state_path, current)
        print(f"Diagnostic batch {batch}: {sum(qualified(o) for o in observations)} qualified; {batch * 8}/64 total search calls", flush=True)
    new = [observation_from_dict(o) for o in current["observations"][32:]]
    csv_path = output / "continuation_results.csv"
    rows = [{
        "total_call": 33 + i, "candidate_id": o.candidate.candidate_id,
        "source": o.candidate.source, "batch": o.batch,
        "Pbar": o.candidate.Pbar, "R": o.candidate.R,
        "weights": json.dumps(o.candidate.weights), "p90": o.metrics.p90,
        "Pj": json.dumps(o.metrics.pj), "objective": o.metrics.objective,
        "evidence_counts": json.dumps([e.observation_count for e in o.qos_evidence]),
        "qualified_pass": qualified(o),
    } for i, o in enumerate(new)]
    if rows:
        with csv_path.open("w", newline="", encoding="utf8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    passed = [(33 + i, o) for i, o in enumerate(new) if qualified(o)]
    selected = min(passed, key=lambda item: (item[1].metrics.objective, item[1].candidate.candidate_id)) if passed else None
    result = {
        "new_calls": len(new), "total_search_calls": 32 + len(new),
        "qualified_new_calls": len(passed), "first_qualified_total_call": passed[0][0] if passed else None,
        "selected_qualified_diagnostic": {
            "total_call": selected[0], "candidate": asdict(selected[1].candidate),
            "p90": selected[1].metrics.p90, "Pj": list(selected[1].metrics.pj),
            "objective": selected[1].metrics.objective,
            "evidence_counts": [e.observation_count for e in selected[1].qos_evidence],
        } if selected else None,
        "runtime_checks_executed": 0,
        "same_initial_job_table_hash": all(
            o.reported["raw"]["initial_job_table_hash"] == context["initial_job_table_hash"] for o in new
        ),
        "same_grid_signal_hash": all(
            o.reported["raw"]["grid_signal_hash"] == GRID_TRACE_HASH for o in new
        ),
    }
    atomic_json(output / "continuation_summary.json", result)
    return result


def report(output: Path, cross_result: dict | None, continuation: dict | None):
    if cross_result is None or continuation is None:
        return
    case = "A" if cross_result["evidence_qualified_pass"] and continuation["qualified_new_calls"] else (
        "B" if cross_result["evidence_qualified_pass"] else
        "C" if continuation["qualified_new_calls"] else "D"
    )
    lines = [
        "# Failed fixed-table diagnostic", "",
        "Historical 32-call evidence was preserved; the cross-workload point is diagnostic only and is excluded from ARGOS search success.", "",
        f"Cross-workload point: p90={cross_result['p90']}, Pj={cross_result['Pj']}, objective={cross_result['objective']}, evidence counts={cross_result['evidence_counts']}, qualified={cross_result['evidence_qualified_pass']}.",
        f"It used arrival seed {cross_result['arrival_seed']}, runtime seed {cross_result['runtime_seed']}, fixed table hash `{cross_result['initial_job_table_hash']}`, grid hash `{cross_result['grid_signal_hash']}`, and target hash `{cross_result['target_trace_hash']}`.",
        f"Unchanged-controller extension: {continuation['new_calls']} new calls, {continuation['total_search_calls']} total, {continuation['qualified_new_calls']} qualified new observations; first at total call {continuation['first_qualified_total_call']}.",
        f"Decision case: {case}.",
    ]
    selected = continuation["selected_qualified_diagnostic"]
    if selected:
        lines.extend([
            f"Selected qualified continuation observation: `{selected['candidate']['candidate_id']}` from `{selected['candidate']['source']}`, Pbar={selected['candidate']['Pbar']}, R={selected['candidate']['R']}, weights={selected['candidate']['weights']}.",
            f"Measured p90={selected['p90']}, Pj={selected['Pj']}, objective={selected['objective']}, evidence counts={selected['evidence_counts']}.",
        ])
    lines.extend([
        "The original controller's hard four-batch stop was not altered. Batch 5 was proposed from its exact saved 32 observations and V3 bank; historical batches 2-4 were reconstructed offline. This is a budget-extension diagnostic, not a claim of an original 64-call run.",
        "No fresh runtime checks were run. This single known-failure table is development evidence, not validation.",
        "See `offline_failed_table_analysis.md`, `controller_tracking_direction_audit.md`, and the compact CSVs for details.", "",
    ])
    atomic_json(output / "diagnostic_report.json", {"case": case})
    (output / "diagnostic_report.md").write_text("\n".join(lines), encoding="utf8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-dir", type=Path, default=HISTORICAL)
    parser.add_argument("--diagnostic-dir", type=Path)
    parser.add_argument("--phase", choices=["offline", "cross", "continue", "all"], default="all")
    parser.add_argument("--max-workers", type=int, default=8)
    args = parser.parse_args(argv)
    historical = args.historical_dir.resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = (args.diagnostic_dir or ROOT / "runs/experiments" / f"argos_fixed_table_failed_seed_diagnostic_{stamp}").resolve()
    if not output.is_relative_to((ROOT / "runs/experiments").resolve()) or output == historical:
        parser.error("Diagnostic directory must be a new location inside runs/experiments")
    manifest, seeds, episode, state, observations = verify(historical)
    create_output(historical, output, manifest, seeds, episode)
    offline(output, episode, observations)
    cross_result = read_json(output / "cross_workload_diagnostic.json") if (output / "cross_workload_diagnostic.json").exists() else None
    continuation = read_json(output / "continuation_summary.json") if (output / "continuation_summary.json").exists() else None
    if args.phase in {"cross", "all"}:
        cross_result = cross(output, episode, seeds)
    if args.phase in {"continue", "all"}:
        continuation = continue_search(output, historical, episode, seeds, manifest, state, args.max_workers)
    report(output, cross_result, continuation)
    print(output)


if __name__ == "__main__":
    main()
