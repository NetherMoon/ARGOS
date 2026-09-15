# ARGOS vNext: original-workload development and verification handoff

This report closes the authorized W2 development work. Independent verification of all eight originals is **PENDING USER RUN**. No mixed or structural-generalization simulation was performed. The detailed numerical development tables and per-observation failure metrics are in [W2 development evidence](vnext_development_results/W2_DEVELOPMENT_REPORT.md).

## A. Git and software state

Starting HEAD: `2c56cc1dadda273686252b6da732d4c386929e05`. Preservation tag: `v0.3.0-h1-closed`. Working branch: `argos-vnext-original-workloads`. Scientific development freeze: `4f2fc8e28bdf7adb66102e35647f139eb2548c8e`. Commit `f79efcc` only preserves LF bytes in the new evidence archives on Windows. The separate verification gate records the later recovery-safeguard source commit; the final handoff commit can be obtained with `git rev-parse HEAD` and is reported in the handoff receipt. A commit cannot contain its own final hash.

FlexDC is pinned to `525dc684d73ab0c6f6c479f5b54811ddf02f1221`; CONDOR-FLEXDC to `2b653facf31de356d8c682ee76d814bd81b8e95d`. Both dependency checkouts were clean at the gate. The checkpoint is best-feasibility epoch146, SHA256 `7f60e28dfc836053064c772c95acc56eb73999b145fa314e98f7b39cf4d0c38a`. The paper runtime uses Python3.12.4, torch2.4.1+cpu, numpy2.2.6, pandas2.2.2, scipy1.14.0, scikit-learn1.6.1. Full source/runtime/input identities are archived in the execution gates. No retraining occurred.

## B. Historical H1 preservation

The complete before and after inventories cover the closed campaign and its report package: 31,018 files and 67,706,934,533 bytes. The expected aggregate is `66bf3e02900035ac02c9d5e64ddadf0764871443debf3fba8be36ac8a02beccb`. The final comparison receipt is [H1_PRESERVATION.json](vnext_development_results/H1_PRESERVATION.json); full per-file inventories remain under `runs/vnext_originals/manifests`. H1 source, old results, reports, closure receipts and reserved seeds are preserved. New evidence uses a separate directory and fresh disjoint seed pools.

## C. Failure diagnosis

The [frozen offline diagnosis](VNEXT_OFFLINE_DIAGNOSIS.md) distinguishes historical and fresh observations. Historical c005 had coverage but failed both confirmations; c006 exposed a tracking/QoS tradeoff and unsuccessful local refinement; c007 was an H1 trajectory-snapshot success; c008 lost direct access to an actually qualified selected V3 endpoint during compression/query selection, although that endpoint remained scenario-fragile. No unqueried bank point is assigned an actual outcome.

In fresh development, c005's elite-only bid passed 0/3 confirmations. ER/ERT rejected fragile search candidates, and ERT also left late qualified points unconfirmed when its budget ended. c006 and c008 were recovered by the ERT bundle, each passing 3/3 confirmations. c007's H1/E bid passed only 1/3 confirmations; ER/ERT returned NO_BID. Fresh c008 H1/E/ER returned NO_BID; ERT found a new local point with a successful repeated screen and 3/3 confirmations. This is distinct from the favorable historical V3 endpoint. Model bias and scenario variability are separate: offline prediction error alone does not establish why a particular unobserved neighborhood failed.

## D. Protected elites

Two distinct V3 endpoints bypass compression and are queried in Batch1, with exact upstream-selected endpoint priority, recorded rank/provenance, deduplication, and two independent exploration slots. The same-geometry/same-scenario historical replay would recover the known c008 qualified endpoint; unknown replay points remain unknown. This is a coverage repair, not a robustness proof.

Fresh elites exposed qualified c005 points, but their returned E bid failed all confirmations. They did not recover c006 by themselves. In c007, the E first-qualified query moved from H1's call6 to call17 and returned the same fragile bid. Fixed elite slots therefore have an opportunity cost. The complete per-context elite counts are archived in mechanism_diagnostics.json.

## E. Correction ladder

A predeclared prequential comparison fit each original context's earlier search batches and predicted only its next batch. No confirmations, mixed workloads, same-query labels, or cross-method temporal pooling entered training. C0 is identity; C1 is a local constant; C2 is local ridge; C3 uses six MatÃ©rn2.5 Gaussian processes with deterministic ridge fallback. Exact transformations, regularization, kernel bounds and selection criteria were fixed before fitting.

Physical-space W2 normalized constraint MAE was .241031/.306220/.328700/.250292 for C0/C1/C2/C3; rank Spearman was .950397/.936508/.871032/.904762. None met the declared improvement criterion. **C0 was selected**, so no correction model was deployed and no artificial ERTC run was added. Held-out W2 batches had zero feasible points, limiting classification/discovery conclusions. This study does not prove that all correction methods are useless. Full per-fold behavior errors, uncertainty/fallback records and provenance are in the offline archive.

## F. Scenario racing

ER/ERT reserve at most eight of32 search calls for repeats, with capacities [0,2,3,3]; unused slots return to unique points. Primary, repeat and confirmation scenarios are disjoint. A single pass is provisional; two distinct passing search scenarios with no observed screen failure establish SEARCH_ROBUST_FEASIBLE. Every failure remains recorded. This is a search rule, not a statistical reliability guarantee. No robust incumbent produces NO_BID; there is no fabricated confirmation candidate.

The fresh c005 and c007 behavior demonstrates why a single pass should not be treated as reliable. Exact repeat usage and provisional-to-fragile transitions are in the joined audit. Late provisional points that never received a repeat are explicitly distinguished from candidates that failed a repeat. ERT's c006 winner passed its repeat and all three independent confirmations.

## G. Targeted probes

ERT generates paired normalized P/conditional-R probes of magnitude .02, legal .01 QoS weight transfers, and legal boundary midpoints from observed pass/fail pairs. It retains explicit targeted and independent slots. Every dispatched probe has its source, anchor, prediction frozen before evaluation, actual outcome and residual saved. Changes with identical physical rounded P/R and weights are skipped.

The c006 winner `b3-local-0-0` refines tracking probe `b2-target-0-003`, which descends from V3 snapshot `v3-0000-0035`. Its P=.5934270917125786, R=.05341346178003087, weights=[.2533412479511694,.25480825970848986,.2493975582187342,.24245293412160673]. Search p90=.014 and maxPj=.0573395893; repeated p90=.025 and maxPj=0. Mean actual search objective=102.5594207113. This lineage supports a useful targeted/local path. ERT versus ER also changes proposal scoring and radius adaptation, so it cannot isolate a causal effect for targeted probes alone. Same-scenario anchor deltas are separately archived.


The c008 winner `b3-local-0-28` has P=0.5885830402265771, R=0.06907010856285434, weights=[0.25749707828984825, 0.25616423253738774, 0.24530195973654825, 0.241036729436216]. It refines tracking anchor `b2-target-0-003` at radius0.015; mean actual search objective100.4078886376. Its search/repeat and confirmation metrics are:

| Phase | p90 | maxPj | Qualified |
|---|---:|---:|---|
| search | 0.207 | 0.0 | True |
| search | 0.179 | 0.0 | True |
| confirmation | 0.03 | 0.0 | True |
| confirmation | 0.08 | 0.0 | True |
| confirmation | 0.144 | 0.0 | True |

## H. Trust-region behavior

ERT starts at radius.06, shrinks after two failures, expands after two improvements, respects [.0075,.12], and restarts from an unused representative when available. The successful c006 local proposal used radius.09. Recorded radii and restart counts are reported below. ER also records diagnostic reconstructed region state, but its applied local proposal radius is fixed at.12. Only ERT applies the adaptive radii. Region/probe/scoring effects are a bundle in this ablation.


### Recorded mechanism counts

| Case, ERT | Unique targeted types | Qualified targeted points | Provisional points failing repeats | Recorded region-state radius range | Maximum recorded restart count |
|---|---|---:|---:|---|---:|
| c005 | {'tracking_direction': 7, 'boundary_probe': 1, 'qos_transfer': 1} | 5 | 5 | 0.0075--0.0600 | 0 |
| c006 | {'tracking_direction': 8, 'qos_transfer': 1, 'boundary_probe': 1} | 3 | 0 | 0.0112--0.0900 | 0 |
| c007 | {'tracking_direction': 5} | 1 | 1 | 0.0075--0.0600 | 1 |
| c008 | {'tracking_direction': 7, 'boundary_probe': 1} | 1 | 0 | 0.0112--0.0900 | 0 |

These count unique dispatched target geometries; source_counts in results.json also includes repeated calls. A radius appearing in a reconstructed state is distinguished from the radius on a dispatched local candidate.

## I. AMD RX7700S and performance

HIP6.2 enumerated RX7700S/gfx1102 and Radeon780M/gfx1103. The installed paper PyTorch backend is CPU; torch.version.hip=null and no GPU device is selected by PyTorch. Ubuntu had no torch or rocminfo. A bounded check did not establish a working local PyTorch/HIP path. GPU tensor/checkpoint/forward/gradient/optimizer parity gates and CPU-versus-HIP speed comparisons were **NOT RUN**. No unsupported architecture override or driver change was made. [ROCm investigation](VNEXT_ROCM.md) preserves the version-specific official evidence.

All fresh development used CPU, four torch threads and four simulator workers. Candidate banks were generated once per context and shared across its methods. Bank time is not multiplied by four when counting physical campaign work. Correction/scoring/simulator times are separate where instrumented; H1/E retain their original aggregate active timer. Missing timing subdivisions are not represented as zero or invented. There is no GPU speedup claim.


### Measured CPU timing (seconds)

| Case | Method | Shared bank | Correction | Proposal scoring | Simulator wall | Active logical wall |
|---|---|---:|---:|---:|---:|---:|
| c005 | E | 321.605 | not separately instrumented | not separately instrumented | not separately instrumented | 176.935 |
| c005 | ER | 321.605 | 0.005 | 2.219 | 159.947 | 162.632 |
| c005 | ERT | 321.605 | 0.004 | 2.495 | 171.192 | 174.102 |
| c005 | H1 | 321.605 | not separately instrumented | not separately instrumented | not separately instrumented | 132.757 |
| c006 | E | 293.531 | not separately instrumented | not separately instrumented | not separately instrumented | 192.902 |
| c006 | ER | 293.531 | 0.005 | 2.027 | 175.331 | 177.867 |
| c006 | ERT | 293.531 | 0.004 | 2.308 | 233.778 | 236.534 |
| c006 | H1 | 293.531 | not separately instrumented | not separately instrumented | not separately instrumented | 185.197 |
| c007 | E | 294.912 | not separately instrumented | not separately instrumented | not separately instrumented | 179.533 |
| c007 | ER | 294.912 | 0.005 | 2.383 | 170.270 | 173.146 |
| c007 | ERT | 294.912 | 0.007 | 3.310 | 193.684 | 197.398 |
| c007 | H1 | 294.912 | not separately instrumented | not separately instrumented | not separately instrumented | 179.418 |
| c008 | E | 300.657 | not separately instrumented | not separately instrumented | not separately instrumented | 163.648 |
| c008 | ER | 300.657 | 0.004 | 2.100 | 187.092 | 189.797 |
| c008 | ERT | 300.657 | 0.005 | 2.376 | 242.281 | 245.309 |
| c008 | H1 | 300.657 | not separately instrumented | not separately instrumented | not separately instrumented | 164.922 |

Shared bank generation totals 1210.705s; summed active method timing 2932.098s. Their sum 4142.804s is accounted active work, not an exact campaign elapsed-wall measurement: reporting, serialization and host overhead are additional. Physical receipt timestamps and observation runtime_seconds remain available for auditing. No physical campaign stopwatch was separately stored.

## J. W2 development results

All four original W2 contexts and H1/E/ER/ERT ablations were run with32 search calls each. Three fresh confirmations were attempted only for returned bids. A NO_BID has zero attempted confirmations, not a failed 0/3 experiment. The generated table and audit below give every result and budget.

| Case | Method | Qualified / robust | Confirmations passed | Search / unique / repeats | Selected objective |
|---|---|---|---|---|---:|
| c005 | E | True / False | 0/3 | 32 / 32 / 0 | 87.58133058279736 |
| c005 | ER | True / False | not attempted: NO_BID | 32 / 29 / 3 | -- |
| c005 | ERT | True / False | not attempted: NO_BID | 32 / 26 / 6 | -- |
| c005 | H1 | False / False | not attempted: NO_BID | 32 / 32 / 0 | -- |
| c006 | E | False / False | not attempted: NO_BID | 32 / 32 / 0 | -- |
| c006 | ER | False / False | not attempted: NO_BID | 32 / 31 / 1 | -- |
| c006 | ERT | True / True | 3/3 | 32 / 29 / 3 | 102.55942071129337 |
| c006 | H1 | False / False | not attempted: NO_BID | 32 / 32 / 0 | -- |
| c007 | E | True / False | 1/3 | 32 / 32 / 0 | 91.25646799152533 |
| c007 | ER | True / False | not attempted: NO_BID | 32 / 30 / 2 | -- |
| c007 | ERT | True / False | not attempted: NO_BID | 32 / 29 / 3 | -- |
| c007 | H1 | True / False | 1/3 | 32 / 32 / 0 | 91.25646799152533 |
| c008 | E | False / False | not attempted: NO_BID | 32 / 32 / 0 | -- |
| c008 | ER | False / False | not attempted: NO_BID | 32 / 32 / 0 | -- |
| c008 | ERT | True / True | 3/3 | 32 / 31 / 1 | 100.40788863758672 |
| c008 | H1 | False / False | not attempted: NO_BID | 32 / 32 / 0 | -- |

ERT returned robust bids in2/4 W2 contexts, both3/3 confirmed. H1 and E each returned c007 with1/3; E additionally returned c005 with0/3. ER returned no robust bids.

## K. Frozen vNext choice

The unchanged lexicographic rule maximizes contexts with at least2/3 confirmations, total confirmation passes, robust-search contexts, then any-qualified contexts; it then minimizes first-qualified query indices, objective ranks and complexity. `configs/vnext/selected.json` records the exact ranking and protocol/results hashes. No budget, elite count, repeat fraction, seed, correction setting, probe delta or radius rule was tuned after outcomes.

Before user handoff a separate recovery-only amendment prevents a full eight-call reservation after abandoned physical attempts leave insufficient budget, and records explicit ERROR if pending retries exhaust the cap. FlexDC already enforced the physical32-attempt cap. Normal W2 executions were unaffected; synthetic equivalence tests compare normal query/state trajectories to frozen4f2fc8e. The development gate/test log remain unchanged. Verification uses its own gate and regression receipt.

## L. All-original verification: pending user execution

| Context | Original workload | U | Search / robust status | Objective / scenarios / confirmations | Calls / unique / repeats / timing |
|---|---|---:|---|---|---|
| c001 | W1 heterogeneous QoS | .6 | PENDING | PENDING | PENDING |
| c002 | W1 heterogeneous QoS | .8 | PENDING | PENDING | PENDING |
| c003 | W1 uniform QoS | .6 | PENDING | PENDING | PENDING |
| c004 | W1 uniform QoS | .8 | PENDING | PENDING | PENDING |
| c005 | W2 heterogeneous QoS | .6 | PENDING | PENDING | PENDING |
| c006 | W2 heterogeneous QoS | .8 | PENDING | PENDING | PENDING |
| c007 | W2 uniform QoS | .6 | PENDING | PENDING | PENDING |
| c008 | W2 uniform QoS | .8 | PENDING | PENDING | PENDING |

Run in PowerShell:

```powershell
& 'C:\Users\Achuthan Menon\Desktop\Research Work\ARGOS Hybrid\scripts\vnext\Run-Original-Verification.ps1'
```

To pause, run the same command in a second PowerShell window with `-Action Pause`. Wait for the running process to report PAUSED and exit before restarting the PC. A bank computation or current simulator batch finishes first. Resume with `-Action Resume`; inspect saved progress with `-Action Status`. After a hard crash, preserve all files and use Resume; the runner validates identity and completed receipts. If the finite physical retry budget is exhausted, it stops for review rather than silently expanding the experiment. Do not remove completion files or reset budgets.

Results, raw simulator evidence, per-query audits and timestamped console logs are saved in `runs/vnext_originals/originals_verification`. The launcher is independent of Codex. Return after it finishes for the all-original report; no automatic mixed testing follows.

## M. W1 regression

Existing H1 software regression tests pass. Offline W1 controls contributed to rejecting correction models. Fresh W1 performance of the selected method is not yet known and is not claimed preserved: c001-c004 verification remains pending. No W1 tuning occurred.

## N. Remaining failures and infrastructure

Every NO_BID and failed confirmation is enumerated, with actual p90, Pj, objective and per-job evidence counts, in the linked detailed report. Mechanism diagnostics list fragile points and unconfirmed outcomes. The final evidence audit checks raw-output and completion hashes, scenario membership, physical observations and same-geometry/same-scenario consistency. The offline archive preserves GP fallback events; no learned correction is fitted in fresh C0 runs. Recovery safeguards are documented separately from scientific failures.

Final development audit: **PASS**,16 completed methods,512 search observations,15 confirmations,3,932 verified evidence files,108 matched geometry/scenario groups and no metric differences. All527 physical attempts are attempt-001: zero abandoned retries. No invalid simulator observations or infrastructure errors occurred. Offline recorded correction events by type: {'gp_warning': 305}. Exact per-output warnings are retained in prequential.json; kernel-bound warnings are not fit failures. Fresh correction fit fallback count is zero because C0 was selected. Regression validation: **207 passed,1 GPU skip**; four synthetic nominal trajectories exactly match frozen4f2fc8e.

## O. Research conclusion

1. Protected elites fix the specific historical endpoint-access failure by construction and counterfactual evidence, but have not established a general fresh robustness fix.
2. Scenario racing exposed single-scenario fragility and withheld such bids; its finite repeat schedule can also leave late useful points unconfirmed.
3. Local correction did not materially improve W2 predictions under the frozen eligibility rule; retain C0.
4. ERT's targeted/local lineages recovered c006 and c008. The ablation cannot separate the contribution of probes, adaptive radii and proposal scoring.
5. A GP was not justified; even simpler corrections failed the eligibility rule.
6. ERT improved fresh W2 development relative to H1 by recovering bids with3/3 confirmations on both c006 and c008. This remains development evidence, not independent verification.
7. Fresh W1 preservation remains unverified.
8. **ORIGINAL-WORKLOAD PROBLEMS REMAIN.** Do not reopen mixed/generalization testing automatically.
