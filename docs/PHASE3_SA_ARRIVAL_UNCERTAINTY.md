# Phase 3 fixed-arrival versus arrival-uncertainty SA

This isolated experiment compares two paper-consistent SA trajectories per W2 workload. Both start at the same frozen candidate, use the `argos_v3_physical` domain, the normal V3/ARGOS `peacsim.aqa_runtimepolicy.AQARuntimePolicy`, one fixed grid segment, one fixed runtime seed, and matched predeclared search draws.

The fixed method generates one arrival table and supplies a fresh mutable copy to every simulator call. The varying method uses the real pinned FlexDC generator with its predeclared seed for each evaluation. Iteration zero is identical across the pair. There is one simulator evaluation per proposed candidate; no candidate averaging, reliability constraint, learned model, or assessment-driven selection is present.

The four long trajectories contain 400 transitions and 401 nominal evaluations each. Trajectories may run concurrently, but iterations within one trajectory are sequential. After optimization, the starting, fixed-SA selected, and varying-SA selected candidates are evaluated on the same ten fresh coupled seeds per workload. These sixty assessment calls cannot alter the selected candidates.

Each completed iteration is appended and fsynced before an atomic checkpoint advances the next-iteration position. The checkpoint contains current, best-scalar, best-feasible, best-violation, temperature, and exact schedule position. A valid completed simulator cell is reused after interruption. Retryable failures repeat only the same planned candidate and scenario.

The independent assessment pass count is descriptive: “passed X of 10 predeclared fresh assessment scenarios.” It is not a reliability probability.
