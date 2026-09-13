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

Python 3.10+ is the package target; Windows/Python 3.12.4 is tested. From this
repository in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\argos.exe bootstrap
```

For the exact tested package versions, use `requirements-tested.txt`. PyTorch's
CPU/GPU wheel choice is platform-dependent; see [REPRODUCIBILITY.md](REPRODUCIBILITY.md).
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

Numerical feasibility requires **p90 tracking <= 0.30 AND every job Pj <= 0.10**.
An execution failure, missing row, mismatched input, incomplete job vector or
non-finite metric is invalid evidence, not a numerical infeasibility label.
The monetary cost plus canonical stable softplus tracking and per-job QoS
penalties defines the reconstructed actual objective.

All observations are retained, including failures. Search ranks measured feasible
candidates by actual objective; otherwise it ranks worst normalized violation,
then total violation, then objective. Every batch reserves independent exploration.
The selected candidate is frozen before fresh, disjoint-within-episode confirmation
seeds run. A `CONFIRMATION_2_OF_2_PASS` status means precisely that finite count.
It does not establish universal reliability. Confirmation data never select an
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
[the upstream configuration](https://github.com/peaclab/flexdc-sim/blob/main/configs/optimization/simulated_annealing/SA_train_low_util_RSR_1000server.ini).
SA optimizer settings are never ARGOS optimizer settings.
