"""Revalidate completed cached observations without spending simulator calls."""

from __future__ import annotations

import argparse
from pathlib import Path

from argos.config import Config
from argos.controller.argos_controller import SearchState
from argos.provenance import read_json, sha256, write_json
from argos.simulator.flexdc_adapter import FlexDCRunner


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    episode = args.episode.resolve()
    config = Config.load(episode / "resolved_config.yaml")
    state = SearchState.load(episode / "state.json")
    manifest = read_json(episode / "manifest.json")
    if sha256(episode / "resolved_config.yaml") != manifest["resolved_config_sha256"]:
        raise ValueError("Resolved config hash mismatch")
    runner = FlexDCRunner(args.root, episode, config)
    before = list((episode / "flexdc_raw").glob("*/attempt-*/execution.json"))
    for observation in state.observations:
        cache = episode / "flexdc_raw" / observation.execution_id / "observation.json"
        if not cache.is_file():
            raise ValueError("Missing cache: refusing to launch a new simulation during audit")
        checked = runner.evaluate(
            observation.candidate, observation.seed, observation.phase, observation.batch
        )
        if checked != observation:
            raise ValueError("Persisted observation/cache mismatch")
    after = list((episode / "flexdc_raw").glob("*/attempt-*/execution.json"))
    if before != after:
        raise ValueError("Audit must not create executions")
    report = {
        "episode_id": episode.name,
        "status": "PASS",
        "observations_revalidated": len(state.observations),
        "simulator_attempts_before": len(before),
        "simulator_attempts_after": len(after),
        "new_confirmation_evidence": 0,
    }
    write_json(episode / "recovery_audit.json", report)
    print(report)


if __name__ == "__main__":
    main()
