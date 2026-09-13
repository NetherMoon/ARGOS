# ARGOS design and scientific contract

## Separation of responsibilities

`surrogate/v3_adapter.py` loads the immutable model and training features.
`search/` owns candidate geometry and deterministic region extraction.
`simulator/` alone knows FlexDC execution and output schemas.
`controller/` owns the bounded adaptive policy. `contracts.py` is the single
feasibility, violation-ranking and objective authority. Typed immutable candidate,
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

At each snapshot, feasible candidates are interleaved from three stable rankings:
lowest objective, largest tracking margin, and largest worst-job QoS margin.
If none are predicted feasible, normalized worst/total violation and objective
rank the group. At most `promising_per_snapshot` distinct IDs survive. The union
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
