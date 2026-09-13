"""Resumable campaign orchestration with frozen source and completion seals."""

import os
import time
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path

from argos.campaign.cache import EarlyReplay, SimulatorCache
from argos.campaign.candidate_bank import get_bank, setup
from argos.campaign.config import campaign_identity, load_config
from argos.campaign.identity import digest, immutable_json, verify_files
from argos.campaign.ledger import validate_case_seeds, validate_ledger
from argos.campaign.methods import FixedController, fixed_probes
from argos.contracts import qualified
from argos.controller.argos_controller import Controller, SearchState
from argos.provenance import git, read_json, sha256, write_json
from argos.reporting.report import report
from argos.surrogate.v3_adapter import V3Adapter


@contextmanager
def campaign_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".campaign.lock").open("a+b") as f:
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
        f.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            f.seek(0)
            if os.name == "nt":
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


def audit_plan(root, directory):
    manifest = read_json(directory / "campaign_manifest.json")
    protocol = read_json(directory / "resolved_protocol.json")
    gate = directory / "execution_gate.json"
    if gate.exists():
        record = read_json(gate)
        if record["campaign_manifest_sha256"] != sha256(
            directory / "campaign_manifest.json"
        ) or record["expanded_plan_sha256"] != sha256(directory / "campaign_cases.csv"):
            raise ValueError("Sealed campaign plan changed")
    if sha256(Path(manifest["protocol_path"])) != manifest["protocol_sha256"] or digest(
        read_json(Path(manifest["protocol_path"]))
    ) != digest(protocol):
        raise ValueError("Frozen protocol changed")
    if campaign_identity(root) != manifest["identity"]:
        raise ValueError("Campaign source/runtime/artifact identity changed")
    ledger = validate_ledger(root / protocol["ledger"], manifest["ledger_sha256"])
    for case in manifest["cases"]:
        validate_case_seeds(case, ledger)
        if digest(case["bank_identity"]) != case["bank_id"]:
            raise ValueError("Planned bank identity mismatch")
        c = load_config(case["settings"])
        if sha256(Path(c.workload)) != case["workload_sha256"]:
            raise ValueError("Planned workload changed")
        from argos.context import check_context

        actual = check_context(root, c)
        if any(case["context"].get(k) != v for k, v in actual.items()):
            raise ValueError("Planned behavior context changed")
        for key, expected in case["context"]["input_hashes"].items():
            if sha256(root / ".deps/FlexDC" / getattr(c, key)) != expected:
                raise ValueError("Planned config changed")
    return manifest


def run_v3_only(episode, config, selected, simulator):
    path = episode / "state.json"
    state = SearchState.load(path) if path.exists() else SearchState(episode.name)
    start = time.perf_counter()

    def save():
        write_json(path, asdict(state))

    if state.phase == "SEARCH":
        if selected is None:
            state.phase = "NO_BID"
            state.stop_reason = "V3_NO_SAFE_ENDPOINT"
            save()
            return state
        if not state.pending:
            state.pending = [selected]
            state.search_calls = 1
            save()
        observation = simulator.evaluate_batch(state.pending, config.search_seed, "search", 1)[0]
        state.observations = [observation]
        state.pending = []
        state.completed_batches = 1
        if not observation.valid:
            state.phase = "ERROR"
            state.stop_reason = "invalid V3 validation"
        elif qualified(observation, config.min_qos_observations_per_type):
            state.incumbent = selected
            state.phase = "CONFIRM"
            state.stop_reason = "V3_SELECTED_BEFORE_VALIDATION"
            immutable_json(episode / "final/selected_candidate.json", asdict(selected))
        else:
            state.phase = "NO_BID"
            state.stop_reason = "V3_SELECTED_POINT_NOT_QUALIFIED"
        save()
    while state.phase == "CONFIRM" and state.confirmation_index < len(config.confirmation_seeds):
        seed = config.confirmation_seeds[state.confirmation_index]
        observation = simulator.evaluate_batch(
            [state.incumbent], seed, "confirmation", state.confirmation_index + 1
        )[0]
        state.observations.append(observation)
        state.confirmation_index += 1
        if not observation.valid:
            state.phase = "ERROR"
            state.stop_reason = "invalid confirmation evidence"
        save()
    if state.phase == "CONFIRM":
        state.phase = "DONE"
    state.elapsed_seconds += time.perf_counter() - start
    save()
    return state


def seal_method(episode, result):
    files = {}
    for relative in ["state.json", "resolved_config.yaml", "manifest.json", "frozen_probes.json"]:
        if (episode / relative).exists():
            files[relative] = sha256(episode / relative)
    for sub in ["logical_queries", "batch_accounting"]:
        for p in sorted((episode / sub).glob("*.json")):
            files[p.relative_to(episode).as_posix()] = sha256(p)
    immutable_json(episode / "completion.json", {"result": result, "files": files})


def _run(root, directory, phases=None):
    with campaign_lock(directory):
        manifest = audit_plan(root, directory)
        if git(root, "status", "--porcelain"):
            raise ValueError("Campaign execution requires clean Git")
        gate = directory / "execution_gate.json"
        if not gate.exists():
            raise ValueError(
                "Execution gate missing; tests, format, lint and doctor must be recorded before launch"
            )
        g = read_json(gate)
        if g["source_identity_digest"] != digest(manifest["identity"]) or g["status"] != "PASS":
            raise ValueError("Execution gate identity mismatch")
        cache = SimulatorCache(root, directory, manifest["identity"])
        adapter = None
        last_phase = None
        for case in manifest["cases"]:
            if phases is not None and case["phase"] not in phases:
                continue
            if last_phase is not None and case["phase"] != last_phase:
                from argos.campaign.reporting import campaign_report

                campaign_report(directory)
            last_phase = case["phase"]
            config = load_config(case["settings"])
            complete = all(
                (directory / "cases" / case["case_id"] / method / "completion.json").exists()
                for method in case["methods"]
            )
            if complete:
                for method in case["methods"]:
                    ep = directory / "cases" / case["case_id"] / method
                    verify_files(ep, read_json(ep / "completion.json")["files"])
                continue
            print(
                f"CONTEXT {case['case_id']} phase={case['phase']} {case['tier']} {case['workload']} N={config.server_count} U={config.utilization}",
                flush=True,
            )
            case_start = time.perf_counter()
            try:
                if adapter is None:
                    adapter = V3Adapter(root, config.torch_threads, config.device)
                values = setup(adapter, root, config)
                bank, bank_meta, reused = get_bank(directory, case, adapter, config, values)
                regions, v3_selected = bank
                _, _, _, _, domain, predict = values
                # Entire fixed strategy is frozen before the first method observes FlexDC.
                fixed_episode = directory / "cases" / case["case_id"] / "v3_fixed_probing"
                probes = (
                    fixed_probes(fixed_episode, config, domain, regions, predict)
                    if "v3_fixed_probing" in case["methods"]
                    else []
                )
                for method in case["methods"]:
                    episode = directory / "cases" / case["case_id"] / method
                    completion = episode / "completion.json"
                    if completion.exists():
                        verify_files(episode, read_json(completion)["files"])
                        continue
                    method_config = replace(
                        config,
                        search_mode="early_stop"
                        if method == "argos_early_stop"
                        else "fixed_budget",
                    )
                    episode.mkdir(parents=True, exist_ok=True)
                    cfg = episode / "resolved_config.yaml"
                    if cfg.exists():
                        if asdict(
                            load_config(__import__("yaml").safe_load(cfg.read_text()))
                        ) != asdict(method_config):
                            raise ValueError("Method config mismatch")
                    else:
                        method_config.save(cfg)
                    bank_used = method != "simulator_only_adaptive"
                    immutable_json(
                        episode / "manifest.json",
                        {
                            "campaign_id": manifest["campaign_id"],
                            "case_id": case["case_id"],
                            "method": method,
                            "argos_dirty": False,
                            "input_identity": {"context_contract": case["context"]},
                            "bank_id": case["bank_id"] if bank_used else None,
                            "bank_manifest_sha256": sha256(
                                directory / "cache/v3_banks" / case["bank_id"] / "manifest.json"
                            )
                            if bank_used
                            else None,
                            "argos_git_head": git(root, "rev-parse", "HEAD"),
                        },
                    )
                    simulator = cache.method(case, method, episode, method_config)
                    if (episode / "state.json").exists():
                        previous = SearchState.load(episode / "state.json")
                        for o in previous.observations:
                            if simulator.evaluate_one(o.candidate, o.seed, o.phase, o.batch) != o:
                                raise ValueError("Resumed state differs from raw evidence")
                    start = time.perf_counter()
                    print(f"METHOD {case['case_id']}/{method}", flush=True)
                    if method == "v3_only":
                        state = run_v3_only(episode, method_config, v3_selected, simulator)
                    else:
                        if method == "argos_early_stop":
                            fixed = SearchState.load(
                                directory
                                / "cases"
                                / case["case_id"]
                                / "argos_fixed_budget/state.json"
                            )
                            if fixed.phase not in {"DONE", "NO_BID"}:
                                raise ValueError("Fixed-budget stream incomplete")
                            simulator = EarlyReplay(simulator, fixed.observations)
                        kwargs = {
                            "episode": episode,
                            "config": method_config,
                            "domain": domain,
                            "regions": [] if method == "simulator_only_adaptive" else regions,
                            "simulator": simulator,
                            "predictor": (lambda c: c)
                            if method == "simulator_only_adaptive"
                            else predict,
                        }
                        controller = (
                            FixedController(**kwargs, proposals=probes)
                            if method == "v3_fixed_probing"
                            else Controller(**kwargs)
                        )
                        state = controller.run()
                    summary = report(episode, method_config, state)
                    result = {
                        "case_id": case["case_id"],
                        "method": method,
                        "bank_id": case["bank_id"] if bank_used else None,
                        "v3_logical_seconds": bank_meta["wall_seconds"] if bank_used else 0,
                        "bank_physically_reused": reused or method != "v3_only"
                        if bank_used
                        else False,
                        "snapshot_count": bank_meta["snapshot_count"] if bank_used else 0,
                        "region_count": bank_meta["region_count"] if bank_used else 0,
                        "physical_active_method_seconds": time.perf_counter() - start,
                        "state_phase": state.phase,
                        "status": summary["status"],
                    }
                    if state.phase == "ERROR":
                        raise RuntimeError(
                            f"Invalid evidence: {case['case_id']}/{method}; preserved raw output"
                        )
                    seal_method(episode, result)
                    from argos.campaign.reporting import campaign_report

                    campaign_report(directory)
                immutable_json(
                    directory / "cases" / case["case_id"] / "completion.json",
                    {
                        "case_id": case["case_id"],
                        "active_wall_seconds": time.perf_counter() - case_start,
                    },
                )
            except Exception as exc:
                write_json(
                    directory / "failures" / f"{case['case_id']}-{time.time_ns()}.json",
                    {
                        "case_id": case["case_id"],
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "status": "CAMPAIGN_STOPPED_INFRASTRUCTURE",
                    },
                )
                from argos.campaign.reporting import campaign_report

                campaign_report(directory)
                raise
        from argos.campaign.reporting import campaign_report

        return campaign_report(directory)


def audit(root, directory):
    manifest = audit_plan(root, directory)
    cache = SimulatorCache(root, directory, manifest["identity"])
    methods = physical = 0
    checked = set()
    for case in manifest["cases"]:
        bank = directory / "cache/v3_banks" / case["bank_id"]
        if (bank / "manifest.json").exists():
            data = read_json(bank / "manifest.json")
            if data["identity"] != case["bank_identity"]:
                raise ValueError("Bank identity mismatch")
            verify_files(bank, data["files"])
        for method in case["methods"]:
            ep = directory / "cases" / case["case_id"] / method
            if (ep / "manifest.json").exists():
                method_manifest = read_json(ep / "manifest.json")
                if method_manifest.get("bank_id") and method_manifest[
                    "bank_manifest_sha256"
                ] != sha256(bank / "manifest.json"):
                    raise ValueError("Method bank seal changed")
            if (ep / "completion.json").exists():
                verify_files(ep, read_json(ep / "completion.json")["files"])
                methods += 1
            if not (ep / "state.json").exists():
                continue
            config = load_config(case["settings"])
            simulator = cache.method(case, method, ep, config)
            state = SearchState.load(ep / "state.json")
            searches = [o for o in state.observations if o.phase == "search"]
            if (
                len(searches) > config.max_search_calls
                or state.search_calls > config.max_search_calls
            ):
                raise ValueError("Logical budget overrun")
            for o in state.observations:
                from argos.campaign.cache import logical_observation, physical_key
                from argos.types import Candidate

                key = physical_key(o.candidate, o.seed, simulator.context)
                folder = directory / "cache/flexdc" / key
                if not (folder / "physical_observation.json").exists():
                    raise ValueError("Physical evidence missing")
                if key not in checked:
                    candidate = Candidate(
                        key, o.candidate.Pbar, o.candidate.R, o.candidate.weights, "campaign_cache"
                    )
                    if not list((folder / "flexdc_raw").glob("*/observation.json")):
                        raise ValueError("Core recovery record missing; audit cannot execute")
                    runner = cache.runner_factory(root, folder, config)
                    observed = runner.evaluate(candidate, o.seed, "search", 1)
                    if logical_observation(observed, o.candidate, o.phase, o.batch) != o:
                        raise ValueError("Raw observation/state mismatch")
                    checked.add(key)
                    physical += 1
    return {
        "status": "PASS",
        "completed_methods": methods,
        "unique_physical_evidence_audited": physical,
        "reserved_seeds_used": False,
    }


def run(root, directory, phases=None):
    start = time.perf_counter()
    from datetime import datetime, timezone

    record = {"started_utc": datetime.now(timezone.utc).isoformat(), "phases": phases}
    try:
        result = _run(root, directory, phases)
        record["status"] = "COMPLETED_REQUESTED_PHASES"
        return result
    except BaseException as exc:
        record["status"] = "INTERRUPTED_OR_FAILED"
        record["error_type"] = type(exc).__name__
        raise
    finally:
        record["wall_seconds"] = time.perf_counter() - start
        write_json(directory / "execution_sessions" / f"{time.time_ns()}.json", record)
