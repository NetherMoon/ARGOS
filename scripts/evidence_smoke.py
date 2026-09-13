"""One exact audit-only W1 invocation; never a search or fresh confirmation claim."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from pathlib import Path

from argos.config import Config
from argos.contracts import assessment
from argos.episode import doctor, episode_identity
from argos.provenance import git, write_json
from argos.simulator.flexdc_adapter import FlexDCRunner
from argos.types import Candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    if args.seed in {20, 100020, 100021}:
        raise ValueError("Use a new audit-only seed")
    root = args.root.resolve()
    config = replace(Config(), run_mode="paper", search_seed=args.seed, confirmation_seeds=())
    environment = doctor(root, config)
    directory = root / "runs" / f"evidence_smoke_seed_{args.seed}"
    directory.mkdir(parents=True, exist_ok=False)
    config.save(directory / "resolved_config.yaml")
    provenance = {
        "argos_git_head": git(root, "rev-parse", "HEAD"),
        "argos_dirty": False,
        "run_mode": "paper",
        "purpose": "single_exact_evidence_parser_audit",
        "identity": episode_identity(root, config),
    }
    write_json(directory / "manifest.json", provenance)
    candidate = Candidate(
        "audit-qos-w1",
        0.3663828670978546,
        0.21973192691802979,
        (0.44971099495887756, 0.16020098328590393, 0.16323329508304596, 0.22685472667217255),
        "audit",
    )
    runner = FlexDCRunner(root, directory, config)
    observation = runner.evaluate_batch([candidate], args.seed, "audit", 1)[0]
    count = len(list((directory / "flexdc_raw").glob("*/attempt-*/execution.json")))
    result = {
        "purpose": "audit_only_not_search_or_confirmation",
        "seed": args.seed,
        "executions": count,
        "provenance": provenance,
        "environment": environment,
        "candidate": asdict(candidate),
        "status": observation.status,
        "assessment": assessment(observation, config.min_qos_observations_per_type),
        "metrics": asdict(observation.metrics) if observation.metrics else None,
        "qos_evidence": [asdict(e) for e in observation.qos_evidence]
        if observation.qos_evidence
        else None,
        "error": observation.error,
    }
    write_json(directory / "summary.json", result)
    if count != 1 or not observation.valid or not result["assessment"]["evidence_sufficient"]:
        raise RuntimeError(f"Smoke failed; preserve and inspect {directory}")
    print(
        {
            "directory": directory.name,
            "seed": args.seed,
            "executions": count,
            "status": observation.status,
            "counts": [e.observation_count for e in observation.qos_evidence],
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
