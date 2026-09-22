# Phase 2B — Expanded W2 Seed Characterization

Characterization only. No optimizer/controller, SA, V3, feasibility, bid, workload, simulator or grid changes. No Phase 3 work. The full experiment is run by the user, not during Codex setup.

## Provenance and inherited simulator path

ARGOS HEAD: `6c95e4b77eebbf25f32522c5836d69759f225963`.
FlexDC: `525dc684d73ab0c6f6c479f5b54811ddf02f1221`.
CONDOR-FLEXDC: `2b653facf31de356d8c682ee76d814bd81b8e95d`.
Both dependencies were clean before setup. Existing Phase 1/2 code and results were preserved; only the shared diagnostic worker's initial-reference handling and planned-cell validation needed extension. Historical outputs include their original source snapshots and hashes, so they remain attributable to the version that actually ran them.

Inputs are the authoritative Phase1 `w2_workload_seed_forensics_20260918T230805_755114Z` and Phase2 `w2_seed_factorization_20260919T002931_161214Z` artifacts. Their ZIP CRCs, directory equivalence, file hashes, original candidates/confirmations, all18 completion seals, and the saved60 exact replay checks are verified. Old simulations are never scheduled.

This extension calls the EXISTING `seed_factorization_worker.run_cell`. There is no second simulator implementation. In pinned FlexDC `.deps/FlexDC/src/peacsim/create_tables.py`, `init_job_table` at153 dispatches to `init_job_table_poisson` at162. Python random generates prefill types and exponential inter-arrivals. The existing helper seeds Python and NumPy for arrival generation. A complete10-row little-endian float64 hash is recorded before a fresh writable copy is passed to fresh nodes/policy/simulator. `Simulator.run` in `simulator.py:208` resets Python and NumPy at216-217 using the independent runtime seed. The active runtime randomness is `scheduler.assign_idle_servers`' Python random.shuffle at26. No runtime arrival regeneration is introduced.

The two-seed simulation and compact extraction body is unchanged. The shared worker adds an optional reference-free GENERATOR-ONLY preparation call for new, already frozen seeds; actual simulator workers always require the prepared reference and check their exact tuple against the56-cell plan. The old Phase2 default remains reference-required. No monkeypatch of simulator/runtime behavior is used. The inherited record_state override only writes compact observations and preserves normal tracking-error formatting.

Fixed context: N1000, U0.6, duration3600s, one-second simulation, canonical normalized ISO signal, start hour16, no random ISO start. The same actual grid hash is checked globally. Actual target hashes are checked within candidate; A and B have different fixed bids, so their targets appropriately differ.

## Seed declaration

Seven IDs, in selection order:
`2720817509, 422443260, 3463391848, 1507332087, 598775175, 3385754323, 2812640469`.

Procedure: the same Python `random.Random(root).randrange(1, 2**32)` rejection-sampling pattern used by `src/argos/vnext/protocol.py`; a separate root20260919 identifies this characterization. Exclude membership in both existing seed ledgers, the ten recovered Phase1 historical seeds,20/21/22, and any duplicate in this new panel. Reserved ledger values are only checked for membership, never printed. Ledger hashes and exclusion count are recorded. The frozen CSV was written BEFORE new trace generation or outcomes. No seed is discarded/replaced because of load, bursts or QoS outcomes.

Config: `configs/diagnostics/w2_seed_characterization_10x3.json`.
Panel: `configs/diagnostics/w2_characterization_new_seed_panel.csv`.
The seven values are shared by both candidates and are disjoint from all existing Phase1/2 seeds for them.

## Two goals, distinct populations

Goal A preserves these ACTUAL three fresh confirmations, then adds seven new S,S cells per candidate:

* c005:2381098110,1841060571,2495920665.
* c007:624506888,144392579,1004088181.

The c007 original search PASS seed3514694477 is NOT one of its fresh confirmations and must NOT enter Goal A's ten-scenario count. The original c007 three fresh confirmations all failed. No selection based on those outcomes is performed here.

Goal B preserves the exact pilot axes:

* c005 runtime axis1841060571,2381098110,2495920665; same original three arrival rows.
* c007 runtime axis3514694477,1004088181,624506888; same original three arrival rows.

Append the shared seven new seeds to each arrival axis ONLY. The runtime axis stays three. Thus Goal A adds14 executions, Goal B adds42, total56 unique planned new cells. They do not overlap: new S,S runtimes are not old pilot runtime-axis seeds. The final outputs represent20 fresh-scenario rows and60 matrix rows. Five old confirmation cells also occur in the old pilot, so combined identity tables deduplicate those overlaps. Runtime summaries contain the18 reused pilot cells plus new56; detailed runtime logs for the old c007 seed144392579 confirmation are not available from Phase2 and are not fabricated.

## Hashes and retention

Before new simulations, preflight generates14 unique new initial contexts and saves each complete table once. Every worker independently uses the real generator and must reproduce that hash. Shared-seed arrivals must also match between the two workload files. All seed IDs remain frozen if an invariant fails; failures abort, not seed replacement.

Original confirmation initial hashes are Phase1 reconstructions; grid hashes are fixed-context references where original runtime traces were not retained. Evidence-source columns make this distinction explicit. New workers' grid and initial hashes are actual-run checked. Existing pilot hashes and replay results are reused and verified.

The new ZIP includes new compressed job/power/queue series, initial tables, old compact aggregate summaries, provenance links, config/tool snapshots, merged result tables, reports and five figures. Old full directories, old per-node data and raw grid copies are not copied. Old per-cell runtime detail remains referenced in the Phase2 ZIP. The existing150MiB compact-artifact bound remains in force (expected output is well below it).

## Accounting and descriptive analysis

The inherited canonical Pj/evidence/feasibility implementation is unchanged: submit_time0 is excluded from Pj; completed positive-submit jobs and eligible unfinished jobs form its support. For n>=2 samples/m strict exceedances, Pj=max(m-1,0)/(n-1), with existing singleton/zero-evidence handling. Finished and horizon-censored violations are separately counted. Waiting for started jobs and completed sojourns are separated from censored lower bounds. No 8/10 rule is defined.

The10x3 decomposition uses SS_arrival=3*sum((row_mean-grand_mean)^2), SS_runtime=10*sum((column_mean-grand_mean)^2), and residual/interaction=sum((cell-row_mean-column_mean+grand_mean)^2). The row/column counts matter: the old3x3 coefficient must not be reused for the10-row runtime component. It is labeled descriptive variance decomposition for this selected finite matrix; no p-values, population causal percentages or reliability probabilities.

Arrival associations use a fixed feature list: Poisson count, prefill count, max60s Poisson burst and final300s arrival fraction for each job type. They are descriptive correlations with the mean Bloom Pj over the three runtime seeds. They do not establish causal sufficiency; complete mixed-job timing and queue evolution may still matter. Pending cells are unknown, not failed or zero. Reports do not claim an expanded result until all56 new cells are valid.

Five figures cover coupled Bloom Pj with0.10 limit and pass/fail styling, coupled overall outcomes, paired10x3 Bloom Pj heatmaps, paired pass/fail heatmaps, and Bloom queue/waiting comparisons across arrival classifications. The original/new boundary and actual seed labels are explicit.

## Execution, resume and errors

From the ARGOS root in PowerShell:

```powershell
& '.\runs\pretest_hardening\paper_install_1789323000349575100\venv\Scripts\python.exe' -B scripts/run_w2_seed_characterization_10x3.py --max-workers 10
```

`--dry-run`: verify old evidence, create the56-cell plan, merge existing results and test partial reporting/ZIP. Zero generation and zero simulations.
`--prepare-only`: additionally generate the14 initial contexts and arrival summaries; zero simulations.
`--resume <output directory>`: verify unchanged tool/config/plan/prepared hashes and skip sealed valid new cells. It never schedules old Phase1/2 cells. A dry-run directory can be resumed with the same tooling to prepare and execute its plan.

Every actual execution is a separate process with private mutable objects, private scratch/output, and one-thread numerical libraries. Maximum workers10. An OS lock prevents concurrent parents for one output. Completed cells have checksum seals. An execution error cancels undispatched work and exports partial evidence after running workers finish. No automatic retries: unsealed/error cells stop resume for explicit review; attempt1 and any execution error are logged, and manifest retries starts empty. Scientific infeasibility is a valid completed result, not an execution error and never grounds for retry or seed replacement.

Output: `runs/diagnostics/w2_seed_characterization_10x3_<UTC timestamp>/` and the same path plus `.zip`. Upload the ZIP after completion. The generated report answers characterization questions and discusses whether evidence motivates a Phase3 proposal; it never starts Phase3 or changes an optimizer.
