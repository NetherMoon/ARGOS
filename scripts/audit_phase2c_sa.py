"""Read-only saved-outcome parity plus ARGOS-owned audit artifacts; no simulations."""

import ast
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from argos.experimental_sa.paper_consistent.feasibility import assess
from argos.experimental_sa.paper_consistent.objective import ObjectiveContract

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "src/argos/experimental_sa"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_csv(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(p, index=False)


def run():
    out = ROOT / json.loads((BASE / "audit_location.json").read_text())["directory"]
    manifest = json.loads((out / "manifest.json").read_text())
    contract = ObjectiveContract(ROOT)
    source = ROOT.parent / "AUDIT/modified-flexdc/am_recompute_flexdc_sa_constants_v3.py"
    src = source.read_text()
    tree = ast.parse(src)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    wanted = {
        "new_tracking_residual",
        "new_tracking_scaled",
        "new_ctrack_softplus",
        "new_ctrack",
        "new_qos_residuals",
        "new_qos_scaled",
        "new_qos_softplus_per_job",
        "new_qos",
        "new_qos_residual_sum",
        "new_full",
    }
    statements = [
        n
        for n in main.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id in wanted for t in n.targets)
    ]
    assert len(statements) == len(wanted)
    code = compile(
        ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[])), str(source), "exec"
    )

    def reference(m, p, pj):
        c = contract.costs
        env = {
            "args": SimpleNamespace(
                psi1=c.psi1,
                psi2=c.psi2,
                tracking_error_constraint=c.tracking_error_constraint,
                beta=c.beta,
                rho=c.rho,
                qos_constraint=c.qos_constraint,
            ),
            "epsilon_90": np.array([p]),
            "probabilities": np.array([pj]),
            "simulator_rsr": np.array([m]),
            "stable_softplus": lambda x: np.logaddexp(0, x),
        }
        exec(code, env)  # noqa: S102 - exact audited local recomputation assignments
        return [m, float(env["new_ctrack"][0]), float(env["new_qos"][0]), float(env["new_full"][0])]

    inputs = out / "inputs"
    inputs.mkdir(exist_ok=True)
    (inputs / source.name).write_bytes(source.read_bytes())
    rows = []
    feas = []
    legacy = []
    flags = []
    saved = []
    panel = ROOT / manifest["phase2b_directory"]
    for cell in sorted((panel / "cells").iterdir()):
        r = json.loads((cell / "result.json").read_text())
        raw = dict(
            r,
            M_RSR=r["monetary_power"] + r["monetary_tracking"],
            mean_tracking=pd.read_csv(cell / "power_trace.csv.gz")
            .trackingError.iloc[1:]
            .abs()
            .mean(),
        )
        obj = contract.evaluate(raw["M_RSR"], r["p90"], r["Pj"])
        ref = reference(raw["M_RSR"], r["p90"], r["Pj"])
        actual = [obj.M_RSR, obj.Ctrack, obj.CQoS, obj.Cfull]
        assert (
            max(abs(x - y) for x, y in zip(actual, ref)) < 1e-12
            and abs(obj.Cfull - r["objective"]) < 1e-12
        )
        for name, a, b in zip(["M_RSR", "Ctrack", "CQoS", "Cfull"], actual, ref):
            rows.append(
                {
                    "source": "ARGOS_PHASE2B",
                    "identity": r["cell_id"],
                    "component": name,
                    "experimental": a,
                    "reference": b,
                    "absolute_difference": abs(a - b),
                    "tolerance": 1e-12,
                    "passed": True,
                }
            )
        validity = assess(raw, ["Resnet", "GPT2", "Llama", "Bloom"], obj.Cfull)
        assert (
            validity["feasible"] == r["evidence_qualified_pass"]
            and validity["tracking_pass"] == r["assessment"]["tracking_pass"]
        )
        feas.append(
            {
                "identity": r["cell_id"],
                "p90": r["p90"],
                "Pj": json.dumps(r["Pj"]),
                "evidence_counts": json.dumps(r["evidence_counts"]),
                "reason": validity["reason"],
                "expected_feasible": r["evidence_qualified_pass"],
                "actual_feasible": validity["feasible"],
                "per_job_match": validity["per_job_pass"] == [v <= 0.1 for v in r["Pj"]],
                "passed": True,
            }
        )
        z = r["monetary_tracking"]
        ct_old = z * (1 + np.logaddexp(0, contract.costs.psi2 * (z - 0.3))) * contract.costs.psi1
        old = r["monetary_power"] + ct_old + obj.CQoS
        legacy.append(
            {
                "identity": r["cell_id"],
                "p90": r["p90"],
                "Pj": json.dumps(r["Pj"]),
                "simulator_power_cost": r["monetary_power"],
                "simulator_mean_tracking_monetary": z,
                "legacy_economic_term": r["monetary_power"],
                "legacy_tracking_transform": ct_old,
                "legacy_qos": obj.CQoS,
                "legacy_full": old,
                "paper_M_RSR": obj.M_RSR,
                "paper_Ctrack": obj.Ctrack,
                "paper_CQoS": obj.CQoS,
                "paper_full": obj.Cfull,
                "legacy_minus_paper": old - obj.Cfull,
            }
        )
        jobs = pd.read_csv(cell / "jobs.csv.gz")
        account = pd.read_csv(cell / "qos_accounting.csv")
        for _, q in account.iterrows():
            x = jobs[jobs.job_type_id == q.job_type_id]
            eligible = (x.arrival_time > 0) & (
                (x.end_time != -1)
                | ((x.end_time == -1) & (x.arrival_time + x.min_execution_time < 3600))
            )
            sojourn = np.where(x.end_time != -1, x.end_time, 3600) - x.arrival_time
            ties = int(
                (eligible & (sojourn == x.min_execution_time * (1 + x.qos_constraint))).sum()
            )
            flags.append(
                {
                    "identity": r["cell_id"],
                    "job_type": q.job_type,
                    "n": q.qos_observations,
                    "m": q.violation_count,
                    "Pj": q.Pj,
                    "empirical_strict": q.empirical_exceedance_fraction,
                    "estimator_gap": q.empirical_exceedance_fraction - q.Pj,
                    "at_threshold_ties": ties,
                    "paper_ge_same_support": (q.violation_count + ties) / q.qos_observations,
                }
            )
        saved.append(raw)
    # Bounded historical V3 data sample, preserving component columns and source-row identity.
    folder = (
        ROOT.parent
        / "AUDIT/modified-flexdc/traditionaliso_newqos_pilot_flexdc_configured_objective"
    )
    path = folder / "traditional_iso16_newqos_AQA_combined_grid_search_results.csv"
    d = pd.read_csv(path, nrows=32, float_precision="round_trip")
    columns = [
        "Source_Output_Dir",
        "Iteration",
        "Simulator_RSR_Total_Cost",
        "Simulator_Power_Cost",
        "Mtrack_Cost",
        "Mtrack_Error_MeanAbs_Normalized",
        "QoS_Delay_Probabilities",
        "Ctrack_Epsilon_90th",
        "Ctrack_Weighted_Cost",
        "Diagnostic_FlexDC_SoftPlus_QoS_Cost",
        "Diagnostic_FullPaperObjective_Cost",
    ]
    d[columns].to_csv(inputs / "v3_saved_32_rows.csv", index=False)
    for i, r in d.iterrows():
        pj = json.loads(r.QoS_Delay_Probabilities)
        obj = contract.evaluate(r.Simulator_RSR_Total_Cost, r.Ctrack_Epsilon_90th, pj)
        actual = [obj.M_RSR, obj.Ctrack, obj.CQoS, obj.Cfull]
        expected = [
            r.Simulator_Power_Cost + r.Mtrack_Cost,
            r.Ctrack_Weighted_Cost,
            r.Diagnostic_FlexDC_SoftPlus_QoS_Cost,
            r.Diagnostic_FullPaperObjective_Cost,
        ]
        assert max(abs(a - b) for a, b in zip(actual, expected)) < 1e-12
        for name, a, b in zip(["M_RSR", "Ctrack", "CQoS", "Cfull"], actual, expected):
            rows.append(
                {
                    "source": "V3_RECOMPUTED_SAVED_DATA",
                    "identity": f"first32_row_{i}",
                    "component": name,
                    "experimental": a,
                    "reference": b,
                    "absolute_difference": abs(a - b),
                    "tolerance": 1e-12,
                    "passed": True,
                }
            )
    (inputs / "phase2b_raw_outcomes.json").write_text(json.dumps(saved, indent=2))
    write_csv(out / "objective_parity.csv", rows)
    write_csv(out / "feasibility_parity.csv", feas)
    write_csv(out / "legacy_vs_paper_objective.csv", legacy)
    write_csv(ROOT / "reports/phase2c_legacy_vs_paper_objective.csv", legacy)
    write_csv(out / "pj_estimator_audit.csv", flags)
    manifest["parity"] = {
        "objective_outcomes": 88,
        "objective_component_checks": len(rows),
        "feasibility_observations": len(feas),
        "max_objective_difference": max(r["absolute_difference"] for r in rows),
        "absolute_tolerance": 1e-12,
        "passed": True,
        "compatibility_script": {
            "path": str(source),
            "sha256": sha(source),
            "executed": "Only exact pure new_* reconstruction assignments; no main or writes",
        },
        "v3_sample": {
            "path": str(path),
            "selection": "first32 data rows, no full campaign traversal",
            "source_size_bytes": path.stat().st_size,
            "sample_sha256": sha(inputs / "v3_saved_32_rows.csv"),
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest["parity"], indent=2))
    print(
        "Legacy minus paper range",
        min(x["legacy_minus_paper"] for x in legacy),
        max(x["legacy_minus_paper"] for x in legacy),
    )
    print("Maximum strict empirical/Pj estimator gap", max(x["estimator_gap"] for x in flags))
    print(
        "Maximum same-support equality-boundary gap",
        max(x["at_threshold_ties"] / x["n"] for x in flags),
    )


if __name__ == "__main__":
    run()
