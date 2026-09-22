# Phase 2C experimental paper-consistent SA

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
