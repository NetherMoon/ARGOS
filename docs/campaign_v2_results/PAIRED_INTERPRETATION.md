# Paired development comparisons

| tier | left | right | matched_contexts | left_only_bid | right_only_bid | both_bid | neither_bid | mean_objective_left_minus_right_among_both_success | lower_objective_left | lower_objective_right | mean_search_calls_left_minus_right |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SCREENING | argos_fixed_budget | v3_only | 14 | ['c009', 'c011', 'c013', 'c015', 'c019'] | [] | [] | ['c010', 'c012', 'c014', 'c016', 'c017', 'c018', 'c020', 'c021', 'c022'] | None | 0 | 0 | 15 |
| SCREENING | v3_fixed_probing | v3_only | 14 | ['c009', 'c011', 'c013', 'c014', 'c015', 'c019'] | [] | [] | ['c010', 'c012', 'c016', 'c017', 'c018', 'c020', 'c021', 'c022'] | None | 0 | 0 | 15 |
| SCREENING | argos_fixed_budget | v3_fixed_probing | 14 | [] | ['c014'] | ['c009', 'c011', 'c013', 'c015', 'c019'] | ['c010', 'c012', 'c016', 'c017', 'c018', 'c020', 'c021', 'c022'] | 0 | 0 | 0 | 0 |
| SCREENING | argos_fixed_budget | simulator_only_adaptive | 14 | ['c009', 'c011', 'c013', 'c015', 'c019'] | ['c017'] | [] | ['c010', 'c012', 'c014', 'c016', 'c018', 'c020', 'c021', 'c022'] | None | 0 | 0 | 0 |
| SCREENING | argos_early_stop | argos_fixed_budget | 14 | [] | [] | ['c009', 'c011', 'c013', 'c015', 'c019'] | ['c010', 'c012', 'c014', 'c016', 'c017', 'c018', 'c020', 'c021', 'c022'] | 0 | 0 | 0 | 0 |
| SERIOUS_DEVELOPMENT | argos_fixed_budget | v3_only | 9 | ['c002', 'c004', 'c007', 'c023'] | ['c008'] | ['c001', 'c003', 'c005'] | ['c006'] | -0.09567 | 1 | 0 | 31.11 |
| SERIOUS_DEVELOPMENT | v3_fixed_probing | v3_only | 9 | ['c002', 'c004', 'c007', 'c023'] | ['c008'] | ['c001', 'c003', 'c005'] | ['c006'] | -0.09567 | 1 | 0 | 31.11 |
| SERIOUS_DEVELOPMENT | argos_fixed_budget | v3_fixed_probing | 9 | [] | [] | ['c001', 'c002', 'c003', 'c004', 'c005', 'c007', 'c023'] | ['c006', 'c008'] | -0.04557 | 2 | 1 | 0 |
| SERIOUS_DEVELOPMENT | argos_fixed_budget | simulator_only_adaptive | 9 | ['c005', 'c007', 'c023'] | [] | ['c001', 'c002', 'c003', 'c004'] | ['c006', 'c008'] | -12.74 | 4 | 0 | 0 |
| SERIOUS_DEVELOPMENT | argos_early_stop | argos_fixed_budget | 9 | [] | [] | ['c001', 'c002', 'c003', 'c004', 'c005', 'c007', 'c023'] | ['c006', 'c008'] | 0.3562 | 0 | 2 | -11.56 |

# ARGOS mechanisms

| case_id | category | v3_selected_endpoint_exists | v3_selected_endpoint_retained_in_pool | v3_selected_endpoint_queried_by_argos | winner_ancestral_source | winner_ancestral_candidate | winner_ancestral_iteration | qualified_initial_batch | qualified_initial_v3_representatives | qualified_local | qualified_independent | winner_source | winner_objective | winner_batch | best_qualified_initial_objective | best_qualified_v3_objective | improvement_over_best_initial | winner_origin_iteration | independent_success_without_qualified_v3_representative | local_success_after_unqualified_initial_batch |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c001 | ORIGINAL_W1 | True | True | True | V3 endpoint | v3-1500-0206 | 1500 | 3 | 3 | 5 | 2 | V3 endpoint | 63.91 | 1 | 63.91 | 63.91 | 0 | 1500 | False | False |
| c002 | ORIGINAL_W1 | False | None | None | V3 endpoint | v3-1500-0333 | 1500 | 3 | 2 | 11 | 3 | local | 73.01 | 2 | 89.12 | 89.12 | 16.1 | None | False | False |
| c003 | ORIGINAL_W1 | True | True | True | V3 endpoint | v3-1500-0383 | 1500 | 2 | 2 | 9 | 2 | V3 endpoint | 61.53 | 1 | 61.53 | 61.53 | 0 | 1500 | False | False |
| c004 | ORIGINAL_W1 | True | True | True | independent | b001-independent-0001 | None | 2 | 2 | 9 | 1 | local | 71.42 | 3 | 73.42 | 73.42 | 2.005 | None | False | False |
| c005 | ORIGINAL_W2 | True | True | False | V3 snapshot | v3-0150-0493 | 150 | 2 | 2 | 0 | 0 | V3 snapshot | 87.63 | 1 | 87.63 | 87.63 | 0 | 150 | False | False |
| c006 | ORIGINAL_W2 | True | True | False | None | None | None | 0 | 0 | 0 | 0 | None | None | None | None | None | None | None | False | False |
| c007 | ORIGINAL_W2 | True | True | False | V3 snapshot | v3-0100-0424 | 100 | 1 | 1 | 0 | 0 | V3 snapshot | 91.4 | 1 | 91.4 | 91.4 | 0 | 100 | False | False |
| c008 | ORIGINAL_W2 | True | True | False | None | None | None | 0 | 0 | 0 | 0 | None | None | None | None | None | None | None | False | False |
| c023 | CLEAN_J4_COMPOSITION | True | True | True | V3 snapshot | v3-0400-0035 | 400 | 1 | 1 | 1 | 0 | local | 84.82 | 4 | 85.31 | 85.31 | 0.4881 | None | False | False |

Lower objective is better. Objective differences use only matched contexts where both methods returned a qualified bid. Counts are descriptive; shared confirmations are not extra independent observations.
