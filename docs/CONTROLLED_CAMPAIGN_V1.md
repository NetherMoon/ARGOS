# Controlled development campaign v1

This protocol tests frozen ARGOS 0.2.0 at annotated tag v0.2.0-pretest,
commit 425eec6b7fec1202bdc97b88f7b50c23ca575aa0. Campaign infrastructure may change
before its execution gate; core numerical, evidence, search and confirmation
semantics may not. A core correctness defect stops affected experiments.

The authoritative machine-readable protocol is configs/campaigns/controlled_v1.json.
Its 47 contexts expand to 227 method runs: one engineering context; eight original
controls; all fourteen mixed J4 screening contexts; six structurally selected serious
mixed contexts; eight historical V4 contexts; six clean variable-J contexts; four
operating-condition contexts. Screening uses 128 starts, 500 iterations and 16
queries. Serious runs use 512 starts, 1500 iterations, snapshot interval 50, four
batches of eight, two independent slots per batch, and at most four workers.
Smoke uses four starts, four iterations and four queries. No outcome-driven changes.

All five methods are compared except operating-condition cases, which use V3-only,
simulator-only and fixed-budget ARGOS. V3-only calls the original pinned
select_distinct_top_k (Safety_Both_Pass); it selects the first original rank
without simulator feedback. No accepted endpoint means NO_BID and zero queries.
Fixed probing freezes the entire set before any simulator results: the core initial
batch, followed by local perturbations cycling original representatives and the
declared independent slots. Core geometry and predictors are reused.
Simulator-only supplies no regions and an identity predictor to the unchanged
measured-result Controller. ARGOS uses that Controller unchanged. Early stopping
replays only an exactly verified prefix of fixed-budget proposals and observations;
its selected candidate receives its own confirmations when different.

Composition roles follow ResNet/GPT2/Llama/Bloom order. Serious cases are TTII, IITT,
ITTT, TTTI, TIII and IIIT, selected structurally before screening. Every clean profile
copies all source fields, including inherited defaults and QoS. Historical V4 uses
the pinned generated INIs and manifest by explicit user authorization: the named
original generator could not be located in either reference repository, available
Git history, or the two research archives. V4 remains composition-plus-QoS stress,
with the unavailable generator clearly recorded. Variable J uses declared ARGOS
relative bounds [0.6/J,1.8/J], never attributed to the historical V4 optimizer.

Saved train/validation/test rows all cover N={250,1000}, U={0.6,0.8} and all four
original workloads. N=500/U=.7 is interpolation-like; N=1500/U=.9 is extrapolation-like
in those conditioned features. Signal, cluster, policy, one-hour duration and all
unconditioned context fields stay locked. No provenance-supported unseen-profile
or optional repeated-profile experiment is declared.

The seed ledger is committed before scientific runs. Historical simulator seeds
20,21,22,100020,100021,2026091301 are excluded. Each case has one predeclared bank
initialization and a common search scenario across methods, plus two disjoint fresh
confirmation scenarios. Engineering seeds are separate. Reserved final benchmark
groups are never passed into planning, search, confirmation or result reporting.
Only their counts and digest are displayed during validation.

Source inspection and an exact CPU regression establish that scenario seed affects
neither raw nor differentiable V3 features, predictions, snapshots, endpoints or
trajectory when the optimizer initialization is fixed. Full bank identities include
artifact/checkpoint, workload and ordered jobs, conditioned and locked context,
all declared settings plus pinned optimizer source defaults, runtime/device/threads.
Reuse checks persisted hashes. Simulator cache keys preserve exact float identities,
context/config hashes, extraction source/schema, dependency revision and scenario.
Logical method queries remain separate from unique physical executions and scenarios.
Interrupted attempts are retained; incomplete simulator executions require audit
before retry, and completed valid results must never be physically rerun.

Logical timing charges each V3 method the full measured bank creation time.
Simulator time is a deterministic FIFO schedule estimate using recorded subprocess
durations and the same maximum worker count. Physical wall time and reuse are separate.
First feasibility is reported at batch completion and includes all launched queries
through that batch. Objectives are reported among successful cases with failure
denominators retained. Every raw Pj, evidence count and horizon warning is preserved.

SA representatives are predeclared as W1-4444, W2-5555, MIX4-TTII and J3-TRAIN.
The unchanged upstream source currently differs in tracking-cost expression and
assigns scenario seeds by iteration. Its compatibility gate must be reported; do
not alter SA to disguise a different experiment. No SA results are claimed unless
actually executed with a documented compatible protocol.

Required execution gate: clean campaign commit, frozen tag, complete tests/lint/
format, doctor, immutable dependency and artifact verification, audited hashed plan,
committed ledger and subsets, and complete expanded serious-plan printout.
Scientific failures continue; corruption, invalid evidence or contract errors stop.
Results answer RQ1–RQ12 descriptively and are not a locked final benchmark.
