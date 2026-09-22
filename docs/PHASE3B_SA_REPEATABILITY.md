# Phase 3B — SA search-path repeatability

Phase 3B reuses the completed Phase 3 optimization arrival schedule, runtime seed, starting candidates, simulator contract, grid, domain, objective, feasibility rules, and SA hyperparameters. It adds two matched fixed/varying search replicates. The primary factor is `sa_search_replicate`.

The setup freezes two deterministic replicate search roots and twenty new coupled assessment seeds before any new simulation runs. Fixed and varying trajectories within a workload/replicate share every search draw. Only the arrival policy differs. Replicate 1 is referenced from the completed Phase 3 directory and is never reoptimized.

The final assessment uses arrival seed equal to runtime seed for each fresh scenario. Panel A and Panel B contain ten seeds each. The proposed 8/10 scenario criterion remains diagnostic. Average metric feasibility requires mean p90 no greater than 0.30 and every mean Pj no greater than 0.10; it is reported separately from complete-scenario pass frequency.

The runner is resume-aware through the Phase 3 checkpoint engine. Re-running the exact command resumes incomplete trajectories and skips valid completed assessment cells. Scientific seeds, candidates, and draw identities are never replaced.
