# Phase 2 descriptive review

Completed 76/100 method cases. Core 2b730c6a1831133b5fe5c0eedfa3d282465e0fa8; protocol SHA256 085c47daf4166beec9bdc7691f58792d7c36069fbf014d1db56155d59aeb11bf.

This review does not change search inputs. Lower objective is better. Objective differences are reported only when both matched methods returned qualified bids. No benchmark or statistical reliability claim.

## Category/method summaries

| category | method | completed | qualified | mean_objective_success_only | logical_search_calls | confirmation_passes | confirmation_executed | mean_logical_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CLEAN_J4_COMPOSITION | argos_early_stop | 15 | 6 | 90 | 240 | 10 | 12 | 138.1 |
| CLEAN_J4_COMPOSITION | argos_fixed_budget | 15 | 6 | 89.92 | 256 | 10 | 12 | 142.2 |
| CLEAN_J4_COMPOSITION | simulator_only_adaptive | 15 | 1 | 94.08 | 256 | 0 | 2 | 75.3 |
| CLEAN_J4_COMPOSITION | v3_fixed_probing | 15 | 7 | 89.91 | 256 | 11 | 14 | 145.3 |
| CLEAN_J4_COMPOSITION | v3_only | 16 | 0 | None | 16 | 0 | 0 | 2526 |

## Every planned method case

| case_id | workload | N | U | method | status | evidence_qualified_bid | actual_objective | first_feasible_batch | queries_launched_through_first_feasible_batch | logical_search_calls | confirmation_status | confirmation_passes | confirmation_executed | winner_source | winner_v3_origin | logical_total_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c009 | MIX4-TTTI | 1000 | 0.6 | v3_only | NO_BID | False | 90.95 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 56.74 |
| c009 | MIX4-TTTI | 1000 | 0.6 | v3_fixed_probing | DONE | True | 95.42 | 1 | 8 | 16 | CONFIRMATION_NONE_PASS | 0 | 2 | initial_v3_region_representative | V3 snapshot | 144.8 |
| c009 | MIX4-TTTI | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 59.99 |
| c009 | MIX4-TTTI | 1000 | 0.6 | argos_fixed_budget | DONE | True | 95.42 | 1 | 8 | 16 | CONFIRMATION_NONE_PASS | 0 | 2 | initial_v3_region_representative | V3 snapshot | 142.7 |
| c009 | MIX4-TTTI | 1000 | 0.6 | argos_early_stop | DONE | True | 95.42 | 1 | 8 | 16 | CONFIRMATION_NONE_PASS | 0 | 2 | initial_v3_region_representative | V3 snapshot | 142.7 |
| c010 | MIX4-TTIT | 1000 | 0.6 | v3_only | NO_BID | False | 89.7 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 49.99 |
| c010 | MIX4-TTIT | 1000 | 0.6 | v3_fixed_probing | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 98.65 |
| c010 | MIX4-TTIT | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 63 |
| c010 | MIX4-TTIT | 1000 | 0.6 | argos_fixed_budget | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 98.89 |
| c010 | MIX4-TTIT | 1000 | 0.6 | argos_early_stop | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 98.89 |
| c011 | MIX4-TTII | 1000 | 0.6 | v3_only | NO_BID | False | 92.33 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 50.63 |
| c011 | MIX4-TTII | 1000 | 0.6 | v3_fixed_probing | DONE | True | 94.06 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 130.1 |
| c011 | MIX4-TTII | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 68.26 |
| c011 | MIX4-TTII | 1000 | 0.6 | argos_fixed_budget | DONE | True | 94.06 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 129.7 |
| c011 | MIX4-TTII | 1000 | 0.6 | argos_early_stop | DONE | True | 94.06 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 129.7 |
| c012 | MIX4-TITT | 1000 | 0.6 | v3_only | NO_BID | False | 89.31 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 50.69 |
| c012 | MIX4-TITT | 1000 | 0.6 | v3_fixed_probing | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 104.8 |
| c012 | MIX4-TITT | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 66.74 |
| c012 | MIX4-TITT | 1000 | 0.6 | argos_fixed_budget | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 104.3 |
| c012 | MIX4-TITT | 1000 | 0.6 | argos_early_stop | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 104.3 |
| c013 | MIX4-TITI | 1000 | 0.6 | v3_only | NO_BID | False | 96.43 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 51.99 |
| c013 | MIX4-TITI | 1000 | 0.6 | v3_fixed_probing | DONE | True | 90.52 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 139.8 |
| c013 | MIX4-TITI | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 66.13 |
| c013 | MIX4-TITI | 1000 | 0.6 | argos_fixed_budget | DONE | True | 90.52 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 136.9 |
| c013 | MIX4-TITI | 1000 | 0.6 | argos_early_stop | DONE | True | 90.52 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 136.9 |
| c014 | MIX4-TIIT | 1000 | 0.6 | v3_only | NO_BID | False | 91.89 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 51.92 |
| c014 | MIX4-TIIT | 1000 | 0.6 | v3_fixed_probing | DONE | True | 89.38 | 2 | 16 | 16 | CONFIRMATION_PARTIAL_PASS | 1 | 2 | local_refinement | local | 138.6 |
| c014 | MIX4-TIIT | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 74.85 |
| c014 | MIX4-TIIT | 1000 | 0.6 | argos_fixed_budget | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 109.2 |
| c014 | MIX4-TIIT | 1000 | 0.6 | argos_early_stop | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 109.2 |
| c015 | MIX4-TIII | 1000 | 0.6 | v3_only | NO_BID | False | 87.11 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 52.43 |
| c015 | MIX4-TIII | 1000 | 0.6 | v3_fixed_probing | DONE | True | 87.49 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 140.9 |
| c015 | MIX4-TIII | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 75.97 |
| c015 | MIX4-TIII | 1000 | 0.6 | argos_fixed_budget | DONE | True | 87.49 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 140.4 |
| c015 | MIX4-TIII | 1000 | 0.6 | argos_early_stop | DONE | True | 87.49 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 140.4 |
| c016 | MIX4-ITTT | 1000 | 0.6 | v3_only | NO_BID | False | 87.44 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 52.22 |
| c016 | MIX4-ITTT | 1000 | 0.6 | v3_fixed_probing | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 106.2 |
| c016 | MIX4-ITTT | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 65.6 |
| c016 | MIX4-ITTT | 1000 | 0.6 | argos_fixed_budget | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 105 |
| c016 | MIX4-ITTT | 1000 | 0.6 | argos_early_stop | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 105 |
| c017 | MIX4-ITTI | 1000 | 0.6 | v3_only | NO_BID | False | 113.8 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 52.75 |
| c017 | MIX4-ITTI | 1000 | 0.6 | v3_fixed_probing | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 109.2 |
| c017 | MIX4-ITTI | 1000 | 0.6 | simulator_only_adaptive | DONE | True | 94.08 | 1 | 8 | 16 | CONFIRMATION_NONE_PASS | 0 | 2 | independent_exploration | independent | 92.6 |
| c017 | MIX4-ITTI | 1000 | 0.6 | argos_fixed_budget | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 107.7 |
| c017 | MIX4-ITTI | 1000 | 0.6 | argos_early_stop | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 107.7 |
| c018 | MIX4-ITIT | 1000 | 0.6 | v3_only | NO_BID | False | 101.4 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 52.15 |
| c018 | MIX4-ITIT | 1000 | 0.6 | v3_fixed_probing | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 116 |
| c018 | MIX4-ITIT | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 72.62 |
| c018 | MIX4-ITIT | 1000 | 0.6 | argos_fixed_budget | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 115.3 |
| c018 | MIX4-ITIT | 1000 | 0.6 | argos_early_stop | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 115.3 |
| c019 | MIX4-ITII | 1000 | 0.6 | v3_only | NO_BID | False | 85.33 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 52.43 |
| c019 | MIX4-ITII | 1000 | 0.6 | v3_fixed_probing | DONE | True | 87.21 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 140.9 |
| c019 | MIX4-ITII | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 72.93 |
| c019 | MIX4-ITII | 1000 | 0.6 | argos_fixed_budget | DONE | True | 87.21 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 139.4 |
| c019 | MIX4-ITII | 1000 | 0.6 | argos_early_stop | DONE | True | 87.21 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 139.4 |
| c020 | MIX4-IITT | 1000 | 0.6 | v3_only | NO_BID | False | 101.3 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 35.74 |
| c020 | MIX4-IITT | 1000 | 0.6 | v3_fixed_probing | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 75.95 |
| c020 | MIX4-IITT | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 70.73 |
| c020 | MIX4-IITT | 1000 | 0.6 | argos_fixed_budget | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 80.45 |
| c020 | MIX4-IITT | 1000 | 0.6 | argos_early_stop | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 80.45 |
| c021 | MIX4-IITI | 1000 | 0.6 | v3_only | NO_BID | False | 87.38 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 46.86 |
| c021 | MIX4-IITI | 1000 | 0.6 | v3_fixed_probing | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 110.1 |
| c021 | MIX4-IITI | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 72.57 |
| c021 | MIX4-IITI | 1000 | 0.6 | argos_fixed_budget | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 106.8 |
| c021 | MIX4-IITI | 1000 | 0.6 | argos_early_stop | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 106.8 |
| c022 | MIX4-IIIT | 1000 | 0.6 | v3_only | NO_BID | False | 88.63 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 47.68 |
| c022 | MIX4-IIIT | 1000 | 0.6 | v3_fixed_probing | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 110 |
| c022 | MIX4-IIIT | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 80.66 |
| c022 | MIX4-IIIT | 1000 | 0.6 | argos_fixed_budget | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 109.3 |
| c022 | MIX4-IIIT | 1000 | 0.6 | argos_early_stop | NO_BID | False | None | None | None | 16 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 109.3 |
| c023 | MIX4-TTII | 1000 | 0.6 | v3_only | NO_BID | False | 93.31 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 369.3 |
| c023 | MIX4-TTII | 1000 | 0.6 | v3_fixed_probing | DONE | True | 85.31 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 513.3 |
| c023 | MIX4-TTII | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 32 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 126.8 |
| c023 | MIX4-TTII | 1000 | 0.6 | argos_fixed_budget | DONE | True | 84.82 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | local_refinement | local | 507.4 |
| c023 | MIX4-TTII | 1000 | 0.6 | argos_early_stop | DONE | True | 85.31 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 444.7 |
| c024 | MIX4-IITT | 1000 | 0.6 | v3_only | NO_BID | False | 101.6 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 3.934e+04 |
| c024 | MIX4-IITT | 1000 | 0.6 | v3_fixed_probing | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c024 | MIX4-IITT | 1000 | 0.6 | simulator_only_adaptive | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c024 | MIX4-IITT | 1000 | 0.6 | argos_fixed_budget | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c024 | MIX4-IITT | 1000 | 0.6 | argos_early_stop | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c025 | MIX4-ITTT | 1000 | 0.6 | v3_only | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c025 | MIX4-ITTT | 1000 | 0.6 | v3_fixed_probing | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c025 | MIX4-ITTT | 1000 | 0.6 | simulator_only_adaptive | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c025 | MIX4-ITTT | 1000 | 0.6 | argos_fixed_budget | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c025 | MIX4-ITTT | 1000 | 0.6 | argos_early_stop | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c026 | MIX4-TTTI | 1000 | 0.6 | v3_only | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c026 | MIX4-TTTI | 1000 | 0.6 | v3_fixed_probing | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c026 | MIX4-TTTI | 1000 | 0.6 | simulator_only_adaptive | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c026 | MIX4-TTTI | 1000 | 0.6 | argos_fixed_budget | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c026 | MIX4-TTTI | 1000 | 0.6 | argos_early_stop | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c027 | MIX4-TIII | 1000 | 0.6 | v3_only | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c027 | MIX4-TIII | 1000 | 0.6 | v3_fixed_probing | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c027 | MIX4-TIII | 1000 | 0.6 | simulator_only_adaptive | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c027 | MIX4-TIII | 1000 | 0.6 | argos_fixed_budget | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c027 | MIX4-TIII | 1000 | 0.6 | argos_early_stop | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c028 | MIX4-IIIT | 1000 | 0.6 | v3_only | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c028 | MIX4-IIIT | 1000 | 0.6 | v3_fixed_probing | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c028 | MIX4-IIIT | 1000 | 0.6 | simulator_only_adaptive | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c028 | MIX4-IIIT | 1000 | 0.6 | argos_fixed_budget | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |
| c028 | MIX4-IIIT | 1000 | 0.6 | argos_early_stop | NOT_ATTEMPTED | False | None | None | None | None | None | None | None | None | None | None |

## Exact matched comparisons

| case | left | right | left_bid | right_bid | objective_left_minus_right | search_calls_saved_by_left |
| --- | --- | --- | --- | --- | --- | --- |
| c009 | argos_fixed_budget | v3_only | True | False | None | -15 |
| c010 | argos_fixed_budget | v3_only | False | False | None | -15 |
| c011 | argos_fixed_budget | v3_only | True | False | None | -15 |
| c012 | argos_fixed_budget | v3_only | False | False | None | -15 |
| c013 | argos_fixed_budget | v3_only | True | False | None | -15 |
| c014 | argos_fixed_budget | v3_only | False | False | None | -15 |
| c015 | argos_fixed_budget | v3_only | True | False | None | -15 |
| c016 | argos_fixed_budget | v3_only | False | False | None | -15 |
| c017 | argos_fixed_budget | v3_only | False | False | None | -15 |
| c018 | argos_fixed_budget | v3_only | False | False | None | -15 |
| c019 | argos_fixed_budget | v3_only | True | False | None | -15 |
| c020 | argos_fixed_budget | v3_only | False | False | None | -15 |
| c021 | argos_fixed_budget | v3_only | False | False | None | -15 |
| c022 | argos_fixed_budget | v3_only | False | False | None | -15 |
| c023 | argos_fixed_budget | v3_only | True | False | None | -31 |
| c009 | v3_fixed_probing | v3_only | True | False | None | -15 |
| c010 | v3_fixed_probing | v3_only | False | False | None | -15 |
| c011 | v3_fixed_probing | v3_only | True | False | None | -15 |
| c012 | v3_fixed_probing | v3_only | False | False | None | -15 |
| c013 | v3_fixed_probing | v3_only | True | False | None | -15 |
| c014 | v3_fixed_probing | v3_only | True | False | None | -15 |
| c015 | v3_fixed_probing | v3_only | True | False | None | -15 |
| c016 | v3_fixed_probing | v3_only | False | False | None | -15 |
| c017 | v3_fixed_probing | v3_only | False | False | None | -15 |
| c018 | v3_fixed_probing | v3_only | False | False | None | -15 |
| c019 | v3_fixed_probing | v3_only | True | False | None | -15 |
| c020 | v3_fixed_probing | v3_only | False | False | None | -15 |
| c021 | v3_fixed_probing | v3_only | False | False | None | -15 |
| c022 | v3_fixed_probing | v3_only | False | False | None | -15 |
| c023 | v3_fixed_probing | v3_only | True | False | None | -31 |
| c009 | argos_fixed_budget | v3_fixed_probing | True | True | 0 | 0 |
| c010 | argos_fixed_budget | v3_fixed_probing | False | False | None | 0 |
| c011 | argos_fixed_budget | v3_fixed_probing | True | True | 0 | 0 |
| c012 | argos_fixed_budget | v3_fixed_probing | False | False | None | 0 |
| c013 | argos_fixed_budget | v3_fixed_probing | True | True | 0 | 0 |
| c014 | argos_fixed_budget | v3_fixed_probing | False | True | None | 0 |
| c015 | argos_fixed_budget | v3_fixed_probing | True | True | 0 | 0 |
| c016 | argos_fixed_budget | v3_fixed_probing | False | False | None | 0 |
| c017 | argos_fixed_budget | v3_fixed_probing | False | False | None | 0 |
| c018 | argos_fixed_budget | v3_fixed_probing | False | False | None | 0 |
| c019 | argos_fixed_budget | v3_fixed_probing | True | True | 0 | 0 |
| c020 | argos_fixed_budget | v3_fixed_probing | False | False | None | 0 |
| c021 | argos_fixed_budget | v3_fixed_probing | False | False | None | 0 |
| c022 | argos_fixed_budget | v3_fixed_probing | False | False | None | 0 |
| c023 | argos_fixed_budget | v3_fixed_probing | True | True | -0.4881 | 0 |
| c009 | argos_fixed_budget | simulator_only_adaptive | True | False | None | 0 |
| c010 | argos_fixed_budget | simulator_only_adaptive | False | False | None | 0 |
| c011 | argos_fixed_budget | simulator_only_adaptive | True | False | None | 0 |
| c012 | argos_fixed_budget | simulator_only_adaptive | False | False | None | 0 |
| c013 | argos_fixed_budget | simulator_only_adaptive | True | False | None | 0 |
| c014 | argos_fixed_budget | simulator_only_adaptive | False | False | None | 0 |
| c015 | argos_fixed_budget | simulator_only_adaptive | True | False | None | 0 |
| c016 | argos_fixed_budget | simulator_only_adaptive | False | False | None | 0 |
| c017 | argos_fixed_budget | simulator_only_adaptive | False | True | None | 0 |
| c018 | argos_fixed_budget | simulator_only_adaptive | False | False | None | 0 |
| c019 | argos_fixed_budget | simulator_only_adaptive | True | False | None | 0 |
| c020 | argos_fixed_budget | simulator_only_adaptive | False | False | None | 0 |
| c021 | argos_fixed_budget | simulator_only_adaptive | False | False | None | 0 |
| c022 | argos_fixed_budget | simulator_only_adaptive | False | False | None | 0 |
| c023 | argos_fixed_budget | simulator_only_adaptive | True | False | None | 0 |
| c009 | argos_early_stop | argos_fixed_budget | True | True | 0 | 0 |
| c010 | argos_early_stop | argos_fixed_budget | False | False | None | 0 |
| c011 | argos_early_stop | argos_fixed_budget | True | True | 0 | 0 |
| c012 | argos_early_stop | argos_fixed_budget | False | False | None | 0 |
| c013 | argos_early_stop | argos_fixed_budget | True | True | 0 | 0 |
| c014 | argos_early_stop | argos_fixed_budget | False | False | None | 0 |
| c015 | argos_early_stop | argos_fixed_budget | True | True | 0 | 0 |
| c016 | argos_early_stop | argos_fixed_budget | False | False | None | 0 |
| c017 | argos_early_stop | argos_fixed_budget | False | False | None | 0 |
| c018 | argos_early_stop | argos_fixed_budget | False | False | None | 0 |
| c019 | argos_early_stop | argos_fixed_budget | True | True | 0 | 0 |
| c020 | argos_early_stop | argos_fixed_budget | False | False | None | 0 |
| c021 | argos_early_stop | argos_fixed_budget | False | False | None | 0 |
| c022 | argos_early_stop | argos_fixed_budget | False | False | None | 0 |
| c023 | argos_early_stop | argos_fixed_budget | True | True | 0.4881 | 16 |

## Selected candidate parameters

| case | method | result_status | qualified_bid | candidate | Pbar | R | weights |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c009 | v3_only | NO_BID | False | v3-0500-0084 | 0.3981 | 0.2385 | [0.15667161345481873, 0.24383419752120972, 0.150478333234787, 0.44901585578918457] |
| c009 | v3_fixed_probing | DONE | True | v3-0100-0049 | 0.5474 | 0.08681 | [0.23338690400123596, 0.24698340892791748, 0.22684180736541748, 0.2927878797054291] |
| c009 | argos_fixed_budget | DONE | True | v3-0100-0049 | 0.5474 | 0.08681 | [0.23338690400123596, 0.24698340892791748, 0.22684180736541748, 0.2927878797054291] |
| c009 | argos_early_stop | DONE | True | v3-0100-0049 | 0.5474 | 0.08681 | [0.23338690400123596, 0.24698340892791748, 0.22684180736541748, 0.2927878797054291] |
| c010 | v3_only | NO_BID | False | v3-0500-0123 | 0.3916 | 0.2341 | [0.15902592241764069, 0.2445315271615982, 0.4444867968559265, 0.1519557535648346] |
| c011 | v3_only | NO_BID | False | v3-0500-0113 | 0.4241 | 0.254 | [0.15249225497245789, 0.15103667974472046, 0.361712783575058, 0.33475828170776367] |
| c011 | v3_fixed_probing | DONE | True | v3-0100-0052 | 0.4969 | 0.03722 | [0.20449694991111755, 0.22778290510177612, 0.27894020080566406, 0.28877994418144226] |
| c011 | argos_fixed_budget | DONE | True | v3-0100-0052 | 0.4969 | 0.03722 | [0.20449694991111755, 0.22778290510177612, 0.27894020080566406, 0.28877994418144226] |
| c011 | argos_early_stop | DONE | True | v3-0100-0052 | 0.4969 | 0.03722 | [0.20449694991111755, 0.22778290510177612, 0.27894020080566406, 0.28877994418144226] |
| c012 | v3_only | NO_BID | False | v3-0500-0052 | 0.3858 | 0.2308 | [0.18006306886672974, 0.4478149116039276, 0.15512080490589142, 0.21700121462345123] |
| c013 | v3_only | NO_BID | False | v3-0500-0109 | 0.4305 | 0.258 | [0.150864377617836, 0.3709043562412262, 0.15038858354091644, 0.32784268260002136] |
| c013 | v3_fixed_probing | DONE | True | v3-0200-0045 | 0.5081 | 0.1013 | [0.18661819398403168, 0.30591997504234314, 0.21465034782886505, 0.29281148314476013] |
| c013 | argos_fixed_budget | DONE | True | v3-0200-0045 | 0.5081 | 0.1013 | [0.18661819398403168, 0.30591997504234314, 0.21465034782886505, 0.29281148314476013] |
| c013 | argos_early_stop | DONE | True | v3-0200-0045 | 0.5081 | 0.1013 | [0.18661819398403168, 0.30591997504234314, 0.21465034782886505, 0.29281148314476013] |
| c014 | v3_only | NO_BID | False | v3-0500-0046 | 0.4314 | 0.2582 | [0.15154427289962769, 0.35430076718330383, 0.34272634983062744, 0.15142859518527985] |
| c014 | v3_fixed_probing | DONE | True | fixed-b002-local-0001 | 0.4951 | 0.1028 | [0.26293052793951555, 0.30605177140624973, 0.26947943166762556, 0.16153826898660928] |
| c015 | v3_only | NO_BID | False | v3-0500-0095 | 0.4684 | 0.1466 | [0.15022556483745575, 0.28945186734199524, 0.2904736399650574, 0.26984894275665283] |
| c015 | v3_fixed_probing | DONE | True | v3-0100-0027 | 0.4782 | 0.08794 | [0.19950240850448608, 0.2714090049266815, 0.27243393659591675, 0.25665464997291565] |
| c015 | argos_fixed_budget | DONE | True | v3-0100-0027 | 0.4782 | 0.08794 | [0.19950240850448608, 0.2714090049266815, 0.27243393659591675, 0.25665464997291565] |
| c015 | argos_early_stop | DONE | True | v3-0100-0027 | 0.4782 | 0.08794 | [0.19950240850448608, 0.2714090049266815, 0.27243393659591675, 0.25665464997291565] |
| c016 | v3_only | NO_BID | False | v3-0500-0126 | 0.4135 | 0.2402 | [0.42581304907798767, 0.2457224726676941, 0.1611139476299286, 0.16735054552555084] |
| c017 | v3_only | NO_BID | False | v3-0500-0116 | 0.4949 | 0.2964 | [0.3034849762916565, 0.18725387752056122, 0.2479698807001114, 0.2612912654876709] |
| c017 | simulator_only_adaptive | DONE | True | b001-independent-0006 | 0.4871 | 0.04161 | [0.2893017499606391, 0.21208116941860516, 0.19964655670354925, 0.29897052391720647] |
| c018 | v3_only | NO_BID | False | v3-0500-0117 | 0.4526 | 0.2057 | [0.34995949268341064, 0.16096779704093933, 0.32020312547683716, 0.16886959969997406] |
| c019 | v3_only | NO_BID | False | v3-0500-0108 | 0.4679 | 0.1327 | [0.30000847578048706, 0.15421198308467865, 0.28533488512039185, 0.26044464111328125] |
| c019 | v3_fixed_probing | DONE | True | v3-0400-0027 | 0.4678 | 0.08075 | [0.2848581075668335, 0.19583827257156372, 0.2668505609035492, 0.2524530589580536] |
| c019 | argos_fixed_budget | DONE | True | v3-0400-0027 | 0.4678 | 0.08075 | [0.2848581075668335, 0.19583827257156372, 0.2668505609035492, 0.2524530589580536] |
| c019 | argos_early_stop | DONE | True | v3-0400-0027 | 0.4678 | 0.08075 | [0.2848581075668335, 0.19583827257156372, 0.2668505609035492, 0.2524530589580536] |
| c020 | v3_only | NO_BID | False | v3-0500-0022 | 0.4326 | 0.2431 | [0.3650442361831665, 0.33108553290367126, 0.15188919007778168, 0.15198104083538055] |
| c021 | v3_only | NO_BID | False | v3-0500-0057 | 0.4751 | 0.1442 | [0.2995959222316742, 0.2847971022129059, 0.15144972503185272, 0.264157235622406] |
| c022 | v3_only | NO_BID | False | v3-0500-0114 | 0.4756 | 0.1411 | [0.29901859164237976, 0.276431679725647, 0.27311816811561584, 0.15143156051635742] |
| c023 | v3_only | NO_BID | False | v3-1500-0295 | 0.4234 | 0.254 | [0.15045906603336334, 0.1504785716533661, 0.36342746019363403, 0.33563488721847534] |
| c023 | v3_fixed_probing | DONE | True | v3-0400-0035 | 0.5064 | 0.1413 | [0.2066788375377655, 0.20657038688659668, 0.30355456471443176, 0.28319618105888367] |
| c023 | argos_fixed_budget | DONE | True | b004-local-0000 | 0.4713 | 0.1049 | [0.19539326982156394, 0.19606762575610506, 0.29107948323465005, 0.3174596211876811] |
| c023 | argos_early_stop | DONE | True | v3-0400-0035 | 0.5064 | 0.1413 | [0.2066788375377655, 0.20657038688659668, 0.30355456471443176, 0.28319618105888367] |
| c024 | v3_only | NO_BID | False | v3-1500-0016 | 0.4329 | 0.2466 | [0.36308690905570984, 0.32660821080207825, 0.15104030072689056, 0.15926459431648254] |

## Per-job selected-point evidence

| case | method | result_status | job | Pj | n | unfinished | horizon_flag |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c009 | v3_only | NO_BID | Resnet.train.4 | 0.3691 | 1518 | 988 | False |
| c009 | v3_only | NO_BID | GPT2.train.4 | 0 | 321 | 172 | True |
| c009 | v3_only | NO_BID | Llama.train.4 | 0 | 301 | 220 | True |
| c009 | v3_only | NO_BID | Bloom.infer.4 | 0.7542 | 11957 | 1076 | False |
| c009 | v3_fixed_probing | DONE | Resnet.train.4 | 0 | 1518 | 30 | False |
| c009 | v3_fixed_probing | DONE | GPT2.train.4 | 0 | 321 | 163 | True |
| c009 | v3_fixed_probing | DONE | Llama.train.4 | 0 | 301 | 106 | True |
| c009 | v3_fixed_probing | DONE | Bloom.infer.4 | 0.07176 | 11957 | 170 | False |
| c009 | argos_fixed_budget | DONE | Resnet.train.4 | 0 | 1518 | 30 | False |
| c009 | argos_fixed_budget | DONE | GPT2.train.4 | 0 | 321 | 163 | True |
| c009 | argos_fixed_budget | DONE | Llama.train.4 | 0 | 301 | 106 | True |
| c009 | argos_fixed_budget | DONE | Bloom.infer.4 | 0.07176 | 11957 | 170 | False |
| c009 | argos_early_stop | DONE | Resnet.train.4 | 0 | 1518 | 30 | False |
| c009 | argos_early_stop | DONE | GPT2.train.4 | 0 | 321 | 163 | True |
| c009 | argos_early_stop | DONE | Llama.train.4 | 0 | 301 | 106 | True |
| c009 | argos_early_stop | DONE | Bloom.infer.4 | 0.07176 | 11957 | 170 | False |
| c010 | v3_only | NO_BID | Resnet.train.4 | 0.2687 | 1419 | 752 | False |
| c010 | v3_only | NO_BID | GPT2.train.4 | 0 | 312 | 146 | True |
| c010 | v3_only | NO_BID | Llama.infer.4 | 0.7978 | 14780 | 777 | False |
| c010 | v3_only | NO_BID | Bloom.train.4 | 0 | 348 | 348 | True |
| c011 | v3_only | NO_BID | Resnet.train.4 | 0.1538 | 1470 | 683 | False |
| c011 | v3_only | NO_BID | GPT2.train.4 | 0 | 301 | 182 | True |
| c011 | v3_only | NO_BID | Llama.infer.4 | 0.6055 | 14958 | 248 | False |
| c011 | v3_only | NO_BID | Bloom.infer.4 | 0.4167 | 11882 | 65 | False |
| c011 | v3_fixed_probing | DONE | Resnet.train.4 | 0 | 1470 | 404 | False |
| c011 | v3_fixed_probing | DONE | GPT2.train.4 | 0 | 301 | 95 | True |
| c011 | v3_fixed_probing | DONE | Llama.infer.4 | 0 | 14958 | 9 | False |
| c011 | v3_fixed_probing | DONE | Bloom.infer.4 | 0 | 11882 | 5 | False |
| c011 | argos_fixed_budget | DONE | Resnet.train.4 | 0 | 1470 | 404 | False |
| c011 | argos_fixed_budget | DONE | GPT2.train.4 | 0 | 301 | 95 | True |
| c011 | argos_fixed_budget | DONE | Llama.infer.4 | 0 | 14958 | 9 | False |
| c011 | argos_fixed_budget | DONE | Bloom.infer.4 | 0 | 11882 | 5 | False |
| c011 | argos_early_stop | DONE | Resnet.train.4 | 0 | 1470 | 404 | False |
| c011 | argos_early_stop | DONE | GPT2.train.4 | 0 | 301 | 95 | True |
| c011 | argos_early_stop | DONE | Llama.infer.4 | 0 | 14958 | 9 | False |
| c011 | argos_early_stop | DONE | Bloom.infer.4 | 0 | 11882 | 5 | False |
| c012 | v3_only | NO_BID | Resnet.train.4 | 0.3128 | 1446 | 782 | False |
| c012 | v3_only | NO_BID | GPT2.infer.4 | 0.7624 | 19251 | 232 | False |
| c012 | v3_only | NO_BID | Llama.train.4 | 0 | 299 | 299 | True |
| c012 | v3_only | NO_BID | Bloom.train.4 | 0 | 351 | 248 | True |
| c013 | v3_only | NO_BID | Resnet.train.4 | 0.2241 | 1514 | 790 | False |
| c013 | v3_only | NO_BID | GPT2.infer.4 | 0.6509 | 19029 | 287 | False |
| c013 | v3_only | NO_BID | Llama.train.4 | 0 | 282 | 165 | True |
| c013 | v3_only | NO_BID | Bloom.infer.4 | 0.4364 | 12070 | 177 | False |
| c013 | v3_fixed_probing | DONE | Resnet.train.4 | 0 | 1514 | 352 | False |
| c013 | v3_fixed_probing | DONE | GPT2.infer.4 | 0.06485 | 19029 | 10 | False |
| c013 | v3_fixed_probing | DONE | Llama.train.4 | 0 | 282 | 100 | True |
| c013 | v3_fixed_probing | DONE | Bloom.infer.4 | 0 | 12070 | 13 | False |
| c013 | argos_fixed_budget | DONE | Resnet.train.4 | 0 | 1514 | 352 | False |
| c013 | argos_fixed_budget | DONE | GPT2.infer.4 | 0.06485 | 19029 | 10 | False |
| c013 | argos_fixed_budget | DONE | Llama.train.4 | 0 | 282 | 100 | True |
| c013 | argos_fixed_budget | DONE | Bloom.infer.4 | 0 | 12070 | 13 | False |
| c013 | argos_early_stop | DONE | Resnet.train.4 | 0 | 1514 | 352 | False |
| c013 | argos_early_stop | DONE | GPT2.infer.4 | 0.06485 | 19029 | 10 | False |
| c013 | argos_early_stop | DONE | Llama.train.4 | 0 | 282 | 100 | True |
| c013 | argos_early_stop | DONE | Bloom.infer.4 | 0 | 12070 | 13 | False |
| c014 | v3_only | NO_BID | Resnet.train.4 | 0.1534 | 1494 | 687 | False |
| c014 | v3_only | NO_BID | GPT2.infer.4 | 0.5784 | 19215 | 34 | False |
| c014 | v3_only | NO_BID | Llama.infer.4 | 0.3896 | 14602 | 34 | False |
| c014 | v3_only | NO_BID | Bloom.train.4 | 0 | 386 | 300 | True |
| c014 | v3_fixed_probing | DONE | Resnet.train.4 | 0 | 1494 | 0 | False |
| c014 | v3_fixed_probing | DONE | GPT2.infer.4 | 0.09467 | 19215 | 149 | False |
| c014 | v3_fixed_probing | DONE | Llama.infer.4 | 0 | 14602 | 58 | False |
| c014 | v3_fixed_probing | DONE | Bloom.train.4 | 0 | 386 | 256 | True |
| c015 | v3_only | NO_BID | Resnet.train.4 | 0.1296 | 1382 | 582 | False |
| c015 | v3_only | NO_BID | GPT2.infer.4 | 0 | 19184 | 13 | False |
| c015 | v3_only | NO_BID | Llama.infer.4 | 0 | 14979 | 15 | False |
| c015 | v3_only | NO_BID | Bloom.infer.4 | 0 | 12070 | 3 | False |
| c015 | v3_fixed_probing | DONE | Resnet.train.4 | 0 | 1382 | 313 | False |
| c015 | v3_fixed_probing | DONE | GPT2.infer.4 | 0 | 19184 | 77 | False |
| c015 | v3_fixed_probing | DONE | Llama.infer.4 | 0 | 14979 | 31 | False |
| c015 | v3_fixed_probing | DONE | Bloom.infer.4 | 0 | 12070 | 51 | False |
| c015 | argos_fixed_budget | DONE | Resnet.train.4 | 0 | 1382 | 313 | False |
| c015 | argos_fixed_budget | DONE | GPT2.infer.4 | 0 | 19184 | 77 | False |
| c015 | argos_fixed_budget | DONE | Llama.infer.4 | 0 | 14979 | 31 | False |
| c015 | argos_fixed_budget | DONE | Bloom.infer.4 | 0 | 12070 | 51 | False |
| c015 | argos_early_stop | DONE | Resnet.train.4 | 0 | 1382 | 313 | False |
| c015 | argos_early_stop | DONE | GPT2.infer.4 | 0 | 19184 | 77 | False |
| c015 | argos_early_stop | DONE | Llama.infer.4 | 0 | 14979 | 31 | False |
| c015 | argos_early_stop | DONE | Bloom.infer.4 | 0 | 12070 | 51 | False |
| c016 | v3_only | NO_BID | Resnet.infer.4 | 0.8524 | 21360 | 1867 | False |
| c016 | v3_only | NO_BID | GPT2.train.4 | 0 | 302 | 142 | True |
| c016 | v3_only | NO_BID | Llama.train.4 | 0 | 289 | 255 | True |
| c016 | v3_only | NO_BID | Bloom.train.4 | 0 | 356 | 319 | True |
| c017 | v3_only | NO_BID | Resnet.infer.4 | 0.9192 | 21455 | 3597 | False |
| c017 | v3_only | NO_BID | GPT2.train.4 | 0 | 323 | 130 | True |
| c017 | v3_only | NO_BID | Llama.train.4 | 0 | 308 | 63 | True |
| c017 | v3_only | NO_BID | Bloom.infer.4 | 0.793 | 12252 | 940 | False |
| c017 | simulator_only_adaptive | DONE | Resnet.infer.4 | 0.07164 | 21455 | 178 | False |
| c017 | simulator_only_adaptive | DONE | GPT2.train.4 | 0 | 323 | 213 | True |
| c017 | simulator_only_adaptive | DONE | Llama.train.4 | 0 | 308 | 211 | True |
| c017 | simulator_only_adaptive | DONE | Bloom.infer.4 | 0 | 12252 | 5 | False |
| c018 | v3_only | NO_BID | Resnet.infer.4 | 0.6455 | 21502 | 3 | False |
| c018 | v3_only | NO_BID | GPT2.train.4 | 0 | 296 | 177 | True |
| c018 | v3_only | NO_BID | Llama.infer.4 | 0.5199 | 15035 | 2 | False |
| c018 | v3_only | NO_BID | Bloom.train.4 | 0 | 355 | 256 | True |
| c019 | v3_only | NO_BID | Resnet.infer.4 | 0 | 21292 | 4 | False |
| c019 | v3_only | NO_BID | GPT2.train.4 | 0 | 357 | 280 | True |
| c019 | v3_only | NO_BID | Llama.infer.4 | 0 | 14749 | 10 | False |
| c019 | v3_only | NO_BID | Bloom.infer.4 | 0 | 12130 | 3 | False |
| c019 | v3_fixed_probing | DONE | Resnet.infer.4 | 0 | 21292 | 13 | False |
| c019 | v3_fixed_probing | DONE | GPT2.train.4 | 0 | 357 | 229 | True |
| c019 | v3_fixed_probing | DONE | Llama.infer.4 | 0 | 14749 | 19 | False |
| c019 | v3_fixed_probing | DONE | Bloom.infer.4 | 0 | 12130 | 185 | False |
| c019 | argos_fixed_budget | DONE | Resnet.infer.4 | 0 | 21292 | 13 | False |
| c019 | argos_fixed_budget | DONE | GPT2.train.4 | 0 | 357 | 229 | True |
| c019 | argos_fixed_budget | DONE | Llama.infer.4 | 0 | 14749 | 19 | False |
| c019 | argos_fixed_budget | DONE | Bloom.infer.4 | 0 | 12130 | 185 | False |
| c019 | argos_early_stop | DONE | Resnet.infer.4 | 0 | 21292 | 13 | False |
| c019 | argos_early_stop | DONE | GPT2.train.4 | 0 | 357 | 229 | True |
| c019 | argos_early_stop | DONE | Llama.infer.4 | 0 | 14749 | 19 | False |
| c019 | argos_early_stop | DONE | Bloom.infer.4 | 0 | 12130 | 185 | False |
| c020 | v3_only | NO_BID | Resnet.infer.4 | 0.6312 | 21418 | 225 | False |
| c020 | v3_only | NO_BID | GPT2.infer.4 | 0.7099 | 19046 | 877 | False |
| c020 | v3_only | NO_BID | Llama.train.4 | 0 | 267 | 149 | True |
| c020 | v3_only | NO_BID | Bloom.train.4 | 0 | 329 | 245 | True |
| c021 | v3_only | NO_BID | Resnet.infer.4 | 0.01452 | 21560 | 11 | False |
| c021 | v3_only | NO_BID | GPT2.infer.4 | 0.07838 | 19062 | 2 | False |
| c021 | v3_only | NO_BID | Llama.train.4 | 0 | 286 | 191 | True |
| c021 | v3_only | NO_BID | Bloom.infer.4 | 0 | 12132 | 4 | False |
| c022 | v3_only | NO_BID | Resnet.infer.4 | 0 | 21463 | 0 | False |
| c022 | v3_only | NO_BID | GPT2.infer.4 | 0 | 19091 | 4 | False |
| c022 | v3_only | NO_BID | Llama.infer.4 | 0 | 14787 | 0 | False |
| c022 | v3_only | NO_BID | Bloom.train.4 | 0 | 353 | 280 | True |
| c023 | v3_only | NO_BID | Resnet.train.4 | 0.215 | 1522 | 754 | False |
| c023 | v3_only | NO_BID | GPT2.train.4 | 0 | 304 | 216 | True |
| c023 | v3_only | NO_BID | Llama.infer.4 | 0.5279 | 14581 | 28 | False |
| c023 | v3_only | NO_BID | Bloom.infer.4 | 0.4532 | 12107 | 414 | False |
| c023 | v3_fixed_probing | DONE | Resnet.train.4 | 0 | 1522 | 176 | False |
| c023 | v3_fixed_probing | DONE | GPT2.train.4 | 0 | 304 | 130 | True |
| c023 | v3_fixed_probing | DONE | Llama.infer.4 | 0.001372 | 14581 | 8 | False |
| c023 | v3_fixed_probing | DONE | Bloom.infer.4 | 0 | 12107 | 33 | False |
| c023 | argos_fixed_budget | DONE | Resnet.train.4 | 0 | 1522 | 459 | False |
| c023 | argos_fixed_budget | DONE | GPT2.train.4 | 0 | 304 | 154 | True |
| c023 | argos_fixed_budget | DONE | Llama.infer.4 | 0 | 14581 | 52 | False |
| c023 | argos_fixed_budget | DONE | Bloom.infer.4 | 0 | 12107 | 13 | False |
| c023 | argos_early_stop | DONE | Resnet.train.4 | 0 | 1522 | 176 | False |
| c023 | argos_early_stop | DONE | GPT2.train.4 | 0 | 304 | 130 | True |
| c023 | argos_early_stop | DONE | Llama.infer.4 | 0.001372 | 14581 | 8 | False |
| c023 | argos_early_stop | DONE | Bloom.infer.4 | 0 | 12107 | 33 | False |
| c024 | v3_only | NO_BID | Resnet.infer.4 | 0.6614 | 21518 | 300 | False |
| c024 | v3_only | NO_BID | GPT2.infer.4 | 0.7223 | 19390 | 1114 | False |
| c024 | v3_only | NO_BID | Llama.train.4 | 0 | 301 | 214 | True |
| c024 | v3_only | NO_BID | Bloom.train.4 | 0 | 349 | 216 | True |

## Prediction errors (actual minus predicted)

| tier | category | method | source_class | J | metric | logical_observations | unique_executions | mean | median | mean_absolute | p10 | p90 | min | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | max_pj | 56 | 56 | 0.1669 | 0.1433 | 0.1773 | -3.483e-13 | 0.3706 | -0.2538 | 0.8702 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | objective | 56 | 56 | 7.799 | 7.193 | 9.136 | 0.119 | 19.08 | -25.06 | 25.37 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | p90 | 56 | 56 | 0.005446 | -0.002429 | 0.1428 | -0.1907 | 0.2593 | -0.9234 | 0.9352 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | pj_0 | 56 | 56 | 0.1227 | 0 | 0.1388 | -0.00502 | 0.3923 | -0.2538 | 0.9278 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | pj_1 | 56 | 56 | 0.06077 | -2.771e-36 | 0.0633 | -7.888e-07 | 0.2615 | -0.04542 | 0.4018 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | pj_2 | 56 | 56 | 0.0519 | -3.761e-35 | 0.05395 | -1.059e-09 | 0.195 | -0.05747 | 0.5829 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | pj_3 | 56 | 56 | 0.04459 | -6.584e-34 | 0.06386 | -2.747e-07 | 0.1892 | -0.4307 | 0.8345 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | max_pj | 94 | 94 | 0.2433 | 0.1453 | 0.246 | -0.0003168 | 0.7278 | -0.03754 | 0.9124 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | objective | 94 | 94 | 11.19 | 8.109 | 11.21 | 0.4307 | 25.25 | -0.6959 | 44.45 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | p90 | 94 | 94 | 0.1399 | 0.05566 | 0.1562 | -0.001683 | 0.3847 | -0.2936 | 1.935 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | pj_0 | 94 | 94 | 0.1437 | -3.367e-35 | 0.1515 | -0.003541 | 0.5399 | -0.09695 | 0.9002 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | pj_1 | 94 | 94 | 0.08389 | -1.43e-20 | 0.08565 | -2.822e-07 | 0.2558 | -0.04472 | 0.9124 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | pj_2 | 94 | 94 | 0.06802 | -4.901e-20 | 0.07026 | -0.004799 | 0.2764 | -0.02533 | 0.8162 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | pj_3 | 94 | 94 | 0.07235 | -3.343e-19 | 0.07452 | -4.215e-06 | 0.2703 | -0.02671 | 0.8899 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | max_pj | 84 | 84 | 0.2778 | 0.232 | 0.2839 | -1.644e-09 | 0.6953 | -0.1184 | 0.8916 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | objective | 84 | 84 | 10.84 | 10.13 | 11.55 | 1.665 | 24.14 | -19.46 | 35.07 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | p90 | 84 | 84 | 0.03865 | 0.003661 | 0.1552 | -0.1912 | 0.3218 | -0.9749 | 0.727 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | pj_0 | 84 | 84 | 0.1765 | 0.02036 | 0.1937 | -0.0018 | 0.604 | -0.3103 | 0.8916 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | pj_1 | 84 | 84 | 0.08518 | -2.472e-24 | 0.08785 | -1.172e-07 | 0.3726 | -0.1119 | 0.7597 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | pj_2 | 84 | 84 | 0.08529 | -1.913e-28 | 0.08964 | -2.754e-07 | 0.3573 | -0.1738 | 0.6971 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | pj_3 | 84 | 84 | 0.0582 | -1.572e-20 | 0.07878 | -6.081e-05 | 0.262 | -0.4834 | 0.7261 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | max_pj | 56 | 56 | 0.1669 | 0.1433 | 0.1773 | -3.483e-13 | 0.3706 | -0.2538 | 0.8702 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | objective | 56 | 56 | 7.799 | 7.193 | 9.136 | 0.119 | 19.08 | -25.06 | 25.37 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | p90 | 56 | 56 | 0.005446 | -0.002429 | 0.1428 | -0.1907 | 0.2593 | -0.9234 | 0.9352 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | pj_0 | 56 | 56 | 0.1227 | 0 | 0.1388 | -0.00502 | 0.3923 | -0.2538 | 0.9278 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | pj_1 | 56 | 56 | 0.06077 | -2.771e-36 | 0.0633 | -7.888e-07 | 0.2615 | -0.04542 | 0.4018 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | pj_2 | 56 | 56 | 0.0519 | -3.761e-35 | 0.05395 | -1.059e-09 | 0.195 | -0.05747 | 0.5829 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | pj_3 | 56 | 56 | 0.04459 | -6.584e-34 | 0.06386 | -2.747e-07 | 0.1892 | -0.4307 | 0.8345 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | max_pj | 94 | 94 | 0.2433 | 0.1453 | 0.246 | -0.0003168 | 0.7278 | -0.03754 | 0.9124 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | objective | 94 | 94 | 11.19 | 8.109 | 11.21 | 0.4307 | 25.25 | -0.6959 | 44.45 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | p90 | 94 | 94 | 0.1399 | 0.05566 | 0.1562 | -0.001683 | 0.3847 | -0.2936 | 1.935 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | pj_0 | 94 | 94 | 0.1437 | -3.367e-35 | 0.1515 | -0.003541 | 0.5399 | -0.09695 | 0.9002 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | pj_1 | 94 | 94 | 0.08389 | -1.43e-20 | 0.08565 | -2.822e-07 | 0.2558 | -0.04472 | 0.9124 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | pj_2 | 94 | 94 | 0.06802 | -4.901e-20 | 0.07026 | -0.004799 | 0.2764 | -0.02533 | 0.8162 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | pj_3 | 94 | 94 | 0.07235 | -3.343e-19 | 0.07452 | -4.215e-06 | 0.2703 | -0.02671 | 0.8899 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | max_pj | 84 | 84 | 0.2778 | 0.232 | 0.2839 | -1.644e-09 | 0.6953 | -0.1184 | 0.8916 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | objective | 84 | 84 | 10.84 | 10.13 | 11.55 | 1.665 | 24.14 | -19.46 | 35.07 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | p90 | 84 | 84 | 0.03865 | 0.003661 | 0.1552 | -0.1912 | 0.3218 | -0.9749 | 0.727 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | pj_0 | 84 | 84 | 0.1765 | 0.02036 | 0.1937 | -0.0018 | 0.604 | -0.3103 | 0.8916 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | pj_1 | 84 | 84 | 0.08518 | -2.472e-24 | 0.08785 | -1.172e-07 | 0.3726 | -0.1119 | 0.7597 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | pj_2 | 84 | 84 | 0.08529 | -1.913e-28 | 0.08964 | -2.754e-07 | 0.3573 | -0.1738 | 0.6971 |
| SCREENING | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | pj_3 | 84 | 84 | 0.0582 | -1.572e-20 | 0.07878 | -6.081e-05 | 0.262 | -0.4834 | 0.7261 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | max_pj | 56 | 56 | 0.1669 | 0.1433 | 0.1773 | -3.483e-13 | 0.3706 | -0.2538 | 0.8702 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | objective | 56 | 56 | 7.799 | 7.193 | 9.136 | 0.119 | 19.08 | -25.06 | 25.37 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | p90 | 56 | 56 | 0.005446 | -0.002429 | 0.1428 | -0.1907 | 0.2593 | -0.9234 | 0.9352 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | pj_0 | 56 | 56 | 0.1227 | 0 | 0.1388 | -0.00502 | 0.3923 | -0.2538 | 0.9278 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | pj_1 | 56 | 56 | 0.06077 | -2.771e-36 | 0.0633 | -7.888e-07 | 0.2615 | -0.04542 | 0.4018 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | pj_2 | 56 | 56 | 0.0519 | -3.761e-35 | 0.05395 | -1.059e-09 | 0.195 | -0.05747 | 0.5829 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | pj_3 | 56 | 56 | 0.04459 | -6.584e-34 | 0.06386 | -2.747e-07 | 0.1892 | -0.4307 | 0.8345 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | max_pj | 94 | 94 | 0.2433 | 0.1453 | 0.246 | -0.0003168 | 0.7278 | -0.03754 | 0.9124 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | objective | 94 | 94 | 11.19 | 8.109 | 11.21 | 0.4307 | 25.25 | -0.6959 | 44.45 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | p90 | 94 | 94 | 0.1399 | 0.05566 | 0.1562 | -0.001683 | 0.3847 | -0.2936 | 1.935 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | pj_0 | 94 | 94 | 0.1437 | -3.367e-35 | 0.1515 | -0.003541 | 0.5399 | -0.09695 | 0.9002 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | pj_1 | 94 | 94 | 0.08389 | -1.43e-20 | 0.08565 | -2.822e-07 | 0.2558 | -0.04472 | 0.9124 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | pj_2 | 94 | 94 | 0.06802 | -4.901e-20 | 0.07026 | -0.004799 | 0.2764 | -0.02533 | 0.8162 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | pj_3 | 94 | 94 | 0.07235 | -3.343e-19 | 0.07452 | -4.215e-06 | 0.2703 | -0.02671 | 0.8899 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | max_pj | 86 | 86 | 0.2186 | 0.1722 | 0.2324 | -6.841e-07 | 0.604 | -0.3784 | 0.9005 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | objective | 86 | 86 | 10.28 | 9.757 | 10.7 | 0.6455 | 21.77 | -10.36 | 32.19 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | p90 | 86 | 86 | 0.08653 | 0.005879 | 0.1462 | -0.05366 | 0.3645 | -0.9127 | 1.017 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | pj_0 | 86 | 86 | 0.1358 | -1.896e-38 | 0.149 | -0.0001286 | 0.5156 | -0.3342 | 0.7994 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | pj_1 | 86 | 86 | 0.08121 | -8.132e-26 | 0.08128 | -7.718e-07 | 0.2917 | -0.002867 | 0.6588 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | pj_2 | 86 | 86 | 0.06472 | -1.25e-22 | 0.08775 | -0.0002079 | 0.3084 | -0.3784 | 0.647 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | pj_3 | 86 | 86 | 0.05853 | -2.584e-24 | 0.06781 | -3.159e-08 | 0.2073 | -0.2402 | 0.9005 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | max_pj | 14 | 14 | 0.4808 | 0.5844 | 0.4912 | -0.01021 | 0.7641 | -0.03754 | 0.8351 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | objective | 14 | 14 | 20.79 | 24.84 | 20.79 | 4.077 | 30.68 | 1.782 | 41.79 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | p90 | 14 | 14 | 0.2037 | 0.1695 | 0.2039 | 0.0009535 | 0.5042 | -0.001479 | 0.6971 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | pj_0 | 14 | 14 | 0.2992 | 0.2428 | 0.3119 | -0.02937 | 0.7096 | -0.03754 | 0.8351 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | pj_1 | 14 | 14 | 0.1776 | -1.122e-10 | 0.1867 | -0.01314 | 0.6197 | -0.04472 | 0.7328 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | pj_2 | 14 | 14 | 0.147 | -6.377e-10 | 0.1537 | -0.01129 | 0.5356 | -0.02533 | 0.7377 |
| SCREENING | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | pj_3 | 14 | 14 | 0.1549 | -6.43e-11 | 0.1651 | -0.02273 | 0.6208 | -0.02671 | 0.7331 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | max_pj | 4 | 4 | 0.174 | 0.1636 | 0.174 | 0.07689 | 0.2793 | 0.05832 | 0.3103 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | objective | 4 | 4 | 11.44 | 10.54 | 11.44 | 5.102 | 18.51 | 2.963 | 21.73 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | p90 | 4 | 4 | 0.09762 | 0.1263 | 0.1941 | -0.1319 | 0.3042 | -0.185 | 0.3229 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | pj_0 | 4 | 4 | 0.1371 | -1.467e-07 | 0.1372 | -7.868e-05 | 0.384 | -0.0001123 | 0.5485 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | pj_1 | 4 | 4 | -1.517e-07 | -1.876e-19 | 1.517e-07 | -4.249e-07 | -3.313e-27 | -6.069e-07 | -8.58e-38 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | pj_2 | 4 | 4 | 0.1594 | 0.1636 | 0.1594 | 0.03607 | 0.2793 | -2.94e-11 | 0.3103 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | independent_exploration | 4 | pj_3 | 4 | 4 | 0.1346 | 0.1524 | 0.1346 | 0.08182 | 0.1732 | 0.05832 | 0.1753 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | max_pj | 8 | 8 | 0.151 | 0.00027 | 0.1515 | -0.0008318 | 0.5033 | -0.0008318 | 0.5296 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | objective | 8 | 8 | 10.3 | 8.988 | 10.3 | 0.516 | 20.86 | 0.5052 | 27.27 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | p90 | 8 | 8 | 0.2051 | 0.1539 | 0.2051 | 0.009198 | 0.4124 | 0.003899 | 0.7451 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | pj_0 | 8 | 8 | 0.08765 | -3.071e-25 | 0.08765 | -4.965e-07 | 0.2371 | -4.965e-07 | 0.2584 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | pj_1 | 8 | 8 | -9.304e-09 | -2.063e-16 | 9.304e-09 | -2.237e-08 | -2.015e-35 | -7.432e-08 | 0 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | pj_2 | 8 | 8 | 0.151 | 0.0002704 | 0.1515 | -0.0008309 | 0.5033 | -0.0008309 | 0.5296 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | initial_v3_region_representative | 4 | pj_3 | 8 | 8 | 0.07835 | -2.404e-10 | 0.07898 | -0.0008318 | 0.2691 | -0.0008318 | 0.4286 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | max_pj | 6 | 6 | 0.2471 | 0.1464 | 0.2471 | -1.526e-08 | 0.5948 | -3.052e-08 | 0.6566 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | objective | 6 | 6 | 14.28 | 7.823 | 14.28 | 2.283 | 32.74 | 1.386 | 36.91 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | p90 | 6 | 6 | 0.08775 | 0.02366 | 0.1201 | -0.04846 | 0.2881 | -0.08261 | 0.4142 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | pj_0 | 6 | 6 | 0.06 | -6.385e-23 | 0.06013 | -0.0002035 | 0.1802 | -0.0004069 | 0.2141 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | pj_1 | 6 | 6 | -1.071e-10 | -1.145e-24 | 1.071e-10 | -3.213e-10 | -1.288e-29 | -6.423e-10 | 0 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | pj_2 | 6 | 6 | 0.2391 | 0.1223 | 0.2391 | -1.184e-08 | 0.5948 | -2.368e-08 | 0.6566 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_early_stop | local_refinement | 4 | pj_3 | 6 | 6 | 0.2236 | 0.1246 | 0.2236 | -1.526e-08 | 0.5462 | -3.052e-08 | 0.6702 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | max_pj | 8 | 8 | 0.1513 | 0.136 | 0.1513 | 0.0874 | 0.238 | 0.05832 | 0.3103 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | objective | 8 | 8 | 10.21 | 9.951 | 10.21 | 2.648 | 20.25 | 1.914 | 21.73 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | p90 | 8 | 8 | 0.0148 | -0.002827 | 0.1382 | -0.2179 | 0.2792 | -0.2948 | 0.3229 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | pj_0 | 8 | 8 | 0.12 | -2.351e-14 | 0.1201 | -3.441e-05 | 0.4529 | -0.0001123 | 0.5485 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | pj_1 | 8 | 8 | -8.629e-08 | -5.731e-14 | 8.629e-08 | -2.404e-07 | -1.108e-30 | -6.069e-07 | -8.58e-38 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | pj_2 | 8 | 8 | 0.1301 | 0.136 | 0.1301 | -8.821e-12 | 0.238 | -2.94e-11 | 0.3103 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | independent_exploration | 4 | pj_3 | 8 | 8 | 0.1306 | 0.1434 | 0.1306 | 0.08281 | 0.1703 | 0.05832 | 0.1753 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | max_pj | 6 | 6 | 0.2017 | 0.09419 | 0.2017 | -1.828e-19 | 0.5108 | -3.657e-19 | 0.5296 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | objective | 6 | 6 | 13.56 | 14.22 | 13.56 | 3.776 | 22.69 | 0.8102 | 27.27 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | p90 | 6 | 6 | 0.2308 | 0.1774 | 0.2308 | 0.007684 | 0.5074 | 0.003899 | 0.7451 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | pj_0 | 6 | 6 | 0.1169 | 0.1074 | 0.1169 | -2.482e-07 | 0.2432 | -4.965e-07 | 0.2584 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | pj_1 | 6 | 6 | -1.24e-08 | -1.033e-16 | 1.24e-08 | -3.721e-08 | -1.439e-35 | -7.432e-08 | 0 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | pj_2 | 6 | 6 | 0.2017 | 0.09419 | 0.2017 | -1.828e-19 | 0.5108 | -3.657e-19 | 0.5296 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | initial_v3_region_representative | 4 | pj_3 | 6 | 6 | 0.1047 | -7.729e-22 | 0.105 | -0.0004159 | 0.3147 | -0.0008318 | 0.4286 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | max_pj | 20 | 20 | 0.1229 | -1.853e-13 | 0.1596 | -0.07188 | 0.511 | -0.1106 | 0.6566 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | objective | 20 | 20 | 7.265 | 3.027 | 7.951 | -1.887 | 28.95 | -1.959 | 36.91 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | p90 | 20 | 20 | 0.08166 | 0.03826 | 0.1056 | -0.03379 | 0.2126 | -0.1096 | 0.456 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | pj_0 | 20 | 20 | 0.05762 | -1.893e-20 | 0.05767 | -3.197e-05 | 0.2223 | -0.0004069 | 0.3553 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | pj_1 | 20 | 20 | -1.527e-10 | -3.749e-20 | 1.527e-10 | -6.45e-11 | -1.444e-35 | -2.412e-09 | 0 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | pj_2 | 20 | 20 | 0.1038 | -8.174e-13 | 0.1322 | -0.05265 | 0.511 | -0.1106 | 0.6566 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | argos_fixed_budget | local_refinement | 4 | pj_3 | 20 | 20 | 0.0993 | -1.483e-12 | 0.1076 | -0.001717 | 0.4244 | -0.06757 | 0.6702 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | max_pj | 8 | 8 | 0.1513 | 0.136 | 0.1513 | 0.0874 | 0.238 | 0.05832 | 0.3103 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | objective | 8 | 8 | 10.21 | 9.951 | 10.21 | 2.648 | 20.25 | 1.914 | 21.73 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | p90 | 8 | 8 | 0.0148 | -0.002827 | 0.1382 | -0.2179 | 0.2792 | -0.2948 | 0.3229 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | pj_0 | 8 | 8 | 0.12 | -2.351e-14 | 0.1201 | -3.441e-05 | 0.4529 | -0.0001123 | 0.5485 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | pj_1 | 8 | 8 | -8.629e-08 | -5.731e-14 | 8.629e-08 | -2.404e-07 | -1.108e-30 | -6.069e-07 | -8.58e-38 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | pj_2 | 8 | 8 | 0.1301 | 0.136 | 0.1301 | -8.821e-12 | 0.238 | -2.94e-11 | 0.3103 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | independent_exploration | 4 | pj_3 | 8 | 8 | 0.1306 | 0.1434 | 0.1306 | 0.08281 | 0.1703 | 0.05832 | 0.1753 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | max_pj | 8 | 8 | 0.151 | 0.00027 | 0.1515 | -0.0008318 | 0.5033 | -0.0008318 | 0.5296 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | objective | 8 | 8 | 10.3 | 8.988 | 10.3 | 0.516 | 20.86 | 0.5052 | 27.27 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | p90 | 8 | 8 | 0.2051 | 0.1539 | 0.2051 | 0.009198 | 0.4124 | 0.003899 | 0.7451 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | pj_0 | 8 | 8 | 0.08765 | -3.071e-25 | 0.08765 | -4.965e-07 | 0.2371 | -4.965e-07 | 0.2584 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | pj_1 | 8 | 8 | -9.304e-09 | -2.063e-16 | 9.304e-09 | -2.237e-08 | -2.015e-35 | -7.432e-08 | 0 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | pj_2 | 8 | 8 | 0.151 | 0.0002704 | 0.1515 | -0.0008309 | 0.5033 | -0.0008309 | 0.5296 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | initial_v3_region_representative | 4 | pj_3 | 8 | 8 | 0.07835 | -2.404e-10 | 0.07898 | -0.0008318 | 0.2691 | -0.0008318 | 0.4286 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | max_pj | 18 | 18 | 0.1552 | 0.112 | 0.1552 | -5.965e-16 | 0.4081 | -0.0001257 | 0.46 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | objective | 18 | 18 | 11.82 | 8.957 | 11.82 | 1.188 | 24.08 | 0.6038 | 29.31 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | p90 | 18 | 18 | 0.1461 | 0.1024 | 0.147 | 0.0002064 | 0.3374 | -0.007332 | 0.5806 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | pj_0 | 18 | 18 | 0.107 | -2.153e-34 | 0.107 | -5.59e-06 | 0.3713 | -8.704e-05 | 0.4496 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | pj_1 | 18 | 18 | -1.933e-09 | -2.814e-15 | 1.933e-09 | -5.751e-09 | 0 | -1.795e-08 | 0 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | pj_2 | 18 | 18 | 0.141 | 0.06182 | 0.141 | -4.396e-11 | 0.4048 | -0.0001257 | 0.46 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_fixed_probing | local_refinement | 4 | pj_3 | 18 | 18 | 0.1067 | -2.203e-34 | 0.1147 | -0.005027 | 0.381 | -0.05849 | 0.4799 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | max_pj | 2 | 2 | 0.5624 | 0.5624 | 0.5624 | 0.506 | 0.6187 | 0.492 | 0.6328 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | objective | 2 | 2 | 29.49 | 29.49 | 29.49 | 27.71 | 31.26 | 27.27 | 31.7 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | p90 | 2 | 2 | 0.1684 | 0.1684 | 0.1684 | 0.08739 | 0.2495 | 0.06712 | 0.2697 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | pj_0 | 2 | 2 | 0.3934 | 0.3934 | 0.3934 | 0.2505 | 0.5362 | 0.2148 | 0.5719 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | pj_1 | 2 | 2 | 0.3176 | 0.3176 | 0.3176 | 0.06353 | 0.5717 | -1.108e-10 | 0.6353 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | pj_2 | 2 | 2 | 0.246 | 0.246 | 0.246 | 0.0492 | 0.4428 | -4.205e-09 | 0.492 |
| SERIOUS_DEVELOPMENT | CLEAN_J4_COMPOSITION | v3_only | v3_endpoint | 4 | pj_3 | 2 | 2 | 0.2143 | 0.2143 | 0.2143 | 0.04286 | 0.3857 | -7.05e-09 | 0.4286 |

Error summaries retain logical-method grouping. Reused physical observations are not independent samples.

## Every recorded failure

| case_id | method | kind | details |
| --- | --- | --- | --- |
| c009 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c009 | v3_fixed_probing | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c009 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c009 | argos_fixed_budget | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c009 | argos_early_stop | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c010 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c010 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c010 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c010 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c010 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c011 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c011 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c012 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c012 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c012 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c012 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c012 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c013 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c013 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c014 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c014 | v3_fixed_probing | CONFIRMATION_FAILURE | CONFIRMATION_PARTIAL_PASS |
| c014 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c014 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c014 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c015 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c015 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c016 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c016 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c016 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c016 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c016 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c017 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c017 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c017 | simulator_only_adaptive | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c017 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c017 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c018 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c018 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c018 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c018 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c018 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c019 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c019 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c020 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c020 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c020 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c020 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c020 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c021 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c021 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c021 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c021 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c021 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c022 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c022 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c022 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c022 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c022 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c023 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c023 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c024 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |

## Limitations

One search scenario and one initialization per context, two fresh confirmation scenarios, and a one-hour simulation horizon. Qualified evidence requires at least one observation per job; that is not proof of statistical reliability. Confirmation evidence is retained in campaign_confirmations.csv. Shared executions are not extra independent scenarios.
