# Reproducibility

Tested host: Windows 11 (build 26200), Python 3.12.4, PyTorch 2.4.1+cpu.
There is no CUDA device in this environment. Four Torch threads and at most four
simulator subprocesses are used, in sequential V3 and simulator phases.

## Pinned inputs

- FlexDC: `525dc684d73ab0c6f6c479f5b54811ddf02f1221`.
- CONDOR-FLEXDC: `2b653facf31de356d8c682ee76d814bd81b8e95d`.
- Checkpoint: `condor_set_transformer_sweep_v3_behavior_v3_best_feasibility.pt`.
- Checkpoint SHA-256: `7f60e28dfc836053064c772c95acc56eb73999b145fa314e98f7b39cf4d0c38a`.
- Architecture: bundled Set Transformer, 13 token and 12 global features, hidden
  dimension 512, four attention heads; checkpoint normalization is loaded unchanged.
- Checkpoint epoch 146 matches its recorded best-feasibility epoch and the artifact
  comparison table. No other checkpoint was tested for selecting a favorable result.

`artifact_manifest.json` hashes every artifact input. The source content matches
current CONDOR V3 after newline normalization; raw hashes differ because clean Git
checkout uses Windows line endings. The loader uses the immutable bundled source.
`dependency_lock.json` records the post-clone timestamp, main branch and clean state.
The initial clone operations immediately preceded this recorded lock timestamp.

Canonical upstream costs are frozen in `configs/canonical_cost_source.ini` with
URL, retrieval time and exact hash in the adjacent JSON file. Git preserves its
bytes. Only [cost_function] and [dr_program] are authoritative: psi1=1, psi2=10,
tracking threshold=0.3, beta=20, rho=2, QoS threshold=0.1, program RSR.
Ordinary gradient settings are copied locally and only these mapped keys change.

## Python environment

Important versions are in `reports/environment.json`. The transitive installed
package versions used by ARGOS and its test tools are in `requirements-tested.txt`.
The development environment used an ARGOS-local venv with system-site-packages;
no installed user packages were upgraded. A fresh reproduction can use:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.4.1+cpu --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\argos.exe bootstrap
.\.venv\Scripts\argos.exe doctor
```

For another platform, select a compatible PyTorch build explicitly; the generic
package does not force CUDA. Exact CPU output parity on every platform is not
claimed. Do not install or generate metadata inside `.deps`.

## Original prediction and optimizer parity

The original saved test-prediction file supplies IDs but not complete input rows.
The pinned deterministic V3 plan generator reconstructs known N=1000/U=0.6 inputs:

```powershell
.\.venv\Scripts\python.exe -B .deps/FlexDC/am_generate_flexdc_sweep_plan_v3.py --repo-root .deps/FlexDC --workload-configs configs/workload/W1-train-qos3333.ini --experiment-configs configs/experiment/new_iso/traditional_signal/generated_server_counts/exp_traditional_iso16_servers_1000.ini --utilizations 0.6 --output-plan ../../runs/audit/known_plan.csv --output-dir ../../runs/audit/plan_artifacts
.\.venv\Scripts\python.exe -B scripts/validate_v3.py
```

32 deterministically spread matched test rows are compared on mean tracking, p90,
max Pj, monetary cost and full objective, with rtol=5e-4 and atol=1e-4 to cover
saved decimal precision and float32 batch/platform effects. The original optimizer
and hooked optimizer have bitwise-identical endpoint DataFrames for 8 starts and
20 iterations with seed 37. Physical-input autograd agrees with central finite
differences in P, R and a simplex tangent. Exact numerical errors and settings
are in `reports/v3_parity.json`. Lightweight real-checkpoint parity also runs in pytest.

The plan is regenerated for one original context; its file hash differs from the
original complete 16-context plan and is not presented as the full original plan.

## Real protocol

Workload order is `Resnet.train.4`, `GPT2.train.4`, `Llama.train.4`, and
`Bloom.train.4`, exactly as listed in the workload configuration. N=1000, utilization=0.6,
policy=AQA, node-count control enabled, one-second simulator steps, one-hour duration,
traditional ISO signal, start hour 16, two-second signal granularity, normalization
on and randomized ISO start off. Source settings and signal bytes are unchanged.
Search simulation seed is 20. Candidate generation seed is 20260912. Confirmation
seeds are 100020 and 100021 and never enter within-episode selection. Both declared
episodes reuse this scenario pair but launch fresh simulator processes; they do not
constitute four distinct confirmation scenarios across experiments.

An initial exact one-candidate smoke test used a saved V3 context candidate. It
produced exactly one validated result and diagnostic row but was measured infeasible
(Pj for one job exceeded 0.1), despite a predicted-feasible label. Its record is in
`reports/flexdc_smoke.json`; this failure was retained.

```powershell
.\.venv\Scripts\argos.exe run --config configs/argos_smoke.yaml
.\.venv\Scripts\argos.exe run --config configs/argos_default.yaml
.\.venv\Scripts\argos.exe resume runs/<episode-id>
```

The small episode used 8 starts x 20 iterations, snapshots every 5, 8 search calls
in 2 batches of 4, plus 2 confirmations. The serious episode uses 512 x 1500,
snapshots every 50, at most 6 regions, 32 search calls in 4 batches of 8, plus
2 confirmations if an observed feasible candidate is selected. These budgets and
configurations were established before their respective executions.

Every episode records exact source-file hashes, runtime versions, configuration
hashes, candidate IDs, source iterations, region IDs, predictions, actual metrics,
residuals, process identities and timing. `search/all_observations.csv` includes all
search and confirmation rows, identified by phase; `final/confirmation.csv` isolates
the confirmation set. `summary.json` and `report.md` state outcomes and limitations.
The full local run directories are excluded from Git. Publishable compact reports
remove local account paths while preserving numerical results and provenance hashes.

Scientific algorithm changes require a newly declared episode. To resume an old
episode, use its original source identities rather than silently migrating state.
Never run two controllers against the same episode directory at the same time.

## Recorded real episodes

| Episode | V3 starts/iterations | Regions | Search batches | Search + confirmation calls | V3 seconds | Controller seconds | Episode seconds* | Result |
|---|---:|---:|---|---:|---:|---:|---:|---|
| argos_20260913T023923_034870Z | 8 / 20 | 4 | 4, 4 | 8 + 2 | 2.892 | 47.247 | 51.106 | 4 observed-feasible candidates; 2/2 confirmation |
| argos_20260913T024050_620101Z | 512 / 1500 | 6 | 8, 8, 8, 8 | 32 + 2 | 416.997 | 118.446 | 559.564 | 16 observed-feasible candidates; 2/2 confirmation |

*Episode elapsed is derived from manifest creation to the final DONE state write.
It includes region/config work but excludes the preflight doctor. The separately
reported V3 + controller sum omits that overhead and is not the whole episode time.
Four simulator workers were configured in both runs; confirmation executes one
frozen candidate per scenario. The initial exact smoke adds one simulator execution,
so the entire real validation study used 45 simulator executions, with none added
by recovery audits. No failed run was deleted.

Compact, portable reports and every query's numerical results:

- [Small episode](reports/argos_20260913T023923_034870Z/summary.json) and
  [all observations](reports/argos_20260913T023923_034870Z/observations.csv).
- [Serious episode](reports/argos_20260913T024050_620101Z/summary.json) and
  [all observations](reports/argos_20260913T024050_620101Z/observations.csv).

The serious episode's final candidate was an initial V3 representative. The automatic
refinement loop executed but did not improve that incumbent. These results demonstrate
integration and finite confirmation; no baseline advantage is established.

Core source was committed in `dc887cd`. The small run began with those source files
staged before that commit, so its manifest truthfully records the earlier Git HEAD
and dirty state as well as exact source hashes. The serious run records `dc887cd`
and its clean source state. Later documentation, tests and export scripts do not
alter the core scientific algorithm.

To audit cached evidence without executing simulations:

```powershell
.\.venv\Scripts\python.exe -B scripts/audit_episode.py runs/argos_20260913T024050_620101Z
.\.venv\Scripts\python.exe -B scripts/export_results.py runs/argos_20260913T024050_620101Z
```

These audits revalidated all 10 small-episode and 34 serious-episode observations,
including objective reconstruction and input hashes, with unchanged execution counts.
