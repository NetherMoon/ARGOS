# ARGOS episode argos_20260913T023923_034870Z

Status: **CONFIRMATION_2_OF_2_PASS**

Context: configs/workload/W1-train-qos3333.ini; N=1000, utilization=0.6, policy=AQA.

Search: 8 reserved calls, 2 completed batches, 4 workers.
Controller wall time: 47.247 s. See v3/search_timing.json for surrogate time.

Observed feasible candidates: 4. Independent confirmation: 2/2 pass.

Stop reason: configured search budget exhausted.

Frozen candidate: Pbar=0.555265188, R=0.243270427, weights=(0.2869108021259308, 0.28310343623161316, 0.25492629408836365, 0.1750594675540924).
Selection seed=20: p90=0.158, Pj=(0.0, 0.0, 0.0, 0.0), actual objective=79.9174643198774.

Confirmation seed 100020: SIMULATOR_OBSERVED_FEASIBLE; metrics=Metrics(mean_tracking=0.0294580555555555, p90=0.168, pj=(0.00908455625436766, 0.0, 0.0, 0.0), objective=80.16839426362822).

Confirmation seed 100021: SIMULATOR_OBSERVED_FEASIBLE; metrics=Metrics(mean_tracking=0.0264563888888888, p90=0.152, pj=(0.00566973777462787, 0.0, 0.0, 0.0), objective=80.00171717902296).

A finite failed search does not establish mathematical infeasibility. Confirmation pass counts do not prove universal reliability. Search and confirmation observations remain separate. Full evidence and provenance are in the episode files.
