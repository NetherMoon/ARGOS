"""Versioned, finite-panel ARGOS-OC search with deterministic progressive racing."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from argos.oc_basic import runner as v1
from argos.oc_basic.core import SEARCH_TABLES, geometry_key
from argos.oc_basic.v1_1 import (
    PROTOCOL_VERSION,
    candidate_state,
    complete_rank,
    next_batch,
    seed_order_from_v1,
    select_final,
    select_initial,
    serialize_state,
)
from argos.provenance import git, read_json, sha256
from argos.types import Candidate, candidate_from_dict

MODES = {
    "development": (1200.0, 250),
    "existence": (2400.0, 600),
    "cold20": (1200.0, 400),
    "cold10": (600.0, 300),
}
SOURCE_FILES = (
    "src/argos/oc_basic/core.py", "src/argos/oc_basic/runner.py",
    "src/argos/oc_basic/v1_1.py", "src/argos/oc_basic/runner_v1_1.py",
    "scripts/run_argos_oc_v1_1.py",
)


def _bool(value: object) -> bool:
    return value is True or str(value).lower() == "true"


def _read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = pd.read_csv(path).to_dict("records")
    for row in rows:
        for key in ("Pj", "evidence_counts"):
            if isinstance(row.get(key), str):
                row[key] = json.loads(row[key])
        for key in ("evidence_valid", "feasible"):
            row[key] = _bool(row.get(key))
        if row.get("candidate_number") is not None:
            row["candidate_number"] = int(row["candidate_number"])
    return rows


def _persist_rows(path: Path, rows: list[dict]) -> None:
    v1.atomic_csv(path, [
        {**r, "Pj": json.dumps(r["Pj"]), "evidence_counts": json.dumps(r["evidence_counts"])}
        for r in rows
    ])


def _v1_prior(source: Path) -> tuple[dict[str, Candidate], list[dict]]:
    old = source / "runs/experiments/argos_oc_basic_w2_n1000_u06_20260926T064500Z"
    if read_json(old / "run_status.json")["status"] != "COMPLETE_NO_TARGET_CANDIDATE":
        raise ValueError("Frozen v1 development source is not the recorded failed run")
    candidates = v1.read_candidate_batches(old)
    rows = _read_rows(old / "search" / "all_scenario_executions.csv")
    measured = {r["candidate_id"] for r in rows}
    if len(rows) != 110 or len(measured) != 11 or not measured.issubset(candidates):
        raise ValueError("Frozen v1 development evidence changed")
    # The five generated-but-unmeasured v1 proposals are not prior observations.
    return {key: value for key, value in candidates.items() if key in measured}, rows


def _batch_candidates(output: Path) -> dict[str, Candidate]:
    result = {}
    for path in sorted((output / "search").glob("batch_*_candidates.json")):
        for item in read_json(path):
            candidate = candidate_from_dict(item)
            if candidate.candidate_id in result or geometry_key(candidate) in {geometry_key(c) for c in result.values()}:
                raise ValueError("Duplicate candidate in frozen OC1.1 batches")
            result[candidate.candidate_id] = candidate
    return result


def _states(candidates: dict[str, Candidate], rows: list[dict], panel: list[int]) -> list:
    by_id: dict[str, list[dict]] = {key: [] for key in candidates}
    for row in rows:
        if row["candidate_id"] not in by_id:
            raise ValueError("Measured row has no frozen candidate")
        by_id[row["candidate_id"]].append(row)
    return [candidate_state(key, value, panel) for key, value in by_id.items()]


def _check_rows(rows: list[dict], panel: list[int], runtime_seed: int, table_hashes: dict[int, str]) -> None:
    keys = [(r["candidate_id"], int(r["arrival_seed"])) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate candidate/table measurement")
    if any(int(r["arrival_seed"]) not in panel or int(r["runtime_seed"]) != runtime_seed for r in rows):
        raise ValueError("OC scenario/runtime identity changed")
    if any(r["initial_job_table_hash"] != table_hashes[int(r["arrival_seed"])] for r in rows):
        raise ValueError("OC initial table hash mismatch")
    if len({r["grid_signal_hash"] for r in rows}) > 1:
        raise ValueError("OC grid trace changed across cells")
    if any(r["execution_status"] != "COMPLETE" for r in rows):
        raise ValueError("Simulator execution error is not a feasibility failure")


def _candidate_number(candidate_id: str, candidates: dict[str, Candidate]) -> int:
    # The number is a stable output-directory identity, not a ranking.
    return list(candidates).index(candidate_id) + 1


def _race_batch(root: Path, output: Path, batch: list[Candidate], candidates: dict[str, Candidate],
                all_rows: list[dict], new_rows: list[dict], seed_order: tuple[int, ...],
                runtime_seed: int, table_hashes: dict[int, str], workers: int,
                hard_cap: int, deadline: float, started: float) -> dict:
    launched = 0
    skipped = 0
    rounds = 0
    peak = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for seed in seed_order:
            measured = {(r["candidate_id"], int(r["arrival_seed"])) for r in all_rows}
            states = {s.candidate_id: s for s in _states(candidates, all_rows, list(seed_order))}
            ready = []
            for candidate in batch:
                if (candidate.candidate_id, seed) in measured:
                    continue
                state = states[candidate.candidate_id]
                if state.failures >= 3:
                    skipped += 1
                    continue
                ready.append(candidate)
            if not ready:
                continue
            if time.monotonic() - started >= deadline and rounds > 0:
                break
            capacity = max(0, hard_cap - len(new_rows))
            ready = ready[:capacity]
            if not ready:
                break
            rounds += 1
            # A fixed scenario round is a deterministic barrier. Completion
            # order only changes wall time, never the next proposal decision.
            for first in range(0, len(ready), workers):
                group = ready[first:first + workers]
                peak = max(peak, len(group))
                futures = {
                    pool.submit(v1.one_execution, root, output / "arrival_panel" / f"table_{seed}",
                                candidate, _candidate_number(candidate.candidate_id, candidates),
                                runtime_seed, "SEARCH"): candidate
                    for candidate in group
                }
                launched += len(group)
                for future in as_completed(futures):
                    row = future.result()
                    row["candidate_number"] = _candidate_number(row["candidate_id"], candidates)
                    row["batch"] = int(row["candidate_id"].split("-")[0][1:])
                    row["cumulative_search_wall_seconds"] = time.monotonic() - started
                    all_rows.append(row)
                    new_rows.append(row)
                    _check_rows(all_rows, list(seed_order), runtime_seed, table_hashes)
                    _persist_rows(output / "search" / "new_scenario_executions.csv", new_rows)
                    states_now = _states(candidates, all_rows, list(seed_order))
                    v1.atomic_csv(output / "search" / "candidate_states.csv", [serialize_state(s) for s in states_now])
                    v1.atomic_json(output / "search" / "progress.json", {
                        "status": "RUNNING", "new_calls_complete": len(new_rows),
                        "prior_calls_reused": len(all_rows) - len(new_rows),
                        "measured_candidates": sum(s.scenarios_evaluated > 0 for s in states_now),
                        "complete_panels": sum(s.complete_panel for s in states_now),
                        "early_rejected": sum(s.early_rejected for s in states_now),
                        "best_support": max((s.passes for s in states_now if s.complete_panel), default=0),
                        "best_g8": min((s.g8 for s in states_now if s.g8 is not None), default=None),
                        "elapsed_seconds": time.monotonic() - started,
                    })
            if len(new_rows) >= hard_cap:
                break
    return {"new_launches": launched, "early_rejection_skipped_opportunities": skipped,
            "seed_rounds": rounds, "peak_workers": peak}


def _write_summary(output: Path, candidates: dict[str, Candidate], rows: list[dict],
                   new_rows: list[dict], panel: list[int], mode: str, timing: dict) -> dict:
    states = _states(candidates, rows, panel)
    complete = [s for s in states if s.g8 is not None]
    best = min(complete, key=complete_rank) if complete else None
    selected = select_final(states)
    summary = {
        "protocol_version": PROTOCOL_VERSION, "mode": mode,
        "candidate_geometries": len(candidates), "measured_candidates": sum(s.scenarios_evaluated > 0 for s in states),
        "full_panels": sum(s.complete_panel for s in states),
        "partial_panels": sum(0 < s.scenarios_evaluated < SEARCH_TABLES for s in states),
        "early_rejected_candidates": sum(s.early_rejected for s in states),
        "new_simulator_executions": len(new_rows), "prior_simulator_executions_reused": len(rows) - len(new_rows),
        "executions_saved_by_racing": sum(SEARCH_TABLES - s.scenarios_evaluated for s in states if s.early_rejected),
        "best_pass_count": max((s.passes for s in complete), default=0),
        "best_g8": min((s.g8 for s in complete), default=None),
        "best_candidate_id": best.candidate_id if best else None,
        "eligible_candidates": sum(s.status == "TARGET_MET_COMPLETE" for s in states),
        "selected_candidate_id": selected.candidate_id if selected else None,
        "selected_mean_objective": selected.mean_objective_all_ten if selected else None,
        "selected_parameters": asdict(candidates[selected.candidate_id]) if selected else None,
        **timing,
    }
    v1.atomic_csv(output / "search" / "candidate_states.csv", [serialize_state(s) for s in states])
    v1.atomic_csv(output / "search" / "candidate_geometries.csv", [v1.candidate_row(c) for c in candidates.values()])
    v1.atomic_json(output / "summary.json", summary)
    lines = [f"# ARGOS-OC {PROTOCOL_VERSION} {mode}", "",
             f"- New search calls: **{len(new_rows)}**; prior v1 calls reused: **{len(rows)-len(new_rows)}**.",
             f"- Complete panels: **{summary['full_panels']}**; partial: **{summary['partial_panels']}**; early rejected: **{summary['early_rejected_candidates']}**.",
             f"- Best complete-panel support: **{summary['best_pass_count']}/10**; best g8: **{summary['best_g8']}**.",
             f"- Eligible >=8/10 candidates: **{summary['eligible_candidates']}**; selected: **{summary['selected_candidate_id']}**.",
             f"- Search wall: **{timing['search_wall_seconds']:.1f} s**; stop: **{timing['stop_reason']}**.",
             "", "Only all-ten-table candidates can be selected. X/10 is a finite-panel count, not a reliability estimate."]
    (output / "report.md").write_text("\n".join(lines), encoding="utf8")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="ARGOS-OC1.1 progressive ten-arrival search")
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--scientific-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-workers", type=int, default=10)
    parser.add_argument("--soft-search-seconds", type=float)
    parser.add_argument("--hard-call-cap", type=int)
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.max_workers <= 10:
        parser.error("--max-workers must be between 1 and 10")
    defaults = MODES[args.mode]
    soft = args.soft_search_seconds if args.soft_search_seconds is not None else defaults[0]
    cap = args.hard_call_cap if args.hard_call_cap is not None else defaults[1]
    if soft <= 0 or cap <= 0 or cap > 600:
        parser.error("Invalid soft time or new-call cap")
    source = Path(__file__).resolve().parents[3]
    root = args.scientific_root.resolve()
    output = args.output.resolve()
    if output.is_relative_to(root) or output.is_relative_to(source / "runs/experiments/argos_oc_basic_w2_n1000_u06_20260926T064500Z"):
        raise ValueError("OC1.1 output must not overwrite frozen scientific evidence")
    spec, _, bank, bank_manifest, panel, table_hashes, provenance = v1.preflight(root, source)
    old = source / "runs/experiments/argos_oc_basic_w2_n1000_u06_20260926T064500Z"
    old_manifest = read_json(old / "manifest.json")
    if old_manifest["seed_plan"] != provenance["seed_plan"]:
        raise ValueError("OC1.1 search or assessment seed contract differs from v1")
    difficulty = source / "runs/diagnostics/oc_basic_v1_forensics_20260926/diagnostics/arrival_seed_difficulty.csv"
    seed_order = seed_order_from_v1(pd.read_csv(difficulty).to_dict("records"))
    if set(seed_order) != set(panel):
        raise ValueError("Frozen v1 difficulty order does not cover search tables")
    identity = {
        "protocol_version": PROTOCOL_VERSION, "mode": args.mode,
        "scientific_root": str(root), "oc_source_root": str(source),
        "source_commit": git(source, "rev-parse", "HEAD"),
        "source_hashes": {p: sha256(source / p) for p in SOURCE_FILES},
        "frozen_v1_manifest_sha256": sha256(old / "manifest.json"),
        "historical_seed_difficulty_sha256": sha256(difficulty),
        "seed_order": seed_order, "seed_plan": provenance["seed_plan"],
        "phase2b": provenance["phase2b"], "bank_manifest_sha256": sha256(bank / "manifest.json"),
        "table_hashes": {str(k): v for k, v in table_hashes.items()},
        "max_workers": args.max_workers, "soft_search_seconds": soft, "new_call_cap": cap,
        "initial_candidates": 15, "refinement_batch_candidates": 8,
        "independent_quota": 2, "failure_cutoff": 3,
        "selection": "complete >=8/10, minimum mean canonical objective over all 10",
    }
    if args.smoke_only:
        print(json.dumps({"status": "SMOKE_PASS_NO_FLEXDC", "seed_order": seed_order,
                          "mode": args.mode, "source_commit": identity["source_commit"]}, indent=2))
        return
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "manifest.json"
    if manifest.exists():
        if read_json(manifest) != identity:
            raise ValueError("OC1.1 frozen source/config identity changed on resume")
    else:
        if any(output.iterdir()):
            raise ValueError("New OC1.1 directory must be empty")
        v1.atomic_json(manifest, identity)
        v1.atomic_json(output / "seed_order.json", {"order": seed_order, "basis": "v1 pass count ascending, minimum signed g descending, seed ascending"})
    if (output / "run_status.json").exists() and read_json(output / "run_status.json")["status"].startswith("COMPLETE"):
        print(f"Already complete: {output}")
        return
    v1.atomic_json(output / "run_status.json", {"status": "RUNNING", "started_utc": datetime.now(timezone.utc).isoformat()})
    wall_start = time.monotonic()
    table_start = time.monotonic()
    v1.ensure_search_tables(root, output, spec, identity["seed_plan"], table_hashes)
    table_seconds = time.monotonic() - table_start
    cloud, domain, cloud_timing = v1.build_cloud(root, output, bank, bank_manifest, identity["seed_plan"]["search_runtime_seed"])
    cloud_seconds = time.monotonic() - wall_start - table_seconds
    old_candidates, old_rows = _v1_prior(source) if args.mode == "development" else ({}, [])
    new_candidates = _batch_candidates(output)
    candidates = {**old_candidates, **new_candidates}
    new_rows = _read_rows(output / "search" / "new_scenario_executions.csv")
    all_rows = old_rows + new_rows
    _check_rows(all_rows, panel, identity["seed_plan"]["search_runtime_seed"], table_hashes)
    search_start = time.monotonic()
    prior_elapsed = float(read_json(output / "search" / "progress.json").get("elapsed_seconds", 0)) if (output / "search" / "progress.json").exists() else 0.0
    total_launched = total_skipped = peak = batches = 0
    stop_reason = "NEW_CALL_CAP"
    batch_number = max((int(path.stem.split("_")[1]) for path in (output / "search").glob("batch_*_candidates.json")), default=0)
    pending_batch_number = batch_number if batch_number and any(
        s.scenarios_evaluated < SEARCH_TABLES and s.failures < 3
        for s in _states(new_candidates, new_rows, panel)
        if s.candidate_id in {
            item["candidate_id"] for item in read_json(output / "search" / f"batch_{batch_number:03d}_candidates.json")
        }
    ) else None
    while len(new_rows) < cap:
        elapsed = prior_elapsed + time.monotonic() - search_start
        if batch_number and elapsed >= soft:
            stop_reason = "SOFT_SEARCH_WALL_TARGET"
            break
        next_number = pending_batch_number or batch_number + 1
        pending_batch_number = None
        batch_path = output / "search" / f"batch_{next_number:03d}_candidates.json"
        if batch_path.exists():
            batch = [candidate_from_dict(item) for item in read_json(batch_path)]
        elif batch_number == 0:
            if args.mode == "development":
                states = _states(candidates, all_rows, panel)
                batch = next_batch(batch=3, candidates=candidates,
                                   rows_by_candidate={key: [r for r in all_rows if r["candidate_id"] == key] for key in candidates},
                                   states=states, cloud=cloud, domain=domain,
                                   rng=np.random.default_rng(np.random.SeedSequence([20260926011, 3])))
            else:
                batch = select_initial(cloud, domain)
        else:
            states = _states(candidates, all_rows, panel)
            batch = next_batch(batch=next_number + (2 if args.mode == "development" else 0),
                               candidates=candidates,
                               rows_by_candidate={key: [r for r in all_rows if r["candidate_id"] == key] for key in candidates},
                               states=states, cloud=cloud, domain=domain,
                               rng=np.random.default_rng(np.random.SeedSequence([20260926011, next_number])))
        if not batch_path.exists():
            for candidate in batch:
                domain.validate(candidate)
                if candidate.candidate_id in candidates or geometry_key(candidate) in {geometry_key(c) for c in candidates.values()}:
                    raise ValueError("Generated duplicate OC1.1 candidate")
            v1.atomic_json(batch_path, [asdict(c) for c in batch])
        for candidate in batch:
            candidates[candidate.candidate_id] = candidate
        batch_number = next_number
        stats = _race_batch(root, output, batch, candidates, all_rows, new_rows, seed_order,
                            identity["seed_plan"]["search_runtime_seed"], table_hashes,
                            args.max_workers, cap, max(0.0, soft - prior_elapsed), search_start)
        total_launched += stats["new_launches"]
        total_skipped += stats["early_rejection_skipped_opportunities"]
        peak = max(peak, stats["peak_workers"])
        batches += 1
        states = _states(candidates, all_rows, panel)
        print(f"OC1.1 {args.mode} batch {batch_number}: {len(new_rows)} new calls; best {max((s.passes for s in states if s.complete_panel), default=0)}/10; g8 {min((s.g8 for s in states if s.g8 is not None), default=None)}", flush=True)
        if stats["new_launches"] == 0:
            stop_reason = "NO_NEW_TASKS"
            break
    timing = {"search_wall_seconds": prior_elapsed + time.monotonic() - search_start,
              "table_generation_seconds_this_invocation": table_seconds,
              "v3_cloud_seconds_this_invocation": cloud_seconds,
              "end_to_end_seconds_this_invocation": time.monotonic() - wall_start,
              "simulator_aggregate_seconds": sum(float(r["elapsed_seconds"]) for r in new_rows),
              "approximate_worker_utilization": min(1.0, sum(float(r["elapsed_seconds"]) for r in new_rows) / max(1e-9, args.max_workers * (prior_elapsed + time.monotonic() - search_start))),
              "peak_workers": peak, "new_tasks_launched_this_invocation": total_launched,
              "early_rejection_skipped_opportunities_this_invocation": total_skipped,
              "batches_this_invocation": batches, "stop_reason": stop_reason,
              "v3_cloud_timing": cloud_timing}
    summary = _write_summary(output, candidates, all_rows, new_rows, panel, args.mode, timing)
    selected = select_final(_states(candidates, all_rows, panel))
    assessment = []
    if args.mode == "existence" and selected is not None:
        old_assessment = old / "final" / "fresh_assessment_results.csv"
        if old_assessment.exists():
            raise ValueError("Historical held-out ledger was already used; freeze a new ledger before assessment")
        assessment, assess_timing = v1.run_assessment(root, output, spec, candidates[selected.candidate_id],
                                                       identity["seed_plan"], args.max_workers)
        summary["assessment"] = assess_timing
        v1.atomic_json(output / "summary.json", summary)
    v1.atomic_json(output / "run_status.json", {"status": "COMPLETE" if selected else "COMPLETE_NO_TARGET_CANDIDATE",
                                                "new_search_calls": len(new_rows), "assessment_calls": len(assessment),
                                                "completed_utc": datetime.now(timezone.utc).isoformat()})
    print(json.dumps({"output": str(output), "summary": summary}, default=str), flush=True)


if __name__ == "__main__":
    main()
