# Phase 1: pinned workload-generator seed audit

Scope: workload generation only. No simulator execution, ARGOS optimization, controller repair, dependency modification, signal randomization or feasibility change. The known v2 grouping/probe-selection issue is outside this task.

## Verified lineage

Before setup, all three repositories were clean. ARGOS HEAD was `6c95e4b77eebbf25f32522c5836d69759f225963`; FlexDC was `525dc684d73ab0c6f6c479f5b54811ddf02f1221`; CONDOR-FLEXDC was `2b653facf31de356d8c682ee76d814bd81b8e95d`. These match the recent W2 experiment gate. The workload, experiment-overlay source, cluster, canonical ISO file and recent execution-input hashes were checked against saved receipts. No material mismatch was found. No old 67 GB campaign scan was performed.

The experiment is `configs/experiment/new_iso/traditional_signal/generated_server_counts/exp_traditional_iso16_servers_1000.ini` inside `.deps/FlexDC`: N=1000, U=.6, duration=3600 seconds, one-second simulation steps, canonical `data/1-17-2025_traditional.csv`, ISO start hour16, two-second signal samples, normalize=true, randomize start=false. The diagnostic preserves these inputs and hashes the signal but does not read it into a simulator or use it in generation.

## Exact pinned source path

All references below are relative to `.deps/FlexDC/src/peacsim/` at the SHA above.

1. `parsing/experiment_config_reader.py:5`, `ExperimentConfigReader.__init__`: reads `[system] random_seed` at line11 and exposes `random_seed` at lines33-34. `workload_trace` defaults to `poisson` at line20.
2. The ARGOS adapter writes an exact plan-row `simulation_seed`. `am_data_extraction_wizard.py:1765`, `grid_search_plan_rows`, applies it to `experiment_config._random_seed` at line1789, then calls `objective_function`.
3. `am_data_extraction_wizard.py:1297`, `create_simulator_object`, calls both `np.random.seed(effective_seed)` and `random.seed(effective_seed)` at lines1304-1305 BEFORE `init_job_table` at line1307. That is the workload-generation entry used in the recent experiments. The standalone `run_simulator.py:67-70` follows the same seed-then-generate ordering. This diagnostic mirrors only these seed calls and imports the real generation function; it never calls `create_simulator_object`.
4. `create_tables.py:153`, `init_job_table`, dispatches to `init_job_table_poisson` at line162. The adaptive median-trial and spike functions exist but are not used by these contexts.
5. `create_tables.py:78`, `generate_arrival_rates`, computes, for each type i, `lambda_i = U*N / J / min_execution_time_i / job_size_i`. `JobProfileReader.__init__` (`parsing/job_profile_reader.py:6`) preserves INI section order, reads minimum times at lines17-20 and job sizes at lines44-47 (default1). Its scale_workload default is1. It also reads an `arrival_rate` field/default, but this Poisson function does NOT consume that field.
6. `init_job_table_poisson` at lines169-174 first assigns `int(N/(2*sum(job_sizes))*(2*J))` prefill jobs using Python `random.randint`. Here that is1000 jobs at time0, with random type membership (expected250 per type).
7. `generate_arrivals` at line92 processes types sequentially, using `arrival_generator` at line140. Each arrival adds `random.expovariate(rate)`; unrounded times strictly less than duration are retained, then globally sorted. The Poisson wrapper rounds them with Python `round` at lines178-181. Prefill consumes the same RNG first; earlier types' draw counts advance the stream used for later types. There is no per-type independent seed.
8. `generate_job_table` at line114 returns a10-by-n float64 array: job_id, job_type_id, arrival_time, start_time, end_time, estimate_finished, update_time, realtime_qos, min_execution_time, qos_constraint. IDs are sequential, starts/ends are -1, estimated progress and realtime QoS are0, update_time initially equals arrival_time. The two type-dependent profile fields are copied per row. `job_size` is NOT an extra row immediately after generation, despite an older output-header mention elsewhere.

## What changes, and what does not

The Python RNG changes prefill type assignments, exponential arrival gaps, per-type counts, sorted interleaving and rounded submit times. Job IDs follow the resulting row order. Fixed per-type minimum execution times and QoS thresholds are not themselves randomized, though their row ordering follows the randomized job types. NumPy creates deterministic arrays in this generation path and does not draw random values here.

The two W2 files have the same job order, job sizes, min/max execution times and power profiles. Only GPT2/Llama/Bloom `qos_constraint` differs (4.5/4/3.5 versus5/5/5). QoS is copied to row9 after arrivals have been generated; it never enters the rate or random draws. Thus same seed yields identical arrival triples and different complete job tables. Pbar, R and scheduling weights do not enter any generator function.

Expected Poisson-only counts for3600 seconds are Resnet21600, GPT2 approximately19285.714286, Llama15000 and Bloom approximately12272.727273. Add250 expected prefill jobs per type for expected total counts. Total count variance is not exactly Poisson because prefill membership is multinomial. The diagnostic reports the pure Poisson comparison separately.

Grid-signal contents and start hour do not enter the generator. `iso_signal.py:7`, `read_iso_signal`, reads/crops the signal for the simulator; its optional random offset at line22 is disabled here. Same seed plus the same ordered physical arrival inputs, pinned source and Python runtime should deterministically regenerate identical arrivals; the diagnostic verifies this rather than assuming it. Complete-table equality additionally requires identical QoS/profile fields. Python/runtime versions matter to exact bitwise regeneration.

## Runtime randomness is a separate stage

`simulator.py:208`, `Simulator.run`, reseeds NumPy and Python at lines216-217 after the workload table exists. The active `aqa_runtimepolicy.py:11` class extends `RuntimePolicyNew`; `runtime_policy_new.py:38`, `execute`, calls `scheduler.assign_idle_servers` at line71. `scheduler.py:7`, `assign_idle_servers`, shuffles the queue/type order using `random.shuffle` at line26 while retaining FIFO within a type. Thus the historical simulation seed changes workload AND scheduling streams; restarting the RNG separates their consumption but does not make the seed labels independent. Arrival-only associations cannot identify the sole cause of Bloom QoS changes. The similarly named legacy `AQA_runtime_policy.py` is not the wizard's active AQA class.

## Recovered history and deterministic panel

`configs/diagnostics/w2_seed_historical_outcomes.csv` contains exactly ten recovered observations for the two exact candidates, with full precision P/R/weights, seed, p90, every Pj, Bloom Pj, evidence counts, objective, qualified result and source hash/path. All earlier exact-candidate search/repeat artifacts were available. Each candidate has one original search observation, one later fresh search-repeat observation and three fresh confirmations; no additional in-budget racing observation exists for either late Batch4 candidate. Nothing was rerun or inferred for a missing observation.

The full panel is the sorted union:
`144392579,624506888,709520479,1004088181,1768413673,1841060571,2043325904,2381098110,2495920665,3514694477`.
The same panel is used for both workloads. No filler, verification-reserved or newly random seeds are used. This deliberately reuses known historical seeds for generator-only reconstruction; it is not a new simulator campaign.

## Run and outputs

From the ARGOS repository root, use the existing paper runtime:

```powershell
& '.\runs\pretest_hardening\paper_install_1789323000349575100\venv\Scripts\python.exe' -B scripts/analyze_workload_seed_variation.py
```

`--help` describes `--root`, `--spec`, `--output-parent` and `--smoke`. `--smoke` restricts generation to the first two shared seeds plus one identical-input repetition. The default runs20 generator calls plus one reproducibility repetition, never any simulation. It creates a new UTC timestamped directory and ZIP under `runs/diagnostics/`; no existing output is overwritten. Outputs are bounded by the fixed ten-seed panel, and an unexpected package above100MiB is rejected. Compressed trace CSVs retain only IDs, type, rounded submit time, prefill flag, minimum execution time and QoS field; constant runtime defaults are documented rather than duplicated.

Manifest and source/config snapshots preserve reproducibility. CSV summaries include all-arrival and Poisson-only statistics; fixed bins retain a separate rounded-T endpoint bin. Four compact plots cover Bloom timing, job counts, burstiness and historical outcome linkage. A generated plain-English report distinguishes descriptive signals from causal or reliability claims. The ZIP is self-contained for analysis; reproducing it still requires the pinned dependencies/runtime named in the manifest.

Input mismatches fail before generation. If compact retention later removes a raw history source, the already verified compact outcome mapping remains available and the missing original path is recorded; a present-but-changed source fails validation. No missing QoS result is synthesized.
