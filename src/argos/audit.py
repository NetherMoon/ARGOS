"""Read-only episode audit: reports new classifications without rewriting history."""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from argos.config import Config
from argos.contracts import assessment, qualified
from argos.controller.argos_controller import SearchState
from argos.controller.stopping import replay
from argos.provenance import read_json, sha256
from argos.search.integrity import verify_search_manifest
from argos.simulator.configuration import canonical_costs
from argos.simulator.output_parser import parse_output
from argos.types import candidate_from_dict, evidence_from_dict


def audit_episode(root: Path, episode: Path, allow_legacy: bool = False) -> dict:
    root, episode = root.resolve(), episode.resolve()
    config = Config.load(episode / "resolved_config.yaml")
    manifest = read_json(episode / "manifest.json")
    failures = []

    def check(condition, message):
        if not condition:
            failures.append(message)

    check(
        sha256(episode / "resolved_config.yaml") == manifest["resolved_config_sha256"],
        "resolved config hash mismatch",
    )
    expected = manifest.get("v3_search_manifest_sha256")
    search_integrity = "LEGACY_UNTRUSTED_SEARCH"
    if expected:
        try:
            verify_search_manifest(episode / "v3", config, expected)
            search_integrity = "VERIFIED"
        except (OSError, ValueError, KeyError) as exc:
            failures.append(str(exc))
    elif not allow_legacy:
        failures.append("Legacy search requires --allow-legacy-audit; no resume trust is granted")
    state = SearchState.load(episode / "state.json")
    attempts = sorted((episode / "flexdc_raw").glob("*/attempt-*/execution.json"))
    count_search = sum(read_json(p)["identity"]["phase"] == "search" for p in attempts)
    check(count_search <= config.max_search_calls, "search attempt budget exceeded")
    check(state.search_calls <= config.max_search_calls, "reserved search budget exceeded")
    check(state.completed_batches <= config.max_search_batches, "batch budget exceeded")
    rows, audited = [], []
    for o in state.observations:
        try:
            raw = o.raw_paths
            execution = read_json(Path(raw["execution"]))
            ident = execution["identity"]
            check(
                ident["seed"] == o.seed and ident["phase"] == o.phase and ident["batch"] == o.batch,
                f"execution identity mismatch {o.execution_id}",
            )
            check(
                candidate_from_dict(ident["candidate"]) == o.candidate,
                f"execution candidate mismatch {o.execution_id}",
            )
            for p, digest in execution["input_hashes"].items():
                check(sha256(Path(p)) == digest, f"input hash mismatch {Path(p).name}")
            for p, digest in o.reported.get("output_hashes", {}).items():
                check(sha256(Path(p)) == digest, f"output hash mismatch {Path(p).name}")
            if not o.valid:
                audited.append(o)
                rows.append(
                    {
                        "execution_id": o.execution_id,
                        "assessment": assessment(o, config.min_qos_observations_per_type),
                        "original_status": o.status,
                    }
                )
                continue
            metrics, reported = parse_output(
                Path(raw["results"]),
                Path(raw["diagnostics"]),
                o.candidate,
                config,
                o.seed,
                o.execution_id,
                ident["context"],
                root / ".deps/FlexDC" / config.workload,
                canonical_costs(root),
            )
            check(metrics == o.metrics, f"metric mismatch {o.execution_id}")
            checked = replace(
                o,
                qos_evidence=evidence_from_dict(reported["qos_evidence"])
                if reported["qos_evidence"] is not None
                else None,
                schema_version=2,
            )
            audited.append(checked)
            parent = Path(raw["results"]).parent
            rows.append(
                {
                    "execution_id": o.execution_id,
                    "candidate_id": o.candidate.candidate_id,
                    "phase": o.phase,
                    "seed": o.seed,
                    "batch": o.batch,
                    "original_status": o.status,
                    "metrics": asdict(metrics),
                    "assessment": assessment(checked, config.min_qos_observations_per_type),
                    "qos_evidence": reported["qos_evidence"],
                    "workload_fingerprint": reported["workload_fingerprint"],
                    "raw_hashes": {
                        name: sha256(parent / name)
                        for name in (
                            "grid_search_results.csv",
                            "grid_search_diagnostics.csv",
                            "job_table.csv",
                            "base_weights.csv",
                        )
                        if (parent / name).is_file()
                    },
                }
            )
        except (OSError, ValueError, KeyError) as exc:
            failures.append(f"{o.execution_id}: {exc}")
    search = [o for o in audited if o.phase == "search"]
    confirmations = [o for o in audited if o.phase == "confirmation"]
    check(all(o.seed == config.search_seed for o in search), "search seed mismatch")
    check(len({o.seed for o in confirmations}) == len(confirmations), "duplicate confirmation seed")
    check(
        all(
            o.seed in config.confirmation_seeds and o.seed != config.search_seed
            for o in confirmations
        ),
        "confirmation seed leakage",
    )
    check(
        all(o.candidate == state.incumbent for o in confirmations), "confirmation candidate changed"
    )
    eligible = [o for o in search if qualified(o, config.min_qos_observations_per_type)]
    if state.incumbent:
        check(
            any(o.candidate == state.incumbent for o in eligible),
            "historical incumbent is not evidence-qualified",
        )
        if eligible:
            best = min(eligible, key=lambda o: (o.metrics.objective, o.candidate.candidate_id))
            check(
                state.incumbent == best.candidate,
                "incumbent differs from best qualified search observation",
            )
    passes = sum(qualified(o, config.min_qos_observations_per_type) for o in confirmations)
    confirmation_status = (
        "CONFIRMATION_ALL_PASS"
        if confirmations and passes == len(confirmations) == len(config.confirmation_seeds)
        else "CONFIRMATION_PARTIAL_PASS"
        if passes
        else "CONFIRMATION_NONE_PASS"
    )
    check(
        attempts == sorted((episode / "flexdc_raw").glob("*/attempt-*/execution.json")),
        "audit created execution",
    )
    return {
        "audit_schema": 2,
        "episode_id": episode.name,
        "status": "FAIL" if failures else "PASS",
        "historical_search_integrity": search_integrity,
        "historical_records_modified": False,
        "new_simulator_calls": 0,
        "failures": failures,
        "observations": rows,
        "confirmation_status": confirmation_status,
        "confirmation_passes": passes,
        "confirmation_runs": len(confirmations),
        "qualified_search_count": len(eligible),
        "search_attempts": count_search,
        "selected_candidate_id": state.incumbent.candidate_id if state.incumbent else None,
        "early_stop_replay": replay(audited, config),
    }
