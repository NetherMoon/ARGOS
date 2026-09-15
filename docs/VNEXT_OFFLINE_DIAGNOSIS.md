# ARGOS vNext offline diagnosis and frozen development protocol

This document is frozen before fresh FlexDC execution. The historical H1 campaign remains closed. Final eight-context verification will be run by the user locally after W2 development and method selection. No mixed, V4, variable-J, or new operating-condition simulation is permitted.

## A. Preservation and source identity

Starting HEAD: `2c56cc1dadda273686252b6da732d4c386929e05`. New branch: `argos-vnext-original-workloads`. New immutable tag: `v0.3.0-h1-closed`, pushed at the starting HEAD. H1 optimizer, controller, surrogate adapter and contracts remain unchanged; new code is under `src/argos/vnext`.

The before inventory covers 31,018 historical files, 67,706,934,533 bytes, aggregate SHA-256 `66bf3e02900035ac02c9d5e64ddadf0764871443debf3fba8be36ac8a02beccb`. The complete per-file inventory is `runs/vnext_originals/manifests/h1_before.json`. At handoff, a second full content inventory must compare equal.

Frozen checkpoint: best-feasibility epoch 146, SHA-256 `7f60e28dfc836053064c772c95acc56eb73999b145fa314e98f7b39cf4d0c38a`. No model retraining or global correction is performed. Dependency identity is rechecked by the execution gate.

## B. W2 failure decomposition

All four selected V3 endpoints were retained in their candidate pools. Each bank contains 512 starts, 31 snapshots per start including endpoints, and six compressed representatives. Distances below use ARGOS's normalized P / conditional-R / bounded-weight metric.

| Context | Pool size | Selected endpoint to nearest representative / Batch 1 | To nearest later ARGOS query | Evidence and diagnosis |
|---|---:|---:|---:|---|
| c005 heterogeneous QoS, U=.6 | 316 | .048932 | .065540 | A queried iteration-150 snapshot was qualified, so generation and initial coverage did succeed. Search p90=.278 failed both fresh confirmations (~.318,.419). Scenario fragility is directly observed. Local search found no robust rescue. |
| c006 heterogeneous QoS, U=.8 | 391 | .007651 | .073275 | No qualified H1 observation among the compared methods. Tracking and QoS constraints trade off. Bank-wide actual feasibility is unknown, since most candidates were never simulated. Local refinement did not bridge the measured constraint gap. |
| c007 uniform QoS, U=.6 | 334 | .063003 | .052395 | A queried iteration-100 snapshot qualified and passed both confirmations. V3-only endpoint failed QoS; trajectory retention mattered. This is a successful H1 control within W2. |
| c008 uniform QoS, U=.8 | 345 | .025616 | .055225 | V3-only endpoint was actually qualified but ARGOS never queried it. Pool construction retained it; compression/query selection lost direct access. Later probes stayed farther away. One of two confirmations failed, so preserving it alone does not establish robustness. |

These are evidence categories, not a claim that all points in a nearby region share outcomes. No outcomes are assigned to unqueried bank points. Every method state, starts/snapshots/endpoints, pools, representatives and selection files used by the audit are hashed in the offline input manifests. The geometry JSON preserves exact qualified observation identities and sources.

Historical W2-HU comparison: the earlier Track-S report's successful point is P=.579596996, R=.144009009 kW/server, weights [.2608986720442772,.2564973756670952,.2425877079367637,.2400162443518638]. The c008 V3 endpoint differs by P=+.002963662455, R=-.009634688493 and weights [+ .002810455859,+ .000969000161,- .001639388502,- .002140067518]. Normalized distance is .017400494339. This historical result used a different model/search and included anchors/known feasible rows; it is diagnostic evidence, not a matched H1 baseline. It is never an online warm start.

Known numerical feasibility exists for every W2 context. In the pinned V3 train/validation/test prediction files, matching numerical-feasible row counts are c005: 0/1/1, c006: 2/0/0, c007: 2/0/0, c008: 3/0/0. All three split file hashes match the existing provenance manifest. Separately, the historical dense aggregate has c005:391/15,620, c006:0/10,100, c007:0/10,100, c008:342/15,700 numerical-feasible rows. Dataset numerical feasibility is distinguished from H1's audited per-job evidence qualification. Zero counts in one dataset do not prove domain infeasibility.

## C. Protected-elite counterfactual

The replay constructs an eight-point first batch from two protected endpoints, up to four distinct representatives and at least two independent points, using the historical candidate RNG. It joins outcomes only by exact physical P/R/weights and the same search scenario, across saved original-method observations. Unknown outcomes remain unknown in `elite_first_batch_replay.json`.

For c008, the exact V3-selected endpoint has a qualified physical search evaluation. Including it would have made the first batch contain a known qualified point and would prevent H1's single-scenario NO_BID, irrespective of the other unknown outcomes. Its known objective is about 95.50. The best counterfactual incumbent/objective cannot be asserted for unqueried alternatives. The endpoint's 1/2 confirmation result remains a fragility warning.

Elite 1 follows the unmodified upstream V3-selected endpoint. Other safe endpoints follow upstream safety/objective/slack ordering; when no safe distinct endpoint remains, use numerical feasibility/least-violation ordering. A .02 normalized separation defines a distinct elite. Elite identity, rank and original source are recorded. The exact endpoint bypasses region compression and still requires FlexDC evidence.

## D. Prequential discrepancy ladder

Primary stream: H1 ARGOS fixed-budget search observations from each of the eight original contexts separately. Fit B1 to predict B2, B1+B2 to predict B3, B1+B2+B3 to predict B4. No confirmation labels, same-query labels, mixed labels, or cross-method time pooling are used. Each fold stores training/test execution IDs and asserts disjointness.

Six behaviors are modeled: mean tracking, p90, and four raw Pj. Features are five independent coordinates: normalized P, conditional R and an orthonormal three-dimensional Helmert basis of the normalized simplex. Its Euclidean distance equals H1's metric for equal weight bounds. Repeated geometry is aggregated into one support site. Pj stays in physical probability space because exact zero/one observations make an unsmoothed logit transform singular. Tracking is compared in physical space and in the pinned V3 log space (floors 1e-6 and 1e-3).

Fixed ladder specification, persisted before fitting: C0 identity; C1 local Gaussian-weighted offset, bandwidth .24; C2 local ridge, bandwidth .24, slope regularizer .1 and intercept regularizer 1e-8; C3 six float64 Matérn-2.5 GPs, initial length .24, bounds [.03,.8], constant kernel amplitude bounds [.1,10], normalized residual noise SD .05, no optimizer restarts. A failed GP uses C2 and records the failure; unavailable uncertainty is null, never a fabricated zero. GP latent uncertainty is not simulator scenario variability.

| Physical-space model | W2 p90 MAE | W2 max-Pj MAE | W2 rank Spearman | W2 normalized constraint MAE | W1 rank Spearman |
|---|---:|---:|---:|---:|---:|
| C0 none | .069759 | .041095 | .950397 | .241031 | .922619 |
| C1 constant | .080037 | .046544 | .936508 | .306220 | .928571 |
| C2 ridge | .081503 | .049604 | .871032 | .328700 | .873016 |
| C3 GP | .069915 | .043965 | .904762 | .250292 | .894841 |

Log-tracking W2 p90 MAEs were .406220 / .529040 / .186414 for C1/C2/C3, and ranks .668651 / .583333 / .851190. None improved the primary W2 ranking. Detailed per-context/fold signed bias, Pj MAEs, classification, top-two feasibility and reconstructed objective error are saved in `prequential.json` and individual prediction files.

A crucial limitation: the held-out W2 batches B2-B4 contain zero qualified/numerically feasible points. All tested models predicted these points infeasible. Thus perfect W2 feasibility classification and zero top-two feasible hits are uninformative about discovering a feasible island; rank mostly measures ordering among infeasible points. W1 has useful feasible controls. No evidence here establishes that all possible online correction models are useless.

Selection rule declared with the ladder: require improved W2 ranking, no top-two feasible loss, >=5% normalized constraint MAE improvement, W1 rank loss <=.05, W1 MAE increase <=10%, and no W1 top-two loss. Prefer the simplest eligible model. GP additionally needs >=.05 rank and >=10% error gain over a simpler eligible model in at least 3/4 W2 contexts. No candidate qualifies. **Select C0; omit ERTC from fresh experiments.**

Objectives are reconstructed through the existing softplus thresholds/costs and the pinned inference energy formula ($.1/kWh, N=1000, 3600 seconds). Actual FlexDC objectives retain integer-watt physical allocation and authoritative raw Pj. No objective definition changes.

## E. Retrospective racing

c005's ARGOS winner has one search pass and two confirmation failures: a repeated screen would expose fragility. c008's endpoint has two passes and one failure across search plus confirmations; accepting after two passes is order-dependent if the failure appears third. Every observed failure remains in the candidate record. These are retrospective diagnostics only: old confirmations were not available to old online selection and are never relabeled as such.

Online states are UNOBSERVED, INFEASIBLE, PROVISIONAL_FEASIBLE, SEARCH_ROBUST_FEASIBLE and SCENARIO_FRAGILE. A single qualified scenario is provisional. Two distinct passing search scenarios with no observed screen failure establish the declared search-robust status, not statistical reliability. Repeated failure marks fragility. Final ranking prioritizes robust status, worst normalized actual violation, aggregate actual objective and deterministic ID. No robust incumbent means NO_BID for ER/ERT; no confirmation candidate is fabricated.

## F. Fixed controller mechanisms

Batch size eight, four batches, 32 total search calls. Potential repeat capacity is [0,2,3,3], at most eight calls (25%). Unneeded slots return to unique exploration. Repeat provisional points first and single-observation boundary failures with worst normalized violation <=.15; skip obvious failures. Already-completed two-pass screens do not receive automatic extra repeats. Repeat scenarios are shared by batch across methods but separate from primary and confirmation pools.

Every batch retains two direct independent legal points. H1 is unchanged. E changes only first-batch endpoint access. ER adds measured scenario grouping/ranking and repeat slots with measured-random local proposals at H1 radius .12. ERT adds targeted proposals, adaptive region radii and V3 scoring of the cheap proposal pool. It uses up to four measured anchors, 32 local proposals per anchor, and one unused region representative where available. A targeted slot cannot be erased by random proposals.

Target deltas: paired +/- .02 normalized P and conditional-R; QoS weight transfer .01 from slack jobs to the dominant violating job, clipped by receiver/donor bounds. At N=1000 this is nominally ten nodes, larger than a one-node rounding increment. Actual AQA allocation depends on active queues/server state and is not inferred from nominal weights. Wizard P/R round to integer watts; changes with identical rounded P/R and identical weights are skipped. Boundary probes interpolate observed pass/fail pairs legally. No universal direction of benefit is assumed.

Trust-region radius starts .06, minimum .0075, maximum .12; two failures halve it, two improvements expand by 1.5. At minimum radius restart from an unused V3 representative when available. Progress, center, radius, discrepancy and restart state are logged. Region state is reconstructed deterministically from accumulated online search observations. DISCOVER prioritizes joint normalized constraints; IMPROVE is enabled only after a robust incumbent and ranks predicted feasible objective. C0 contributes no learned uncertainty or correction.

## G. GPU decision and verification gates

See `VNEXT_ROCM.md`. The RX7700S is detected by HIP6.2 as gfx1102, but no functional local PyTorch/HIP environment was established. Use the unchanged CPU environment, four torch threads, four simulator workers. GPU parity and CPU/HIP speed comparisons are explicitly not run, not labeled passed. Mocked tests cover CPU/NVIDIA/HIP and auto selection. No driver or architecture overrides are introduced.

Before simulation: full H1 plus new regression tests, meaningful synthetic compression/fragility/bias/QoS/no-feasible/recovery tests, lint/format, immutable protocol and ledger committed, clean Git, dependency/checkpoint/runtime/context hashes sealed. Every query freezes predictions and IDs before simulation. Recovery reuses completed evidence; physical retry attempts count against the budget. Pause stops at safe bank/batch boundaries. The old campaign is not a writable cache.

## H. Exact fresh development and final handoff

Development: c005-c008, four methods H1/E/ER/ERT, N1000, U.6/.8, AQA, original one-hour ISO/cluster/QoS contract, 512 starts x1500 iterations, snapshot interval50. V3 banks are generated fresh and shared only within a matched context. Each method receives 32 search calls including repeats; a returned candidate receives three fresh confirmations. Confirmations never update an episode's search or candidate choice. A software failure stops affected work; a scientific failure is reported without changing constants or budgets.

Fresh seeds are committed in `configs/vnext/seed_ledger.json`, with separate development/verification primary, repeat, confirmation and candidate groups. All are disjoint from every old ledger group (including old reserved seeds), training scenarios and prior candidate seeds. Old reserved values are not exposed. Exact case settings and copied original-workload hashes are in `configs/vnext/protocol.json`.

**Predeclared winner rule:** lexicographically maximize W2 contexts with >=2/3 confirmation passes, total confirmation passes, robust-search contexts, then contexts with any qualified search point. Next minimize summed first-qualified query indices (33 if none), summed per-context objective ranks (missing last), then complexity H1<E<ER<ERT. No criteria are chosen after fresh outcomes.

After all16 development runs, freeze selected.json and commit. The user then runs the selected method on all eight originals using the independent verification pool, 32 search calls including repeats and three fresh confirmations. No W1 tuning. Final verification remains PENDING USER RUN at this handoff. Its development target is a qualified bid in every context and >=2/3 confirmations per returned bid. A miss stops and is reported; no automatic retuning or mixed testing follows.
