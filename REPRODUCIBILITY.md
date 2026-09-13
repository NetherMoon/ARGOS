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

Portable correctness CI covers Python 3.10, 3.11 and 3.12 with current compatible
packages (`pip install -e ".[dev]"`). The package declares >=3.10,<3.13; later
interpreters need validation before expanding that range. Public CI downloads no
V3 artifact and executes no simulator. Artifact/dependency tests skip explicitly.

Historical verified simulations used Windows x86-64, Python **3.12.4**, runtime
PyTorch **2.4.1+cpu** with four threads. Their development venv exposed system site
packages. The installed distribution metadata reported torch 2.4.1; the runtime
reported 2.4.1+cpu. `constraints-paper-cpu.txt` pins the official CPU wheel explicitly
and the 38-package runtime/test/build dependency closure at the tested versions.
It does not reproduce unrelated packages in the historical shared environment.
`requirements-tested.txt` remains the original inventory, not the reproduction lock.

For exact paper CPU reproduction, create a new environment using Python 3.12.4
(check `py -3.12 --version` first) and run:

```powershell
py -3.12 -m venv .venv-paper
.\.venv-paper\Scripts\python.exe -m pip install -c constraints-paper-cpu.txt setuptools wheel
.\.venv-paper\Scripts\python.exe -m pip install --no-build-isolation -c constraints-paper-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu -e ".[dev]"
.\.venv-paper\Scripts\python.exe -m pip check
.\.venv-paper\Scripts\python.exe -B -m pytest -q
.\.venv-paper\Scripts\python.exe -B -m ruff check .
.\.venv-paper\Scripts\python.exe -B -m ruff format --check .
.\.venv-paper\Scripts\argos.exe --help
```

The first install pins setuptools and wheel; `--no-build-isolation` uses those
versions for the editable build. The second install obeys all runtime/test pins
and obtains the exact CPU wheel from PyTorch's official index. `--no-compile` may
be added to either install to skip bytecode precompilation without changing packages.
A separate Windows CI lane uses Python 3.12.4 and these exact commands. No CUDA
paper environment is claimed. Exact cross-platform floating-point parity is not
claimed. Ordinary runtime-only doctor records absent pytest/Ruff as NOT_INSTALLED;
CI/release gates explicitly install development tools.

After providing the immutable artifact and pinned dependencies, run bootstrap and
paper-mode doctor from a clean tree. Never install or generate files inside `.deps`.

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
and its clean source state. That describes the historical release. The publication-hardening revision changes
evidence eligibility and optional search policies; it must not resume those old runs.

To audit cached evidence without executing simulations:

```powershell
.\.venv\Scripts\python.exe -B scripts/audit_episode.py runs/argos_20260913T024050_620101Z
.\.venv\Scripts\python.exe -B scripts/export_results.py runs/argos_20260913T024050_620101Z
```

These audits revalidated all 10 small-episode and 34 serious-episode observations,
including objective reconstruction and input hashes, with unchanged execution counts.


## Publication-hardening release gate

Use a fresh checkout without .deps, model files, runs, cached pytest directories,
or a reused virtual environment. Create a new environment and install `.[dev]`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\argos.exe --help
```

Pytest uses .pytest_tmp directly; no manual runs directory is needed. Artifact tests
skip with an explicit reason. GitHub Actions runs the same artifact-free gate.
A passing portable gate does not substitute for local artifact parity or real evidence.
Current paper configs explicitly declare clean-tree mode, search mode, and evidence
threshold. Doctor writes ignored runs/doctor_environment.json, preserving clean state.

The new `argos audit` command checks objective reconstruction, raw counts, ordered
identities, input/output hashes where available, budgets and confirmation isolation.
Use --allow-legacy-audit for old search artifacts lacking a trusted V3 manifest;
audit success does not retroactively grant resume integrity. Post-audit files are
separate and original historical state/summary/raw files remain unchanged.

The validation scope for this remediation is CPU parity, portable and full tests,
historical raw-data audits, and one exact audit-only simulator invocation using a
new seed. No W2, mixed-workload, or real variable-J campaign is authorized by this
release gate. Historical fixed-budget results are not presented as early-stop runs.


The automated local gate is `python -B scripts/release_gate.py`. It clones the
current committed HEAD into a new ignored location and creates a distinct venv
without system site packages. It installs `.[dev]` with `--no-compile` (only bytecode
precompilation is skipped), then runs tests, Ruff, formatting and the installed
`argos --help`. It asserts that runs was absent initially and remains absent.
Do not treat an interrupted install or a reused environment as a release pass.

For the one-call audit smoke, from a clean tree with the immutable dependencies:

```powershell
.\.venv\Scripts\python.exe -B scripts/evidence_smoke.py --seed 2026091301
```

That seed has already been executed for this report; the script deliberately refuses
to overwrite its existing run directory. Inspect its saved evidence rather than
rerunning it. It is audit-only, not a search or confirmation result. A future
explicitly authorized audit must use a new seed and preserve its own provenance.
See REPORT.md and reports/publication_audit/release_validation.json for validation
results, the interrupted-install history, and the real recovery defect correction.


## Canonical upstream revision and final pre-testing gates

The stored cost source exactly matches peaclab/flexdc-sim commit
`20986e7ddd0c5c4e33ee0b162c722ca2b46a79f9` at
`configs/optimization/simulated_annealing/SA_train_low_util_RSR_1000server.ini`.
[Commit-qualified source](https://github.com/peaclab/flexdc-sim/blob/20986e7ddd0c5c4e33ee0b162c722ca2b46a79f9/configs/optimization/simulated_annealing/SA_train_low_util_RSR_1000server.ini).
SHA-256: `f20f3f78f53cca79d29c8b077747df86d9a23dc5bf19a5870142154c9b0567c4`.
The upstream file history was queried and bytes verified before recording the
revision on 2026-09-13. Metadata records the upstream repository, commit, path,
verified file hash and verification timestamp. Offline tests verify the recorded
metadata/hash agreement. Only cost_function and dr_program are used; initialization,
simulated_annealing, boundaries and step_size remain ignored. ARGOS does not use SA.

From Python 3.12.4, run both isolated final-commit gates:

```powershell
python -B scripts/release_gate.py --environment portable
python -B scripts/release_gate.py --environment paper-cpu
```

Each creates its own clean checkout and brand-new venv without system packages,
dependencies, artifact, prior runs or pytest caches. Package download caches may be
used; installed environments are never reused. Both perform install, pip check,
pytest, Ruff, formatting and installed CLI checks. The paper gate also checks the
CPU Torch build. Results and exact source HEAD are stored under runs/release_gate.

Read-only final historical audits (choose new output filenames):

```powershell
argos audit runs/argos_20260913T024050_620101Z --allow-historical-audit --output runs/pretest_serious_audit.json
argos audit runs/argos_20260913T023923_034870Z --allow-historical-audit --output runs/pretest_small_audit.json
argos audit runs/evidence_smoke_seed_2026091301 --allow-historical-audit --output runs/pretest_smoke_audit.json
argos doctor --config configs/argos_paper.yaml
```

The authoritative Pj is always FlexDC's reported column. Raw-table calculation
validates estimator parity and records counts, not replacement probabilities.
Historical raw validity is separate from current software/model identity. Changed
ARGOS source and missing historical metadata are explicit; no manifest is rewritten
or retrospectively certified for resume. The older smoke has no resolved-config
hash anchor; its audit labels that limitation HISTORICAL_UNANCHORED while checking
recorded execution/input hashes. New smoke manifests include the config hash.

This hardening pass adds no new simulator result or campaign. Existing W1 Pj/counts
and selected bids remain the same; n>=1 still means only nonempty evidence and
statistical_reliability_established remains false. GPT2/Llama/Bloom thresholds
exceed the one-hour horizon. The historical V4 weight-policy attribution remains
unestablished. Controlled experiments will be specified separately.
