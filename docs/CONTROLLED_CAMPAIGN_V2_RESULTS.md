# ARGOS controlled campaign v2: final report at early closure

**Status: closed early by the user on 14 September 2026.** This report covers 121 of 227 declared method cases: 5 engineering smoke, all 40 original-workload cases, all 70 mixed screening cases, all 5 methods for serious MIX4-TTII, and V3-only for serious MIX4-IITT. The remaining 106 cases were not run by decision; they are not failures. No further execution is authorized. The standalone launcher is disabled by the closure marker.

ARGOS was successful on the two W1 training workloads at both tested utilization levels. The W2 short-job workloads remained fragile, especially at 80% utilization. On the eight original operating contexts, ARGOS and fixed probing both produced six search-qualified bids, with five passing both fresh confirmations. V3-only produced four, with two passing both confirmations. Thus the evidence supports useful V3-guided probing, but does not establish a consistent advantage for ARGOS adaptation over fixed probing.

This is controlled development evidence, not the final locked benchmark or a reliability guarantee. The study was stopped after outcomes were observed; the partial expanded suite cannot represent the entire predeclared test domain.

## A. Git, frozen protocol, and software identity

- Corrected frozen core: `2b730c6a1831133b5fe5c0eedfa3d282465e0fa8`, tag `v0.3.0-pretest`.
- Campaign execution/protocol code HEAD: `9a3221ebef7bb2fa90cb4412c069e31a3bca3dc6`. A later documentation commit does not change this execution identity.
- FlexDC: `525dc684d73ab0c6f6c479f5b54811ddf02f1221`.
- CONDOR-FLEXDC: `2b653facf31de356d8c682ee76d814bd81b8e95d`.
- Best-feasibility V3 epoch146 checkpoint SHA256: `7f60e28dfc836053064c772c95acc56eb73999b145fa314e98f7b39cf4d0c38a`.
- V2 protocol SHA256: `085c47daf4166beec9bdc7691f58792d7c36069fbf014d1db56155d59aeb11bf`.
- Unchanged ledger SHA256: `6c6af5412070623c5b8fcf6eb4223a4169b86bdd702e32731ebf803d5a33f4b6`.
- Canonical cost SHA256: `f20f3f78f53cca79d29c8b077747df86d9a23dc5bf19a5870142154c9b0567c4`.

“V3-only + validation” means V3's originally ranked selected endpoint is checked by FlexDC, then receives two fresh confirmations if qualified. “V3 + fixed probing” means a pre-frozen sequence of probes from the shared V3 bank, without adaptive simulator feedback. All V3-based methods use the same trained model and the corrected bounded-logistic weight transform. They are not a claim about the numerically broken, byte-for-byte unchanged v0.2.0 optimizer. The pinned dependency source/model was not retrained or edited.

## B. Seed ledger and provenance

Training seeds found: 20, 21, 22. Excluded historical seed union: 20, 21, 22, 100020, 100021, 2026091301. Ledger pools contain 3 engineering, 96 development search, 192 development confirmation, 100 reserved final-search, and 200 reserved final-confirmation seeds. Reserved values are neither displayed nor executed.

Each context has one search scenario, one bank initialization, and two fresh confirmation seeds disjoint from its search seed. Methods share the same allocated scenarios. Shared physical confirmations are not extra independent evidence. All v1 case allocations, serious subsets, seeds, and budgets were retained for v2; no result-driven reseeding or budget change occurred. Model provenance uses original workload profiles with training N=250/1000 and U=0.6/0.8. New mixtures combine familiar profiles.

## C. Candidate banks, reuse, and verification

Generated **25 banks**, with **97 completed V3-method bank uses** and **72 reuse receipts**. No v1 result or diagnostic bank was imported. Complete bank identities, snapshot/region counts, settings and recorded per-context optimizer times are in [candidate_bank_manifest.csv](campaign_v2_results/candidate_bank_manifest.csv).

Exact scenario-invariance regressions covered raw/differentiable features, predictions, endpoints, snapshots and trajectory; capture parity also passed. The independent full c001 regression used 512 starts and 1,500 iterations: 15,872 snapshots, 16,384 snapshot/endpoint rows legal under the unchanged domain, maximum weight-sum error 4.470348358154297e-08. Recomputed endpoints/snapshots/starts/original-top-k CSV hashes matched the actual c001 bank. Those diagnostic outputs were never imported.

**Timing caveat:** c024 recorded 39,327.6395283 optimizer seconds across a long system-time gap. Preserve this raw value, but exclude c024 from comparative timing interpretation. This isolated, partially evaluated context is not evidence of normal optimization throughput. The other 24 banks total 3604.696 recorded optimizer seconds.

## D. All original workloads

All four workloads were evaluated at N=1000, U=0.6 and 0.8: eight operating contexts and five methods each. A qualified bid requires valid simulator output, tracking p90 <=0.30, every reported Pj <=0.10, and at least one observation for every job. Raw FlexDC Pj is authoritative. Confirmation is a separate outcome.

Cells below show **objective; fresh confirmations passed/2**. Lower objective is better. NO_BID includes a rejected selected endpoint or no qualified point within the declared search budget. Rejected candidates' objective values are retained in detailed files but are not displayed as successful bids here.

| Case | Workload | U | V3-only + validation | V3 + fixed probing | Simulator-only | ARGOS fixed | ARGOS early |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c001 | W1-train-qos3333 | 0.6 | 63.91; 2/2 | 63.91; 2/2 | 87.07; 2/2 | 63.91; 2/2 | 63.91; 2/2 |
| c002 | W1-train-qos3333 | 0.8 | NO_BID | 78.36; 2/2 | 75.33; 2/2 | 73.01; 2/2 | 73.01; 2/2 |
| c003 | W1-train-qos4444 | 0.6 | 61.53; 2/2 | 61.53; 2/2 | 76.88; 2/2 | 61.53; 2/2 | 61.53; 2/2 |
| c004 | W1-train-qos4444 | 0.8 | NO_BID | 65.90; 2/2 | 81.56; 2/2 | 71.42; 2/2 | 73.42; 2/2 |
| c005 | W2-short-qos5_4.5_4_3.5 | 0.6 | 87.92; 1/2 | 87.63; 0/2 | NO_BID | 87.63; 0/2 | 87.63; 0/2 |
| c006 | W2-short-qos5_4.5_4_3.5 | 0.8 | NO_BID | NO_BID | NO_BID | NO_BID | NO_BID |
| c007 | W2-short-qos5555 | 0.6 | NO_BID | 91.40; 2/2 | NO_BID | 91.40; 2/2 | 91.40; 2/2 |
| c008 | W2-short-qos5555 | 0.8 | 95.50; 1/2 | NO_BID | NO_BID | NO_BID | NO_BID |

| Method | Completed | Qualified bids | Bids passing both confirmations | Search queries |
| --- | --- | --- | --- | --- |
| V3-only + validation | 8 | 4 | 2 | 7 |
| V3 + fixed probing | 8 | 6 | 5 | 256 |
| Simulator-only | 8 | 4 | 4 | 256 |
| ARGOS fixed | 8 | 6 | 5 | 256 |
| ARGOS early | 8 | 6 | 5 | 168 |

**W1-train-qos3333:** At U=0.6 all V3 methods tie at 63.9113, while simulator-only is 87.0664; all confirm. At U=0.8 V3-only has no safe endpoint. ARGOS refines to 73.0132, better than fixed probing 78.3599 and simulator-only 75.3290; all returned bids confirm.

**W1-train-qos4444:** At U=0.6 V3-only already suffices at 61.5334. At U=0.8 its selected endpoint fails measured Resnet Pj=0.1009942439>0.10. Fixed probing 65.9017 beats ARGOS fixed 71.4175 and early 73.4224; simulator-only 81.5610 is worse. All returned bids confirm.

**W2-short-qos5_4.5_4_3.5:** At U=0.6 ARGOS/fixed probing select 87.6325 but fail both confirmations. V3-only 87.9195 passes one of two; its failed confirmation has p90=0.303>0.30. Simulator-only returns no bid. At U=0.8 every method returns no bid. This does not prove the entire domain is infeasible.

**W2-short-qos5555:** At U=0.6 ARGOS/fixed probing select 91.4048 and pass both confirmations; V3-only fails Bloom Pj=0.2135144, and simulator-only finds no bid. At U=0.8 V3-only selects 95.4964, search-qualified but only one of two confirmations passes; all other methods return no bid. ARGOS retained that endpoint in its pool but never queried it. Pool retention alone did not guarantee coverage.

Full 40-row results, candidate P/R/weight vectors, queries/batches, sources, timings, selected-point per-job evidence and failures are in [PHASE1_REVIEW.md](campaign_v2_results/PHASE1_REVIEW.md) and [campaign_results.csv](campaign_v2_results/campaign_results.csv).

## E. Composition-only tests: completed screening and partial serious suite

All fourteen 16-query screening cases completed. No V3-only endpoint qualified. Fixed probing found 6/14 bids, ARGOS fixed/early 5/14, and simulator-only 1/14. Fixed probing and each ARGOS variant had 4/14 bids pass both confirmations; simulator-only's sole bid failed both. ARGOS tied fixed probing's objective in all five joint successes and missed its c014 bid. These results do not support a screening advantage from adaptation.

| Case | Workload | U | V3-only + validation | V3 + fixed probing | Simulator-only | ARGOS fixed | ARGOS early |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c009 | MIX4-TTTI | 0.6 | NO_BID | 95.42; 0/2 | NO_BID | 95.42; 0/2 | 95.42; 0/2 |
| c010 | MIX4-TTIT | 0.6 | NO_BID | NO_BID | NO_BID | NO_BID | NO_BID |
| c011 | MIX4-TTII | 0.6 | NO_BID | 94.06; 2/2 | NO_BID | 94.06; 2/2 | 94.06; 2/2 |
| c012 | MIX4-TITT | 0.6 | NO_BID | NO_BID | NO_BID | NO_BID | NO_BID |
| c013 | MIX4-TITI | 0.6 | NO_BID | 90.52; 2/2 | NO_BID | 90.52; 2/2 | 90.52; 2/2 |
| c014 | MIX4-TIIT | 0.6 | NO_BID | 89.38; 1/2 | NO_BID | NO_BID | NO_BID |
| c015 | MIX4-TIII | 0.6 | NO_BID | 87.49; 2/2 | NO_BID | 87.49; 2/2 | 87.49; 2/2 |
| c016 | MIX4-ITTT | 0.6 | NO_BID | NO_BID | NO_BID | NO_BID | NO_BID |
| c017 | MIX4-ITTI | 0.6 | NO_BID | NO_BID | 94.08; 0/2 | NO_BID | NO_BID |
| c018 | MIX4-ITIT | 0.6 | NO_BID | NO_BID | NO_BID | NO_BID | NO_BID |
| c019 | MIX4-ITII | 0.6 | NO_BID | 87.21; 2/2 | NO_BID | 87.21; 2/2 | 87.21; 2/2 |
| c020 | MIX4-IITT | 0.6 | NO_BID | NO_BID | NO_BID | NO_BID | NO_BID |
| c021 | MIX4-IITI | 0.6 | NO_BID | NO_BID | NO_BID | NO_BID | NO_BID |
| c022 | MIX4-IIIT | 0.6 | NO_BID | NO_BID | NO_BID | NO_BID | NO_BID |

The serious subset was predeclared, not selected from these outcomes. It uses 512 starts, 1,500 iterations and 32 search queries. Search/bank seeds differ from screening, so this is not a pure budget ablation. Only c023 is a fully paired serious mixed case: ARGOS improves84.8243 versus fixed probing 85.3125, and both confirm twice. Its local winner appears in batch4. Early stopping saves16 queries but keeps85.3125. V3-only and simulator-only return no bid.

At c024 only V3-only completed before stopping; it failed QoS (maxPj=0.7222652) and is not a paired comparison. Its bank is complete and preserved. The remaining serious cases were not executed.

| Case | Workload | U | V3-only + validation | V3 + fixed probing | Simulator-only | ARGOS fixed | ARGOS early |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c023 | MIX4-TTII | 0.6 | NO_BID | 85.31; 2/2 | NO_BID | 84.82; 2/2 | 85.31; 2/2 |
| c024 | MIX4-IITT | 0.6 | NO_BID | Not run: user stop | Not run: user stop | Not run: user stop | Not run: user stop |
| c025 | MIX4-ITTT | 0.6 | Not run: user stop | Not run: user stop | Not run: user stop | Not run: user stop | Not run: user stop |
| c026 | MIX4-TTTI | 0.6 | Not run: user stop | Not run: user stop | Not run: user stop | Not run: user stop | Not run: user stop |
| c027 | MIX4-TIII | 0.6 | Not run: user stop | Not run: user stop | Not run: user stop | Not run: user stop | Not run: user stop |
| c028 | MIX4-IIIT | 0.6 | Not run: user stop | Not run: user stop | Not run: user stop | Not run: user stop | Not run: user stop |

Full mixed results and evidence: [PHASE2_REVIEW.md](campaign_v2_results/PHASE2_REVIEW.md).

## F. Historical V4

All eight historical V4 cases were declared but **not executed**. They are composition-plus-QoS stress cases, not clean composition-only tests. The named generator was unavailable; the user approved the pinned eight INIs and composition/QoS manifest as authority. No V4 performance or J-generalization result is claimed.

## G. Structural J

The six J3/J5/J6/J8 structural cases were **not executed**. No variable-J feasibility or generalization conclusion follows from this campaign. J4 bounds were [0.15,0.45]; other declared J bounds were [0.6/J,1.8/J]. The numerical weight-transform regression across J values establishes implementation checks, not simulator success.

## H. Optional repeated-profile tests

Not declared or executed. No repeated-profile or provenance-unsupported unseen-profile generalization claim.

## I. Operating-condition tests and overall coverage

The four additional operating cases were **not executed**. N=500/U=0.7 was classified as interpolation-like, N=1500/U=0.9 as extrapolation-like relative to training N/U features. These labels are provenance labels, not measured predictive performance. All original controls above were at N=1000.

| Phase | Completed | Declared | Disposition |
| --- | --- | --- | --- |
| 0 | 5 | 5 | Complete |
| 1 | 40 | 40 | Complete |
| 2 | 76 | 100 | Closed early by user; remaining cases not run |
| 3 | 0 | 40 | Closed early by user; remaining cases not run |
| 4 | 0 | 30 | Closed early by user; remaining cases not run |
| 5 | 0 | 12 | Closed early by user; remaining cases not run |

All declared case identities and allocations, including unexecuted cases, are retained in [campaign_cases.csv](campaign_v2_results/campaign_cases.csv).

## J. V3 prediction error

Residuals are actual minus predicted. Across the fourteen selected V3-only screening endpoints: p90 mean+0.2036733/MAE0.2038846; maxPj mean+0.4808448/MAE0.4912344; objective mean/MAE+20.7931835. Eleven fail QoS, four fail tracking, and one fails both. These are large optimistic errors at evaluated selected points, not unbiased whole-domain accuracy estimates.

All p90, per-job Pj, maxPj and objective residual summaries by tier/category/method/source/J are in [prediction_error_summary.csv](campaign_v2_results/prediction_error_summary.csv). [ANALYSIS_SUPPLEMENT.md](campaign_v2_results/ANALYSIS_SUPPLEMENT.md) separates search/confirmation and deduplicates physical executions after retaining available predictions. Simulator-only has no V3 predictions. Shared observations are not extra independent samples.

## K. Winner sources and ancestry

Original ARGOS fixed winners: two V3 endpoint representatives(c001/c003), two intermediate-snapshot representatives(c005/c007), and two local refinements(c002/c004). c002's local winner descends from a V3 endpoint at iteration 1500 and improves the best qualified initial objective89.1171 to 73.0132. c004's local winner descends from an independent point. Both contexts already had qualified initial V3 representatives; local winning paths do not prove refinement was necessary for initial feasibility.

The two successful W2 ARGOS selections were snapshots at iterations 150 and 100, with no improvement over fixed probing. c023's serious mixed winner is local and improves the initial85.3125 to 84.8243. Independent exploration can contribute useful ancestry, but the completed original ARGOS cases do not demonstrate a necessary independent rescue after all initial V3 representatives failed. Source counts and traced mechanisms are in [winner_sources.csv](campaign_v2_results/winner_sources.csv) and [PAIRED_INTERPRETATION.md](campaign_v2_results/PAIRED_INTERPRETATION.md).

## L. Efficiency and query/physical accounting

Across all completed methods, including smoke: **1,984 logical search queries + 102 logical confirmations = 2,086 logical evaluations**, served by **1,166 unique physical evaluations** and **920 cache hits**. Recorded physical subprocess-duration sum is 18376.334 seconds; it is not elapsed wall time. Logical time simulates FIFO scheduling of recorded durations on four workers, charging each V3 method the full bank optimization duration. Recorded component timings, physical batch times and per-method completion data remain in the CSVs; elapsed monitoring gaps and c024's contaminated bank timer preclude a clean whole-session throughput comparison.

Original ARGOS early stopping uses 168 versus 256 queries, saving88(34.375%). It preserves all six qualified bids and matches full-budget objective in five, but loses2.0049 objective units at c004. Across the nine fully paired serious contexts, including c023, it saves104 of 288 queries (36.1111%) and misses later improvements at c004/c023. Screening has no savings with its two-batch cap. First feasibility counts all queries launched through the completed first feasible batch, not only the first successful candidate. Full query budgets, batches, first feasibility and timings are in [campaign_results.csv](campaign_v2_results/campaign_results.csv) and [early_stop_comparison.csv](campaign_v2_results/early_stop_comparison.csv).

## M. Confirmation and finite-horizon evidence

Original-workload search-qualified/both-confirmed counts: V3-only 4/2; fixed probing 6/5; simulator-only 4/4; ARGOS fixed 6/5; ARGOS early 6/5. These are bids across eight contexts, not confidence estimates. All original W1 returned bids pass both confirmations, while W2 includes partial and zero-confirmation outcomes.

Original W1 has 22 unique physical confirmations, all qualified, but66 of 88execution/job evidence records flag thresholds beyond the one-hour horizon. This finite-horizon success does not establish eventual job QoS. W2 has 8 unique physical confirmations,4 qualified, without horizon flags. Shared confirmations must not be multiplied into independent replicates. Reported Pj is authoritative; reconstructed Pj is validation only. Minimum one observation per job is evidence qualification, not established statistical reliability. Unfinished jobs and horizon flags are retained.

Every candidate confirmation, per-job observation count, unfinished count and horizon flag is saved in [campaign_confirmations.csv](campaign_v2_results/campaign_confirmations.csv), with selected-point evidence also in the phase reviews. The full raw simulator traces remain locally under the campaign cache.

## N. SA baseline

The unchanged pinned SA implementation was not executed: iteration-dependent scenario seeds, a different tracking-cost expression and unconditional wandb integration failed the matched-protocol compatibility gate. No adapted-SA result is claimed. Source evidence is retained in `configs/campaigns/sa_compatibility_v1.json`.

## O. Every failure, software issue, and stopping decision

The completed v2 records contain **70 NO_BID method outcomes and 10 confirmation-failure method outcomes**, with no recorded invalid execution or infrastructure-failure entry. Every entry is listed below and in [campaign_failures.csv](campaign_v2_results/campaign_failures.csv). The final raw audit **PASS** verified all 121 completed methods against 1,166 unique physical evidence records and confirmed that reserved seeds were not used; see [FINAL_AUDIT.json](campaign_v2_results/FINAL_AUDIT.json). Unexecuted cases are not included as failures.

V1 stopped on a genuine contract failure before any serious FlexDC evaluation: its unbracketed Newton weight transform produced four0.15 weights summing0.60. The user authorized the separate v0.3.0 correction: bracketed bisection with an implicit first derivative, unchanged domain tolerance, and raw bank persistence before region extraction. Pinned source/model and v1 results remain preserved. Full validation: 176 tests passed/1 CUDA skip, lint/format/doctor/provenance gates passed, and the full 1500-iteration regression passed. See [the v1 stop report](CONTROLLED_CAMPAIGN_V1_STOP.md).

Resume/report helper issues were corrected without altering scientific results: a regression-test metadata field, a report column name/deduplication detail, and JSON numeric export types. The user-requested stop preserved121completedmethod seals and 25 banks with no uncertain physical simulator attempt at the saved checkpoint. c024's bank and V3-only result finished before the stop. Later safe-pause controls were tested with fakes only; no new scientific execution followed. Final closure supersedes the earlier plan to resume locally. No outcome was filtered, no threshold relaxed, no seed changed, and no failed point relabeled as feasible.

| Case | Method | Kind | Reason |
| --- | --- | --- | --- |
| c002 | v3_only | NO_BID | V3_NO_SAFE_ENDPOINT |
| c004 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c005 | v3_only | CONFIRMATION_FAILURE | CONFIRMATION_PARTIAL_PASS |
| c005 | v3_fixed_probing | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c005 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c005 | argos_fixed_budget | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c005 | argos_early_stop | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c006 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c006 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c006 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c006 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c006 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c007 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c007 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c008 | v3_only | CONFIRMATION_FAILURE | CONFIRMATION_PARTIAL_PASS |
| c008 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c008 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c008 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c008 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c009 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c009 | v3_fixed_probing | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c009 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c009 | argos_fixed_budget | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c009 | argos_early_stop | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c010 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c010 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c010 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c010 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c010 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c011 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c011 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c012 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c012 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c012 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c012 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c012 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c013 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c013 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c014 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c014 | v3_fixed_probing | CONFIRMATION_FAILURE | CONFIRMATION_PARTIAL_PASS |
| c014 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c014 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c014 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c015 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c015 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c016 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c016 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c016 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c016 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c016 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c017 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c017 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c017 | simulator_only_adaptive | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c017 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c017 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c018 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c018 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c018 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c018 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c018 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c019 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c019 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c020 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c020 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c020 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c020 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c020 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c021 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c021 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c021 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c021 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c021 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c022 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c022 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c022 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c022 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c022 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c023 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c023 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c024 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |

## P. Research questions answered from the completed data

1. **V3 alone on original workloads?** Search-qualified 4/8; both-confirmed 2/8. It suffices at the two U=0.6 W1 controls, but is not consistently sufficient across the original domain.
2. **Regions useful when the V3 final point is wrong?** Yes descriptively: fixed probing/ARGOS rescue c002, c004, c007 while V3-only fails. Conversely c008 is V3-only's search-qualified point missed by region methods, and only one of two confirmations passes there. Screening gives further guided-probing successes despite 0/14 qualified selected endpoints.
3. **Adaptive versus fixed?** No consistent original advantage: equal 6/8 qualified and 5/8 both-confirmed, one objective win, one loss, four ties. Screening is worse for ARGOS by one bid. The one fully paired serious mixed case favors ARGOS by 0.4881 objective units. That single result does not establish broad superiority.
4. **Guidance versus simulator-only?** On original W1, ARGOS is better in objective in all four jointly successful contexts. Across originals it finds 6 versus 4 bids, but needs V3 computation. Simulator-only confirms all four returned bids. In screening it alone succeeds on c017, but that bid fails both confirmations. Guidance is useful, not uniformly dominant.
5. **Local refinement versus initial V3?** Local refinement wins two original contexts and c023; it improves measured objective there. Initial qualified candidates already existed, so this is not proof refinement was necessary to establish feasibility. Snapshot representatives explain both successful W2 ARGOS selections.
6. **Independent exploration rescue?** Independent ancestry contributes to c004's local winner, and fixed probing's c002 winner is independent. The original ARGOS results do not demonstrate a necessary independent rescue after all initial guided candidates fail. Avoid stronger causal claims without ablations.
7. **W1 versus W2?** ARGOS is 4/4 qualified and 4/4 both-confirmed on W1, versus 2/4 qualified and 1/4 both-confirmed on W2. The short-job cases are the principal demonstrated weakness.
8. **Unseen compositions of familiar profiles?** Completed screening: ARGOS 5/14 qualified, 4/14 both-confirmed; fixed 6/14 and 4/14; V3-only 0/14. c023 serious succeeds for probing/ARGOS. Serious suite coverage is incomplete, so generalization to all mixtures is unestablished.
9. **Varying J?** Not answered scientifically: structural and historical V4 simulator cases were not executed. Numerical J regression is not workload feasibility evidence.
10. **Early stopping?** Original 88/256 queries saved with one objective loss; all nine fully paired serious contexts 104/288 saved with two objective losses. It is not a free efficiency gain.
11. **Where are predictions wrong?** Mixed selected endpoints show strong optimism, especially maxPj(+0.4808 mean) and objective(+20.7932 mean). Original W2 confirmation fragility and individual original endpoint QoS errors are also documented. The per-job/category/source CSVs show distributions; these selected-point data are not an unbiased validation set.
12. **Fresh confirmation consistency?** W1 returned bids are consistent across the two fresh checks; W2 is not. Original ARGOS has 5/8 both-confirmed bids, fixed probing the same, V3-only 2/8 and simulator-only 4/8. Two confirmations and shared finite-horizon evidence do not establish statistical reliability.

## Q. Recommendation and final disposition

**Recommendation category: ARGOS needs a specific targeted improvement.** Do not expand this campaign under the current configuration. The supported targets are selected-endpoint coverage (c008's retained but unqueried V3 endpoint) and the short-job prediction/confirmation failures. The data do not prove that a particular fix will recover feasibility, and no fix or new experiment is implemented by this report. No optional learned extension is recommended automatically.

The evidence does not support either “all four original workloads are infeasible” or “ARGOS consistently beats fixed probing.” It supports strong finite-horizon W1 results, fragile W2 results, and mixed value from adaptation. The user has chosen to stop further testing. All existing results remain preserved, the unused allocations remain unused, and reopening execution requires a new explicit user request.

## Saved evidence and reproducibility

The report package contains the complete original/mixed result tables, all candidate selections/confirmation evidence, all failures, bank identity/runtime table, prediction summaries, source analysis, closure and audit receipts, and a SHA256 inventory. Archive text uses canonical LF line endings; the saved source evidence is unchanged. Raw banks, simulator inputs/output traces, per-method states and immutable completion seals remain in `runs/campaigns/controlled_development_v2/`. No `.env` file, trained model, reserved seed value or raw multi-gigabyte cache is copied into this documentation package.
