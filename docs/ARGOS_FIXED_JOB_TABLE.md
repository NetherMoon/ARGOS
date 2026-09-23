# Fixed-job-table ARGOS W2 experiment

This is a separate ARGOS research mode. It asks whether ARGOS can find a feasible
bid for each **individual generated job table**. The two workloads each have
three new arrival seeds, giving six independent searches. Each search may select
its own Pbar, R and scheduling weights. The experiment does not seek one bid that
works across different generated tables.

The frozen plan is in `configs/fixed_table/seed_plan.json` and
`configs/fixed_table/episode_plan.csv`. The seed allocator used Python 3.12
`random.Random(20260922)` and rejected values appearing in the recorded prior
seed ledgers and Phase 3/3B/3C plans. Selection happened before any new table
or simulator outcome was viewed. The three arrival seeds are 3883208862,
3090083691 and 2888586026. Every search evaluation uses runtime seed
3122970382. Only after selecting a bid, the same table is checked under runtime
seeds 1551038600, 439454967 and 3928942722. The controller seed is fixed
within each workload across its three episodes; it differs between workloads.

For each episode, the real pinned FlexDC generator creates one full initial job
table and stores `initial_jobs.csv.gz`. Every candidate uses a fresh subprocess
that loads and copies that table, initializes fresh nodes and runtime state, and
sets the fixed search runtime seed. The worker runs normal
`peacsim.aqa_runtimepolicy.AQARuntimePolicy` and the pinned simulator. It reports
authoritative Pj and per-job evidence through the unchanged extraction contract.
The grid is the canonical traditional ISO signal at hour 16. The table and grid
hashes are checked on every evaluation. A bid's power-target hash must remain
the same across its three runtime checks; different bids can have different
power targets.

ARGOS uses the frozen V3 model with 512 starts and 1,500 iterations, retains
intermediate snapshots and endpoints, protects two V3 elites, and uses the
existing ERT region, targeted-probe, trust-region and independent-exploration
mechanisms. One V3 bank is generated per workload and reused read-only across
that workload's three table episodes. Search observations and local state remain
separate. No SA or historical winning bid enters these searches.

The fixed-table controller uses four batches of eight distinct candidate
geometries, at most 32 launched FlexDC calls per episode. There are no search
runtime repeats or racing slots. One valid evidence-qualified feasible search
observation can establish an incumbent. At the end, the lowest measured
canonical objective among qualified feasible search observations is frozen. If
none exists, the best measured violation is retained as a diagnostic and the
three runtime checks are skipped. A finite unsuccessful search does not prove
the workload is infeasible.

The six episodes have a maximum of 192 search calls. At most 18 runtime-only
checks follow selection, giving 210 planned scientific calls at most. Episodes
run sequentially. Each candidate batch and each episode's three final checks
use at most 10 FlexDC processes globally, with isolated mutable state and
output folders. Failed attempts remain visible and consume their call slots;
they do not cause seed substitution or unlimited retries.

From the repository root, with the tested `.venv` environment:

```powershell
& '.\.venv\Scripts\python.exe' -B 'scripts\run_argos_fixed_job_table.py' --max-workers 10
```

The launcher creates `runs/experiments/argos_fixed_job_table_<UTC timestamp>/`
and a matching `.zip`. It writes the manifest, frozen plans, compact initial
tables, bank identities and reuse receipts, every candidate search result and
ancestry, selected bids, final runtime checks, timings, summaries and a plain
English report. Transient simulator scratch is removed only after its compact
metrics and evidence are extracted. On a failure, the diagnostic cell and log
remain for inspection. A repeated command can use `--experiment-dir` with the
original directory to resume completed valid cells; an incomplete attempted
cell requires review and is never silently relaunched.

The setup smoke uses two **historical** seeds and a historical bid, outside the
new scientific plan. The same-seed run reproduced p90, all four Pj, evidence
counts and objective exactly. The second run changed only runtime seed and
preserved the table, grid and same-bid power-target hashes. The V3 model and
dependencies were verified but the six full searches were not run during setup.
CPU model loading, V3 bank, simulator search, final-check and end-to-end times
are recorded as descriptive laptop measurements, not as a five-minute
benchmark or a CPU-versus-GPU speedup claim.
