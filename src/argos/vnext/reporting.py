"""Join pre-query records to actual observations without fitting to outcomes."""

from collections import defaultdict
from dataclasses import asdict

import pandas as pd

from argos.campaign.identity import digest
from argos.contracts import assessment
from argos.provenance import read_json, sha256, write_json
from argos.types import observation_from_dict
from argos.vnext.correction import behaviors
from argos.vnext.mechanisms import geometry_key, scenario_status


def query_report(episode, state, method):
    frozen = {}
    for path in sorted((episode / "prequery").glob("*.json")):
        record = read_json(path)
        for e in record["entries"]:
            frozen[(e["candidate"]["candidate_id"], e["seed"], "search")] = (
                record,
                e,
                sha256(path),
            )
    dispatch = {}
    for path in sorted((episode / "dispatch").glob("*.json")):
        record = read_json(path)
        for c in record["candidates"]:
            dispatch[(c["candidate_id"], record["seed"], record["phase"])] = (record, sha256(path))
    prior = defaultdict(list)
    rows = []
    for raw in state["observations"]:
        o = observation_from_dict(raw)
        key = (o.candidate.candidate_id, o.seed, o.phase)
        location = geometry_key(o.candidate)
        before = scenario_status(prior[location])
        repeat_number = len(prior[location]) if o.phase == "search" else None
        if o.phase == "search":
            prior[location].append(o)
        after = scenario_status(prior[location])
        pred = behaviors(o.candidate.prediction) if o.candidate.prediction else None
        record, entry, hashvalue = frozen.get(key, ({}, {}, None))
        if not record:
            d, hashvalue = dispatch.get(key, ({}, None))
            record = {"created_unix": d.get("created_unix"), "mode": method}
        corrected = entry.get("corrected_behaviors", pred.tolist() if pred is not None else None)
        actual = behaviors(o.metrics) if o.metrics else None
        rows.append(
            {
                "candidate_id": o.candidate.candidate_id,
                "source": o.candidate.source,
                "elite_rank": o.candidate.provenance.get("v3_rank"),
                "region_id": o.candidate.region_id,
                "anchor": o.candidate.provenance.get("anchor"),
                "targeted_probe": o.candidate.provenance,
                "unique_location_id": digest(location),
                "scenario_id": o.seed,
                "phase": o.phase,
                "batch": o.batch,
                "repeat_number": repeat_number,
                "state_before": before,
                "state_after": after,
                "decision_reason": record["mode"],
                "prequery_timestamp": record.get("created_unix"),
                "prequery_file_sha256": hashvalue,
                "v3_prediction": asdict(o.candidate.prediction) if pred is not None else None,
                "corrected_behaviors": corrected,
                "correction_uncertainty": entry.get("model_uncertainty"),
                "actual": asdict(o.metrics) if o.metrics else None,
                "v3_residual": (actual - pred).tolist()
                if actual is not None and pred is not None
                else None,
                "corrected_residual": (actual - corrected).tolist()
                if actual is not None and corrected is not None
                else None,
                "assessment": assessment(o),
                "requested_P_R_weights": [
                    o.candidate.Pbar,
                    o.candidate.R,
                    list(o.candidate.weights),
                ],
                "effective_P_R_watts": [
                    o.reported.get("P_actual_watts"),
                    o.reported.get("R_actual_watts"),
                ],
                "effective_dynamic_job_allocation": "Time-varying AQA allocation; not inferred from nominal weights",
                "execution_id": o.execution_id,
                "runtime_seconds": o.runtime_seconds,
            }
        )
    write_json(episode / "query_audit.json", rows)
    pd.DataFrame(rows).to_csv(episode / "query_audit.csv", index=False)
    return rows
