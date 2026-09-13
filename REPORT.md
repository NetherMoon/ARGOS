# ARGOS implementation and real-results report

A simulator-observed feasible bid was found. The selected candidate in the serious
known-context episode passed 2/2 fresh confirmation executions.

## Repository and dependencies

Local directory: the user-specified ARGOS Hybrid workspace. Remote:
https://github.com/NetherMoon/ARGOS.git, branch main. Initial remote was empty.
The two original reference repositories and both clean dependency clones were
left unchanged. The immutable checkpoint bundle is excluded from Git. Core changes
were committed as `d2afb64` (bootstrap/V3 parity) and `dc887cd` (complete controller
and exact simulator integration). Documentation/results form the final milestone.

FlexDC is pinned to `525dc684d73ab0c6f6c479f5b54811ddf02f1221` and CONDOR-FLEXDC to
`2b653facf31de356d8c682ee76d814bd81b8e95d`. Python 3.12.4 and CPU PyTorch 2.4.1 were
used. Exact package versions are in `requirements-tested.txt` and environment.json.

## Artifact and parity

Checkpoint: `condor_set_transformer_sweep_v3_behavior_v3_best_feasibility.pt`.
SHA-256: `7f60e28dfc836053064c772c95acc56eb73999b145fa314e98f7b39cf4d0c38a`.
Epoch 146 is the recorded best-feasibility checkpoint. The exact artifact architecture
and feature/normalization utilities are bound to pinned generic inference code.
The source content matches current CONDOR V3 after newline normalization.

32 original saved predictions matched the declared rtol=5e-4/atol=1e-4 tolerance.
Maximum absolute discrepancies: mean tracking 1.887e-5, p90 5.573e-5, max Pj
4.083e-7, monetary cost 1.022e-4, full objective 5.644e-4. Per-job probability
vectors were not present in the saved prediction table, so that comparison is
limited to saved max-Pj; the loader returns the complete vector for actual searches.

Trajectory-hook and original optimizer endpoints were bitwise identical for
8 starts x 20 iterations, seed 37. The three tested input-gradient directions
matched central differences within the declared tolerance; all details are in
reports/v3_parity.json. No architecture, checkpoint or dependency source was edited.

## Framework implemented

The publishable src layout provides typed candidate/region/observation/state records,
central feasibility and objective contracts, strict YAML validation, CLI bootstrap,
doctor, artifact inspection, run and resume, frozen V3 adaptation, per-start snapshots,
normalized legal geometry, bounded-simplex sampling/projection, diverse region selection,
parallel exact FlexDC execution, automatic measured-result refinement, finite stopping,
frozen independent confirmation, durable recovery and machine-readable reporting.

No GP, residual correction, transferable model or reliability model was implemented.
Future extension and baseline interfaces are described in DESIGN.md.

## Every real experiment

All runs used `W1-train-qos3333`, N=1000, utilization=0.6, AQA with node-count control,
a 3600-second simulation and the unchanged traditional ISO16 signal context.
Job order: Resnet.train.4, GPT2.train.4, Llama.train.4, Bloom.train.4.
Search seed: 20. Candidate RNG seed: 20260912.

The initial exact smoke used one V3-known candidate: Pbar=0.52944, R=0.317664,
weights=[0.2833333333,0.15,0.2833333333,0.2833333333]. One result and one diagnostic
row validated. Actual p90=0.258, Pj=[0.12548015364916776,0,0,0], objective=
73.20028890479986. Runtime=10.760 seconds. This point was observed infeasible despite
V3 predicting feasibility. No confirmation was attempted for this point.

| ARGOS episode | Starts / iterations | Snapshot interval | Regions | Search batches | Workers | V3 s | Controller s | Episode s* | Feasible search observations |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| Small: 20260913T023923_034870Z | 8 / 20 | 5 | 4 | 4,4 | 4 | 2.892 | 47.247 | 51.106 | 4/8 |
| Serious: 20260913T024050_620101Z | 512 / 1500 | 50 | 6 | 8,8,8,8 | 4 | 416.997 | 118.446 | 559.564 | 16/32 |

*Manifest creation through the final DONE checkpoint; excludes preflight doctor.
The small episode captured 40 snapshots. The serious episode captured 15,872
snapshots and retained 604 distinct promising candidates. Each episode added two
confirmation executions. Total real executions across smoke and both episodes: 45.

| Selected candidate | Pbar (kW/server) | R (kW/server) | Weights in configured job order | Actual p90 | Every actual Pj | Actual objective |
|---|---:|---:|---|---:|---|---:|
| Small, v3-0020-0005 | 0.5552651882171631 | 0.24327042698860168 | [0.2869108021,0.2831034362,0.2549262941,0.1750594676] | 0.158 | [0,0,0,0] | 79.9174643198774 |
| Serious, v3-1500-0265 | 0.3663828670978546 | 0.21973192691802979 | [0.4497109950,0.1602009833,0.1632332951,0.2268547267] | 0.006 | [0,0,0,0] | 62.603871176479714 |

| Episode | Confirmation seed | Actual p90 | Every actual Pj | Actual objective | Outcome |
|---|---:|---:|---|---:|---|
| Small | 100020 | 0.168 | [0.00908455625436766,0,0,0] | 80.16839426362822 | Pass |
| Small | 100021 | 0.152 | [0.00566973777462787,0,0,0] | 80.00171717902296 | Pass |
| Serious | 100020 | 0.006 | [0,0,0,0] | 62.60601356347972 | Pass |
| Serious | 100021 | 0.006 | [0,0,0,0] | 62.60316925481305 | Pass |

Both confirmation sets are disjoint from their episode's search seed and were freshly
executed after freezing the candidate. The two experiments reused the same confirmation
scenario pair; these are not four unique scenarios. Zero reported Pj values are
simulator estimates, not proof of zero true risk. The serious finalist came from
an initial region representative, so this experiment does not establish an adaptive
improvement over a V3-only baseline.

## Validation and recovery

Final pytest result: `25 passed in 12.01s`. Ruff: `All checks passed!`; formatting:
`35 files already formatted`. Tests cover scientific/domain/config contracts, synthetic cases
A-D, invalid evidence, deterministic recovery, real-output corruption rejection and
actual checkpoint integration. Ruff lint and formatting passed. The real exact smoke
and both end-to-end episodes passed evidence validation. Synthetic Case D truthfully
reported 0/2 confirmation passes with the frozen candidate.

A completed small-run resume added zero simulator executions. Independent cache audits
revalidated 10/10 and 34/34 observations and their config hashes without new evidence.

## Failures and limitations

- The predicted-feasible initial smoke point failed the actual per-job constraint;
  its full evidence was retained.
- Initial sandbox network/Python restrictions were resolved with approved access.
- Automatic approval review blocked a push containing absolute local paths in a
  generated report. The report was sanitized, checked, and subsequently pushed.
- No invalid simulator outputs occurred in either complete ARGOS episode.
- This is a known-context integration result; there is no OOD or baseline superiority
  claim, and two passing confirmation scenarios do not establish broad reliability.
- CPU was tested; GPU execution, alternative durations/policies and public release
  licensing require separate work. Core supports serial resume of one controller per
  episode; concurrent controllers for the same episode are unsupported.
- Stored byte-level identities intentionally reject changed inputs on resume. A
  moved or rewritten historical run may require its original environment and paths.

## Reproduction

From the ARGOS repository after installing the artifact and pinned dependencies:

```powershell
.\.venv\Scripts\argos.exe doctor
.\.venv\Scripts\python.exe -B scripts/validate_v3.py
.\.venv\Scripts\argos.exe run --config configs/argos_default.yaml
```

The parity command requires regenerating the known plan first; the exact command,
installation procedure and all declared inputs are in REPRODUCIBILITY.md.
See reports/argos_20260913T024050_620101Z/summary.json and observations.csv for full
machine-readable evidence. All original raw simulator files remain under runs/.
