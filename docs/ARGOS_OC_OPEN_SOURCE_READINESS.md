# ARGOS-OC open-source readiness

The active framework separates job-agnostic proposal and finite-panel rules
(`src/argos/oc_basic/generic.py`) from the original-16 experiment adapter
(`breadth_plan.py`, `breadth_runner.py`). `PanelRule` supplies configured job
identities, panel size, required passes, tracking limit, and QoS limit. Generic
logic uses every measured Pj, identifies constraints by count and severity,
and constructs legal weight, Pbar, conditional-R, and combined probes. It has
no semantic ResNet/GPT2/Llama/Bloom priority.

To apply the generic controller to another supported context, a user would
need an ordered workload/job configuration, a trained V3 checkpoint with the
same feature and output dimensions, a compatible legal P/R and weight domain,
a simulator adapter producing p90, ordered Pj, evidence counts, objective
inputs and immutable job-table hashes, and declared search/assessment seeds.
The current runnable breadth adapter is intentionally bound to the four
original V3-supported workloads, the pinned FlexDC worker and normal AQA,
one-hour fixed signal, and existing V3 candidate banks. It has not been
validated on arbitrary hardware, job counts, simulators, or workloads.

The original16 scientific source is unchanged. Historical OC development
modules retain their frozen W2 behavior as versioned provenance; the new
benchmark invokes the generic path. The benchmark freezes source hashes,
context contracts, an anchor-first 10-table search ledger, and 30 new matched
arrival/runtime pairs before any scientific run. Search is limited to 20 minutes
and 400 FlexDC calls per context, with at most 10 workers. An 8/10 search-panel
bid is descriptive and never a certified reliability claim. The 30-pair
assessment compares the exact frozen OC, V3, and standard ARGOS bids on the
same fresh pairs where each method has a bid.

The complete original-16 breadth run and its results remain pending user
execution. Revisit this document after that run to add measured evidence,
limitations, and release guidance.
