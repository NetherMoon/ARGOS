# ARGOS design and scientific contract

## Separation of responsibilities

`surrogate/v3_adapter.py` loads the immutable model and training features.
`search/` owns candidate geometry and deterministic region extraction.
`simulator/` alone knows FlexDC execution and output schemas.
`controller/` owns the bounded adaptive policy. `contracts.py` is the single
ARGOS feasibility, violation-ranking and objective-composition authority. FlexDC owns simulator Pj. Typed immutable candidate,
metric, region and observation records preserve job order and scientific provenance.

A candidate comprises Pbar and R in kW/server plus one scheduler weight per job.
A workload comprises job profiles; a fixed context adds N, utilization, signal,
policy, duration and other experiment settings. Region frequency is not a
probability of feasibility. Predictions are guidance, never simulator evidence.

## Frozen V3 and trajectories

Artifact and checkpoint hashes select epoch 146, best-feasibility. The bundled
architecture and training source match current CONDOR V3 source after newline
normalization. We nevertheless load the artifact files directly. Temporary import
bindings connect the pinned generic inference module to those exact model/features.
No model parameter requires gradients; gradients flow only to candidate inputs.

The original generic optimizer only logs aggregate trajectory statistics. ARGOS
uses its unchanged function bytecode in a private global namespace with two
observation hooks. One retains parameterized weights, the other copies requested
per-start predictions. Nothing is patched in the dependency module. At iteration
k, snapshots represent the state before update k; iteration `iterations` is the
final state after every Adam update. Iteration 0 and the final state are retained.
The endpoint DataFrames match the original optimizer bitwise on the parity case.

The original Adam/cosine schedule, constraint penalties, legal transforms and
start initialization remain in force. The model objective is the source's
analytical monetary cost plus canonical penalties. Margins in the original
optimizer guide proposals but do not change actual feasibility thresholds.

## Legal geometry and candidate regions

The pinned V3 plan generator establishes Pbar in [0.9 Pmin, Pmax], R >= 0.01,
R <= 0.6 Pbar, and Pbar+R <= 1.2 Pmax. The known J=4 study has weight bounds
[0.15,0.45], intersected with the upstream server/job-count bounds. Other J values
must supply a feasible bounded simplex; no weight identity is sorted away.

Pbar is scaled to its legal interval. Reserve is scaled within the legal interval
conditional on that Pbar. Weights are scaled within their own configured bounds.
Distance is sqrt((delta_P^2 + delta_Rfraction^2 + mean(delta_weight^2))/3), so each
of the P, R and weight blocks contributes equally. This is a declared heuristic
geometry, not a claim of physically optimal distance.

At each snapshot, round-robin quotas retain lowest-cost predicted-feasible bids,
best tracking and worst-job QoS margins across all candidates, lowest normalized
violation across all candidates, a dedicated lowest-violation infeasible quota,
and geometric diversity. Quotas consume one unseen ID per round; short lists are
skipped and ties use objective then candidate ID. With at least six slots all
nonempty categories receive a turn. At most `promising_per_snapshot` IDs survive. The union
starts with the best global feasibility/objective rank, then interleaves snapshot
ranks. Near-identical configurations are removed. Greedy radius-separated
representatives are selected up to `max_regions`; remaining members are assigned
to their nearest representative. Member IDs and source iterations remain recorded.

Independent sampling draws P directly in its legal interval and then conditional
R. A random job order with sequential feasible allocations directly samples the
bounded simplex; it is **not claimed to be uniform**. Local proposals use truncated
interval perturbations in normalized P/R coordinates and Euclidean projection of
perturbed weights onto the bounded simplex. Projection uses scalar bisection.
The numeric legality tolerance accommodates float32 V3 output and is not a repair.

## Exact FlexDC boundary

The upstream config snapshot is hashed and tracked. Only its canonical cost/DR
sections are mapped into the ordinary gradient configuration. The pinned config
generator replaces each requested key exactly once and preserves unrelated text.
Each episode gets its own gradient and seed-specific experiment INIs with source
hashes and old/new values. Only N, utilization and random seed are overlaid on the
experiment. The ISO path text stays unchanged; an identical signal copy recreates
its relative path inside each isolated process working directory.

Each subprocess receives a one-row exact plan, one workload, one seed and one
weight vector. ThreadPoolExecutor bounds concurrency. Python bytecode writing is
disabled for all dependency imports. Every attempt has its own directory, logs,
process identity, command and config hashes. FlexDC rounds physical total watts;
ARGOS verifies that declared upstream conversion in addition to physical bid fields.

Results and diagnostics must each contain exactly one matching row. Workload,
context identity, seed, N, utilization, policy, weights and bid are verified.
Finite p90 and exactly J finite probabilities are required. ARGOS independently
reconstructs the objective and compares the logged full objective, while preserving
both raw files. Hashes verify unchanged input configs and signal contents.
Failures have explicit invalid-evidence or execution/contract statuses.

## Automatic measured refinement and stopping

The initial batch selects distinct V3 region representatives plus independent
candidates. Subsequent batches retain one unused region when available, generate
nearby proposals around diverse measured anchors, and retain independent slots.
Finite attempt limits avoid infinite candidate generation. Predictions are attached
to every query before execution, including local and independent proposals.

Feasible measured points rank by actual cost. Otherwise the primary rank is worst
normalized violation, then total violation, then actual cost. In particular, mean
Pj cannot hide a failing job. The final incumbent is the cheapest measured feasible
candidate after the configured call/batch budget. Optional wall stopping is checked
between batches in the controller; it excludes initial V3 setup/search time. A
per-call timeout separately bounds simulator execution. Fatal invalid evidence
stops the episode. No budget or threshold changes are made to obtain success.

## Confirmation and recovery

Search uses its declared scenario seed. The incumbent is frozen before confirmation.
All confirmation seeds differ from the episode's selection seed. Each scenario is
executed freshly unless resuming an already completed identical confirmation.
Confirmation failures never re-enter search or select another candidate in core
ARGOS. Pass counts and mixed results remain explicit.

The controller atomically checkpoints before dispatch and after each batch. Candidate
identities and call reservations are durable. Candidate RNG progression is derived
from (candidate_seed, batch index), so resumed proposals are deterministic. Each
completed subprocess separately writes its observation. Pending cached completions
are reparsed and reused without another execution. Interrupted attempts are kept;
retries consume the finite search call budget and are refused if an earlier recorded
process is still alive. Resume rejects changed source/runtime/dependency/artifact/
context identities. Resume one process at a time. Exhausted-budget incomplete batches
require inspection and fail without spending additional calls.

## Future options, deliberately unimplemented

Possible hooks are pre-query scoring, post-observation updates, warm-start generation,
local prediction correction, and trust/novelty signals. Future candidates include:

- Simple empirical local offset or local linear correction.
- Local GP/residual model.
- Reliability or calibration model.
- Transferable correction model.
- Novelty/OOD-aware allocation.
- Reuse of validated regions as warm starts.

The same scientific metrics, simulator boundary and confirmation protocol can serve
future V3-final-check, fixed-nearby-probe and simulator-only baselines. Those methods
are not implemented merely to increase framework complexity.

## Current limitations

Only the declared one-hour AQA known context was exercised with real simulations.
CPU floating-point equivalence is tested; GPU trajectories may differ. Radius,
snapshot retention, exploration fraction and local scale are initial hyperparameters.
The global domain is not exhaustively searched. Fixed-seed selection and two
confirmation scenarios are limited evidence. The simulator's per-job probability
estimator and output precision are inherited, including zero estimates with limited
job evidence. Raw traces are preserved for later analysis. A general-purpose
concurrent-episode lock, broad OOD validation, alternative-duration objective
contracts, baseline experiments and a release license decision remain future work.


## Simulator Pj authority and raw-evidence validation

`Metrics.pj` is parsed directly from FlexDC's `QoS_Delay_Probabilities` result
column. `validate_reported_qos_evidence` returns QoSEvidence metadata and checks
that the pinned raw-record formula agrees with each reported value. It never
returns a replacement metric vector. Mismatch raises a contract failure. The
same rtol=1e-10 / atol=1e-12 tolerance is centralized for validation and typed
records. Tiny tolerated differences remain in the simulator-reported value.
Reported Pj drives all numerical tests, margins, residuals, ranking and penalties.

The following formula documents validation of FlexDC's estimator, not a separate
ARGOS definition.

## QoS estimator source trace (publication audit)

Pinned FlexDC `src/peacsim/calculate_qos_cost.py:calculate_delay_prob`
receives `sim_hour=1` from the exact-plan wizard. For each numeric job index,
its sample contains finished jobs with arrival_time > 0, plus unfinished jobs
with arrival_time > 0, arrival_time <= 3600, and arrival_time + minimum runtime
< 3600. A finished job contributes end_time - arrival_time - minimum runtime;
an eligible unfinished job contributes 3600 - arrival_time - minimum runtime.
The strict exceedance threshold is qos_constraint * minimum runtime.
For runs longer than two hours, upstream uses first_hour=1 and
last_hour=sim_hour-1; the last_hour cutoff applies only to unfinished jobs.

Let n be the sample size and m the number of strict exceedances. Upstream
sorts the delays and constructs linspace(0, 1, n). For n >= 2 and m > 0,
Pj = (m - 1)/(n - 1). With no exceedances Pj=0. For n=1, Pj is 1 if the
single observation exceeds the threshold, otherwise 0. For n=0, upstream
emits a zero sentinel: this is not evidence of satisfaction. Consequently
Pj is not m/n, and one exceedance among n>=2 observations also yields zero.
We retain sample counts, actual exceedance counts, and this estimator's
separate numerator/denominator; empty samples have no numerator/denominator.
A minimum of one observation only establishes a nonempty estimator, not a
confidence interval or statistical reliability. Unfinished observations are
censored sojourn estimates, not proof that those jobs eventually met QoS.

JobProfileReader assigns numeric indices by INI section order. The exact-plan
wizard writes those ordered section names in base_weights.csv and writes six
physical/runtime/QoS/job-size descriptors in workload_mix. Both outputs must
match the requested ordered workload. Raw job_table.csv preserves the final
simulator table needed to reconstruct the estimator without simulator edits.

Initial read-only W1 selected/confirmation reconstruction (job order Resnet,
GPT2, Llama, Bloom): seed20 n=(1563,281,284,375), seed100020
n=(1432,303,280,309), seed100021 n=(1412,317,323,335). All strict exceedance
counts are zero. These results pass the minimum-n=1 evidence check. They do
not establish long-horizon QoS or statistical confidence.


## Explicit policy and integrity revisions

The historical controller was fixed-budget and selected numerically feasible bids.
Current selection uses evidence-qualified feasibility. `fixed_budget` remains the
default; `early_stop` uses `qualified_local_patience_v1`: at least one qualified
search observation, at least one completed later batch containing a local proposal,
minimum two completed batches, and patience=1 without improvement greater than
absolute epsilon=1e-6. Epsilon is a numerical tolerance, not tuned from W1 outcomes.
The same function replays saved batches. Confirmation never updates this state.
If independent slots or unused regions consume all guided capacity, stopping waits
until a local proposal actually executes. Hard call/batch/wall limits take precedence;
wall limits are checked between batches, not a mid-simulator cancellation deadline.

Default local proposals are measured_random. Optional v3_screened builds a pool
four times the remaining guided slots, scores it, and applies tradeoff retention.
FixedRadius implements RadiusPolicy; no adaptive radius, GP, residual model, or
reliability model was introduced. Policy versions are centralized in versions.py.

The old retention rule excluded all infeasible candidates whenever feasible points
existed. The new dedicated infeasible quota prevents that loss. This is a declared
method change; historical episode artifacts are not regenerated. The search manifest
hashes starts, snapshots, endpoints, trajectory, candidate_pool, regions and timing;
CSV and candidate/region counts, snapshot settings and policy versions are checked
before resume. Existing completed raw files, counts, and state/cache identities are
also revalidated. These hashes detect accidental changes, not adversarial rewrites of
both a file and every trusted hash anchor.

Relative weight bounds are an explicit new ARGOS policy. The historical V4 claim
could not be established in local condor_flexdc_v4 source or its zip archive.
The pinned generic inference calculate_weight_bounds function uses parameterized
fractions of equal allocation: lower=max(min_fraction/J,1/N),
upper=min(max_multiple/J,1-(J-1)*lower). Its defaults are .1 and 4.0; its
paired-comparison notebook explicitly chooses .6 and 1.8. ARGOS applies its
configured bounds as stricter overrides intersected with the upstream defaults. This supports the implementation rationale (fraction of equal
allocation plus at least one server), not attribution to a particular V4 experiment.
Fixed bounds remain [.15,.45], and fixed J=8 is correctly infeasible.

Zero-width legal reserve edges encode a deterministic zero reserve coordinate.
Truly negative intervals are rejected; near-zero conditional sampling intervals
collapse only within 1e-12 roundoff tolerance. No invalid interval is silently widened.

The context contract explicitly records policy, node-count control, duration,
control granularity, idle watts, cluster hash, ISO content hash, offset, granularity,
normalization and randomization. No such fields appear in V3's feature lists, so
unknown changes cannot be treated as conditioned predictions. N/U, workload's six
ordered descriptors, J and bid variables do appear in the features. Replicate seed
varies without conditioning; this does not model per-seed randomness. The context
restriction is conservative and does not claim every trained context was recovered.

Per-job evidence also reports threshold_sojourn_seconds and whether that threshold
exceeds the simulation horizon. In W1, GPT2/Llama/Bloom require 4740/4968/4416 seconds
to exceed QoS; the 3600-second run cannot observe those violations for new arrivals.
Their nonempty censored estimators meet the declared n>=1 rule, but do not establish
long-horizon QoS. Resnet's corresponding threshold is 1348 seconds.


The history check found the same parameterized rule with .1/4.0 defaults in older
CONDOR commit 4eaacd4. Available local optimize_v4.py instead declares a .1/J
floor and [.3/J,2.4/J] trust region. Neither establishes the requested V4 dynamic
label. See reports/publication_audit/weight_policy_provenance.json for exact sources.


## Pre-testing execution and provenance contract (0.2.0)

`inspect_process` returns LIVE with creation time, ABSENT for a vanished/zombie
process, or UNKNOWN for permission/other psutil errors. `original_process_running`
compares the creation time to avoid confusing a reused PID with the original.
Matching live or indeterminate prior processes block duplicate dispatch. A process
observed absent immediately after Popen is recorded as absent; its owned Popen
handle is still waited and its exit recorded as a structured attempt. Unknown
inspection after Popen does not lose ownership of that handle or prevent bounded
waiting. Unknown identity during later recovery fails conservatively. Every failed
attempt and cached failed observation remain recoverable without a duplicate call.

The immutable FlexDC INI replacement function is cached by resolved source path.
Runner construction loads it before dispatch, and a lock also protects first use
by concurrent overlay callers. The lock covers import/cache access, not INI
preparation or simulations. Dynamic imports share an interpreter-state lock and
restore bytecode policy and previous module bindings on failure. Overlay output
and audit metadata are deterministic and match the pinned helper's serial output.

New observations use schema 3 and execution-only status: PARSED,
SIMULATOR_EXECUTION_FAILED, CONTRACT_MISMATCH (or another explicit invalid-output
status). Scientific facts are orthogonal structured assessment fields. For example,
PARSED may coexist with numerical_feasible=false and evidence_sufficient=false.
Schema-1/2 historical records retain their stored status; the execution_status
property and exports normalize valid historical labels to PARSED. They do not
retroactively acquire evidence. No analysis uses a lossy scientific status string.

Confirmation status is derived centrally from actual executions and qualified
passes: zero executions=NOT_RUN; zero passes among executions=NONE_PASS; some
passes=PARTIAL_PASS; all executed runs pass=ALL_PASS. Expected count and completion
are separate; an interrupted confirmation plan can have ALL_PASS so far while
confirmation_complete=false and the overall episode remains incomplete.

Audit records raw_data_validity separately from current_environment_identity.
ARGOS source (HEAD, dirty flag, source hashes), dependency commits/URLs/dirty flags,
checkpoint bytes, artifact manifest and all listed file hashes, canonical source
bytes/metadata, and context-contract bytes are compared independently. Missing
historical dimensions remain HISTORICAL with their recorded/current values shown;
known differences remain MISMATCH even in historical mode. Unavailable current
inputs remain UNAVAILABLE. Exact current audit fails any non-match. Explicit
historical audit permits raw reconstruction success without claiming environment
identity. Neither path mutates old manifests. Audit-only smoke layouts are
supported without inventing search state or confirmation executions.

Software and scientific policy/schema constants live in versions.py. Package
metadata derives version 0.2.0 from that module. Search policy versions stay
unchanged; observation/report/audit schemas advance for the clarified interfaces.
The default algorithm remains frozen V3 guidance, measured refinement, fixed local
radius, measured_random local proposals and disjoint final confirmation. Experiment
novelty labels introduce no optimizer behavior and no learned extension is added.

Historical objective parity uses the execution's retained gradient INI after its
recorded input hash is verified. A different current canonical cost source is an
environment mismatch; it does not replace historical cost constants or invalidate
otherwise reconstructable historical raw data. Changed historical inputs still fail.
