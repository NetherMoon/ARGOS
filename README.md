# ARGOS

**Adaptive Region-Guided Optimization Search** combines a frozen CONDOR/FlexDC
Behavior Model V3 with bounded batches of real FlexDC simulations. V3 proposes
candidate regions. ARGOS preserves diversity, probes those regions, and refines
using measured constraints and cost. FlexDC is the truth oracle for this protocol.

```text
Frozen V3 -> batched gradient search -> per-start snapshots -> diverse regions
                                                               |
Independent legal samples -------------------------------------+
                                                               v
                  exact parallel FlexDC calls -> measured ranking -> local probes
                                                       |
                                                       v
                              freeze incumbent -> fresh confirmation scenarios
```

ARGOS does not train V3 or implement a GP, residual model, reliability model, or
transferable correction model. A failed finite search is a valid result.

## Install

ARGOS 0.2.0 supports Python 3.10, 3.11 and 3.12, covered by portable CI.
The exact paper CPU environment uses Windows x86-64 and Python 3.12.4.
For a portable installation with current compatible packages, from PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\argos.exe bootstrap
```

For paper CPU reproduction, use a fresh Python 3.12.4 environment and:

```powershell
python -m pip install -c constraints-paper-cpu.txt setuptools wheel
python -m pip install --no-build-isolation -c constraints-paper-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu -e ".[dev]"
python -m pip check
```

Use that environment's `python`. The CPU constraint selects `torch==2.4.1+cpu`.
The general package retains open dependency specifications; the paper constraints
pin the tested dependency closure. `requirements-tested.txt` remains a historical
inventory. See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for exact commands and limits.
Runtime-only `pip install .` does not require pytest or Ruff. Doctor reports those
optional tools as `NOT_INSTALLED`; missing runtime dependencies still fail.
Scikit-learn is needed by the immutable training utility imports; ARGOS does not
use it for region grouping. No simulator package is installed into the clones.

`bootstrap` uses `.deps/FlexDC` and `.deps/CONDOR-FLEXDC`, with the exact commits
in `dependency_lock.json`. It refuses dirty or mismatched dependencies. An explicit
`bootstrap --refresh-lock` refreshes clean clones and rewrites the lock; do not do
this while reproducing a published episode.

Place the unchanged V3 bundle in
`condor_set_transformer_sweep_v3_behavior_v3_best_feasibility_artifacts/`.
The required checkpoint is
`condor_set_transformer_sweep_v3_behavior_v3_best_feasibility.pt`.
Its SHA-256 and the companion-file inventory are in `artifact_manifest.json`.
Neither artifact download nor credentials are supplied by this repository.

```powershell
.\.venv\Scripts\argos.exe inspect-artifact
.\.venv\Scripts\argos.exe doctor
.\.venv\Scripts\argos.exe run --config configs/argos_smoke.yaml
.\.venv\Scripts\argos.exe run --config configs/argos_default.yaml
.\.venv\Scripts\argos.exe resume runs/<episode-id>
```

The smoke configuration is a small complete episode: 8 V3 starts, 20 iterations,
8 search calls, and two confirmation calls if an observed feasible bid is selected.
The default is a declared larger experiment: 512 starts, 1500 iterations, snapshots
every 50 iterations, at most 6 regions and 32 search calls in batches of 8.
Both use at most four simulator workers. The actual simulator duration stays 3600 s.
The first context is W1-train-qos3333, N=1000, utilization=0.6, AQA, traditional
ISO signal starting at hour 16. This is a known-domain integration experiment,
not a generalization result. Review the resolved configuration before changing a study.

## Evidence and outputs

**FlexDC-reported Pj is authoritative.** `Metrics.pj` comes directly from
`grid_search_results.csv:QoS_Delay_Probabilities`. ARGOS validates FlexDC's reported
Pj against `job_table.csv` and records its observation support. Reproducing the
pinned estimator is a parity check only (rtol=1e-10, atol=1e-12). A mismatch invalidates
the observation; ARGOS never substitutes a reconstructed Pj. The reported values
feed numerical feasibility, margins, ranking, residuals and objective reconstruction.

Numerical feasibility requires **p90 tracking <= 0.30 AND every job Pj <= 0.10**.
An execution failure, missing row, mismatched input, incomplete job vector or
non-finite metric is invalid evidence, not a numerical infeasibility label.
The monetary cost plus canonical stable softplus tracking and per-job QoS
penalties defines the reconstructed actual objective.

Execution status is separate from scientific assessment. Parsed outputs retain
`PARSED`, including simultaneous numerical infeasibility and insufficient evidence.
Structured assessment fields are authoritative; historical status labels are
normalized for display without rewriting saved observations.

All observations are retained, including failures. Search ranks evidence-qualified feasible
candidates by actual objective; otherwise it ranks worst normalized violation,
then total violation, then objective. Every batch reserves independent exploration.
The selected candidate is frozen before fresh, disjoint-within-episode confirmation
seeds run. Confirmation status counts executions that actually occurred:

- `CONFIRMATION_NOT_RUN`: zero executions.
- `CONFIRMATION_NONE_PASS`: executions occurred, zero qualified passes.
- `CONFIRMATION_PARTIAL_PASS`: some executions qualified.
- `CONFIRMATION_ALL_PASS`: every executed confirmation qualified.

Expected runs and completion are separate fields, so ALL_PASS on a partially
completed confirmation plan does not imply the plan finished. These statuses do
not establish universal reliability. Confirmation data never select an
alternative candidate within that episode.

```text
runs/<episode>/
  manifest.json, resolved_config.yaml, dependency_manifest.json, artifact_manifest.json
  generated_configs/               # source-preserving INIs and old/new/hash audits
  v3/                              # starts, snapshots, endpoints, pool, regions, timing
  search/                          # completed batches and all_observations.csv
  flexdc_raw/<execution>/attempt-*/ # exact plan, logs, exit/evidence record, raw CSVs
  final/                           # frozen candidate and confirmation.csv
  state.json, summary.json, report.md
```

Cached completions support recovery and do not count as new confirmation evidence.
Resume rejects changed source, dependency, checkpoint, context or resolved config
identities. Interrupted simulator attempts remain on disk and retries consume the
call budget. Never resume the same episode concurrently from two processes.
Raw traces can be large; all run folders are ignored by Git.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Real V3 tests require the local artifact and pinned clones; synthetic tests are
fast and do not execute FlexDC. See [reports/v3_parity.json](reports/v3_parity.json),
[reports/flexdc_smoke.json](reports/flexdc_smoke.json), and the real episode reports
listed in [REPRODUCIBILITY.md](REPRODUCIBILITY.md).

Dependencies: [FlexDC](https://github.com/amenon871/FlexDC),
[CONDOR-FLEXDC](https://github.com/NetherMoon/CONDOR-FLEXDC), and the original
[FlexDC simulator](https://github.com/peaclab/flexdc-sim).
Canonical costs come only from the `cost_function` and `dr_program` sections of
[the upstream configuration](https://github.com/peaclab/flexdc-sim/blob/20986e7ddd0c5c4e33ee0b162c722ca2b46a79f9/configs/optimization/simulated_annealing/SA_train_low_util_RSR_1000server.ini).
SA optimizer settings are never ARGOS optimizer settings.


## Publication correctness contract

Simulator selection requires valid execution, numerical feasibility, and at least
`min_qos_observations_per_type` observations for **every** ordered job type (default
1). Missing counts are UNKNOWN; zero counts are INSUFFICIENT, even when upstream
reports Pj=0. Evidence insufficiency is a completed execution, not a fatal simulator
failure. The objective is unchanged. The threshold only establishes nonempty
estimators; censored one-hour observations are not statistical reliability evidence.
See DESIGN.md for the exact nonstandard ranked-CDF numerator/denominator.

`search_mode: fixed_budget` preserves the historical method. `early_stop` waits for
a qualified bid, a subsequent local refinement batch, and one no-improvement batch
(default epsilon 1e-6, minimum two batches); hard budgets always bound execution.
The optional `local_proposal_mode: v3_screened` scores a larger legal local pool and
retains trade-offs. `measured_random` remains the default; no superiority is claimed.
`local_radius_mode: fixed` uses the typed radius-policy interface.

`weight_policy: fixed` retains [.15,.45]. `relative_to_equal` explicitly requests
[.6/J,1.8/J], intersected with pinned upstream server/job bounds. There is no
automatic J switch. J=3/4/5/6/8 have domain tests, not new simulator campaigns.

`device: cpu|cuda|auto` records the requested and actual device. Explicit unavailable
CUDA fails. CPU remains the parity authority; GPU results need tolerance-based
validation. `run_mode: paper` requires clean ARGOS and pinned dependency trees;
`development` records dirty status. `configs/argos_paper.yaml` is the paper example.

The tracked V3 context contract locks unconditioned signal/system/hardware behavior.
N, utilization, and workload descriptors are feature-conditioned, which alone does
not establish generalization. `allow_context_ood: true` explicitly tags mismatches.
The simulator's one-hour objective restriction still applies.

Generated V3 search files have a hashed, versioned `v3/search_manifest.json`, anchored
in the episode manifest. Resume verifies it before using candidates and revalidates
completed simulator evidence. Legacy runs without it are audit-only:

```powershell
argos audit runs/argos_20260913T024050_620101Z --allow-legacy-audit --output runs/new_w1_audit.json
```

Audit output must be a new file outside the original episode. Historical reports are
preserved; the explicit post-audit qualification is in REPORT.md and
`reports/publication_audit/`. A clean checkout can install `.[dev]`, run pytest,
Ruff, formatting, and `argos --help` without a `runs/` directory or model artifact.


## Pre-testing audit and execution hardening

`argos audit` reports `raw_data_validity` independently from
`current_environment_identity`. Seven dimensions identify ARGOS source, both pinned
dependencies, checkpoint, artifact manifest/files, canonical cost source and context
contract. Each reports MATCH, MISMATCH, UNAVAILABLE or HISTORICAL. Normal audit
fails an environment mismatch or missing identity. Explicit
`--allow-historical-audit` (alias `--allow-legacy-audit`) permits internally valid
historical raw data to pass while retaining every environment discrepancy. It
never grants resume trust or rewrites old manifests. `reported_pj_validation`
reports the raw parity check; it is not a second Pj metric.

Process inspection handles vanished/zombie PIDs and creation-time reuse. A live
matching process blocks duplicate resume; an indeterminate identity also blocks it.
Fast simulator exits produce durable failed attempts. Configuration overlays use
one cached pinned FlexDC replacement helper loaded before worker dispatch; no
candidate reimports it. Dependencies remain immutable.

The final pre-testing pass adds no experiment-label controller or learned model.
The search, retention, variable-J policies, fixed radius and default local proposal
method remain unchanged. The one-hour horizon and n>=1 evidence limitations remain.
