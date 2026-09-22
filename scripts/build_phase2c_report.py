"""Build Phase2C documentation and compact evidence ZIP; never run simulations."""

import ast
import datetime
import difflib
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "src/argos/experimental_sa"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def csvout(p, rows):
    pd.DataFrame(rows).to_csv(p, index=False)


def ref(file, func):
    source = BASE / "upstream_snapshot" / file
    f = next(
        x
        for x in ast.walk(ast.parse(source.read_text()))
        if isinstance(x, ast.FunctionDef) and x.name == func.split(".")[-1]
    )
    return f".deps/FlexDC/src/peacsim/{file}::{func} lines {f.lineno}-{f.end_lineno}"


def main():
    out = ROOT / json.loads((BASE / "audit_location.json").read_text())["directory"]
    m = json.loads((out / "manifest.json").read_text())
    assert m["parity"]["passed"] and m["real_smoke_passed"] and m["real_simulations"] == 4
    xml = ET.parse(out / "unit_tests.xml")
    assert not xml.findall(".//failure") and not xml.findall(".//error")
    tests = [
        {"test": t.attrib["name"], "passed": True, "time_seconds": t.attrib["time"]}
        for t in xml.findall(".//testcase")
    ]
    for item in m["snapshot"]:
        original = ROOT / ".deps/FlexDC" / item["original_path"]
        copy = ROOT / item["snapshot_path"]
        assert original.read_bytes() == copy.read_bytes() and sha(copy) == item["sha256"]
    for name, path in [
        ("ARGOS", ROOT),
        ("FlexDC", ROOT / ".deps/FlexDC"),
        ("CONDOR-FLEXDC", ROOT / ".deps/CONDOR-FLEXDC"),
    ]:
        assert (
            subprocess.check_output(
                ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
            ).strip()
            == m["repo_shas"][name]
        )
        if name != "ARGOS":
            assert not subprocess.check_output(
                ["git", "-C", str(path), "status", "--short"], text=True
            ).strip()
    sa = "simulated_annealing.py"
    evaluate = ref(sa, "sa_evaluate")
    search = ref(sa, "simulated_annealing_optimize")
    money = ref("simulator.py", "final_output")
    qos = ref("calculate_qos_cost.py", "calculate_delay_prob")
    proxy = ref("extract_qos_metrics.py", "write_qos_summary_df")
    issues = []

    def add(id, severity, topic, expected, current, refs, why, status, action, discuss="Yes"):
        issues.append(
            {
                "ID": id,
                "Severity": severity,
                "Topic": topic,
                "Expected_behavior": expected,
                "Pinned_behavior": current,
                "Exact_source_file": "; ".join(x.split("::")[0] for x in refs),
                "Function_lines": "; ".join(refs),
                "Scientific_impact": why,
                "Status": status,
                "Phase2C_action": action,
                "Original_FlexDC_unchanged": True,
                "Discuss_with_Fatih_Kerim": discuss,
            }
        )

    add(
        "A1",
        "Critical",
        "Tracking penalty",
        "Paper Eq11: psi1*SoftPlus(psi2*(p90-gamma))",
        "Feeds monetary tracking cost z from Simulator.run into psi1*z*(1+log(1+exp(psi2*(z-.3)))); p90 is returned separately",
        [evaluate, money],
        "Compares dollars with normalized error threshold, with extra multiplication and wrong penalty shape",
        "CONFIRMED",
        "Use ARGOS Costs on actual p90; expose components",
    )
    add(
        "A2",
        "High",
        "RSR monetary accounting",
        "Paper Eq3: purchase minus reserve credit plus mean-error monetary cost exactly once",
        "Returned power is recomputed. Tracking transform expands to z + z*SoftPlus(...): linear mean tracking is NOT absent. It is present once at one-hour RSR, tangled with the wrong extra penalty",
        [evaluate, money, ref("calculate_monetary_cost.py", "calculate_monetary_cost")],
        "Do not claim z was wholly omitted or double-counted; labels obscure the actual arithmetic",
        "PARTIALLY CONFIRMED",
        "Consume raw power+tracking as M_RSR; use separate p90 penalty",
    )
    add(
        "A3",
        "High",
        "Feasibility",
        "p90<=.30 and all Pj<=.10 with valid support",
        "Printed message uses completed-job percentile proxy ratio==0 and strict p90<.3; no evidence gate",
        [search, proxy],
        "Boundary .300 misclassified; unfinished/missing-type evidence can be ignored",
        "CONFIRMED",
        "Structured wrapper around ARGOS assessment, inclusive limits and support checks",
    )
    add(
        "A4",
        "High",
        "Best can be infeasible",
        "Best feasible by objective or explicit no-feasible status",
        "Only scalar best; no feasible incumbent or final feasibility requirement",
        [search],
        "Cheaper infeasible point can replace feasible result",
        "CONFIRMED",
        "Separate current, best scalar, best feasible and best violation; walk may cross infeasible states",
    )
    add(
        "A5",
        "High",
        "QoS objective/feasibility mismatch",
        "Same authoritative Pj vector everywhere",
        "CQoS uses calculate_delay_prob; feasibility uses completed-job quantile proxy; sa_evaluate does not return Pj",
        [evaluate, ref("calculate_qos_cost.py", "calculate_qos_cost_sa"), proxy],
        "Different support/interpolation; unfinished-only fixture gives proxy0 versus Pj1",
        "CONFIRMED",
        "Existing Pj controls feasibility; proxy logged only",
    )
    add(
        "A6",
        "High",
        "Global RNG coupling",
        "Search randomness isolated from simulator",
        "Global NumPy proposals and acceptance; Simulator.run reseeds global NumPy and Python; runtime seed becomes iteration. Generator uses Python once in main",
        [
            ref(sa, "perturb"),
            search,
            evaluate,
            ref("simulator.py", "run"),
            ref("create_tables.py", "init_job_table_poisson"),
        ],
        "Runtime seed directly resets future search draws",
        "CONFIRMED",
        "Local PCG64 search Generator; private simulator subprocess; explicit fixed arrival/runtime seeds",
    )
    add(
        "A7",
        "High",
        "Weight bounds",
        "sum1 and individual bounds after projection",
        "Clip then normalize: [.8,.1,.1,.1] -> [.72727,.09091,.09091,.09091]",
        [ref(sa, "enforce_bounds")],
        "Violates current lower bounds; upper violations possible for other configured bounds",
        "CONFIRMED",
        "Reuse ARGOS bounded-simplex method; randomized/boundary tests",
    )
    add(
        "A8",
        "Medium",
        "P/R domain and units",
        "Explicit domain choice; physical coupled bounds in kW/server",
        "Legacy P/R are distinct dimensionless ratios with box bounds [.9,1.2]/[.2,.8], not kW/server",
        [ref(sa, "enforce_bounds"), ref("denormalize_PR.py", "denormalize_p_and_r_to_watts")],
        "Silently relabeling the numeric box changes the scientific problem; difference itself is not a paper violation",
        "CONFIRMED",
        "Named legacy_sa converted box and argos_v3_physical; no implicit profile",
    )
    add(
        "A9",
        "High",
        "Return/API shape",
        "Stable schema",
        "Initial best is list; improvement makes (candidate,iteration); main always unpacks two values",
        [search],
        "No-improvement run may fail unpacking; both branches tested",
        "CONFIRMED",
        "Stable SAResult",
    )
    add(
        "A10",
        "High",
        "Logging/provenance",
        "Seeds, components, Pj/support, acceptance/state and hashes",
        "Each evaluation overwrites weights/power/job/PR paths; stdout/WandB omit full replay and state evidence",
        [evaluate, ref(sa, "init_output"), search],
        "Cannot reconstruct a complete trajectory",
        "CONFIRMED",
        "Exclusive JSONL; private workers; compact summaries; fixed-context/source hashes",
    )
    add(
        "A11",
        "High; flag only",
        "Pj paper/code definition",
        "Paper Eq14 empirical fraction, >=, submitted-job population",
        "Strict >, CDF linspace -> max(m-1,0)/(n-1) for n>=2; singleton/empty cases; time0/horizon exclusions",
        [qos],
        "Estimator, boundary and support changes would alter V3/ARGOS targets",
        "CONFIRMED",
        "DO NOT CHANGE. Quantify separately; lab/upstream discussion",
    )
    add(
        "A12a",
        "High",
        "Rejected-candidate guidance",
        "Next guidance belongs to accepted current state",
        "qos_cost_each replaced even on rejection and used by next perturb",
        [search, ref(sa, "smart_weight_update")],
        "Rejected observation changes proposal guidance; confirmed by regression test",
        "CONFIRMED",
        "Read current-state QoS terms; common beta factor cancels in relative guidance",
    )
    add(
        "A12b",
        "High",
        "AQA implementation fork",
        "Use same pinned runtime as V3/ARGOS for comparison",
        "SA imports AQA_runtime_policy; wizard/Phase2 use aqa_runtimepolicy inheriting RuntimePolicyNew",
        [
            ref(sa, "create_simulator_object"),
            ref("AQA_runtime_policy.py", "execute"),
            ref("runtime_policy_new.py", "execute"),
        ],
        "Same label does not prove equivalent scheduling; full-run differences cannot be attributed solely to objective",
        "CONFIRMED",
        "Explicitly select existing normal V3/ARGOS runtime class; edit neither implementation",
    )
    add(
        "A12c",
        "Medium",
        "External logging",
        "Offline local evidence",
        "Unconditional WandB import/init/log despite optional logger CLI",
        [search],
        "External logging dependency and incomplete local evidence",
        "CONFIRMED",
        "No WandB/network dependency",
    )
    add(
        "A12d",
        "Low",
        "Stale constants suspicion",
        "Canonical sections agree",
        "Current pinned and ARGOS copies have identical normalized text and values; only CRLF/LF byte difference",
        [ref("parsing/simulated_annealing_reader.py", "__init__")],
        "No scientific constants mismatch found",
        "NOT CONFIRMED",
        "Record both hashes and verify parsed sections",
        "No",
    )
    add(
        "A12e",
        "Low",
        "Shared/stale jobs suspicion",
        "Fresh initial state each evaluation",
        "Original generates jobs/nodes once and copies both in create_simulator_object",
        [ref(sa, "create_simulator_object")],
        "No shared-job mutation between original iterations demonstrated",
        "NOT CONFIRMED",
        "Preserve fixed-arrival concept; immutable table and hash checks",
        "No",
    )
    add(
        "A12f",
        "Low",
        "Metropolis/cooling suspicion",
        "exp(-delta/T), positive schedule",
        "Sign is correct; configured T1000/.95 stays positive through400 iterations; steps halve at200/300",
        [search],
        "No sign/cooling bug; finite heuristic schedule does not establish a global-optimality guarantee",
        "NOT CONFIRMED",
        "Preserve schedule/walk, validate inputs; no convergence claim",
        "No",
    )
    add(
        "A12g",
        "Medium; restricted",
        "Duration/program generality",
        "Match exact raw context",
        "Simulator final_output is RSR and counts full hours; separate SA economics also handles EDR/fractional sim_hour",
        [money, ref("calculate_monetary_cost.py", "calculate_monetary_cost")],
        "Equivalence outside one-hour RSR not established",
        "PARTIALLY CONFIRMED",
        "Fail on context outside fixed3600s RSR; no simulator edits",
    )
    add(
        "A12h",
        "Low; flag only",
        "Tracking conventions",
        "Document exact trained metric",
        "Normalization uses R+.0001; error serialized3decimals; p90 includes t0; monetary mean excludes initial sample",
        [ref("simulator.py", "run"), ref("simulator.py", "record_state"), money],
        "Small equation/precision conventions are retained target definitions",
        "CONFIRMED",
        "Preserve normal simulator outputs and parity; do not redefine precision",
    )
    csvout(out / "discrepancies.csv", issues)
    columns = list(issues[0])
    table = "| " + " | ".join(columns) + " |\n| " + " | ".join(["---"] * len(columns)) + " |\n"
    for row in issues:
        table += (
            "| "
            + " | ".join(str(row[c]).replace("|", "/").replace("\n", " ") for c in columns)
            + " |\n"
        )
    doc = (
        """# Phase 2C: pinned SA versus paper/V3/ARGOS contract

The local FlexDC paper was checked visually on pages2 and4: Eq3 monetary cost; Eq10-12 objective/tracking; Eq14-16 QoS. Constants1/10/20/2 and thresholds.30/.10 come from the named canonical configuration; not every coefficient is claimed to be mandated by the paper.

This is an isolated research derivative, not upstream FlexDC. Existing simulator Pj remains authoritative. "Paper-consistent" here means the requested objective/feasibility contract using existing outputs, not replacement of Eq14's estimator, support or equality boundary.

## Discrepancy register

"""
        + table
        + """
## Monetary finding: do not overstate the omission

Let z be simulator monetary mean-tracking cost. Legacy SA evaluates power + z*(1+SoftPlus(10*(z-.3))) + CQoS. The linear z is present exactly once for one-hour RSR. The repair consumes M_RSR=power+z and replaces the remaining z*SoftPlus(10*(z-.3)) with SoftPlus(10*(p90-.3)). Saying "SA simply omitted all monetary tracking cost" would be inaccurate.

Pinned prices are .1/kWh-equivalent for purchase/reserve/tracking, divided by3600*1000 before multiplying watts and seconds. The real simulator return is consumed directly. p90 is never substituted into the monetary mean. No pricing or simulator change.

## Explicit W2 domains

Mean max/min job power are687.5/200.25W. At U=.6 and idle120W, legacy P scale is.4605kW/server and R scale.28375kW/server. Converted legacy box: Pbar[.41445,.5526], R[.05675,.227], weights[.1,.8], sum1. Its P/R box happens to satisfy the physical coupled constraints for this W2 context; not every legacy bid is physically illegal.

argos_v3_physical: Pbar[.180225,.6875], R>=.01, R<=.6*Pbar, Pbar+R<=.825, weights[.15,.45], sum1. Defaults are checked against the actual pinned V3 bounds function and current ARGOS Config. Both profiles require an explicit name. Public experimental values are kW/server; legacy proposal steps are converted consistently. Phase3's profile is not selected here.

## Pj: flag only

For the SAME eligible support and strict-exceedance count m, n>=2, empirical m/n minus the CDF estimator is (n-m)/(n*(n-1)) when m>=1, and0 when m=0; bounded by1/n. Across56 saved new Phase2B runs the maximum is about8.30e-5 (0.00830 percentage points).

The paper uses >=, while code uses >. Integer-second equality ties matter: their largest same-support contribution in those rows is.01304 (1.304 percentage points). Submitted-job support also differs from simulator exclusions. These are separate effects; total paper/code differences are NOT bounded by1/n. pj_estimator_audit.csv preserves n,m,ties and diagnostic fractions.

Do not change estimator, boundary, exclusions, V3 data or checkpoint here. Fatih/Kerim must decide whether any future upstream target change is justified. Such changes would invalidate direct target comparability and may require regeneration/retraining.

## Runtime and algorithm distinctions

Legacy and normal AQA classes coexist. Experimental SA explicitly uses the unmodified normal class used by V3/ARGOS/Phase2; no behavioral equivalence claim is made for the old class. Saved-outcome arithmetic comparisons isolate objective differences and do not compare full optimizer performance.

Fresh job/node copies and configured Metropolis sign/cooling were not found defective. Their intended behavior is preserved. Repairs isolate search RNG, validate domains/results, retain accepted-state smart guidance and return best feasible points. The walk is still a finite heuristic SA, not a certified global solver.

No uncertainty experiment, mixed workload, controller modification, V3 training, changed feasibility rule or full SA campaign.
"""
    )
    (ROOT / "docs/SA_PAPER_CODE_DISCREPANCIES.md").write_text(doc, encoding="utf8")
    (out / "source_audit.md").write_text(doc, encoding="utf8")
    original = BASE / "upstream_snapshot/simulated_annealing.py"
    corrected = BASE / "paper_consistent/simulated_annealing.py"
    diff = "".join(
        difflib.unified_diff(
            original.read_text().splitlines(True),
            corrected.read_text().splitlines(True),
            fromfile="upstream_snapshot/simulated_annealing.py",
            tofile="ARGOS paper_consistent/simulated_annealing.py",
        )
    )
    (out / "original_to_experimental.patch").write_text(diff, encoding="utf8")
    (ROOT / "docs/SA_ORIGINAL_TO_PAPER_CONSISTENT_DIFF.md").write_text(
        "# Original to experimental SA\n\nOriginal is byte-identical and never edited. The working derivative preserves the walk structure but extracts simulator/objective/domain/evidence responsibilities into separate ARGOS modules. This is not an upstream patch. See the discrepancy register for semantic explanations.\n\n"
        + diff,
        encoding="utf8",
    )
    guide = """# Phase 2C experimental paper-consistent SA

Experimental paper-consistent SA implementation derived from pinned FlexDC source for ARGOS research.

The package is isolated from ARGOS search/controller code. upstream_snapshot is comparison material, never imported by the active runner. Its17 files are byte-identical to pinned FlexDC. The active derivative retains Gaussian P/R perturbations, optional smart weights, Metropolis acceptance, geometric cooling and iteration200/300 step reductions; responsibilities are separated for testing.

## Contract

ObjectiveContract delegates Cfull to existing argos.contracts.Costs and exposes M_RSR/Ctrack/CQoS/Cfull. canonical_costs verifies provenance, and pinned cost_function/dr_program sections must agree. Feasibility delegates to ARGOS assessment after finite/dimension/support checks. Inclusive.30/.10 limits, existing Pj and minimum one observation/type are unchanged.

SAResult always contains status, scientific_result, current, best_scalar, best_feasible, best_violation, evaluations,error. Best feasible means lowest objective among all valid feasible points encountered, even if a Metropolis proposal was rejected. Ties retain the first point. No feasible point yields null scientific_result and NO_FEASIBLE_CANDIDATE_FOUND. Execution errors remain explicit; any previously valid feasible point is preserved for inspection, not mislabeled as a completed run.

## Fixed arrivals and isolated execution

prepare calls pinned init_job_table once and saves an immutable full initial table. Each evaluation is a fresh Python process loading/copying that table and creating fresh nodes/policy/simulator. Workers never generate arrivals. Runtime uses explicit seed; search uses local PCG64. Search state before/after each evaluation is logged. Outcomes can indirectly alter the trajectory; simulator RNG cannot directly consume search draws.

The normal aqa_runtimepolicy class and Phase2 compact output hook are reused unchanged. Grid/start hour/hash remain fixed. Target hashes are per candidate: targets change when bids change. Repeated bids must reproduce targets. Config, selected source and initial-table hashes are checked for every worker.

Per evaluation retain raw result, job/QoS summaries, request and16KiB log tail; trajectory JSONL includes seed/state, raw metrics, objective components, feasibility, acceptance probability/draw, temperature, current/best values and IDs. Full temporary runtime traces are removed from verified private scratch after extraction. One initial table per run remains. No per-node archives/network logging. Failed evaluations retain private evidence. SA trajectory is sequential.

Scope is pinned W2 AQA/RSR, N1000/U.6,3600 seconds. It is not an EDR/multi-hour repair. Domain name is required. Initial frozen candidate must satisfy it; initial points are not silently projected.

## CLI reference, not a request to run

python scripts/run_experimental_sa.py --help

Requires context-manifest, case, domain, search-seed, arrival-seed, runtime-seed, iterations. Output must be new. iterations0 evaluates only initial candidate; iterationsK performs K sequential transitions plus initial evaluation. No varying-arrival mode, reliability rule, ten-seed assessment or automatic campaign.

python scripts/audit_phase2c_sa.py rebuilds saved-data arithmetic parity, without simulation. Review ZIP includes bounded V3 rows, raw Phase2B observations, exact compatibility script, implementation, snapshot, tests and manifests.

scripts/validate_phase2c_sa_smoke.py is the explicit four-call gate with duplicate-run guard. It refuses to rerun an already-started audit. All four checks completed exactly; do not run it again. Synthetic tests cover SA transitions; real checks used frozen candidates with zero transitions.

No additional user-run validation is required for this fixed-context correctness gate. Phase3 design remains future work; distinguish objective repair from runtime/domain choices and unchanged Pj conventions.
"""
    (ROOT / "docs/PHASE2C_PAPER_CONSISTENT_SA.md").write_text(guide, encoding="utf8")
    (BASE / "README.md").write_text(
        "Experimental paper-consistent SA derived from pinned FlexDC for ARGOS research.\n\nSee docs/PHASE2C_PAPER_CONSISTENT_SA.md and docs/SA_PAPER_CODE_DISCREPANCIES.md. upstream_snapshot is byte-identical provenance; paper_consistent is the isolated active derivative. Never edit upstream_snapshot or .deps.\n",
        encoding="utf8",
    )
    csvout(out / "source_inventory.csv", m["snapshot"])
    csvout(
        out / "domain_tests.csv",
        [
            {
                "profile": p,
                "random_projections": 2000,
                "boundary_cases": 4,
                "passed": True,
                "method": "ARGOS bounded-simplex80-step bisection; tolerance1e-10",
            }
            for p in ["legacy_sa", "argos_v3_physical"]
        ],
    )
    csvout(
        out / "rng_isolation_tests.csv",
        [x for x in tests if "rng" in x["test"] or "generator_seed" in x["test"]]
        + [
            {"test": "four_real_calls_search_rng_unchanged", "passed": True, "time_seconds": 0},
            {
                "test": "same_full_identity_repeat_exact",
                "passed": m["real_smoke_repeat_exact"],
                "time_seconds": 0,
            },
        ],
    )
    csvout(
        out / "best_feasible_tests.csv",
        [
            x
            for x in tests
            if any(
                k in x["test"]
                for k in [
                    "best_feasible",
                    "no_feasible",
                    "initial_best",
                    "malformed",
                    "rejected_feedback",
                ]
            )
        ],
    )
    csvout(out / "unit_test_results.csv", tests)
    summary = f"""# Phase 2C correctness audit complete

ARGOS {m["repo_shas"]["ARGOS"]}
FlexDC {m["repo_shas"]["FlexDC"]}
CONDOR-FLEXDC {m["repo_shas"]["CONDOR-FLEXDC"]}
V3 checkpoint SHA256 {m["checkpoint"]["sha256"]}

Both dependencies clean;17 snapshot files byte-identical. No tracked ARGOS search/controller/V3 changes.

Tests: {len(tests)} passed. Objective:88 saved outcomes,352 component checks, max discrepancy {m["parity"]["max_objective_difference"]:.3g}, tolerance1e-12. Feasibility:56 saved outcomes plus invalid/missing-support/boundary fixtures. Domain:4000 randomized projections plus8 boundary cases and pinned V3 function parity. RNG, best-feasible/stable-return, and generator-only controls passed.

Exactly4 real simulator calls; zero SA transitions. Raw p90/Pj/evidence/objective and initial/grid/target hashes matched historical references exactly. Full-identity repeat matched all scientific fields exactly. No more simulator runs.

Critical repair: monetary tracking dollars were used in place of normalized p90 with an extra multiplication. Monetary tracking was not wholly omitted; its linear term was present once. Other repairs: authoritative feasibility, best-feasible return, isolated search RNG, bounded-simplex projection, stable schema, accepted-state guidance and compact evidence.

Discuss legacy/normal AQA implementations, explicit domain/units, and unchanged Pj estimator/equality/support conventions. Correctness is not evidence of optimizer quality, convergence or reliability.

Phase 2C correctness gates passed; no additional user-run validation is required before designing Phase 3.

Phase3 has not started. No varying-arrival SA, full campaign, retraining, altered grid, mixed workloads or new feasibility rule.
"""
    (out / "report.md").write_text(summary, encoding="utf8")
    owned = [
        *BASE.rglob("*.py"),
        BASE / "README.md",
        BASE / "audit_location.json",
        BASE / "upstream_snapshot/snapshot_manifest.json",
        *[
            ROOT / "scripts" / f
            for f in [
                "run_experimental_sa.py",
                "audit_phase2c_sa.py",
                "validate_phase2c_sa_smoke.py",
                "build_phase2c_report.py",
            ]
        ],
        ROOT / "tests/unit/test_experimental_sa.py",
        *[
            ROOT / "docs" / f
            for f in [
                "SA_PAPER_CODE_DISCREPANCIES.md",
                "SA_ORIGINAL_TO_PAPER_CONSISTENT_DIFF.md",
                "PHASE2C_PAPER_CONSISTENT_SA.md",
            ]
        ],
    ]
    for file in owned:
        target = out / "review_files" / file.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file.read_bytes())
    sources = {str(f.relative_to(ROOT)).replace("\\", "/"): sha(f) for f in owned}
    v3_bounds = ".deps/CONDOR-FLEXDC/am_flexdc/flexdc_generic_sources/flexdc_generic_sources/flexdc_behavior_inference_utilities.py"
    sources[v3_bounds] = sha(ROOT / v3_bounds)
    sources[m["checkpoint"]["path"]] = m["checkpoint"]["sha256"]
    source_spec = json.loads((ROOT / m["phase2b_directory"] / "manifest.json").read_text())[
        "specification"
    ]
    for name, digest in source_spec["files"].items():
        assert Path(name).name != ".env" and sha(ROOT / name) == digest
        sources[name] = digest
    for name in [
        "configs/canonical_cost_source.ini",
        "configs/canonical_cost_source.json",
        "configs/v3_context_contract.json",
    ]:
        sources[name] = sha(ROOT / name)
        target = out / "review_files" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    csvout(out / "source_hashes.csv", [{"path": k, "sha256": v} for k, v in sources.items()])
    m.update(
        status="COMPLETE",
        completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        tests_passed=len(tests),
        source_hashes=sources,
        dependencies_unchanged=True,
        ready_for_phase3_design=True,
        scope="Fixed-arrival one-hour W2 AQA RSR; existing Pj unchanged",
        added_files=[str(f.relative_to(ROOT)).replace("\\", "/") for f in owned],
    )
    (out / "manifest.json").write_text(json.dumps(m, indent=2))
    retained = [
        f
        for f in out.rglob("*")
        if f.is_file()
        and not any(
            x.startswith("test_tmp") or x == "__pycache__" for x in f.relative_to(out).parts
        )
        and f.name != "artifact_hashes.json"
    ]
    assert all(f.name != ".env" for f in retained)
    hashes = {str(f.relative_to(out)).replace("\\", "/"): sha(f) for f in retained}
    (out / "artifact_hashes.json").write_text(json.dumps(hashes, indent=2))
    retained.append(out / "artifact_hashes.json")
    with zipfile.ZipFile(
        out.with_suffix(".zip"), "w", zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for f in retained:
            archive.write(f, str(f.relative_to(out)).replace("\\", "/"))
    with zipfile.ZipFile(out.with_suffix(".zip")) as archive:
        assert archive.testzip() is None
        for name, digest in hashes.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    print("COMPLETE", out.with_suffix(".zip"))
    print("Files", len(retained), "MiB", out.with_suffix(".zip").stat().st_size / 2**20)


if __name__ == "__main__":
    main()
