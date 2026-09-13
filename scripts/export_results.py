"""Export compact research evidence without machine-specific absolute paths."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from argos.contracts import assessment
from argos.provenance import read_json, write_json
from argos.types import observation_from_dict


def portable(value, root: Path):
    if isinstance(value, str):
        for prefix in [str(root), root.as_posix(), json.dumps(str(root))[1:-1]]:
            value = value.replace(prefix, "<ARGOS_ROOT>")
        return value
    if isinstance(value, list):
        return [portable(x, root) for x in value]
    if isinstance(value, dict):
        return {portable(k, root): portable(v, root) for k, v in value.items()}
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    episode = args.episode.resolve()
    summary = read_json(episode / "summary.json")
    state = read_json(episode / "state.json")
    manifest = read_json(episode / "manifest.json")
    summary["execution_provenance"] = manifest
    summary["actual_simulator_attempts"] = len(
        list((episode / "flexdc_raw").glob("*/attempt-*/execution.json"))
    )
    summary["batch_wall_seconds"] = [
        read_json(p)["wall_seconds"] for p in sorted((episode / "search").glob("batch_*.json"))
    ]
    # State is atomically written at DONE before final report generation. This timestamp
    # measures the whole episode from manifest creation, including pool/config work.
    summary["episode_elapsed_seconds_from_timestamps"] = (
        episode / "state.json"
    ).stat().st_mtime - datetime.fromisoformat(manifest["created_at_utc"]).timestamp()
    summary["timing_semantics"] = (
        "Episode elapsed includes setup after manifest creation, V3, region extraction and controller; excludes preflight doctor. Active sum is V3 plus controller only."
    )
    summary["recovery_audit"] = (
        read_json(episode / "recovery_audit.json")
        if (episode / "recovery_audit.json").is_file()
        else None
    )
    target = root / "reports" / episode.name
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "summary.json", portable(summary, root))
    rows = []
    for o in state["observations"]:
        c = o["candidate"]
        m = o["metrics"]
        p = c["prediction"]
        rows.append(
            {
                **assessment(
                    observation_from_dict(o),
                    summary["config"].get("min_qos_observations_per_type", 1),
                ),
                "qos_evidence": json.dumps(o.get("qos_evidence")),
                "actual_max_pj": max(m["pj"]) if m else None,
                "candidate_id": c["candidate_id"],
                "Pbar": c["Pbar"],
                "R": c["R"],
                "weights": json.dumps(c["weights"]),
                "source": c["source"],
                "start_id": c["start_id"],
                "iteration": c["iteration"],
                "region_id": c["region_id"],
                "seed": o["seed"],
                "phase": o["phase"],
                "batch": o["batch"],
                "status": o["status"],
                "valid": o["valid"],
                "runtime_seconds": o["runtime_seconds"],
                "actual_p90": m["p90"] if m else None,
                "actual_pj": json.dumps(m["pj"]) if m else None,
                "actual_objective": m["objective"] if m else None,
                "predicted_p90": p["p90"] if p else None,
                "predicted_pj": json.dumps(p["pj"]) if p else None,
                "predicted_objective": p["objective"] if p else None,
            }
        )
    pd.DataFrame(rows).to_csv(target / "observations.csv", index=False)
    (target / "report.md").write_text(
        portable((episode / "report.md").read_text(), root), encoding="utf-8"
    )
    print(
        {
            "export": str(target.relative_to(root)),
            "episode_elapsed_seconds": summary["episode_elapsed_seconds_from_timestamps"],
            "batch_wall_seconds": summary["batch_wall_seconds"],
            "attempts": summary["actual_simulator_attempts"],
        }
    )


if __name__ == "__main__":
    main()
