# ARGOS episode argos_20260913T024050_620101Z

Status: **CONFIRMATION_2_OF_2_PASS**

Context: configs/workload/W1-train-qos3333.ini; N=1000, utilization=0.6, policy=AQA.

Search: 32 reserved calls, 4 completed batches, 4 workers.
Controller wall time: 118.446 s. See v3/search_timing.json for surrogate time.

Observed feasible candidates: 16. Independent confirmation: 2/2 pass.

Stop reason: configured search budget exhausted.

Frozen candidate: Pbar=0.366382867, R=0.219731927, weights=(0.44971099495887756, 0.16020098328590393, 0.16323329508304596, 0.22685472667217255).
Selection seed=20: p90=0.006, Pj=(0.0, 0.0, 0.0, 0.0), actual objective=62.603871176479714.

Confirmation seed 100020: SIMULATOR_OBSERVED_FEASIBLE; metrics=Metrics(mean_tracking=0.0017425, p90=0.006, pj=(0.0, 0.0, 0.0, 0.0), objective=62.60601356347972).

Confirmation seed 100021: SIMULATOR_OBSERVED_FEASIBLE; metrics=Metrics(mean_tracking=0.0016130555555555, p90=0.006, pj=(0.0, 0.0, 0.0, 0.0), objective=62.60316925481305).

A finite failed search does not establish mathematical infeasibility. Confirmation pass counts do not prove universal reliability. Search and confirmation observations remain separate. Full evidence and provenance are in the episode files.
