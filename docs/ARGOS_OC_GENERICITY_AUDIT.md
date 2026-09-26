# ARGOS-OC genericity audit before original-16 breadth

The new active breadth path is `src/argos/oc_basic/generic.py` with
`breadth_plan.py` and `breadth_runner.py`. It uses configured job identities and
the complete simulator-reported Pj vector. No job name has a special search
priority. Historical `core.py`, `v1_1.py`, `runner.py`, and `runner_v1_1.py`
retain the W2 development protocol and its Bloom-specific choices so archived
experiments remain interpretable; they are not imported as proposal/selection
engines by the breadth runner. The breadth runner imports the historical runner
only for atomic file writing and seed-ledger discovery.

| Concern | Active breadth behavior | Remaining limitation |
|---|---|---|
| Job identities | `ordered_jobs` sets the ordered names; Pj length is checked on every evaluation. | Current V3 checkpoint and the original-16 benchmark have four jobs. |
| Bottleneck | Count of violated scenarios, total normalized severity, then configured order. Tracking and every QoS job compete under one rule. | This ranking is a frozen heuristic, not an optimality guarantee. |
| Weight probes | Any observed QoS job can receive legal weight from a donor selected by current measured Pj and available weight slack. | Weight shares influence dynamic AQA; they do not reserve fixed servers. |
| P/R probes | Symmetric legal Pbar and conditional-R offsets, plus combined weight/P/R probes for the two highest-ranked QoS constraints. | Probe scales and candidate quota are frozen for this study. |
| Scenario panel | `PanelRule(job_types, panel_size, required_passes)` supports 5/4 synthetic tests and the frozen 10/8 benchmark. | The real V3 adapter needs a compatible trained checkpoint for a different J. |
| Early rejection | Stop launching when passes + unmeasured scenarios < required passes. In-flight tasks are recorded. | A candidate must have a complete valid panel to be selected. |
| Final selection | Lowest mean canonical objective across *all ten* search tables among complete 8/10 candidates. | The 8/10 criterion is a finite-panel protocol, not a reliability certificate. |

The four workload names in `breadth_plan.py` identify the predeclared original-16
benchmark and mark the OC development context. They do not steer the controller.
The baseline comparison uses frozen pure-V3 and standard-ARGOS bids and does
not feed their outcomes into OC. One verified historical V3 bank per context is
reused; no historical simulator observation is reused as OC search truth.

The model-independent generic rules are synthetic-tested for J=2, 3, 4, and 5,
reordered names, finite-panel thresholds, legal transfers, and early rejection.
Only the original-16 four-job contexts have pinned simulator/V3 artifacts for
this benchmark. The long breadth experiment has **not** been run by Codex; its
frozen command is handed to the user separately.
