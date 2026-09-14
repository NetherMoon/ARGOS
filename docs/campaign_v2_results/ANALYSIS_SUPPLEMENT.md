# Descriptive analysis supplement

All values are computed from completed saved results. Engineering smoke is excluded. Screening is separate from serious development. Unique execution means one physical run, not an independent workload or initialization.

## category methods

| tier | category | method | contexts | qualified | both_confirmed | no_bid | search_calls | confirmation_passes | confirmation_runs | median_first_batch | mean_logical_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | 14 | 5 | 4 | 9 | 224 | 8 | 10 | 1 | 116.1 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | 14 | 5 | 4 | 9 | 224 | 8 | 10 | 1 | 116.1 |
| SCREENING | CLEAN_J4_COMPOSITION | simulator_only_adaptive | 14 | 1 | 0 | 13 | 224 | 0 | 2 | 1 | 71.62 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | 14 | 6 | 4 | 8 | 224 | 9 | 12 | 1 | 119 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_only | 14 | 0 | 0 | 14 | 14 | 0 | 0 | None | 50.3 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | 1 | 1 | 1 | 0 | 16 | 2 | 2 | 1 | 444.7 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | 1 | 1 | 1 | 0 | 32 | 2 | 2 | 1 | 507.4 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | simulator_only_adaptive | 1 | 0 | 0 | 1 | 32 | 0 | 0 | None | 126.8 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | 1 | 1 | 1 | 0 | 32 | 2 | 2 | 1 | 513.3 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_only | 2 | 0 | 0 | 2 | 2 | 0 | 0 | None | 1.986e+04 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | 4 | 4 | 4 | 0 | 72 | 8 | 8 | 1 | 434 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | 4 | 4 | 4 | 0 | 128 | 8 | 8 | 1 | 480.9 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | simulator_only_adaptive | 4 | 4 | 4 | 0 | 128 | 8 | 8 | 1 | 126.1 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | 4 | 4 | 4 | 0 | 128 | 8 | 8 | 1 | 481 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_only | 4 | 2 | 2 | 2 | 3 | 4 | 4 | 1 | 369.6 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | 4 | 2 | 1 | 2 | 96 | 2 | 4 | 1 | 472.9 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | 4 | 2 | 1 | 2 | 128 | 2 | 4 | 1 | 508.3 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | simulator_only_adaptive | 4 | 0 | 0 | 4 | 128 | 0 | 0 | None | 166.8 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | 4 | 2 | 1 | 2 | 128 | 2 | 4 | 1 | 520 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_only | 4 | 2 | 0 | 2 | 4 | 2 | 4 | 1 | 355.8 |

## category pairs

| tier | category | left | right | paired | left_only | right_only | both | left_better | right_better | ties | mean_delta | left_both_confirmed | right_both_confirmed | left_queries_saved |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | v3_only | 14 | ['c009', 'c011', 'c013', 'c015', 'c019'] | [] | 0 | 0 | 0 | 0 | None | 4 | 0 | -210 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | v3_fixed_probing | 14 | [] | ['c014'] | 5 | 0 | 0 | 5 | 0 | 4 | 4 | 0 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | simulator_only_adaptive | 14 | ['c009', 'c011', 'c013', 'c015', 'c019'] | ['c017'] | 0 | 0 | 0 | 0 | None | 4 | 0 | 0 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | argos_fixed_budget | 14 | [] | [] | 5 | 0 | 0 | 5 | 0 | 4 | 4 | 0 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | v3_only | 1 | ['c023'] | [] | 0 | 0 | 0 | 0 | None | 1 | 0 | -31 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | v3_fixed_probing | 1 | [] | [] | 1 | 1 | 0 | 0 | -0.4881 | 1 | 1 | 0 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | simulator_only_adaptive | 1 | ['c023'] | [] | 0 | 0 | 0 | 0 | None | 1 | 0 | 0 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | argos_fixed_budget | 1 | [] | [] | 1 | 0 | 1 | 0 | 0.4881 | 1 | 1 | 16 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | v3_only | 4 | ['c002', 'c004'] | [] | 2 | 0 | 0 | 2 | 0 | 4 | 2 | -125 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | v3_fixed_probing | 4 | [] | [] | 4 | 1 | 1 | 2 | 0.04229 | 4 | 4 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | simulator_only_adaptive | 4 | [] | [] | 4 | 4 | 0 | 0 | -12.74 | 4 | 4 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | argos_fixed_budget | 4 | [] | [] | 4 | 0 | 1 | 3 | 0.5012 | 4 | 4 | 56 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | v3_only | 4 | ['c007'] | ['c008'] | 1 | 1 | 0 | 0 | -0.287 | 1 | 0 | -124 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | v3_fixed_probing | 4 | [] | [] | 2 | 0 | 0 | 2 | 0 | 1 | 1 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | simulator_only_adaptive | 4 | ['c005', 'c007'] | [] | 0 | 0 | 0 | 0 | None | 1 | 0 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | argos_fixed_budget | 4 | [] | [] | 2 | 0 | 0 | 2 | 0 | 1 | 1 | 32 |

## unique physical prediction errors

| tier | category | phase | metric | unique_physical_observations | mean | mae | min | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SCREENING | CLEAN_J4_COMPOSITION | confirmation | max_pj | 12 | 0.04826 | 0.06621 | -0.05221 | 0.3528 |
| SCREENING | CLEAN_J4_COMPOSITION | confirmation | objective | 12 | 1.537 | 1.537 | 0.03142 | 7.457 |
| SCREENING | CLEAN_J4_COMPOSITION | confirmation | p90 | 12 | 0.149 | 0.1514 | -0.00777 | 0.3507 |
| SCREENING | CLEAN_J4_COMPOSITION | search | max_pj | 305 | 0.2466 | 0.2542 | -0.3784 | 0.9124 |
| SCREENING | CLEAN_J4_COMPOSITION | search | objective | 305 | 10.91 | 11.48 | -25.06 | 44.45 |
| SCREENING | CLEAN_J4_COMPOSITION | search | p90 | 305 | 0.07406 | 0.1517 | -0.9749 | 1.935 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | confirmation | max_pj | 4 | -0.03219 | 0.03219 | -0.1106 | -0.0008318 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | confirmation | objective | 4 | -0.287 | 0.7999 | -1.959 | 0.5207 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | confirmation | p90 | 4 | 0.07268 | 0.07268 | 0.007432 | 0.1309 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | search | max_pj | 50 | 0.1687 | 0.1783 | -0.1106 | 0.6566 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | search | objective | 50 | 10.93 | 11.11 | -1.904 | 36.91 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | search | p90 | 50 | 0.1077 | 0.1373 | -0.2948 | 0.7451 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | confirmation | max_pj | 14 | -0.01415 | 0.02446 | -0.05828 | 0.03666 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | confirmation | objective | 14 | -0.2672 | 0.4627 | -1.095 | 0.7135 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | confirmation | p90 | 14 | 0.0004436 | 0.0009368 | -0.001257 | 0.003326 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | search | max_pj | 186 | -0.01235 | 0.03106 | -0.3276 | 0.1885 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | search | objective | 186 | -0.7693 | 1.299 | -18.76 | 3.895 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | search | p90 | 186 | -0.04431 | 0.05915 | -1.841 | 0.3613 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | confirmation | max_pj | 8 | 0.003161 | 0.01327 | -0.01325 | 0.0236 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | confirmation | objective | 8 | 0.3673 | 0.4734 | -0.4244 | 1.253 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | confirmation | p90 | 8 | 0.1091 | 0.1091 | 0.02083 | 0.1977 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | search | max_pj | 191 | -0.0002526 | 0.02918 | -0.5623 | 0.4569 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | search | objective | 191 | -0.1972 | 2.061 | -16.69 | 14.23 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | search | p90 | 191 | -0.001975 | 0.06085 | -0.399 | 0.3296 |

## unique physical job evidence

| tier | category | phase | unique_execution_job_records | minimum_observation_count | zero_observation_records | one_observation_records | horizon_flagged_records | unfinished_sum |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SCREENING | CLEAN_J4_COMPOSITION | confirmation | 56 | 259 | 0 | 0 | 16 | 8863 |
| SCREENING | CLEAN_J4_COMPOSITION | search | 1880 | 267 | 0 | 0 | 707 | 3061649 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | confirmation | 16 | 284 | 0 | 0 | 4 | 1787 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | search | 288 | 301 | 0 | 0 | 73 | 239654 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | confirmation | 88 | 261 | 0 | 0 | 66 | 28508 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | search | 1112 | 252 | 0 | 0 | 834 | 413444 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | confirmation | 32 | 11960 | 0 | 0 | 0 | 5390 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | search | 1144 | 12093 | 0 | 0 | 0 | 3581571 |

## unique physical confirmation outcomes

| tier | category | unique_physical_confirmations | qualified |
| --- | --- | --- | --- |
| SCREENING | CLEAN_J4_COMPOSITION | 14 | 9 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | 4 | 4 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | 22 | 22 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | 8 | 4 |
