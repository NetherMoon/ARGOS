"""All outcomes, logical/physical accounting, evidence and descriptive comparisons."""

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from argos.campaign.config import load_config
from argos.contracts import assessment, confirmation_status, qualified
from argos.controller.argos_controller import SearchState
from argos.provenance import read_json, write_json


def source_class(candidate):
    if candidate is None:
        return None
    if candidate.source == "local":
        return "local_refinement"
    if candidate.source == "independent":
        return "independent_exploration"
    if candidate.region_id:
        return "initial_v3_region_representative"
    return "v3_endpoint" if candidate.source == "V3 endpoint" else "v3_intermediate_snapshot"


def csv(path, rows, columns=None):
    encoded = [
        {
            k: json.dumps(v, allow_nan=False) if isinstance(v, (list, tuple, dict)) else v
            for k, v in row.items()
        }
        for row in rows
    ]
    pd.DataFrame(encoded, columns=columns if not rows else None).to_csv(path, index=False)


def table(rows):
    if not rows:
        return "_No completed observations._"
    columns = list(rows[0])
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        values = []
        for k in columns:
            v = row[k]
            if isinstance(v, float):
                v = f"{v:.4g}"
            values.append(str(v).replace("|", "/").replace("\n", " "))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def observation_row(case, method, o):
    return {
        "case_id": case["case_id"],
        "phase_number": case["phase"],
        "tier": case["tier"],
        "category": case["category"],
        "J": case["J"],
        "method": method,
        "source_class": source_class(o.candidate),
        **asdict(o),
        **assessment(o),
        "horizon_flags": [e.threshold_exceeds_horizon for e in o.qos_evidence]
        if o.qos_evidence
        else None,
    }


def campaign_report(directory: Path):
    manifest = read_json(directory / "campaign_manifest.json")
    results = []
    observations = []
    confirmations = []
    failures = []
    banks = []
    physical = []
    for case in manifest["cases"]:
        bank_path = directory / "cache/v3_banks" / case["bank_id"] / "manifest.json"
        if bank_path.exists():
            bank = read_json(bank_path)
            banks.append(
                {
                    "case_id": case["case_id"],
                    "bank_id": case["bank_id"],
                    "wall_seconds": bank["wall_seconds"],
                    "snapshot_count": bank["snapshot_count"],
                    "region_count": bank["region_count"],
                    "settings": bank["settings"],
                }
            )
        for method in case["methods"]:
            c = load_config(case["settings"])
            ep = directory / "cases" / case["case_id"] / method
            row = {
                k: case[k]
                for k in [
                    "case_id",
                    "phase",
                    "tier",
                    "category",
                    "workload",
                    "workload_sha256",
                    "J",
                    "context_hash",
                ]
            }
            row.update(
                campaign_id=manifest["campaign_id"],
                method=method,
                N=c.server_count,
                U=c.utilization,
                weight_policy=c.weight_policy,
                scenario_seed=c.search_seed,
                confirmation_seeds=c.confirmation_seeds,
                candidate_bank_seed=c.candidate_seed
                if method != "simulator_only_adaptive"
                else None,
                starts=c.starts if method != "simulator_only_adaptive" else 0,
                iterations=c.iterations if method != "simulator_only_adaptive" else 0,
                logical_search_budget=1 if method == "v3_only" else c.max_search_calls,
                attempted=(ep / "state.json").exists(),
                completed=(ep / "completion.json").exists(),
                status="NOT_ATTEMPTED",
                evidence_qualified_bid=False,
            )
            if not row["attempted"]:
                results.append(row)
                continue
            state = SearchState.load(ep / "state.json")
            searches = [o for o in state.observations if o.phase == "search"]
            confirms = [o for o in state.observations if o.phase == "confirmation"]
            valid = [o for o in searches if qualified(o)]
            selected = next(
                (o for o in searches if state.incumbent and o.candidate == state.incumbent), None
            )
            if selected is None and method == "v3_only" and searches and searches[0].valid:
                selected = searches[0]
            first = min((o.batch for o in valid), default=None)
            accounting = [read_json(p) for p in sorted((ep / "batch_accounting").glob("*.json"))]
            search_timing = [b for b in accounting if b["phase"] == "search"]
            receipts = [read_json(p) for p in sorted((ep / "logical_queries").glob("*.json"))]
            completion = read_json(ep / "completion.json")["result"] if row["completed"] else {}
            row.update(**completion)
            row.update(
                status=state.phase,
                stop_reason=state.stop_reason,
                batches=state.completed_batches,
                logical_search_calls=state.search_calls,
                completed_search_calls=len(searches),
                logical_confirmation_calls=len(confirms),
                physical_simulator_executions=sum(
                    not r["physical_execution_reused"] for r in receipts
                ),
                cache_hits=sum(r["physical_execution_reused"] for r in receipts),
                first_feasible_batch=first,
                queries_launched_through_first_feasible_batch=sum(
                    b["logical_queries"]
                    for b in search_timing
                    if first is not None and b["batch"] <= first
                )
                if first
                else None,
                logical_seconds_through_first_feasible_batch=sum(
                    b["logical_simulator_seconds"]
                    for b in search_timing
                    if first is not None and b["batch"] <= first
                )
                if first
                else None,
                evidence_qualified_bid=selected is not None and qualified(selected),
                selected_candidate=asdict(selected.candidate) if selected else None,
                winner_source=source_class(selected.candidate) if selected else None,
                winner_v3_origin=selected.candidate.source if selected else None,
                actual_objective=selected.metrics.objective if selected else None,
                actual_p90=selected.metrics.p90 if selected else None,
                actual_pj=selected.metrics.pj if selected else None,
                final_assessment=assessment(selected) if selected else None,
                final_qos_evidence=[asdict(e) for e in selected.qos_evidence]
                if selected and selected.qos_evidence
                else None,
                final_residuals=selected.residuals if selected else None,
                confirmation_status=confirmation_status(confirms),
                confirmation_passes=sum(qualified(o) for o in confirms),
                confirmation_expected=2,
                confirmation_executed=len(confirms),
                logical_simulator_seconds=sum(b["logical_simulator_seconds"] for b in accounting),
                physical_batch_wall_seconds=sum(b["physical_wall_seconds"] for b in accounting),
            )
            row["logical_total_seconds"] = (
                row.get("v3_logical_seconds", 0) + row["logical_simulator_seconds"]
            )
            if first:
                row["logical_seconds_through_first_feasible_batch"] += row.get(
                    "v3_logical_seconds", 0
                )
            results.append(row)
            for o in state.observations:
                record = observation_row(case, method, o)
                observations.append(record)
                if o.phase == "confirmation":
                    confirmations.append(record)
                if not o.valid:
                    failures.append(
                        {
                            "case_id": case["case_id"],
                            "method": method,
                            "kind": "INVALID_EXECUTION",
                            "execution_id": o.execution_id,
                            "details": o.error,
                        }
                    )
            if state.phase == "NO_BID":
                failures.append(
                    {
                        "case_id": case["case_id"],
                        "method": method,
                        "kind": "NO_BID",
                        "details": state.stop_reason,
                    }
                )
            if confirms and not all(qualified(o) for o in confirms):
                failures.append(
                    {
                        "case_id": case["case_id"],
                        "method": method,
                        "kind": "CONFIRMATION_FAILURE",
                        "details": confirmation_status(confirms),
                    }
                )
    for p in sorted((directory / "failures").glob("*.json")):
        failures.append(read_json(p))
    for p in sorted((directory / "cache/flexdc").glob("*/owner.json")):
        record = read_json(p)
        observation = p.parent / "physical_observation.json"
        record.update(
            complete=observation.exists(),
            attempt_count=len(list((p.parent / "flexdc_raw").glob("*/attempt-*/execution.json"))),
        )
        if observation.exists():
            o = read_json(observation)
            record.update(
                runtime_seconds=o["runtime_seconds"],
                valid=o["valid"],
                status=o["status"],
                execution_id=o["execution_id"],
            )
        physical.append(record)
    for name, rows, cols in [
        ("campaign_results", results, ["case_id", "method", "status"]),
        ("campaign_confirmations", confirmations, ["case_id", "method", "seed"]),
        ("campaign_failures", failures, ["case_id", "method", "kind", "details"]),
        ("candidate_bank_manifest", banks, ["case_id", "bank_id"]),
        ("simulator_cache_manifest", physical, ["key", "complete"]),
        ("campaign_observations", observations, ["case_id", "method", "phase"]),
    ]:
        csv(directory / (name + ".csv"), rows, cols)
    error_rows = []
    for o in observations:
        residuals = o["residuals"]
        for metric in ["p90", "max_pj", "objective"]:
            if metric in residuals:
                error_rows.append(
                    {k: o[k] for k in ["tier", "category", "method", "source_class", "J"]}
                    | {
                        "metric": metric,
                        "residual": residuals[metric],
                        "execution_id": o["execution_id"],
                    }
                )
        for i, value in enumerate(residuals.get("pj", [])):
            error_rows.append(
                {k: o[k] for k in ["tier", "category", "method", "source_class", "J"]}
                | {"metric": f"pj_{i}", "residual": value, "execution_id": o["execution_id"]}
            )
    csv(directory / "prediction_residuals.csv", error_rows, ["tier", "metric", "residual"])
    error_summary = []
    if error_rows:
        frame = pd.DataFrame(error_rows)
        for keys, g in frame.groupby(
            ["tier", "category", "method", "source_class", "J", "metric"], dropna=False
        ):
            a = g.residual
            error_summary.append(
                dict(zip(["tier", "category", "method", "source_class", "J", "metric"], keys))
                | {
                    "logical_observations": len(a),
                    "unique_executions": g.execution_id.nunique(),
                    "mean": float(a.mean()),
                    "median": float(a.median()),
                    "mean_absolute": float(a.abs().mean()),
                    "p10": float(a.quantile(0.1)),
                    "p90": float(a.quantile(0.9)),
                    "min": float(a.min()),
                    "max": float(a.max()),
                }
            )
    csv(directory / "prediction_error_summary.csv", error_summary, ["tier", "category", "metric"])
    aggregate = []
    for tier in ["ENGINEERING_SMOKE", "SCREENING", "SERIOUS_DEVELOPMENT"]:
        for method in sorted({r["method"] for r in results}):
            group = [
                r for r in results if r["tier"] == tier and r["method"] == method and r["attempted"]
            ]
            if not group:
                continue
            good = [r for r in group if r["evidence_qualified_bid"]]
            aggregate.append(
                {
                    "tier": tier,
                    "method": method,
                    "attempted": len(group),
                    "completed": sum(r["completed"] for r in group),
                    "qualified_bids": len(good),
                    "success_fraction_descriptive": len(good) / len(group),
                    "mean_search_calls": sum(r["logical_search_calls"] for r in group) / len(group),
                    "median_search_calls": float(
                        pd.Series([r["logical_search_calls"] for r in group]).median()
                    ),
                    "mean_success_objective": sum(r["actual_objective"] for r in good) / len(good)
                    if good
                    else None,
                    "confirmation_passes": sum(r["confirmation_passes"] for r in group),
                    "confirmation_runs": sum(r["confirmation_executed"] for r in group),
                    "mean_logical_seconds": sum(r["logical_total_seconds"] for r in group)
                    / len(group),
                }
            )
    csv(directory / "method_comparison.csv", aggregate, ["tier", "method", "attempted"])
    completed = sum(r["completed"] for r in results)
    text = [
        "# ARGOS controlled development campaign",
        f"\nCompleted method cases: {completed}/{len(results)}.",
        "\nThis is controlled development testing. Two confirmations provide descriptive evidence only. No reserved benchmark seed was used.",
        "\n## Protocol and frozen identities",
        f"Core: {manifest['identity']['core']['commit']}. Tag: v0.2.0-pretest.",
        f"Protocol SHA256: {manifest['protocol_sha256']}. Ledger SHA256: {manifest['ledger_sha256']}.",
        f"Checkpoint SHA256: {manifest['identity']['checkpoint_sha256']}.",
        "Dependencies: " + json.dumps(manifest["identity"]["dependencies"]),
        "Seed pool counts only: " + json.dumps(manifest["seed_group_counts"]),
        "\nScenario-invariance regression checks exact raw/differentiable features, predictions, endpoints, snapshots and trajectory. Bank settings and identities are in candidate_bank_manifest.csv and each immutable bank manifest.",
        "\n## Method comparison",
        table(aggregate),
    ]
    categories = []
    for tier in ["SCREENING", "SERIOUS_DEVELOPMENT"]:
        for category in sorted({r["category"] for r in results if r["tier"] == tier}):
            for method in sorted({r["method"] for r in results}):
                g = [
                    r
                    for r in results
                    if r["tier"] == tier
                    and r["category"] == category
                    and r["method"] == method
                    and r["attempted"]
                ]
                if g:
                    categories.append(
                        {
                            "tier": tier,
                            "category": category,
                            "method": method,
                            "attempted": len(g),
                            "qualified_bids": sum(r["evidence_qualified_bid"] for r in g),
                            "confirmation_passes": sum(r["confirmation_passes"] for r in g),
                        }
                    )
    csv(directory / "category_comparison.csv", categories, ["tier", "category", "method"])
    text += ["\n## Workload category comparison", table(categories)]
    for phase in range(6):
        text.append(f"\n## Phase {phase}")
        phase_rows = []
        for r in results:
            if r["phase"] == phase:
                phase_rows.append(
                    {
                        "case": r["case_id"],
                        "tier": r["tier"],
                        "workload": r["workload"],
                        "N/U": f"{r['N']}/{r['U']}",
                        "method": r["method"],
                        "status": r["status"],
                        "bid": r["evidence_qualified_bid"],
                        "objective": r.get("actual_objective"),
                        "calls": r.get("logical_search_calls"),
                        "first_batch": r.get("first_feasible_batch"),
                        "queries_through_batch": r.get(
                            "queries_launched_through_first_feasible_batch"
                        ),
                        "confirm": f"{r.get('confirmation_passes', 0)}/{r.get('confirmation_executed', 0)}",
                        "source": r.get("winner_source"),
                        "logical_seconds": r.get("logical_total_seconds"),
                    }
                )
        text.append(table(phase_rows))
    winners = Counter(
        (r["tier"], r["method"], r.get("winner_source"), r.get("winner_v3_origin"))
        for r in results
        if r["evidence_qualified_bid"]
    )
    winner_rows = [
        dict(zip(["tier", "method", "source", "v3_origin"], key)) | {"count": count}
        for key, count in winners.items()
    ]
    csv(directory / "winner_sources.csv", winner_rows, ["tier", "method", "source", "count"])
    text += ["\n## Winner sources", table(winner_rows)]
    pairs = []
    for case in manifest["cases"]:
        r = {r["method"]: r for r in results if r["case_id"] == case["case_id"] and r["completed"]}
        if "argos_fixed_budget" in r and "argos_early_stop" in r:
            fixed, early = r["argos_fixed_budget"], r["argos_early_stop"]
            pairs.append(
                {
                    "case_id": case["case_id"],
                    "tier": case["tier"],
                    "fixed_calls": fixed["logical_search_calls"],
                    "early_calls": early["logical_search_calls"],
                    "saved_calls": fixed["logical_search_calls"] - early["logical_search_calls"],
                    "same_selected_candidate": fixed["selected_candidate"]
                    == early["selected_candidate"],
                    "early_stop_reason": early["stop_reason"],
                }
            )
    csv(directory / "early_stop_comparison.csv", pairs, ["case_id", "saved_calls"])
    text += [
        "\n## Search efficiency and physical reuse",
        table(pairs),
        f"Unique completed physical simulator executions: {sum(p['complete'] for p in physical)}. Logical query receipts: {sum(r.get('completed_search_calls', 0) + r.get('logical_confirmation_calls', 0) for r in results)}.",
        f"Physical subprocess duration sum: {sum(p.get('runtime_seconds', 0) for p in physical):.3f} seconds (not wall time). Physical V3 bank time: {sum(b['wall_seconds'] for b in banks):.3f} seconds.",
        "Logical simulator time uses FIFO scheduling of recorded subprocess durations on the declared workers. Each V3 method pays the full bank creation time. Physical timing/reuse is reported separately. First feasibility counts all launched queries through the completed batch.",
        "\n## Prediction error",
        "Full p90, per-job Pj, max-Pj and objective residual distributions by tier/category/method/source/J are in prediction_error_summary.csv. Reused executions are not independent observations. Simulator-only has no V3 selection or diagnostic predictions.",
        "\n## Confirmation and evidence",
        "Every confirmation is in campaign_confirmations.csv, including raw Pj, typed evidence, unfinished counts and threshold/horizon flags. Nonempty evidence does not establish statistical reliability. One-hour zeros for thresholds beyond the horizon do not prove eventual QoS.",
        "\n## Failures",
        table(
            [
                {
                    "case": f.get("case_id"),
                    "method": f.get("method"),
                    "kind": f.get("kind", f.get("type")),
                    "details": f.get("details", f.get("message")),
                }
                for f in failures
            ]
        ),
        "\n## SA and optional suites",
        "SA was not executed: the unchanged pinned source fails the declared matched-scenario/canonical-objective compatibility gate. It assigns seeds by iteration and uses a different tracking-cost expression. Source evidence is in configs/campaigns/sa_compatibility_v1.json. No SA result is claimed. Optional repeated-profile cases and provenance-unsupported unseen-profile cases were not declared.",
        "\n## Research questions",
        research_questions(results, pairs, completed == len(results)),
        "\n## Limitations and recommendation",
        "One development search scenario and one initialization per context, two confirmations, limited one-hour horizon, shared physical evidence, and descriptive comparisons. Operating interpolation/extrapolation concerns N/U features only. Historical V4 changes QoS as well as composition. See complete candidate/evidence/residual records in the CSVs.",
        "Recommendation: evidence is mixed and more testing is needed."
        if completed == len(results)
        else "Recommendation deferred: the campaign is incomplete.",
    ]
    (directory / "REPORT.md").write_text("\n\n".join(text) + "\n", encoding="utf-8")
    summary = {
        "completed": completed,
        "planned": len(results),
        "physical_executions": sum(p["complete"] for p in physical),
        "banks_generated": len(banks),
        "failures": len(failures),
    }
    write_json(directory / "progress.json", summary)
    return summary


def research_questions(results, pairs, complete):
    serious = [r for r in results if r["tier"] == "SERIOUS_DEVELOPMENT" and r["completed"]]

    def counts(method, predicate=lambda r: True):
        g = [r for r in serious if r["method"] == method and predicate(r)]
        return f"{sum(r['evidence_qualified_bid'] for r in g)}/{len(g)}"

    answers = [
        f"RQ1 - Original controls, V3-only qualified bids: {counts('v3_only', lambda r: r['phase'] == 1)}.",
        f"RQ2 - Region usefulness: compare V3-only {counts('v3_only')} with fixed probing {counts('v3_fixed_probing')}; inspect paired case outcomes before attributing a rescue to regions.",
        f"RQ3 - Adaptive versus fixed: ARGOS {counts('argos_fixed_budget')}; fixed probing {counts('v3_fixed_probing')}. Objective comparisons are conditional on successful paired cases.",
        f"RQ4 - V3 guidance: ARGOS {counts('argos_fixed_budget')}; simulator-only {counts('simulator_only_adaptive')}.",
        "RQ5 - Initial versus local winners are enumerated in winner_sources.csv; local winners demonstrate selection after measured refinement, not proof refinement is necessary.",
        "RQ6 - Independent winners are enumerated separately; paired initial-batch failures must be inspected before claiming rescue.",
        f"RQ7 - ARGOS original W1 {counts('argos_fixed_budget', lambda r: r['category'] == 'ORIGINAL_W1')}; W2 {counts('argos_fixed_budget', lambda r: r['category'] == 'ORIGINAL_W2')}.",
        f"RQ8 - Serious clean J4 ARGOS bids: {counts('argos_fixed_budget', lambda r: r['category'] == 'CLEAN_J4_COMPOSITION')}. Constituents are familiar profiles.",
        f"RQ9 - Structural J ARGOS bids: {counts('argos_fixed_budget', lambda r: r['phase'] == 4)}. Category tables separate J3/J5/J6/J8 and historical V4.",
        f"RQ10 - Serious early-stop logical calls saved: {sum(p['saved_calls'] for p in pairs if p['tier'] == 'SERIOUS_DEVELOPMENT')}; exact-prefix checks required for every replay.",
        "RQ11 - prediction_error_summary.csv reports signed and absolute errors and ranges for every evaluated point with a prediction, separated by tier and context.",
        f"RQ12 - Serious fresh confirmations passed {sum(r.get('confirmation_passes', 0) for r in serious)} of {sum(r.get('confirmation_executed', 0) for r in serious)} logical confirmations. Exact shared physical results are not extra independent scenarios.",
    ]
    return (
        "Completed development results; no final benchmark claims.\n\n"
        if complete
        else "INTERIM: unanswered portions remain pending.\n\n"
    ) + "\n\n".join(answers)
