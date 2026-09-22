# Phase 2: W2 arrival/runtime seed factorization

This is an ARGOS-owned diagnostic, not an optimization campaign. The FlexDC and CONDOR-FLEXDC dependencies, optimizer, controller, SA, V3, workloads, grid, bids and feasibility contracts are unchanged.

## Frozen provenance and panels

ARGOS: `6c95e4b77eebbf25f32522c5836d69759f225963`.
FlexDC: `525dc684d73ab0c6f6c479f5b54811ddf02f1221`.
CONDOR-FLEXDC: `2b653facf31de356d8c682ee76d814bd81b8e95d`.
The entire authoritative Phase 1 directory and ZIP were compared, its output hashes checked, and the six selected original observations checked against their saved candidate, metrics and evidence. Existing Phase 1 files are preserved. The new frozen specification records source/config hashes and the pre-setup working tree.

`configs/diagnostics/w2_seed_factorization.json` is frozen before any Phase 2 simulator execution. Each panel is used on both axes; order is fixed:

| Case | Seeds | Selection rationale |
|---|---|---|
| c005, qos5_4.5_4_3.5 | 1841060571; 2381098110; 2495920665 | Best confirmed Bloom pass; heavy-arrival failure; worse failure with almost the same heavy count |
| c007, qos5555 | 3514694477; 1004088181; 624506888 | Original pass; failure with only six more Bloom Poisson arrivals and smaller max60s burst; failure with largest Bloom max60s burst |

Both exact saved candidate weights and full-precision Pbar/R are in the specification. They are revalidated against original saved observations on every invocation. The context remains N=1000, U=.6, 3600 seconds, one-second simulation steps, canonical ISO start hour16, two-second signal samples, normalization enabled, random start disabled, AQA with node_count_control=True. The experiment's U=.6 overlay is the same as historical exact-plan rows.

## Exact pinned seed boundary

All following source references are inside `.deps/FlexDC/src/peacsim/` at the commit above.

* `am_data_extraction_wizard.py:1297`, `create_simulator_object`, seeds NumPy and Python random at lines1304-1305, then calls `init_job_table` at1307. Historical exact-plan rows apply their simulation seed at1789. This factory couples the two labels, so the harness composes its real component APIs instead of calling the factory.
* `create_tables.py:153`, `init_job_table`, dispatches to `init_job_table_poisson` at162. Prefill type draws use Python `random.randint` at173; `arrival_generator` uses Python `random.expovariate` at149. NumPy is seeded for parity but does not draw in this active generation path. The Phase 1 helper calls this real generator once per cell, restoring its caller RNG state afterward; subsequent constructors have no active stochastic consumers in this fixed context.
* The harness hashes the full10-by-n initial table as C-order little-endian float64 (same Phase 1 definition), marks the original array read-only, and passes a separate writable copy to fresh nodes, a fresh policy and a fresh simulator. Generated fields are IDs, type, arrival, start, end, estimate_finished, update_time, realtime_qos, min_execution_time and qos_constraint. Rows3-7 mutate at runtime; IDs/type/arrival/profile metadata remain fixed. A new node table, policy weights/cache state and simulator histories are required for every run. Separate worker processes isolate module RNGs and all objects/output paths.
* The harness sets `experiment._random_seed` to the runtime seed before constructing `Simulator`. `simulator.py:36`, `Simulator.__init__`, stores it at58. `Simulator.run` at208 calls both `np.random.seed` and `random.seed` at216-217 AFTER the table exists. That unchanged method is the runtime reset and execution authority.
* Active AQA is lowercase `aqa_runtimepolicy.py:11`, inheriting `runtime_policy_new.py:10`. `execute` at38 calls scheduling; `schedule_jobs` at65 calls `scheduler.assign_idle_servers` at71. `scheduler.py:7` uses `random.shuffle(job_order)` at26. FIFO order within a type is retained. No active NumPy stochastic draw was found in this AQA runtime, node/job DAO, progress calculation or power capper. Imports of random are not themselves draws. Legacy similarly named AQA implementations and wizard weight sampling are not executed.
* `iso_signal.py:7`, `read_iso_signal`, has an optional NumPy random offset at22, but `randomize_iso_start=False` makes it inactive. Grid contents and start hour never enter workload generation. `Simulator.run` and the active runtime-policy path do not call the workload generator again.

There is no simulator-source patch, monkeypatch of scheduling, replayed custom scheduler, or reimplementation of arrivals. The only subclass override is `Simulator.record_state` (upstream193), an output-only method. It preserves the first nine power CSV columns with the exact upstream integer/one-decimal/three-decimal formatting. It replaces the huge per-node output columns with a separate compact, read-only per-type observer. It consumes no RNG and changes no simulation state. `run`, `error_violate`, `final_output`, scheduling and QoS functions remain pinned. A formatting change to trackingError would change p90, so it is explicitly tested and gated against history.

Holding a runtime seed fixed holds the pseudorandom stream fixed, not a pre-assigned random decision at each wall-clock instant. Different arrivals can change when/how often scheduler.shuffle is called. This natural dependence can appear as an interaction and must be interpreted accordingly.

## Replay controls

The full command runs all six historical diagonals first, at bounded concurrency. Only if every comparison passes does it dispatch the remaining twelve cells. Diagonals count toward the18; they are not extra simulations. Historical infeasible results are expected to remain infeasible and still pass replay validation.

Exact equality: initial full-table/arrival hashes, counts and evidence-qualified pass. p90, each Pj and objective use absolute tolerance1e-12, relative tolerance0. This allows only floating-point serialization/summation differences; it is far below output precision or scientific decision margins. The initial reference hashes are Phase 1 reconstructions, not archived historical simulator hashes (those are unavailable). Every saved source observation is independently verified before running.

A replay mismatch stops before off-diagonals and exports `REPLAY_FAILED` with per-field expected/actual differences. A worker failure also aborts after currently dispatched stage workers finish. A matching replay does not certify simulator correctness; it establishes fidelity to the pinned historical behavior.

## Grid and target invariants

The actual normalized ISO slice is expanded to all3601 simulation ticks and hashed with times in little-endian float64. The actual pre-rounding `P + R*signal` target is likewise hashed and checked in every worker, against a fixed preflight API calculation. Compact sampled grid/target files are retained once per candidate. Logged rounded target hashes are also retained.

Grid hashes must be identical across all18cells. Target hashes must be identical across each candidate's nine cells; they should differ between A and B because their fixed Pbar/R bids differ. Upstream conversion to integer watts is retained. Requiring cross-candidate target equality would silently change a bid and would be scientifically incorrect.

## Measurement definitions

Per-type populations include prefill, subsequent generated arrivals (including any rounded to0), strictly positive submit times, completed, unfinished, never started and started-but-unfinished jobs. All generated arrivals are at or before3600.

Waiting-time quantiles use start-arrival for jobs that actually started. Never-started jobs have separate censored lower-bound waits of3600-arrival. Completed sojourn quantiles use end-arrival. Unfinished jobs have separate censored sojourn lower bounds. These are not uncensored estimates of eventual delay.

Reported Pj comes directly from `calculate_qos_cost.py:4`, `calculate_delay_prob`, using the in-memory final table exactly as the wizard does. ARGOS `validate_reported_qos_evidence` reconstructs support, and existing `assessment` determines evidence-qualified feasibility. The objective uses the unchanged canonical cost source and actual upstream monetary returns. No threshold is changed.

For these one-hour contexts, Pj excludes all submit_time=0 jobs (including Poisson jobs rounded to0). Completed positive-submit jobs are included. Unfinished jobs are included only when submit>0, submit<=3600 and submit+min_time<3600. Their sojourn is censored at3600. Strict exceedance is sojourn>min_time*(1+qos_constraint). With n>=2 samples and m exceedances the upstream linspace-CDF estimator reports max(m-1,0)/(n-1), not m/n. For n=1, numerator=m, denominator=1; no evidence means Pj=0 but insufficient evidence. Both empirical m/n and the exact estimator numerator/denominator are saved, including completed/unfinished splits. The ordinary qos_summary.csv percentile diagnostic is not the Pj authority.

Per-type queues are observed after policy execution at t=0..3600 inclusive. The legacy `waitingSum` aggregate is computed before policy and is separately labeled in the retained normal power trace. Queue sums are sample sums, not a continuous-time integral. Resource logs record active servers, unique running job IDs, actual/estimated power, number of commanded caps and their sum, and cluster active/idle servers. Commanded caps affect subsequent progress; they are not same-tick actual power. Per-node traces and internal scheduler decision histories are deliberately not retained; the requested aggregates are obtained without invasive instrumentation.

## Outputs and interpretation

Outputs include manifest, frozen panels and historical inputs, replay_checks, all_runs, per_job_run_summary, qos_accounting, queue_summary, per-cell compressed jobs/power/queue resources, initial hashes, grid hashes, initial full tables once per arrival context, crossed metric matrices, descriptive_factor_effects, report, source audit, four plots and artifact hashes. Final ZIP packages compact evidence only; it excludes scratch, environment files and lock files, and rejects artifacts over150MiB before packaging.

Four figures compare the two candidates: Bloom Pj, qualified pass/fail, p90, and Bloom unfinished/p90 waiting. The factor table reports row/column means, ranges/variances at fixed other factor, and an equal-weight sum-of-squares decomposition. Interaction is an unreplicated residual, not an error variance. No ANOVA p-values or significance claims are made. This small selected panel is a diagnostic, not a robustness certification.

Each worker creates only its isolated scratch directory. After compact extraction/sealing, that specific directory is removed; historical and dependency paths are never touched. Normal successful output retains only compact tables and a24KiB log tail. Complete-cell seals allow resume without rerunning valid cells. Source/config changes or corrupted seals stop resume. Interrupted unsealed cells require explicit review and are not automatically rerun (avoids unnoticed duplicate simulations). A process lock prevents simultaneous orchestrators for one output directory.

## Commands

From the ARGOS repository root in PowerShell:

```powershell
& '.\runs\pretest_hardening\paper_install_1789323000349575100\venv\Scripts\python.exe' -B scripts/run_w2_seed_factorization.py --max-workers 10
```

`--help` explains options. `--prepare-only` creates six hashed initial tables without simulations. `--smoke-replays 1` or2 runs only the first diagonal per candidate and stops. `--resume runs/diagnostics/w2_seed_factorization_<timestamp>` reuses sealed results. An optional single cell accepts `--case`, `--arrival-seed`, `--runtime-seed`; off-diagonal requests still execute/reuse all six replay controls first. Single diagonal mode is only a smoke check and does not authorize crossed results. Smoke outputs may be resumed for the formal experiment with unchanged tooling; already valid diagonals remain part of the maximum18.

Default outputs: `runs/diagnostics/w2_seed_factorization_<UTC timestamp>/` and the same path plus `.zip`. The user runs the full experiment. No optimizer campaign, baseline or mixed workload is invoked.
