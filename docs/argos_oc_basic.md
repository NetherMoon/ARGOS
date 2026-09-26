# ARGOS-OC basic experiment

This branch is derived from the frozen original16 ARGOS source at
`3c4949fc4a2694daa243f077073875b9ffb45e21`. It adds an isolated
multi-arrival experiment and does not change the standard ARGOS controller,
V3 checkpoint, FlexDC, or the historical original16 result.

The first context is `W2-short-qos5_4.5_4_3.5`, N=1000, U=0.6, one hour,
normal AQA and the original fixed grid signal. The search panel reuses the
ten exact arrival seeds and initial-table hashes in the completed Phase 2B
10×3 characterization. Every complete candidate `(Pbar, R, four weights)`
is evaluated against all ten frozen tables with one fixed runtime seed.
Each candidate therefore costs ten FlexDC executions, even though the ten
workers may run concurrently.

The candidate cloud combines the verified historical V3 bank's endpoints
and trajectory snapshots with 256 independently sampled legal bids scored
by the same pinned V3 model. Ten diverse bids form the first measured round.
Later six-bid rounds reserve four bids for measured-anchor local refinement
and two for independent exploration. V3 predictions cannot veto all local
probes around a promising measured anchor. The ordinary legal coupled P/R
and bounded-simplex weight domain is enforced before every launch.

The finite search-panel target is at least 8/10 evidence-qualified passes.
Among candidates meeting it, selection minimizes the **mean canonical
objective over all ten tables**, including failed table outcomes. The run
stops at a 20-minute soft search target or 400 search executions at most.
It does not stop at the first 8/10 candidate. An 8/10 count is not a
reliability probability or a continuous feasible-region certificate.

Before search starts, the tool freezes 30 fresh arrival/runtime seed pairs
and records their deterministic selection root. If an eligible bid exists,
it is frozen before any of those tables are generated or evaluated. The
30 outcomes never feed back into search or candidate selection. If no bid
reaches 8/10, no selected bid or final assessment is manufactured.

`argos.oc_basic.runner` uses the existing `FixedEvaluator` and pinned
generator to create immutable initial tables, launch isolated FlexDC worker
processes, verify table/grid/evidence identities, and extract compact
per-scenario results. An execution error stops the experiment rather than
being counted as an infeasible bid. Completed cells are reused by exact
request identity on recovery; incomplete cells require review.

The entry point is `scripts/run_argos_oc_basic.py`. It needs the frozen
scientific checkout (`--scientific-root`) and completed V3 baseline
(`--v3-baseline`). It writes a new experiment under this branch's
`runs/experiments/` by default. The output contains seed/table manifests,
V3 candidate-cloud evidence, every simulator cell, search-panel and
held-out assessment CSVs, figures, timing, and a scope-aware comparison.
