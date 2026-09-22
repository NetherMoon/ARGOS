"""Phase 3C compact analysis, plots, final recommendation, and ZIP."""

from __future__ import annotations

import csv
import json
import zipfile
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .planning import CASES, METHODS, REPLICATES

JOBS = ["ResNet", "GPT2", "Llama", "Bloom"]


def _read(path: Path): return json.loads(path.read_text(encoding="utf8"))
def _rows(path: Path): return [json.loads(x) for x in path.read_text(encoding="utf8").splitlines() if x]
def _read_csv(path: Path):
    with path.open(newline="", encoding="utf8") as stream: return list(csv.DictReader(stream))
def _write_csv(path: Path, rows): pd.DataFrame(rows).to_csv(path, index=False)


def _failure_reasons(p90, pjs):
    values = ["tracking"] if p90 > 0.30 else []
    values += [job for job, value in zip(JOBS, pjs, strict=True) if value > 0.10]
    return "+".join(values) if values else "NONE"


def _flatten(value):
    raw, obj, feasible = value["raw"], value["objective"], value["feasibility"]
    row = {
        "cell_id": value["cell_id"], "case_label": value["case_label"], "case": value["case"],
        "candidate_role": value["candidate_role"], "replicate": int(value["replicate"]),
        "method": value["method"], "selection": value["selection"],
        "sa_success": str(value["sa_success"]).lower() == "true" if isinstance(value["sa_success"], str) else bool(value["sa_success"]),
        "optimization_candidate_id": value["optimization_candidate_id"], "panel": value["panel"],
        "panel_index": int(value["panel_index"]), "seed": int(value["seed"]),
        "arrival_seed": int(raw["arrival_seed"]), "runtime_seed": int(raw["runtime_seed"]),
        "Pbar": value["params"][0], "R": value["params"][1],
        "weights": json.dumps(value["params"][2:], separators=(",", ":")),
        "p90": raw["p90"], "M_RSR": obj["M_RSR"], "Ctrack": obj["Ctrack"],
        "CQoS": obj["CQoS"], "Cfull": obj["Cfull"], "max_Pj": max(raw["Pj"]),
        "evidence_counts": json.dumps(raw["evidence_counts"], separators=(",", ":")),
        "valid": bool(feasible["valid"]), "complete_scenario_pass": bool(feasible["feasible"]),
        "initial_job_table_hash": raw["initial_job_table_hash"],
        "grid_signal_hash": raw["grid_signal_hash"], "target_trace_hash": raw["target_trace_hash"],
        "failure_reasons": _failure_reasons(raw["p90"], raw["Pj"]),
    }
    for i, job in enumerate(JOBS): row[f"{job}_Pj"] = raw["Pj"][i]
    return row


def _with_combined(frame):
    combined = frame.copy(); combined["panel"] = "COMBINED"
    combined["panel_index"] = combined.groupby(["case", "candidate_role"]).cumcount() + 1
    return pd.concat([frame, combined], ignore_index=True)


def _average_feasible(group):
    return bool(group.p90.mean() <= 0.30 and all(group[f"{job}_Pj"].mean() <= 0.10 for job in JOBS))


def assessment_summaries(frame):
    rows = []
    for keys, group in _with_combined(frame).groupby(["case", "candidate_role", "replicate", "method", "panel"], sort=False):
        case, role, replicate, method, panel = keys
        row = {"case": case, "candidate_role": role, "replicate": int(replicate), "method": method,
               "panel": panel, "tested_scenarios": len(group),
               "pass_count": int(group.complete_scenario_pass.sum()),
               "proposed_8_of_10_scenario_criterion": bool(group.complete_scenario_pass.sum() >= 8) if panel in {"A", "B"} else "NOT_APPLICABLE",
               "average_metric_feasible": _average_feasible(group),
               "tracking_failure_count": int((group.p90 > 0.30).sum()), "valid_count": int(group.valid.sum())}
        for metric in ["p90", "Cfull", *[f"{job}_Pj" for job in JOBS]]:
            for stat in ["mean", "median", "min", "max"]: row[f"{stat}_{metric}"] = getattr(group[metric], stat)()
        for job in JOBS: row[f"{job}_failure_count"] = int((group[f"{job}_Pj"] > 0.10).sum())
        rows.append(row)
    return rows


def paired(frame):
    rows = []
    for case in frame.case.unique():
        for replicate in REPLICATES:
            nrole, srole = f"replicate_{replicate}_naive", f"replicate_{replicate}_shared3"
            wide = frame[(frame.case == case) & frame.candidate_role.isin([nrole, srole])].pivot(index="seed", columns="candidate_role")
            for seed, item in wide.iterrows():
                npass, spass = bool(item[("complete_scenario_pass", nrole)]), bool(item[("complete_scenario_pass", srole)])
                row = {"case": case, "replicate": replicate, "seed": int(seed), "panel": item[("panel", nrole)],
                       "naive_pass": npass, "shared3_pass": spass,
                       "classification": "S3_ONLY_PASS" if spass and not npass else "N_ONLY_PASS" if npass and not spass else "BOTH_PASS" if npass else "BOTH_FAIL",
                       "delta_shared3_minus_naive_p90": item[("p90", srole)] - item[("p90", nrole)],
                       "delta_shared3_minus_naive_Cfull": item[("Cfull", srole)] - item[("Cfull", nrole)]}
                for job in JOBS: row[f"delta_shared3_minus_naive_{job}_Pj"] = item[(f"{job}_Pj", srole)] - item[(f"{job}_Pj", nrole)]
                rows.append(row)
    return rows


def optimization_summaries(experiment):
    rows, panel_rows = [], []
    for replicate in REPLICATES:
        for _label, case in CASES:
            for method in METHODS:
                path = experiment / f"optimization/replicate_{replicate}/{case}_{method}"
                iterations, result = _rows(path / "iterations.jsonl"), _read(path / "result.json")
                metadata = _read(path / "trajectory_metadata.json")
                if method == "naive":
                    feasible = [x for x in iterations if x["feasibility"]["valid"] and x["feasibility"]["feasible"]]
                    selected = result["best_feasible"] or result["best_violation"]
                    selected_iteration = int(selected["candidate_id"].rsplit(":", 1)[1])
                    best_scalar = result["best_scalar"]["objective"]["Cfull"]
                    best_feasible = result["best_feasible"]["objective"]["Cfull"] if result["best_feasible"] else None
                    first_feasible = min((x["iteration"] for x in feasible), default=None)
                    panel_evaluations = None; panels_consumed = None; panel_switches = None
                    distinct_hashes = len({x["raw"]["initial_job_table_hash"] for x in iterations})
                    accepted = sum(bool(x["accepted"]) for x in iterations[1:])
                    failure_source = [(x["raw"]["p90"], x["raw"]["Pj"]) for x in iterations if x["feasibility"]["valid"]]
                else:
                    events = [_read(x)["current"] for x in sorted((path / "panel_events").glob("*.json"))]
                    evaluations = [x["panel_evaluation"] for x in iterations] + events
                    for item in evaluations:
                        panel_rows.append({"replicate": replicate, "case": case, "method": method,
                                           "candidate_id": item["candidate_id"], "panel_evaluation_id": item["panel_evaluation_id"],
                                           "panel_index": item["panel_index"], "panel_seeds": json.dumps(item["panel_seeds"]),
                                           "panel_mean_Cfull": item["panel_mean_Cfull"], "panel_mean_p90": item["panel_mean_p90"],
                                           "panel_mean_Pj": json.dumps(item["panel_mean_Pj"]), "panel_pass_count": item["panel_pass_count"],
                                           "panel_all_valid": item["panel_all_valid"], "panel_all_feasible": item["panel_all_feasible"]})
                    feasible = [x for x in evaluations if x["panel_all_feasible"]]
                    selected = result["best_panel_feasible"] or result["best_violation"]
                    selected_iteration = int(selected["candidate_id"].rsplit(":", 1)[1])
                    best_scalar = result["best_scalar"]["panel_mean_Cfull"]
                    best_feasible = result["best_panel_feasible"]["panel_mean_Cfull"] if result["best_panel_feasible"] else None
                    first_feasible = min((int(x["candidate_id"].rsplit(":", 1)[1]) for x in feasible), default=None)
                    panel_evaluations = len(evaluations); panels_consumed = len({x["panel_index"] for x in evaluations}); panel_switches = len(events)
                    distinct_hashes = len({y["raw"]["initial_job_table_hash"] for x in evaluations for y in x["scenario_observations"]})
                    accepted = sum(bool(x["accepted"]) for x in iterations[1:])
                    failure_source = [(y["raw"]["p90"], y["raw"]["Pj"]) for x in evaluations for y in x["scenario_observations"]]
                row = {"replicate": replicate, "case": case, "method": method, "status": result["status"],
                       "sa_success": bool(result.get("best_feasible") if method == "naive" else result.get("best_panel_feasible")),
                       "transitions": 400, "accepted_transitions": accepted, "feasible_evaluations": len(feasible),
                       "first_feasible_iteration": first_feasible, "selected_iteration": selected_iteration,
                       "best_scalar_objective": best_scalar, "best_feasible_objective": best_feasible,
                       "selected_objective": selected.get("panel_mean_Cfull", selected["objective"]["Cfull"]),
                       "selected_candidate_id": selected["candidate_id"], "Pbar": selected["params"][0], "R": selected["params"][1],
                       "weights": json.dumps(selected["params"][2:], separators=(",", ":")),
                       "simulator_calls": result["simulator_calls"], "wall_clock_seconds": metadata["wall_clock_seconds_accumulated"],
                       "distinct_arrival_hashes": distinct_hashes, "panels_consumed": panels_consumed,
                       "panel_evaluations": panel_evaluations, "panel_switches": panel_switches,
                       "tracking_failure_count": sum(p90 > 0.30 for p90, _ in failure_source)}
                for i, job in enumerate(JOBS): row[f"{job}_failure_count"] = sum(pjs[i] > 0.10 for _, pjs in failure_source)
                rows.append(row)
    return rows, panel_rows


def stability(summary):
    rows = []
    combined = summary[summary.panel == "COMBINED"]
    for case in combined.case.unique():
        wins = Counter(); pass_values = {m: [] for m in METHODS}; objective_values = {m: [] for m in METHODS}
        for replicate in REPLICATES:
            n = combined[(combined.case == case) & (combined.candidate_role == f"replicate_{replicate}_naive")].iloc[0]
            s = combined[(combined.case == case) & (combined.candidate_role == f"replicate_{replicate}_shared3")].iloc[0]
            wins["S3"] += s.pass_count > n.pass_count; wins["N"] += n.pass_count > s.pass_count; wins["TIE"] += n.pass_count == s.pass_count
            pass_values["naive"].append(n.pass_count); pass_values["shared3"].append(s.pass_count)
        for method in METHODS:
            rows.append({"case": case, "method": method, "s3_wins": wins["S3"], "naive_wins": wins["N"], "ties": wins["TIE"],
                         "assessment_pass_min": min(pass_values[method]), "assessment_pass_max": max(pass_values[method]),
                         "assessment_pass_spread": max(pass_values[method]) - min(pass_values[method])})
    return rows


def plots(experiment, summary, optimization):
    plots_dir = experiment / "plots"; plots_dir.mkdir(exist_ok=True)
    combined = summary[(summary.panel == "COMBINED") & summary.method.isin(METHODS)]
    fig, ax = plt.subplots(figsize=(10, 5))
    labels, values, colors = [], [], []
    for _, r in combined.iterrows(): labels.append(f"{r.case} R{r.replicate} {r.method}"); values.append(r.pass_count); colors.append("#f28e2b" if r.method == "shared3" else "#4e79a7")
    ax.bar(labels, values, color=colors); ax.set_ylabel("Complete scenarios passed (of 20)"); ax.tick_params(axis="x", rotation=55); fig.tight_layout(); fig.savefig(plots_dir / "combined_pass_counts.png", dpi=160); plt.close(fig)
    panels = summary[(summary.panel.isin(["A", "B"])) & summary.method.isin(METHODS)]
    fig, ax = plt.subplots(figsize=(12, 5)); labels=[f"{r.case}R{r.replicate}{r.method[0]}-{r.panel}" for _,r in panels.iterrows()]
    ax.bar(labels, panels.pass_count, color=["#f28e2b" if x=="shared3" else "#4e79a7" for x in panels.method]); ax.axhline(8,color="red",ls="--"); ax.tick_params(axis="x",rotation=70); ax.set_ylabel("Passes of 10"); fig.tight_layout(); fig.savefig(plots_dir / "panel_A_B_pass_counts.png",dpi=160); plt.close(fig)
    for metric, limit, name in [("mean_p90", .30, "mean_p90"), ("mean_Bloom_Pj", .10, "mean_Bloom_Pj")]:
        fig, ax=plt.subplots(figsize=(10,5)); ax.bar(labels[:len(panels)], panels[metric], color=["#f28e2b" if x=="shared3" else "#4e79a7" for x in panels.method]); ax.axhline(limit,color="red",ls="--"); ax.tick_params(axis="x",rotation=70); ax.set_ylabel(metric); fig.tight_layout(); fig.savefig(plots_dir/f"{name}.png",dpi=160); plt.close(fig)
    criteria = panels.copy(); criteria["scenario"] = criteria.proposed_8_of_10_scenario_criterion.astype(int); criteria["average"] = criteria.average_metric_feasible.astype(int)
    fig, ax=plt.subplots(figsize=(6,10)); matrix=criteria[["scenario","average"]].to_numpy(); ax.imshow(matrix,cmap="RdYlGn",vmin=0,vmax=1); ax.set_xticks([0,1],["Proposed 8/10","Average feasible"]); ax.set_yticks(range(len(criteria)),labels); fig.tight_layout(); fig.savefig(plots_dir/"criterion_comparison.png",dpi=160); plt.close(fig)
    candidates=pd.read_csv(experiment/"selected_candidates.csv"); candidates=candidates[candidates.method.isin(METHODS)]
    fig,axes=plt.subplots(1,2,figsize=(12,5));
    for method,color in [("naive","#4e79a7"),("shared3","#f28e2b")]:
        x=candidates[candidates.method==method]; axes[0].scatter(x.Pbar,x.R,label=method,color=color); axes[1].scatter(x.replicate,[json.loads(w)[-1] for w in x.weights],label=method,color=color)
    axes[0].set(xlabel="Pbar",ylabel="R"); axes[1].set(xlabel="Replicate",ylabel="Bloom weight"); [a.legend() for a in axes]; fig.tight_layout(); fig.savefig(plots_dir/"selected_parameters.png",dpi=160); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(14,5),sharey=False)
    for ax,(_label,case) in zip(axes,CASES,strict=True):
        for replicate in REPLICATES:
            for method,color in [("naive","#4e79a7"),("shared3","#f28e2b")]:
                path=experiment/f"optimization/replicate_{replicate}/{case}_{method}/iterations.jsonl"; data=_rows(path)
                y=[x["objective"]["Cfull"] if method=="naive" else x["panel_evaluation"]["panel_mean_Cfull"] for x in data]
                ax.plot(range(len(y)),y,label=f"R{replicate} {method}",color=color,alpha=.55+.2*replicate)
        ax.set_title(case); ax.set_xlabel("Transition"); ax.set_ylabel("Training objective"); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(plots_dir/"optimization_trajectories.png",dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(6,4)); costs=optimization.groupby("method").simulator_calls.sum(); ax.bar(costs.index,costs.values,color=["#4e79a7","#f28e2b"]); ax.set_ylabel("Optimization simulator calls"); fig.tight_layout(); fig.savefig(plots_dir/"simulator_call_cost.png",dpi=160); plt.close(fig)


def report(experiment, summary, paired_frame, stability_frame, optimization):
    combined=summary[summary.panel=="COMBINED"]; lines=["# Phase 3C — Shared-Scenario Candidate Evaluation and Final Pre-ARGOS Decision","", "X/10 and X/20 are tested-scenario counts, not certified reliability probabilities. Average-metric feasibility and scenario-level feasibility are different operational criteria.","","## Final assessment"]
    for case in [x[1] for x in CASES]:
        lines += ["",f"### {case}"]
        for role in ["starting",*[f"replicate_{r}_{m}" for r in REPLICATES for m in METHODS]]:
            rows=summary[(summary.case==case)&(summary.candidate_role==role)]; a=rows[rows.panel=="A"].iloc[0]; b=rows[rows.panel=="B"].iloc[0]; c=rows[rows.panel=="COMBINED"].iloc[0]
            lines.append(f"- {role}: A {a.pass_count}/10 (8/10 {'YES' if a.proposed_8_of_10_scenario_criterion else 'NO'}, average {'YES' if a.average_metric_feasible else 'NO'}); B {b.pass_count}/10 (8/10 {'YES' if b.proposed_8_of_10_scenario_criterion else 'NO'}, average {'YES' if b.average_metric_feasible else 'NO'}); combined {c.pass_count}/20 (average {'YES' if c.average_metric_feasible else 'NO'}).")
    lines += ["","## Paired N versus S3"]
    for case in [x[1] for x in CASES]:
        for replicate in REPLICATES:
            n=combined[(combined.case==case)&(combined.candidate_role==f"replicate_{replicate}_naive")].iloc[0]; s=combined[(combined.case==case)&(combined.candidate_role==f"replicate_{replicate}_shared3")].iloc[0]
            pair=paired_frame[(paired_frame.case==case)&(paired_frame.replicate==replicate)]; counts=Counter(pair.classification)
            lines.append(f"- {case} R{replicate}: N {n.pass_count}/20, S3 {s.pass_count}/20; S3-only {counts['S3_ONLY_PASS']}, N-only {counts['N_ONLY_PASS']}, both-pass {counts['BOTH_PASS']}, both-fail {counts['BOTH_FAIL']}; mean S3-N deltas p90 {s.mean_p90-n.mean_p90:+.6f}, Bloom Pj {s.mean_Bloom_Pj-n.mean_Bloom_Pj:+.6f}, Cfull {s.mean_Cfull-n.mean_Cfull:+.6f}.")
    lines += ["","## Stability and cost"]
    for case in [x[1] for x in CASES]:
        row=stability_frame[(stability_frame.case==case)&(stability_frame.method=="shared3")].iloc[0]
        lines.append(f"- {case}: S3 wins {row.s3_wins}/2, N wins {row.naive_wins}/2, ties {row.ties}/2 on combined pass count.")
    for method in METHODS:
        x=optimization[optimization.method==method]; lines.append(f"- {method}: {int(x.simulator_calls.sum())} optimization calls; {x.wall_clock_seconds.sum():.1f} accumulated trajectory-seconds; selected-candidate combined passes per optimization call is a descriptive cost measure only.")
    total_s3=sum(stability_frame[stability_frame.method=="shared3"].s3_wins); total_n=sum(stability_frame[stability_frame.method=="shared3"].naive_wins)
    if total_s3 > total_n:
        option="OPTION A — adaptive shared/multi-scenario evaluation"; rationale="S3 was more stable or robust often enough to justify candidate-level scenario evidence, while its 3.29× optimization cost argues for adaptive allocation rather than three calls for every candidate."
    elif total_s3 == total_n:
        option="OPTION B — single-scenario search with selective matched repeats"; rationale="N and S3 were similar across the final matched comparison, so cheap exploration plus shared verification offers the better cost/evidence balance."
    else:
        option="OPTION B — single-scenario search with selective matched repeats"; rationale="S3 did not recover its extra cost in selected-candidate performance; uncertainty still matters, so promising candidates should receive matched multi-scenario verification and refinement."
    lines += ["","# Final Pre-ARGOS Recommendation","",f"**{option}.** {rationale}","",
              "Evidence synthesis:","",
              "- Phase 1 found deterministic, ordinary Poisson workload generation with no clear generator defect.",
              "- Phases 2 and 2B showed that arrival realization dominates much Bloom variation, while runtime randomness can still change severity or flip boundary feasibility.",
              "- Phase 2C established the corrected objective, authoritative feasibility, normal AQA, isolated RNG, legal domain, and best-feasible selection contract used here.",
              "- Phase 3 showed that naive varying-arrival SA can find candidates that generalize beyond one training realization.",
              "- Phase 3B showed that this advantage is only partially repeatable and that one-scenario candidate comparisons remain search-path sensitive.",
              "- Phase 3C provides the final direct evidence above on whether shared scenarios improve candidate comparison enough to justify their extra calls.","",
              "ARGOS should treat **candidate + collection of scenario outcomes** as the fundamental evidence object. A single outcome can be the first member of that collection, but it must not replace the candidate's accumulated evidence.","",
              "For each outcome ARGOS should retain the candidate identity, arrival seed and initial-job hash, runtime seed, grid/target-trace hashes, evidence-validity counts, p90, every Pj, objective components, and feasibility result. Candidate-level state should retain the number and diversity of scenarios plus matched-comparison provenance.","",
              "The known ARGOS v2 weakness allowed one favorable observation for a candidate geometry to drive targeted probing even when another observation failed. The next ARGOS implementation should group observations by the exact candidate identity, retain every scenario outcome, and make probing/promotion decisions from the collection with explicit evidence counts and matched-scenario comparisons.","",
              "This is the final pre-ARGOS SA decision. The next work item is ARGOS implementation and development, not another simulated-annealing experiment.","", "## Limitations","", "This finite experiment uses two search replicates, one fixed optimization runtime seed, fixed grid input, and two W2 workloads. Pass counts are descriptive and neither 8/10 nor X/20 is a certified reliability probability."]
    (experiment/"report.md").write_text("\n".join(lines)+"\n",encoding="utf8")


def build_final_outputs(root: Path, experiment: Path, rebuild_zip=False):
    result_paths=sorted((experiment/"assessment/cells").glob("*/result.json"))
    if len(result_paths)!=200: raise ValueError(f"Expected 200 assessment results, found {len(result_paths)}")
    results=[_flatten(_read(x)) for x in result_paths]; _write_csv(experiment/"assessment_results.csv",results); frame=pd.DataFrame(results)
    if not ((frame.arrival_seed==frame.runtime_seed)&(frame.seed==frame.arrival_seed)).all(): raise ValueError("Assessment seed contract changed")
    summaries=assessment_summaries(frame); _write_csv(experiment/"assessment_summary_by_panel.csv",summaries); summary=pd.DataFrame(summaries)
    _write_csv(experiment/"scenario_pass_summary.csv",summary[["case","candidate_role","replicate","method","panel","tested_scenarios","pass_count","proposed_8_of_10_scenario_criterion"]].to_dict("records"))
    avgcols=["case","candidate_role","replicate","method","panel","tested_scenarios","mean_p90",*[f"mean_{j}_Pj" for j in JOBS],"average_metric_feasible"]
    _write_csv(experiment/"average_metric_feasibility.csv",summary[avgcols].to_dict("records"))
    pair=paired(frame); _write_csv(experiment/"paired_naive_vs_shared.csv",pair); pair_frame=pd.DataFrame(pair)
    opt,panel=optimization_summaries(experiment); _write_csv(experiment/"optimization_summary.csv",opt); _write_csv(experiment/"panel_evaluation_summary.csv",panel); opt_frame=pd.DataFrame(opt)
    stable=stability(summary); _write_csv(experiment/"method_stability_summary.csv",stable); stable_frame=pd.DataFrame(stable)
    failures=[]
    for (case,role,panel_name),group in _with_combined(frame).groupby(["case","candidate_role","panel"],sort=False):
        for reason,count in Counter(group.failure_reasons).items(): failures.append({"case":case,"candidate_role":role,"panel":panel_name,"failure_combination":reason,"count":count})
    _write_csv(experiment/"failure_summary.csv",failures)
    efficiency=[]
    for _,r in opt_frame.iterrows():
        passes=int(summary[(summary.case==r.case)&(summary.candidate_role==f"replicate_{int(r.replicate)}_{r.method}")&(summary.panel=="COMBINED")].iloc[0].pass_count)
        efficiency.append({"case":r.case,"replicate":r.replicate,"method":r.method,"optimization_simulator_calls":r.simulator_calls,"wall_clock_seconds":r.wall_clock_seconds,"combined_assessment_passes":passes,"passes_per_optimization_call":passes/r.simulator_calls})
    _write_csv(experiment/"simulator_efficiency.csv",efficiency)
    plots(experiment,summary,opt_frame); report(experiment,summary,pair_frame,stable_frame,opt_frame)
    if rebuild_zip: build_zip(experiment)


def build_zip(experiment: Path):
    target=experiment.with_suffix(".zip")
    if target.exists(): target.unlink()
    selected=[]
    for path in experiment.rglob("*"):
        if not path.is_file() or path.name.endswith(".tmp"): continue
        rel=path.relative_to(experiment); parts=rel.parts
        include=len(parts)==1 or parts[0] in {"plots","search_draw_schedule"}
        include |= parts[0]=="optimization" and path.name in {"checkpoint.json","iterations.jsonl","result.json","trajectory.log","trajectory_metadata.json"}
        include |= "panel_events" in parts and path.suffix==".json"
        include |= parts[:2]==("assessment","cells") and path.name=="result.json"
        include |= parts[0]=="smoke" and path.name in {"smoke_result.json","checkpoint.json","iterations.jsonl","result.json"}
        if include: selected.append(path)
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(selected): archive.write(path,Path(experiment.name)/path.relative_to(experiment))
    return target
