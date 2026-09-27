"""Finish reports for a completed OC breadth run without evaluating candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from collections import Counter
from pathlib import Path

from argos.oc_basic import breadth_runner as report
from argos.oc_basic.breadth_plan import (
    ASSESSMENT_LEDGER,
    CONTRACT_CSV,
    PROTOCOL,
    SEARCH_LEDGER,
    preflight,
)
from argos.provenance import read_json, sha256


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def verify_reporting_only_change(source: Path, manifest: dict, protocol: dict) -> None:
    """Only the two aggregate-report corrections may differ from frozen source."""
    relative = "src/argos/oc_basic/breadth_runner.py"
    before = subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={source}",
            "-C",
            str(source),
            "show",
            f"{manifest['source_head_at_start']}:{relative}",
        ]
    )
    if hashlib.sha256(before).hexdigest() != protocol["source_hashes"][relative]:
        raise ValueError("Original run source does not match its frozen hash")
    old_call = "_aggregate(output, results, contracts, protocol, elapsed)"
    new_call = "_aggregate(root, output, results, contracts, protocol, elapsed)"
    old_identity = 'or oc["target_trace_hash"] != old["target_trace_hash"]'
    new_identity = 'or oc["grid_signal_hash"] != old["grid_signal_hash"]'
    old_argos_index = (
        'argos_old = pd.read_csv(root / ORIGINAL_RUN / "context_summary.csv").set_index("context")'
    )
    new_argos_index = (
        'argos_old = pd.read_csv(root / ORIGINAL_RUN / "context_summary.csv")\n'
        '    argos_old["context"] = argos_old.apply(\n'
        "        lambda row: context_key(\n"
        '            row["workload"], int(row["server_count"]), float(row["utilization"])\n'
        "        ),\n"
        "        axis=1,\n"
        "    )\n"
        '    argos_old = argos_old.set_index("context")'
    )
    historical = before.decode("utf-8").replace("\r\n", "\n")
    current = (source / relative).read_text(encoding="utf-8").replace("\r\n", "\n")
    if (
        historical.count(old_call) != 1
        or historical.count(old_identity) != 1
        or historical.count(old_argos_index) != 1
        or current
        != historical.replace(old_call, new_call)
        .replace(old_identity, new_identity)
        .replace(old_argos_index, new_argos_index)
    ):
        raise ValueError("Frozen runner changed beyond the three reporting-only corrections")


def validate(source: Path, root: Path, output: Path) -> tuple[list[dict], list[dict], dict]:
    protocol = read_json(source / PROTOCOL)
    manifest = read_json(output / "manifest.json")
    if manifest["protocol_sha256"] != sha256(source / PROTOCOL):
        raise ValueError("Run protocol hash differs from frozen protocol")
    if (
        manifest["scientific_root_head_at_start"]
        != subprocess.check_output(
            ["git", "-c", f"safe.directory={root}", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
        ).strip()
    ):
        raise ValueError("Scientific root revision changed")
    verify_reporting_only_change(source, manifest, protocol)
    for relative, expected in protocol["source_hashes"].items():
        if relative == "src/argos/oc_basic/breadth_runner.py":
            continue
        path = source / relative if (source / relative).exists() else root / relative
        if sha256(path) != expected:
            raise ValueError(f"Frozen source changed: {relative}")
    for relative, expected in (
        (SEARCH_LEDGER, protocol["search_seed_ledger_sha256"]),
        (ASSESSMENT_LEDGER, protocol["assessment_seed_ledger_sha256"]),
        (CONTRACT_CSV, protocol["context_contract_sha256"]),
    ):
        if sha256(source / relative) != expected:
            raise ValueError(f"Frozen ledger/contract changed: {relative}")
    _, contracts = preflight(root)
    search = read_json(source / SEARCH_LEDGER)
    assessment = read_json(source / ASSESSMENT_LEDGER)
    if (
        manifest["search_seed_ledger"] != search
        or manifest["assessment_seed_ledger"] != assessment
        or manifest["contexts"] != [c["context"] for c in contracts]
    ):
        raise ValueError("Run plan differs from frozen ledgers")
    if len(contracts) != 16 or len(assessment["pairs"]) != 30:
        raise ValueError("Incomplete benchmark plan")
    if len(rows(source / CONTRACT_CSV)) != 16:
        raise ValueError("Context contract is incomplete")

    results = []
    for contract in contracts:
        episode = output / contract["context"]
        result = read_json(episode / "context_summary.json")
        search_summary = read_json(episode / "search" / "summary.json")
        assessment_summary = read_json(episode / "final" / "assessment_summary.json")
        executions = rows(episode / "search" / "scenario_executions.csv")
        candidates = rows(episode / "search" / "candidate_summary.csv")
        selected_panel = rows(episode / "final" / "oc_search_panel.csv")
        checks = rows(episode / "final" / "matched_assessment.csv")
        bids = read_json(episode / "final" / "frozen_comparison_bids.json")
        if result["status"] != "COMPLETE" or result["context"] != contract["context"]:
            raise ValueError(f"Context is incomplete: {contract['context']}")
        if (
            result["search_calls"] != search_summary["total_search_calls"]
            or len(executions) != result["search_calls"]
            or result["search_calls"] > 400
            or result["selected_candidate_id"] != search_summary["selected_candidate_id"]
            or result["selected_parameters"] != bids["argos_oc"]
        ):
            raise ValueError(f"Search record differs: {contract['context']}")
        if result["grid_signal_hash"] != contract["grid_trace_hash"]:
            raise ValueError(f"Grid signal differs: {contract['context']}")
        eligible = [
            item
            for item in candidates
            if item["status"] == "TARGET_MET_COMPLETE" and item["complete_panel"] == "True"
        ]
        if (
            len(selected_panel) != 10
            or sum(cell["feasible"] == "True" for cell in selected_panel) != result["search_passes"]
            or result["search_passes"] < 8
            or len(eligible) != search_summary["eligible_candidates"]
            or min(
                eligible,
                key=lambda item: (
                    float(item["mean_objective_all"]),
                    -int(item["passes"]),
                    float(item["g_target"]),
                    item["candidate_id"],
                ),
            )["candidate_id"]
            != result["selected_candidate_id"]
        ):
            raise ValueError(f"8/10 selection semantics differ: {contract['context']}")
        for cell in executions:
            if (
                cell["execution_status"] != "COMPLETE"
                or cell["grid_signal_hash"] != result["grid_signal_hash"]
                or cell["initial_job_table_hash"]
                != result["initial_table_hashes"][cell["arrival_seed"]]
            ):
                raise ValueError(f"Search input identity differs: {contract['context']}")
        if (
            assessment_summary["status"] != "COMPLETE"
            or len(checks) != assessment_summary["completed_cells"]
        ):
            raise ValueError(f"Assessment is incomplete: {contract['context']}")
        counts = Counter(cell["method"] for cell in checks)
        pair_hashes: dict[int, str] = {}
        for method, bid in bids.items():
            if counts[method] != (30 if bid else 0):
                raise ValueError(f"Assessment count differs: {contract['context']} {method}")
        for cell in checks:
            index = int(cell["pair_index"])
            pair = assessment["pairs"][index - 1]
            if (
                int(cell["arrival_seed"]) != pair["arrival_seed"]
                or int(cell["runtime_seed"]) != pair["runtime_seed"]
                or cell["grid_signal_hash"] != result["grid_signal_hash"]
                or cell["execution_status"] != "COMPLETE"
            ):
                raise ValueError(f"Assessment identity differs: {contract['context']}")
            previous = pair_hashes.setdefault(index, cell["initial_job_table_hash"])
            if previous != cell["initial_job_table_hash"]:
                raise ValueError(f"Assessment methods used different tables: {contract['context']}")
        for name, value in result["initial_table_hashes"].items():
            identities = rows(episode / "arrival_panel" / "table_identity.csv")
            matching = [r for r in identities if int(r["arrival_seed"]) == int(name)]
            if len(matching) != 1 or matching[0]["initial_job_table_hash"] != value:
                raise ValueError(f"Arrival table identity differs: {contract['context']}")
        results.append(result)
    return results, contracts, protocol


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scientific-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parents[1]
    root, output = args.scientific_root.resolve(), args.output.resolve()
    results, contracts, protocol = validate(source, root, output)
    status = read_json(output / "run_status.json")
    if status["status"] not in {"INTERRUPTED_NEEDS_REVIEW", "COMPLETE"}:
        raise ValueError("Reporting-only finalization requires a completed scientific run")
    elapsed = sum(float(result["episode_wall_seconds_this_session"]) for result in results)
    report._aggregate(root, output, results, contracts, protocol, elapsed)
    archive = report._package(output)
    report._json(
        output / "run_status.json",
        {
            "status": "COMPLETE",
            "completed_contexts": 16,
            "total_contexts": 16,
            "reporting_only_finalization": True,
            "new_flexdc_calls_during_finalization": 0,
            "scientific_protocol_sha256": sha256(source / PROTOCOL),
            "reporting_source_commit": subprocess.check_output(
                ["git", "-c", f"safe.directory={source}", "-C", str(source), "rev-parse", "HEAD"],
                text=True,
            ).strip(),
            "sum_recorded_episode_seconds": elapsed,
            "archive": str(archive),
        },
    )
    report._package(output)
    print(output)
    print(archive)


if __name__ == "__main__":
    main()
