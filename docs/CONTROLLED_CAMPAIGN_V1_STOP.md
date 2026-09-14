# Controlled campaign v1: stopped for V3 weight-contract failure

Status: **STOPPED_CORE_CONTRACT_FAILURE**. Recovery and diagnosis completed 2026-09-14 UTC.
This is a partial development report, not a completed comparison or benchmark.
Do not resume this campaign with repaired weights, skipped snapshots, relaxed validation, changed seeds, or modified source.

## Failure and exact reproduction

The first serious context, c001 (W1-train-qos3333, N=1000, U=0.6), failed before any serious FlexDC evaluation.
The original 512-start, 1500-iteration V3 calculation completed, then region construction raised
`ValueError: Illegal weights` through `promising -> tradeoff_select -> Domain.distance -> Domain.validate`.

A diagnostic rerun retained the original optimizer bytecode, settings and initialization seed 300001.
It added observation hooks only and stopped at the first illegal captured snapshot:
iteration 150, start 454, candidate v3-0150-0454.

- Pbar: 0.18888403475284576; R: 0.11027190834283829.
- Logits: [-4.956484794616699, 3.278822898864746, -5.34633207321167, 2.506721258163452].
- Weights: [0.15000000596046448, 0.15000000596046448, 0.15000000596046448, 0.15000000596046448].
- Sum: **0.6000000238418579**; absolute error: **0.3999999761581421**.
- Required sum: 1, tolerance 1e-6; each weight bound: [0.15, 0.45].
- Earlier captured snapshots 0, 50 and 100 passed. This identifies the first bad *captured* snapshot, not necessarily the first bad optimizer iteration.
- Diagnostic runtime: 38.323018 seconds; simulator calls: zero.

The defect originates in the pinned CONDOR-FLEXDC inference utility,
`parameterize_weights`, lines 893-926. Its bounded-simplex branch runs 32 unbracketed Newton
updates and returns without verifying convergence. Saturation can leave every weight at a bound.
Standalone logits [10,10,-10,-10] and [20,20,-20,-20] both return four
0.44999998807907104 weights, sum 1.7999999523162842.
ARGOS's validator correctly rejects the violated upstream contract.
This is a substantive normalization failure, not float32 roundoff or a scientific NO_BID.

Run `scripts/diagnostics/reproduce_v3_weight_contract.py` using the pinned paper environment.
It calls the existing upstream function, changes no source, and deliberately exits 1 when
the contract fails. The full optimization diagnostic and evidence remain under
`runs/campaign_preparation/weight_failure_diagnostic/`; console logs and
`diagnose_weight_failure.py` are in its parent directory.

There is also a campaign persistence limitation: candidate-bank CSVs are written only after
region extraction. Consequently, the failed completed optimization's full arrays were not
saved. The diagnostic preserves the exact offending snapshot; it does not pretend to recover
the entire original bank. A future version should durably save raw optimizer outputs before
region validation, preserving failure status separately.

## A. Git and protocol

- Frozen core: 425eec6b7fec1202bdc97b88f7b50c23ca575aa0; annotated tag v0.2.0-pretest.
- Executed campaign code: 33af50461c0cb09c5d956f6d6b5630a45dba9548.
- FlexDC: 525dc684d73ab0c6f6c479f5b54811ddf02f1221.
- CONDOR-FLEXDC: 2b653facf31de356d8c682ee76d814bd81b8e95d.
- Checkpoint SHA256: 7f60e28dfc836053064c772c95acc56eb73999b145fa314e98f7b39cf4d0c38a.
- Protocol SHA256: 8bce898485c5616b96667d000c4845f9b7742e905bb77220a21e396e9e2c5d2f.
- Ledger SHA256: 6c6af5412070623c5b8fcf6eb4223a4169b86bdd702e32731ebf803d5a33f4b6.
- Runtime: paper_install_1789323000349575100/venv, Python 3.12.4, Torch 2.4.1+cpu, four threads.
- This report and standalone diagnostic are subsequent documentation/diagnostic additions; they do not change the executed source identity or sealed results.

After the crash, the full gate passed again: **147 tests passed, one CUDA skip**;
Ruff, formatting, doctor and provenance checks passed. Passing the existing short optimizer
regression did not establish numerical correctness of long optimization.

## B. Seed ledger

Training data exposed scenario seeds 20, 21 and 22. The excluded historical/training set is
20, 21, 22, 100020, 100021 and 2026091301.
Disjoint pools contain three engineering seeds, 96 development search seeds,
192 development confirmation seeds, 100 reserved final search seeds and 200 reserved final
confirmation seeds. Reserved values have not been displayed or used for execution/selection.
Each context has two fresh confirmation seeds separate from its search scenario.
The interrupted context was resumed with its original initialization and scenario allocation.

## C. Candidate banks

One complete engineering bank exists:
e65a4f84740070c52861f8d9a793f377c42686dea4cb3e218a08507de3a431af.
It contains 12 snapshots and four regions; generation took 22.437027 seconds.
Four V3-based smoke methods share this bank; simulator-only does not use its guidance.

Serious bank 971d36cd7ca2ac04e52f391cd15e0f4bc6b6d28d881641065dc38c0f99153a1b
has no complete manifest. Its initial interrupted attempt and failed resumed attempt are retained.
The failed resumed session took 356.737208 seconds overall; its optimizer-only duration was
not persisted. The first interrupted attempt's elapsed duration is unavailable.

The exact CPU scenario-invariance regression passed for raw/differentiable features,
predictions, endpoints, snapshots and trajectory with a common initialization.
That proof does not imply the bounded-weight function is correct for all logits.

## D-I. Planned scientific suites

| Suite | Contexts | Method cases | Actual status |
| --- | ---: | ---: | --- |
| D: Phase 1 original controls | 8 | 40 | c001 shared bank failed; zero method results |
| E: Phase 2 clean composition screening | 14 | 70 | Not run |
| E: Phase 2 predeclared serious compositions | 6 | 30 | Not run |
| F: Phase 3 historical V4 | 8 | 40 | Not run |
| G: Phase 4 structural J3/J5/J6/J8 | 6 | 30 | Not run |
| I: Phase 5 operating conditions | 4 | 12 | Not run |

All 222 scientific method cases remain incomplete. The completed five method cases belong
only to engineering smoke. In generated method tables, c001 rows are NOT_ATTEMPTED because
the shared bank failed before method execution; the context-level failure is recorded separately.
Unattempted rows are not NO_BID or evidence of infeasibility.

V4 uses the pinned eight INIs and composition/QoS manifest, explicitly authorized by the user
because the original named generator was unavailable. It remains composition-plus-QoS stress,
not a clean composition experiment. All 32 generated workloads passed parser/lineage checks.
Operating cases predeclare N=500/U=0.7 as interpolation-like and N=1500/U=0.9 as
extrapolation-like in operating features only. No outcomes exist.
H: optional repeated-profile tests were not declared or executed.

## J-K. Prediction errors and winner sources

No serious-phase prediction-error or winner-source conclusions are available.
Engineering output tables retain their original predictions and evidence.
Smoke winners: V3-only selected a V3 endpoint; probing and both ARGOS methods selected an
initial V3 region representative; simulator-only selected a local refinement.
These short smoke runs cannot establish the benefit of V3 regions or adaptive refinement.

## L-M. Engineering efficiency and confirmation only

| Method | Search queries | Objective | Fresh confirmation passes |
| --- | ---: | ---: | ---: |
| V3-only | 1 | 85.18098085467791 | 2/2 |
| V3 fixed probing | 4 | 85.18098085467791 | 2/2 |
| Simulator-only adaptive | 4 | 78.38824522620101 | 2/2 |
| ARGOS fixed budget | 4 | 85.18098085467791 | 2/2 |
| ARGOS early stop | 4 | 85.18098085467791 | 2/2 |

There were 27 logical evaluations including confirmations and 12 distinct physical executions.
Exact caching avoided 15 duplicate physical calls; shared confirmations are not additional
independent evidence. Early-stop replay saved zero search calls in this smoke.
Original wall-time and evidence tables remain in
`runs/campaigns/controlled_development_v1/REPORT.md` and its CSVs.
The resumed audit revalidated all five completed method records and all 12 physical records.

All five smoke methods had qualified bids, but the one-hour horizon and unfinished jobs
limit interpretation. For example, a retained W1 smoke observation had completion counts
1465/304/276/350 and unfinished counts 238/190/218/182 across the four ordered jobs;
the latter three jobs had horizon flags. Zero reported QoS violation probability is not
proof of eventual completion or statistical reliability.
There are zero serious-phase confirmation executions.

## N. SA

Not executed: the unchanged pinned implementation changes scenario seed by iteration and
uses a different tracking objective. The compatibility decision and source evidence are in
configs/campaigns/sa_compatibility_v1.json. No matched SA result is claimed.

## O. All failures and affected experiments

1. User restart/crash interruption during the initial c001 bank calculation: no serious simulator
   results existed. The interrupted attempt is retained; original elapsed time was not saved.
2. Resumed c001 bank failed with Illegal weights. The deterministic diagnostic reproduced the
   upstream contract violation without changing sources or running FlexDC.
3. Full failed-bank optimizer arrays were not persisted because of the save ordering described above.

No scientific NO_BID or invalid physical simulator execution was observed; the campaign
stopped before serious method execution. The completed engineering results remain evidence
for the original version and must not be relabeled as validation of a corrected version.
No historical result files have been modified or automatically declared invalid.
Any future corrected optimizer requires new source/bank identities and fresh affected
V3-guided comparisons; the failed c001 bank cannot be reused. All scientific suites are on hold.

## P. Research questions

RQ1-RQ4: V3 sufficiency, region utility, adaptation benefit and V3 guidance versus simulator-only
are unanswered: zero serious matched comparisons.
RQ5-RQ6: refinement benefit and independent-exploration rescue are unanswered; engineering
winner labels above are not evidence of either mechanism's scientific value.
RQ7-RQ9: W1 versus W2, clean unseen compositions and structural J generalization are unanswered.
RQ10: serious early-stop efficiency is unanswered; smoke saved zero calls.
RQ11: scientific prediction-error characterization is unavailable.
RQ12: scientific confirmation reliability is unavailable; two smoke confirmations per method
remain descriptive and partly physically shared.

## Q. Recommendation and resumption boundary

A targeted numerical correctness fix is needed before evaluating whether ARGOS is sufficient.
Proposed scope for a separately versioned change: safeguard the bounded-simplex scalar solve
with a convergent bracketed method, verify meaningful gradients, add regressions for the actual
offending logits and saturated inputs across supported J/dtypes, and save failed-bank raw
outputs before region extraction. Do not normalize after optimization, filter candidates or
relax Domain.validate: those would hide or alter the contract failure.

Preserve v0.2.0-pretest and this stopped campaign. A corrected version needs its own reviewed
source identity, frozen protocol and gates, followed by new smoke and affected comparisons.
Await the user's decision about that separate version before changing the frozen method.
