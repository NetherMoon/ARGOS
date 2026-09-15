"""New campaign runner; never dispatches non-original workloads."""

from __future__ import annotations

import argparse
import time
from collections import Counter
from dataclasses import asdict, replace

import numpy as np
import pandas as pd

from argos.campaign.candidate_bank import get_bank, setup
from argos.campaign.config import source_files
from argos.campaign.identity import digest, immutable_json, verify_files
from argos.campaign.runner import campaign_lock
from argos.contracts import assessment, qualified
from argos.controller.argos_controller import Controller
from argos.environment import package_versions
from argos.provenance import (
    ARTIFACT,
    CHECKPOINT,
    git,
    read_json,
    sha256,
    verify_dependencies,
    write_json,
)
from argos.search.regions import from_snapshot
from argos.simulator.flexdc_adapter import FlexDCRunner
from argos.types import candidate_from_dict, observation_from_dict
from argos.vnext.controller import EliteController, NextController
from argos.vnext.device import V3Adapter
from argos.vnext.mechanisms import groups, protected_elites, scenario_status
from argos.vnext.protocol import BASE, ROOT, prepare, validate_case
from argos.vnext.reporting import query_report

PROTOCOL = ROOT / "configs/vnext/protocol.json"


class PauseRequested(Exception):
    pass


class LoggedRunner:
    def __init__(self, runner, episode, pause):
        self.runner = runner
        self.episode = episode
        self.pause = pause

    def search_attempts(self):
        return self.runner.search_attempts()

    def evaluate_batch(self, candidates, seed, phase, batch):
        if self.pause.exists():
            raise PauseRequested("Paused before next simulator batch")
        record = {
            "candidates": [asdict(c) for c in candidates],
            "seed": seed,
            "phase": phase,
            "batch": batch,
        }
        path = self.episode / "dispatch" / f"{digest(record)}.json"
        if not path.exists():
            immutable_json(path, {**record, "created_unix": time.time()})
        return self.runner.evaluate_batch(candidates, seed, phase, batch)


def gate():
    if git(ROOT, "status", "--porcelain"):
        raise ValueError("Commit implementation and protocol before sealing execution")
    protocol = read_json(PROTOCOL)
    for case in protocol["cases"]:
        validate_case(case)
    log = BASE / "reports/all_tests.log"
    if (
        not log.exists()
        or "failed" in log.read_text().splitlines()[-1]
        or "passed" not in log.read_text().splitlines()[-1]
    ):
        raise ValueError("Passing regression log required")
    value = {
        "status": "PASS",
        "commit": git(ROOT, "rev-parse", "HEAD"),
        "protocol_sha256": sha256(PROTOCOL),
        "ledger_sha256": sha256(ROOT / "configs/vnext/seed_ledger.json"),
        "sources": source_files(ROOT),
        "runtime": package_versions(),
        "dependencies": verify_dependencies(ROOT),
        "checkpoint": sha256(ROOT / ARTIFACT / CHECKPOINT),
        "tests_sha256": sha256(log),
        "h1_preservation_sha256": sha256(BASE / "manifests/h1_before.json"),
    }
    immutable_json(BASE / "manifests/execution_gate.json", value)
    print("Execution gate sealed.", flush=True)


def audit_gate():
    g = read_json(BASE / "manifests/execution_gate.json")
    if (
        sha256(PROTOCOL) != g["protocol_sha256"]
        or sha256(ROOT / "configs/vnext/seed_ledger.json") != g["ledger_sha256"]
        or source_files(ROOT) != g["sources"]
        or package_versions() != g["runtime"]
        or verify_dependencies(ROOT) != g["dependencies"]
        or sha256(ROOT / ARTIFACT / CHECKPOINT) != g["checkpoint"]
    ):
        raise ValueError("Frozen source, protocol, runtime or checkpoint changed")
    if git(ROOT, "status", "--porcelain"):
        raise ValueError("Scientific execution requires clean Git")
    return g


def run(stage):
    g = audit_gate()
    protocol = read_json(PROTOCOL)
    directory = BASE / ("w2_development" if stage == "development" else "originals_verification")
    pause = BASE / "PAUSE"
    chosen = None
    if stage == "verification":
        choice = read_json(ROOT / "configs/vnext/selected.json")
        chosen = choice["method"]
        if choice["protocol_sha256"] != sha256(PROTOCOL):
            raise ValueError("Selected configuration protocol changed")
    with campaign_lock(directory):
        adapter = None
        for case in [c for c in protocol["cases"] if c["stage"] == stage]:
            config = validate_case(case)
            methods = case["methods"] if chosen is None else [chosen]
            if pause.exists():
                print("PAUSED at a safe boundary.", flush=True)
                return
            if all(
                (directory / "cases" / case["case_id"] / m / "completion.json").exists()
                for m in methods
            ):
                for m in methods:
                    ep = directory / "cases" / case["case_id"] / m
                    verify_files(ep, read_json(ep / "completion.json")["files"])
                continue
            if adapter is None:
                adapter = V3Adapter(ROOT, config.torch_threads, config.device)
            values = setup(adapter, ROOT, config)
            _, _, _, _, domain, predict = values
            identity = {
                "candidate_seed": config.candidate_seed,
                "workload_sha256": case["workload_sha256"],
                "N": 1000,
                "U": config.utilization,
                "starts": 512,
                "iterations": 1500,
                "sources": g["sources"],
                "checkpoint": g["checkpoint"],
                "device": adapter.device_metadata,
            }
            bank_case = {**case, "bank_id": digest(identity), "bank_identity": identity}
            print(
                f"CONTEXT {stage} {case['case_id']} {case['workload']} U={config.utilization}",
                flush=True,
            )
            (regions, selected), meta, _reused = get_bank(
                directory, bank_case, adapter, config, values
            )
            bank = directory / "cache/v3_banks" / bank_case["bank_id"] / meta["completed_attempt"]
            frame = pd.read_csv(bank / "endpoints.csv")
            for col in ["weights", "Predicted_QoS_Probabilities"]:
                frame[col] = frame[col].map(__import__("json").loads)
            frame["Iteration"] = config.iterations
            endpoints = [
                replace(
                    from_snapshot(row, config.iterations),
                    provenance={
                        "v3_selection_safe": bool(row["Safety_Both_Pass"]),
                        "tracking_slack": float(row["Safety_Tracking_Slack"]),
                        "qos_slack": float(row["Safety_QoS_Slack"]),
                    },
                )
                for row in frame.to_dict("records")
            ]
            elites = protected_elites(selected, endpoints, domain)
            for method in methods:
                ep = directory / "cases" / case["case_id"] / method
                ep.mkdir(parents=True, exist_ok=True)
                if (ep / "completion.json").exists():
                    verify_files(ep, read_json(ep / "completion.json")["files"])
                    continue
                if pause.exists():
                    print("PAUSED.", flush=True)
                    return
                immutable_json(
                    ep / "manifest.json",
                    {
                        "case": case,
                        "method": method,
                        "gate_sha256": sha256(BASE / "manifests/execution_gate.json"),
                        "bank_id": bank_case["bank_id"],
                        "bank_seconds": meta["wall_seconds"],
                        "bank_reused": True,
                        "device": adapter.device_metadata,
                        "protocol_sha256": sha256(PROTOCOL),
                    },
                )
                runner = LoggedRunner(FlexDCRunner(ROOT, ep, config), ep, pause)
                try:
                    if method in {"H1", "E"}:
                        cls = Controller if method == "H1" else EliteController
                        kwargs = {} if method == "H1" else {"elites": elites}
                        state = cls(ep, config, domain, regions, runner, predict, **kwargs).run()
                        state = asdict(state)
                    else:
                        state = NextController(
                            ep,
                            config,
                            domain,
                            regions,
                            runner,
                            predict,
                            elites,
                            case["repeat_seeds"],
                            method,
                        ).run(pause)
                except PauseRequested:
                    print(
                        "PAUSED before simulator dispatch. Completed observations preserved.",
                        flush=True,
                    )
                    return
                if state["phase"] not in {"DONE", "NO_BID", "ERROR"}:
                    return
                query_report(ep, state, method)
                summary = summarize(state, case, method, meta["wall_seconds"])
                write_json(ep / "summary.json", summary)
                # Seal logical state and raw observation receipts; large simulator
                # output hashes are already recorded and verified by FlexDCRunner.
                files = {
                    p.relative_to(ep).as_posix(): sha256(p)
                    for p in ep.rglob("*.json")
                    if p.name != "completion.json"
                    and (
                        "attempt-" not in p.as_posix()
                        or p.name in {"observation.json", "execution.json"}
                    )
                }
                immutable_json(ep / "completion.json", {"result": summary, "files": files})
                report(stage)
                if state["phase"] == "ERROR":
                    raise RuntimeError(
                        "Invalid scientific execution: inspect preserved evidence before continuing"
                    )


def summarize(state, case, method, bank_seconds):
    obs = [observation_from_dict(o) for o in state["observations"]]
    search = [o for o in obs if o.phase == "search"]
    confirm = [o for o in obs if o.phase == "confirmation"]
    clustered = groups(search)
    good = [o for o in search if qualified(o)]
    robust = [g for g in clustered if scenario_status(g) == "SEARCH_ROBUST_FEASIBLE"]
    inc = candidate_from_dict(state["incumbent"]) if state.get("incumbent") else None
    chosen = [
        o
        for o in search
        if inc
        and (o.candidate.Pbar, o.candidate.R, o.candidate.weights) == (inc.Pbar, inc.R, inc.weights)
    ]
    return {
        "case": case["case_id"],
        "workload": case["workload"],
        "U": case["settings"]["utilization"],
        "method": method,
        "phase": state["phase"],
        "search_qualified": bool(good),
        "search_robust": bool(robust),
        "first_qualified_call": next((i for i, o in enumerate(search, 1) if qualified(o)), None),
        "search_calls": state["search_calls"],
        "unique_geometries": len(clustered),
        "repeat_calls": len(search) - len(clustered),
        "confirmation_passes": sum(qualified(o) for o in confirm),
        "confirmation_count": len(confirm),
        "selected_objective": float(np.mean([o.metrics.objective for o in chosen]))
        if chosen
        else None,
        "winner_source": inc.source if inc else None,
        "source_counts": dict(Counter(o.candidate.source for o in search)),
        "bank_seconds": bank_seconds,
        "timing": state.get("timing", {"active_wall": state.get("elapsed_seconds")}),
        "assessments": [
            {
                "candidate": asdict(o.candidate),
                "seed": o.seed,
                "phase": o.phase,
                "batch": o.batch,
                "metrics": asdict(o.metrics) if o.metrics else None,
                "assessment": assessment(o),
                "execution_id": o.execution_id,
                "residuals": o.residuals,
                "runtime_seconds": o.runtime_seconds,
            }
            for o in obs
        ],
    }


def report(stage):
    directory = BASE / ("w2_development" if stage == "development" else "originals_verification")
    rows = [
        read_json(p)
        for p in sorted((directory / "cases").glob("*/ */summary.json".replace(" ", "")))
    ]
    write_json(directory / "results.json", rows)
    if rows:
        pd.DataFrame(
            [
                {k: v for k, v in r.items() if k not in {"assessments", "timing", "source_counts"}}
                for r in rows
            ]
        ).to_csv(directory / "results.csv", index=False)
    return rows


def select():
    rows = report("development")
    if len(rows) != 16 or any(r["phase"] == "ERROR" for r in rows):
        raise ValueError("All 16 valid W2 method runs are required before selection")
    methods = ["H1", "E", "ER", "ERT"]
    ranking = []
    for method in methods:
        rs = [r for r in rows if r["method"] == method]
        objective_rank = 0
        for row in rs:
            available = sorted(
                [
                    x["selected_objective"]
                    for x in rows
                    if x["case"] == row["case"] and x["selected_objective"] is not None
                ]
            )
            objective_rank += (
                sum(v < row["selected_objective"] for v in available)
                if row["selected_objective"] is not None
                else 4
            )
        key = (
            -sum(r["confirmation_passes"] >= 2 for r in rs),
            -sum(r["confirmation_passes"] for r in rs),
            -sum(r["search_robust"] for r in rs),
            -sum(r["search_qualified"] for r in rs),
            sum(r["first_qualified_call"] or 33 for r in rs),
            objective_rank,
            methods.index(method),
        )
        ranking.append({"method": method, "selection_key": list(key)})
    ranking.sort(key=lambda r: r["selection_key"])
    value = {
        "method": ranking[0]["method"],
        "ranking": ranking,
        "protocol_sha256": sha256(PROTOCOL),
        "development_results_sha256": sha256(BASE / "w2_development/results.json"),
        "selection_rule": read_json(PROTOCOL)["selection_rule"],
    }
    immutable_json(ROOT / "configs/vnext/selected.json", value)
    print(
        value["method"] + " selected by the frozen rule. Final verification remains for the user.",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "gate", "run", "report", "select"])
    parser.add_argument("--stage", choices=["development", "verification"], default="development")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "gate":
        gate()
    elif args.command == "run":
        run(args.stage)
    elif args.command == "select":
        select()
    else:
        report(args.stage)


if __name__ == "__main__":
    main()
