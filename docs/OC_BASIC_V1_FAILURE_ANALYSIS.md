# OC-basic v1: frozen 5/10 run forensics

This audit reads `argos_oc_basic_w2_n1000_u06_20260926T064500Z` without changing its artifacts or running FlexDC. The original experiment remains `COMPLETE_NO_TARGET_CANDIDATE`: no bid was selected and no held-out assessment was run. The new numerical files are in `runs/diagnostics/oc_basic_v1_forensics_20260926/diagnostics/`.

## Why the search stopped after 110 calls

The ten initial bids were each evaluated on all ten frozen arrival tables: **100/110 calls (90.9%)**. Their tenth result was saved at 1,161.2 seconds of cumulative search time. Batch 2 then generated four measured-anchor local bids and two independent bids, but the serial, complete-panel scheduler evaluated only `b02-measured-0-0`. Its ten calls ended at 1,258.8 seconds, past the 1,200-second soft target. The other **five generated batch-2 bids were never evaluated**. This was a budget-allocation and scheduling limitation, not an execution or evidence failure. Eleven complete panels consumed 1,258.9 seconds of search wall time; all 110 executions were valid.

The initial set had five V3 snapshots and five independent points. All five independent points passed 0/10, and two were extreme QoS-failing low-power points. The only measured local probe changed Pbar, R, and all four weights simultaneously with normalized radius 0.18; it passed 0/10. The V3-preferred first initial point passed only 1/10.

## Exact best measured candidate

`b01-initial-01` was a V3 snapshot from batch 1, with Pbar **0.4750245809555053**, R **0.0537046119570732**, and weights **[0.26021212339401245, 0.2505734860897064, 0.25269371271133423, 0.2365206927061081]**. Its mean canonical objective across all ten tables was **95.39346969897232**. Its archived ancestry is V3 start **369**, iteration **50**, cloud ID `v3-0050-0369`; no post-hoc V3 prediction was needed for this point.

It passed **5/10**. The signed scenario violation `g = max(p90/0.30 - 1, each Pj/0.10 - 1)` gives **g8 = 3.593980693**, g9 = **4.136935603**, and g10 = **4.833198249**. To reach eight passes it would need the three easiest failures repaired. Those are:

| Arrival seed | Active failure | Measured value | Signed g |
|---:|---|---:|---:|
| 2812640469 | tracking | p90 0.346 | 0.153333 |
| 2720817509 | Bloom | Pj 0.350232 | 2.502323 |
| 2381098110 | Bloom | Pj 0.459398 | 3.593981 |

Their positive signed violations sum to **6.249637**. The two harder Bloom failures were seed 1507332087 at **0.513694** (g 4.136936) and seed 2495920665 at **0.583320** (g 4.833198). These are large QoS misses, not near-0.10 boundary crossings. The five passing scenarios had p90 at most **0.250**, leaving at least **0.050** absolute tracking slack, although their margins can still change under a new bid. All required QoS evidence was present.

## Arrival-seed difficulty and complementarity

Across these eleven measured bids, seeds **2381098110, 2495920665, 2720817509, 1507332087, and 2812640469** had **zero** passing candidates. Seed 1841060571 had three passing candidates; each of the other four seeds passed by the winner had only one. The best measured signed violation for seed 2812640469 was just **0.016667**, while the minima for the other four never-passed seeds ranged from **0.516831** to **1.160299**.

No other measured candidate passed a seed that `b01-initial-01` failed. Pairwise union coverage therefore never exceeded **5/10**. This panel provides no measured complementary bid that solves one of the winner's missing tables. It also does not rule out useful unmeasured geometry. The higher-reserve `b01-initial-00` is only **0.1521** normalized domain distance from the winner and passed one seed already passed by the winner; it had just 1/10 support but a much lower **g8 = 1.076512**. Thus pass count and the distance to the 8/10 boundary rank the existing bids differently. The v1 ranking favored the 5/10 point and its first local probe, while a g8-focused rule would have given stronger attention to another measured region.

## V3 error pattern

For the best bid, V3 predicted p90 **0.063091** versus a ten-table mean actual p90 **0.215**, and predicted Bloom Pj **0.002737** versus mean actual **0.203661** and worst **0.583320**. The first four V3 snapshot bids all underpredicted mean Bloom Pj; a fifth high-power snapshot predicted essentially zero and measured zero, so this is not a universal V3 error over all geometry. The highest V3 predicted safety margin among the five snapshots belonged to the 5/10 winner (normalized predicted margin **0.790**), yet its g8 was worse than that of two 1/10 bids. V3 can guide plausible geometry, but its single context prediction did not rank ten-arrival robustness reliably in this small measured set. The one local probe lacked an archived V3 prediction; the diagnostic obtained it offline from the same pinned model without changing the historical search.

## Arrivals and timing

The winner's five failed tables averaged **12,631** generated Bloom jobs versus **12,460** for its five passing tables. Their average maximum Bloom arrivals in a 60-second window were **255.6** versus **247.6**. The four Bloom-failing tables were heavier on average, but the fifth failure was tracking and had a relatively low Bloom count. These ten descriptive comparisons do not establish causality or a reliable classifier; full arrival timing and queue behavior can matter.

Per-panel wall time was **83.8–164.2 seconds**. Summed panel wall time was **1,131.7 seconds** versus **1,258.9 seconds** total search time. The mean descriptive worker-utilization proxy, sum of ten individual simulator times divided by ten times panel wall, was **0.868**; the mean slowest-versus-median cell gap was **4.7 seconds**. Thus straggler idle time existed but was modest in most panels. The dominant measured waste was spending 100 calls before adaptive feedback, not a large measured straggler gap. A persistent cross-candidate scheduler and early rejection may improve throughput, but their gains must be measured rather than assumed.

## Interpretation and next step

**Verified:** v1's 20-minute protocol gave only one adaptive candidate a complete panel; the winner's g8 was far positive and four Bloom failures were large. **Interpretation:** better initial screening, an 8/10-aligned signed score, small structured probes, and early rejection are reasonable mechanisms to test. **Unknown:** whether any 8/10 bid exists within the legal domain. The saved eleven bids do not establish a nearby pocket. OC1.1 development can use these eleven panels as development evidence; later clean timing runs must not reuse simulator outcomes.
