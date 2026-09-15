"""Exact-outcome first-batch counterfactual; unknown outcomes stay unknown."""

import json
from dataclasses import asdict, replace

import numpy as np
import pandas as pd

from argos.contracts import qualified
from argos.provenance import write_json
from argos.search.candidates import Domain
from argos.search.regions import from_snapshot
from argos.types import candidate_from_dict, observation_from_dict
from argos.vnext.mechanisms import geometry_key, protected_elites
from argos.vnext.offline import OLD, OUT, SOURCES, read, record


def main():
    manifest = read(OLD / "campaign_manifest.json")
    reports = []
    for case in [
        c for c in manifest["cases"] if c["case_id"] in [f"c{i:03d}" for i in range(1, 9)]
    ]:
        bank = OLD / "cache/v3_banks" / case["bank_id"]
        meta = read(bank / "manifest.json")
        attempt = bank / meta["completed_attempt"]
        domain = Domain(**meta["domain"])
        selected = read(attempt / "selection.json")
        selected = candidate_from_dict(selected) if selected else None
        frame = pd.read_csv(record(attempt / "endpoints.csv"))
        frame["Iteration"] = 1500
        for col in ["weights", "Predicted_QoS_Probabilities"]:
            frame[col] = frame[col].map(json.loads)
        endpoints = [
            replace(
                from_snapshot(row, 1500),
                provenance={
                    "v3_selection_safe": bool(row["Safety_Both_Pass"]),
                    "tracking_slack": float(row["Safety_Tracking_Slack"]),
                    "qos_slack": float(row["Safety_QoS_Slack"]),
                },
            )
            for row in frame.to_dict("records")
        ]
        elites = protected_elites(selected, endpoints, domain)
        regions = [candidate_from_dict(r["representative"]) for r in read(attempt / "regions.json")]
        batch = []
        for c in elites + regions:
            if all(domain.distance(c, p) > 1e-4 for p in batch):
                batch.append(c)
            if len(batch) == 6:
                break
        rng = np.random.default_rng(np.random.SeedSequence([case["settings"]["candidate_seed"], 1]))
        serial = 0
        while len(batch) < 8:
            c = domain.independent(rng, f"counterfactual-independent-{serial}")
            serial += 1
            if all(domain.distance(c, p) > 1e-4 for p in batch):
                batch.append(c)
        measured = {}
        original = []
        for method in case["methods"]:
            obs = [
                observation_from_dict(o)
                for o in read(OLD / "cases" / case["case_id"] / method / "state.json")[
                    "observations"
                ]
            ]
            for o in obs:
                if o.phase == "search" and o.seed == case["settings"]["search_seed"]:
                    measured.setdefault(geometry_key(o.candidate), {})[o.execution_id] = o
            if method == "argos_fixed_budget":
                original = [o for o in obs if o.phase == "search" and o.batch == 1]
        rows = []
        for c in batch:
            known = list(measured.get(geometry_key(c), {}).values())
            rows.append(
                {
                    "candidate": asdict(c),
                    "outcome_known": bool(known),
                    "actual": [
                        {
                            "qualified": qualified(o),
                            "metrics": asdict(o.metrics),
                            "execution_id": o.execution_id,
                        }
                        for o in known
                    ],
                }
            )
        reports.append(
            {
                "case": case["case_id"],
                "observed_first_batch_qualified": sum(qualified(o) for o in original),
                "counterfactual_known_qualified": sum(
                    any(o["qualified"] for o in r["actual"]) for r in rows
                ),
                "unknown_candidates": sum(not r["outcome_known"] for r in rows),
                "batch": rows,
                "interpretation": "Known feasible points establish only a lower bound on counterfactual first-batch feasibility. Unknown outcomes cannot establish final incumbent/objective or scenario robustness.",
            }
        )
    record(__file__)
    write_json(OUT / "elite_first_batch_replay.json", reports)
    write_json(OUT / "elite_replay_inputs.json", SOURCES)


if __name__ == "__main__":
    main()
