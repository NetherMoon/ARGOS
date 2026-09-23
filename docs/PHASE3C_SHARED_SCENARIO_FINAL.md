# Phase 3C — shared-scenario candidate evaluation (SHELVED)

This prepared campaign was cancelled for the current research direction after the
Kerim meeting. Its source and completed setup smoke evidence are preserved. The
launcher now requires explicit acknowledgement before its long run can start.
The active workflow is [fixed-job-table ARGOS](ARGOS_FIXED_JOB_TABLE.md).

Phase 3C is the final simulated-annealing methodology experiment before ARGOS development.
It compares naive one-fresh-arrival evaluation against a shared three-arrival panel held for
ten transitions. Both methods use the same two frozen search-draw replicates, fixed runtime
seed `3609882979`, fixed grid, normal `peacsim.aqa_runtimepolicy.AQARuntimePolicy`, corrected
paper-consistent objective, authoritative feasibility, and `argos_v3_physical` domain.

The shared method evaluates the initial state on three scenarios, evaluates every proposal on
the current three-scenario panel, caches the accepted current score inside a block, and
reevaluates the current state when switching panels. Its nominal cost is 1,320 simulator calls
per trajectory. The naive control uses 401 calls per trajectory. Final assessment uses twenty
new coupled arrival/runtime seeds shared across every selected candidate.

All schedules and plans are frozen before the real integration smoke. The full user-run command
is resumable, executes independent trajectories concurrently, and keeps each trajectory itself
sequential.
