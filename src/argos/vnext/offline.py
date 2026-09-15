"""Offline original-only H1 audit. This module cannot launch FlexDC."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from argos.contracts import qualified
from argos.provenance import sha256, write_json
from argos.search.candidates import Domain
from argos.types import candidate_from_dict, observation_from_dict
from argos.vnext.correction import Correction, CorrectionSpec, behaviors

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / "runs/campaigns/controlled_development_v2"
OUT = ROOT / "runs/vnext_originals/offline"
SOURCES = {}


def record(path):
    path = Path(path).resolve()
    if any(p == ".env" or p.startswith(".env.") for p in path.parts):
        raise ValueError("Excluded secret file")
    if str(path) not in SOURCES:
        SOURCES[str(path)] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    return path


def read(path):
    return json.loads(record(path).read_text(encoding="utf-8-sig"))


from argos.vnext.costs import objective


def order(y, objs):
    v = np.maximum(y[:, 1:] / np.array([0.3, 0.1, 0.1, 0.1, 0.1]) - 1, 0)
    return sorted(
        range(len(y)), key=lambda i: (bool(v[i].max() > 0), v[i].max(), v[i].sum(), objs[i], i)
    )


def scores(actual, pred, actual_obj, pred_obj):
    actual_ok = (actual[:, 1] <= 0.3) & (actual[:, 2:].max(axis=1) <= 0.1)
    pred_ok = (pred[:, 1] <= 0.3) & (pred[:, 2:].max(axis=1) <= 0.1)
    ar = order(actual, actual_obj)
    pr = order(pred, pred_obj)
    aorder = np.argsort(ar)
    porder = np.argsort(pr)
    return {
        "p90_mae": float(abs(pred[:, 1] - actual[:, 1]).mean()),
        "mean_tracking_mae": float(abs(pred[:, 0] - actual[:, 0]).mean()),
        "pj_mae": abs(pred[:, 2:] - actual[:, 2:]).mean(axis=0).tolist(),
        "max_pj_mae": float(abs(pred[:, 2:].max(axis=1) - actual[:, 2:].max(axis=1)).mean()),
        "signed_bias": (pred - actual).mean(axis=0).tolist(),
        "classification_accuracy": float((actual_ok == pred_ok).mean()),
        "false_feasible": int((pred_ok & ~actual_ok).sum()),
        "missed_feasible": int((~pred_ok & actual_ok).sum()),
        "rank_spearman": float(spearmanr(aorder, porder).statistic),
        "top2_feasible": int(actual_ok[pr[:2]].sum()),
        "available_feasible": int(actual_ok.sum()),
        "objective_mae": float(abs(pred_obj - actual_obj).mean()),
        "normalized_constraint_mae": float(
            (abs(pred[:, 1:] - actual[:, 1:]) / np.array([0.3, 0.1, 0.1, 0.1, 0.1])).mean()
        ),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = read(OLD / "campaign_manifest.json")
    cases = [c for c in manifest["cases"] if c["case_id"] in [f"c{i:03d}" for i in range(1, 9)]]
    # This specification is persisted before fitting. No outcome-dependent hyperparameter grid.
    specs = [
        CorrectionSpec(model=m, space=s)
        for s in ["physical", "tracking_log"]
        for m in ["C0", "C1", "C2", "C3"]
        if m != "C0" or s == "physical"
    ]
    write_json(
        OUT / "ladder_specification.json",
        {
            "specs": [asdict(s) for s in specs],
            "stream": "argos_fixed_budget search only, each context separately",
            "folds": "fit B1->B2; B1+B2->B3; B1+B2+B3->B4",
            "selection": "Require positive W2 mean rank improvement and no loss of top2 feasible hits versus C0; normalized constraint MAE improvement >=5%; W1 rank loss <=0.05, W1 normalized MAE increase <=10%, no W1 top2 loss. Choose simplest eligible model; choose space by W2 rank then MAE. GP must beat best simpler eligible model by >=0.05 W2 rank and >=10% normalized MAE in >=3/4 W2 contexts; otherwise reject GP.",
        },
    )
    results = []
    geometry = []
    counterfactual = []
    for case in cases:
        cid = case["case_id"]
        bank = OLD / "cache/v3_banks" / case["bank_id"]
        meta = read(bank / "manifest.json")
        attempt = bank / meta["completed_attempt"]
        domain = Domain(**meta["domain"])
        frames = {
            name: pd.read_csv(record(attempt / f"{name}.csv"))
            for name in ["starts", "snapshots", "endpoints"]
        }
        pool = [candidate_from_dict(c) for c in read(attempt / "pool.json")]
        regs = read(attempt / "regions.json")
        selected_raw = read(attempt / "selection.json")
        selected = candidate_from_dict(selected_raw) if selected_raw else None
        states = {
            method: read(OLD / "cases" / cid / method / "state.json") for method in case["methods"]
        }
        observations = {
            method: [observation_from_dict(o) for o in state["observations"]]
            for method, state in states.items()
        }
        search = [o for o in observations["argos_fixed_budget"] if o.phase == "search"]
        for spec in specs:
            for batch in [2, 3, 4]:
                train = [o for o in search if o.batch < batch]
                test = [
                    o for o in search if o.batch == batch and o.valid and o.candidate.prediction
                ]
                model = Correction(domain, spec).fit(train)
                pred, std = model.predict([o.candidate for o in test])
                actual = np.array([behaviors(o.metrics) for o in test])
                aobj = np.array([o.metrics.objective for o in test])
                pobj = np.array([objective(o.candidate, y) for o, y in zip(test, pred)])
                result = {
                    "case": cid,
                    "family": case["category"],
                    "model": spec.model,
                    "space": spec.space,
                    "batch": batch,
                    "train_ids": model.training_ids,
                    "test_ids": [o.execution_id for o in test],
                    "training_geometries": len(model.x),
                    "metrics": scores(actual, pred, aobj, pobj),
                    "events": model.events,
                    "model_uncertainty_available": std is not None,
                }
                if set(result["train_ids"]) & set(result["test_ids"]):
                    raise AssertionError("Prequential leakage")
                results.append(result)
                write_json(
                    OUT / "predictions" / f"{cid}_{spec.model}_{spec.space}_b{batch}.json",
                    {
                        "summary": result,
                        "actual": actual.tolist(),
                        "predicted": pred.tolist(),
                        "model_uncertainty": std.tolist() if std is not None else None,
                    },
                )
        exact = [
            o
            for obs in observations.values()
            for o in obs
            if selected
            and (o.candidate.Pbar, o.candidate.R, o.candidate.weights)
            == (selected.Pbar, selected.R, selected.weights)
        ]
        same_seed = [
            o for o in exact if o.phase == "search" and o.seed == case["settings"]["search_seed"]
        ]
        unique = {o.execution_id: o for obs in observations.values() for o in obs}
        good = [o for o in unique.values() if qualified(o)]

        def nearest(candidates, domain=domain, selected=selected):
            return (
                min((domain.distance(selected, c) for c in candidates), default=None)
                if selected
                else None
            )

        geometry.append(
            {
                "case": cid,
                "workload": case["workload"],
                "utilization": case["settings"]["utilization"],
                "counts": {k: len(v) for k, v in frames.items()},
                "pool_size": len(pool),
                "regions": len(regs),
                "selected": selected_raw,
                "selected_in_pool": any(c.candidate_id == selected.candidate_id for c in pool)
                if selected
                else None,
                "selected_region_distance": nearest(
                    [candidate_from_dict(r["representative"]) for r in regs]
                ),
                "selected_first_batch_distance": nearest(
                    [o.candidate for o in search if o.batch == 1]
                ),
                "selected_later_batch_distance": nearest(
                    [o.candidate for o in search if o.batch > 1]
                ),
                "known_qualified_physical_evaluations": len(good),
                "known_qualified_sources": [
                    {
                        "method_sources": [
                            m
                            for m, obs in observations.items()
                            if any(x.execution_id == o.execution_id for x in obs)
                        ],
                        "candidate": asdict(o.candidate),
                        "phase": o.phase,
                        "metrics": asdict(o.metrics),
                        "execution_id": o.execution_id,
                    }
                    for o in good
                ],
                "selected_exact_observations": [
                    {
                        "phase": o.phase,
                        "qualified": qualified(o),
                        "metrics": asdict(o.metrics),
                        "execution_id": o.execution_id,
                    }
                    for o in {o.execution_id: o for o in exact}.values()
                ],
                "unknown_unqueried_outcomes": True,
            }
        )
        counterfactual.append(
            {
                "case": cid,
                "observed_batch1_qualified": sum(qualified(o) for o in search if o.batch == 1),
                "elite1_exact_same_scenario_qualified": any(qualified(o) for o in same_seed)
                if same_seed
                else None,
                "elite1_already_queried": any(
                    selected and o.candidate.candidate_id == selected.candidate_id for o in search
                ),
                "elite2_outcome": "UNKNOWN unless exact physical evidence; not imputed",
                "interpretation": "c008 elite1 would rescue single-scenario first-batch feasibility and NO_BID under H1 rules; this does not establish scenario robustness"
                if cid == "c008"
                else "Only exact observed elite outcome supports a counterfactual; alternative full-episode selection is unknown",
            }
        )
        print(f"offline {cid} complete", flush=True)
    write_json(OUT / "prequential.json", results)
    write_json(OUT / "geometry.json", geometry)
    write_json(OUT / "protected_elite_counterfactual.json", counterfactual)
    summary = []
    for spec in specs:
        for family in ["ORIGINAL_W1", "ORIGINAL_W2"]:
            rows = [
                r["metrics"]
                for r in results
                if r["model"] == spec.model and r["space"] == spec.space and r["family"] == family
            ]
            summary.append(
                {
                    "model": spec.model,
                    "space": spec.space,
                    "family": family,
                    **{
                        key: float(np.mean([r[key] for r in rows]))
                        for key in [
                            "p90_mae",
                            "max_pj_mae",
                            "classification_accuracy",
                            "rank_spearman",
                            "objective_mae",
                            "normalized_constraint_mae",
                        ]
                    },
                    "top2_feasible": sum(r["top2_feasible"] for r in rows),
                }
            )
    write_json(OUT / "ladder_summary.json", summary)
    for p in [
        ROOT / "src/argos/vnext/correction.py",
        Path(__file__),
        ROOT / "src/argos/contracts.py",
        ROOT
        / ".deps/CONDOR-FLEXDC/am_flexdc/flexdc_generic_sources/flexdc_generic_sources/flexdc_behavior_inference_utilities.py",
        ROOT
        / "condor_set_transformer_sweep_v3_behavior_v3_best_feasibility_artifacts/am_flexdc_behavior_training_utilities_v3.py",
    ]:
        record(p)
    write_json(OUT / "inputs.json", SOURCES)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
