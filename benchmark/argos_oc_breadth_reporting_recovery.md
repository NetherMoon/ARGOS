# Completed original-16 breadth run: reporting recovery

The scientific run in `runs/experiments/argos_oc_original16_breadth_frozen_v1`
completed all 16 searches and held-out assessments under the unchanged frozen
protocol. Its original entry point then failed before aggregate reporting.
`scripts/finalize_argos_oc_breadth.py` reads and validates those saved results and
creates the aggregate report and ZIP without calling FlexDC.

Three corrections affect reporting only:

1. Pass the scientific root to `_aggregate` in the normal breadth runner.
2. Compare matched methods on their arrival table, runtime seed, and fixed grid.
   The target trace depends on each method's Pbar/R and need not match.
3. Derive the standard ARGOS baseline's context key from its workload, server
   count, and utilization columns. Its historical CSV has no `context` column.

The finalizer checks the original protocol hash, frozen source and seed ledgers,
all 16 complete contexts, each search-call count and selected 8/10 panel, all
30 held-out pairs per available bid, and matching fixed inputs across methods.
It permits only the three documented source corrections above. The frozen
scientific protocol and saved simulator outputs are not rewritten.
