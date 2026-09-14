# Phase 1 descriptive review

Completed 40/40 method cases. Core 2b730c6a1831133b5fe5c0eedfa3d282465e0fa8; protocol SHA256 085c47daf4166beec9bdc7691f58792d7c36069fbf014d1db56155d59aeb11bf.

This review does not change search inputs. Lower objective is better. Objective differences are reported only when both matched methods returned qualified bids. No benchmark or statistical reliability claim.

## Category/method summaries

| category | method | completed | qualified | mean_objective_success_only | logical_search_calls | confirmation_passes | confirmation_executed | mean_logical_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ORIGINAL_W1 | argos_early_stop | 4 | 4 | 67.97 | 72 | 8 | 8 | 434 |
| ORIGINAL_W1 | argos_fixed_budget | 4 | 4 | 67.47 | 128 | 8 | 8 | 480.9 |
| ORIGINAL_W1 | simulator_only_adaptive | 4 | 4 | 80.21 | 128 | 8 | 8 | 126.1 |
| ORIGINAL_W1 | v3_fixed_probing | 4 | 4 | 67.43 | 128 | 8 | 8 | 481 |
| ORIGINAL_W1 | v3_only | 4 | 2 | 62.72 | 3 | 4 | 4 | 369.6 |
| ORIGINAL_W2 | argos_early_stop | 4 | 2 | 89.52 | 96 | 2 | 4 | 472.9 |
| ORIGINAL_W2 | argos_fixed_budget | 4 | 2 | 89.52 | 128 | 2 | 4 | 508.3 |
| ORIGINAL_W2 | simulator_only_adaptive | 4 | 0 | None | 128 | 0 | 0 | 166.8 |
| ORIGINAL_W2 | v3_fixed_probing | 4 | 2 | 89.52 | 128 | 2 | 4 | 520 |
| ORIGINAL_W2 | v3_only | 4 | 2 | 91.71 | 4 | 2 | 4 | 355.8 |

## Every planned method case

| case_id | workload | N | U | method | status | evidence_qualified_bid | actual_objective | first_feasible_batch | queries_launched_through_first_feasible_batch | logical_search_calls | confirmation_status | confirmation_passes | confirmation_executed | winner_source | winner_v3_origin | logical_total_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c001 | W1-train-qos3333 | 1000 | 0.6 | v3_only | DONE | True | 63.91 | 1 | 1 | 1 | CONFIRMATION_ALL_PASS | 2 | 2 | v3_endpoint | V3 endpoint | 393.2 |
| c001 | W1-train-qos3333 | 1000 | 0.6 | v3_fixed_probing | DONE | True | 63.91 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 endpoint | 487 |
| c001 | W1-train-qos3333 | 1000 | 0.6 | simulator_only_adaptive | DONE | True | 87.07 | 3 | 24 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | independent_exploration | independent | 128.2 |
| c001 | W1-train-qos3333 | 1000 | 0.6 | argos_fixed_budget | DONE | True | 63.91 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 endpoint | 488.9 |
| c001 | W1-train-qos3333 | 1000 | 0.6 | argos_early_stop | DONE | True | 63.91 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 endpoint | 435.3 |
| c002 | W1-train-qos3333 | 1000 | 0.8 | v3_only | NO_BID | False | None | None | None | 0 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 368.5 |
| c002 | W1-train-qos3333 | 1000 | 0.8 | v3_fixed_probing | DONE | True | 78.36 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | independent_exploration | independent | 505.2 |
| c002 | W1-train-qos3333 | 1000 | 0.8 | simulator_only_adaptive | DONE | True | 75.33 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | local_refinement | local | 128.8 |
| c002 | W1-train-qos3333 | 1000 | 0.8 | argos_fixed_budget | DONE | True | 73.01 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | local_refinement | local | 504.3 |
| c002 | W1-train-qos3333 | 1000 | 0.8 | argos_early_stop | DONE | True | 73.01 | 1 | 8 | 24 | CONFIRMATION_ALL_PASS | 2 | 2 | local_refinement | local | 476.6 |
| c003 | W1-train-qos4444 | 1000 | 0.6 | v3_only | DONE | True | 61.53 | 1 | 1 | 1 | CONFIRMATION_ALL_PASS | 2 | 2 | v3_endpoint | V3 endpoint | 362.2 |
| c003 | W1-train-qos4444 | 1000 | 0.6 | v3_fixed_probing | DONE | True | 61.53 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 endpoint | 456.9 |
| c003 | W1-train-qos4444 | 1000 | 0.6 | simulator_only_adaptive | DONE | True | 76.88 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | local_refinement | local | 118.4 |
| c003 | W1-train-qos4444 | 1000 | 0.6 | argos_fixed_budget | DONE | True | 61.53 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 endpoint | 456 |
| c003 | W1-train-qos4444 | 1000 | 0.6 | argos_early_stop | DONE | True | 61.53 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 endpoint | 403.7 |
| c004 | W1-train-qos4444 | 1000 | 0.8 | v3_only | NO_BID | False | 65.22 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 354.5 |
| c004 | W1-train-qos4444 | 1000 | 0.8 | v3_fixed_probing | DONE | True | 65.9 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | local_refinement | local | 474.9 |
| c004 | W1-train-qos4444 | 1000 | 0.8 | simulator_only_adaptive | DONE | True | 81.56 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | independent_exploration | independent | 129.1 |
| c004 | W1-train-qos4444 | 1000 | 0.8 | argos_fixed_budget | DONE | True | 71.42 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | local_refinement | local | 474.3 |
| c004 | W1-train-qos4444 | 1000 | 0.8 | argos_early_stop | DONE | True | 73.42 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 420.4 |
| c005 | W2-short-qos5_4.5_4_3.5 | 1000 | 0.6 | v3_only | DONE | True | 87.92 | 1 | 1 | 1 | CONFIRMATION_PARTIAL_PASS | 1 | 2 | v3_endpoint | V3 endpoint | 353.1 |
| c005 | W2-short-qos5_4.5_4_3.5 | 1000 | 0.6 | v3_fixed_probing | DONE | True | 87.63 | 1 | 8 | 32 | CONFIRMATION_NONE_PASS | 0 | 2 | initial_v3_region_representative | V3 snapshot | 493.7 |
| c005 | W2-short-qos5_4.5_4_3.5 | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 32 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 142.9 |
| c005 | W2-short-qos5_4.5_4_3.5 | 1000 | 0.6 | argos_fixed_budget | DONE | True | 87.63 | 1 | 8 | 32 | CONFIRMATION_NONE_PASS | 0 | 2 | initial_v3_region_representative | V3 snapshot | 484.3 |
| c005 | W2-short-qos5_4.5_4_3.5 | 1000 | 0.6 | argos_early_stop | DONE | True | 87.63 | 1 | 8 | 16 | CONFIRMATION_NONE_PASS | 0 | 2 | initial_v3_region_representative | V3 snapshot | 417 |
| c006 | W2-short-qos5_4.5_4_3.5 | 1000 | 0.8 | v3_only | NO_BID | False | 97.44 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 350.6 |
| c006 | W2-short-qos5_4.5_4_3.5 | 1000 | 0.8 | v3_fixed_probing | NO_BID | False | None | None | None | 32 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 540.7 |
| c006 | W2-short-qos5_4.5_4_3.5 | 1000 | 0.8 | simulator_only_adaptive | NO_BID | False | None | None | None | 32 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 195.6 |
| c006 | W2-short-qos5_4.5_4_3.5 | 1000 | 0.8 | argos_fixed_budget | NO_BID | False | None | None | None | 32 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 529.9 |
| c006 | W2-short-qos5_4.5_4_3.5 | 1000 | 0.8 | argos_early_stop | NO_BID | False | None | None | None | 32 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 529.9 |
| c007 | W2-short-qos5555 | 1000 | 0.6 | v3_only | NO_BID | False | 88.95 | None | None | 1 | CONFIRMATION_NOT_RUN | 0 | 0 | v3_endpoint | V3 endpoint | 321.9 |
| c007 | W2-short-qos5555 | 1000 | 0.6 | v3_fixed_probing | DONE | True | 91.4 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 495.8 |
| c007 | W2-short-qos5555 | 1000 | 0.6 | simulator_only_adaptive | NO_BID | False | None | None | None | 32 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 150 |
| c007 | W2-short-qos5555 | 1000 | 0.6 | argos_fixed_budget | DONE | True | 91.4 | 1 | 8 | 32 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 486.4 |
| c007 | W2-short-qos5555 | 1000 | 0.6 | argos_early_stop | DONE | True | 91.4 | 1 | 8 | 16 | CONFIRMATION_ALL_PASS | 2 | 2 | initial_v3_region_representative | V3 snapshot | 412.1 |
| c008 | W2-short-qos5555 | 1000 | 0.8 | v3_only | DONE | True | 95.5 | 1 | 1 | 1 | CONFIRMATION_PARTIAL_PASS | 1 | 2 | v3_endpoint | V3 endpoint | 397.6 |
| c008 | W2-short-qos5555 | 1000 | 0.8 | v3_fixed_probing | NO_BID | False | None | None | None | 32 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 549.7 |
| c008 | W2-short-qos5555 | 1000 | 0.8 | simulator_only_adaptive | NO_BID | False | None | None | None | 32 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 178.8 |
| c008 | W2-short-qos5555 | 1000 | 0.8 | argos_fixed_budget | NO_BID | False | None | None | None | 32 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 532.4 |
| c008 | W2-short-qos5555 | 1000 | 0.8 | argos_early_stop | NO_BID | False | None | None | None | 32 | CONFIRMATION_NOT_RUN | 0 | 0 | None | None | 532.4 |

## Exact matched comparisons

| case | left | right | left_bid | right_bid | objective_left_minus_right | search_calls_saved_by_left |
| --- | --- | --- | --- | --- | --- | --- |
| c001 | argos_fixed_budget | v3_only | True | True | 0 | -31 |
| c002 | argos_fixed_budget | v3_only | True | False | None | -32 |
| c003 | argos_fixed_budget | v3_only | True | True | 0 | -31 |
| c004 | argos_fixed_budget | v3_only | True | False | None | -31 |
| c005 | argos_fixed_budget | v3_only | True | True | -0.287 | -31 |
| c006 | argos_fixed_budget | v3_only | False | False | None | -31 |
| c007 | argos_fixed_budget | v3_only | True | False | None | -31 |
| c008 | argos_fixed_budget | v3_only | False | True | None | -31 |
| c001 | v3_fixed_probing | v3_only | True | True | 0 | -31 |
| c002 | v3_fixed_probing | v3_only | True | False | None | -32 |
| c003 | v3_fixed_probing | v3_only | True | True | 0 | -31 |
| c004 | v3_fixed_probing | v3_only | True | False | None | -31 |
| c005 | v3_fixed_probing | v3_only | True | True | -0.287 | -31 |
| c006 | v3_fixed_probing | v3_only | False | False | None | -31 |
| c007 | v3_fixed_probing | v3_only | True | False | None | -31 |
| c008 | v3_fixed_probing | v3_only | False | True | None | -31 |
| c001 | argos_fixed_budget | v3_fixed_probing | True | True | 0 | 0 |
| c002 | argos_fixed_budget | v3_fixed_probing | True | True | -5.347 | 0 |
| c003 | argos_fixed_budget | v3_fixed_probing | True | True | 0 | 0 |
| c004 | argos_fixed_budget | v3_fixed_probing | True | True | 5.516 | 0 |
| c005 | argos_fixed_budget | v3_fixed_probing | True | True | 0 | 0 |
| c006 | argos_fixed_budget | v3_fixed_probing | False | False | None | 0 |
| c007 | argos_fixed_budget | v3_fixed_probing | True | True | 0 | 0 |
| c008 | argos_fixed_budget | v3_fixed_probing | False | False | None | 0 |
| c001 | argos_fixed_budget | simulator_only_adaptive | True | True | -23.16 | 0 |
| c002 | argos_fixed_budget | simulator_only_adaptive | True | True | -2.316 | 0 |
| c003 | argos_fixed_budget | simulator_only_adaptive | True | True | -15.35 | 0 |
| c004 | argos_fixed_budget | simulator_only_adaptive | True | True | -10.14 | 0 |
| c005 | argos_fixed_budget | simulator_only_adaptive | True | False | None | 0 |
| c006 | argos_fixed_budget | simulator_only_adaptive | False | False | None | 0 |
| c007 | argos_fixed_budget | simulator_only_adaptive | True | False | None | 0 |
| c008 | argos_fixed_budget | simulator_only_adaptive | False | False | None | 0 |
| c001 | argos_early_stop | argos_fixed_budget | True | True | 0 | 16 |
| c002 | argos_early_stop | argos_fixed_budget | True | True | 0 | 8 |
| c003 | argos_early_stop | argos_fixed_budget | True | True | 0 | 16 |
| c004 | argos_early_stop | argos_fixed_budget | True | True | 2.005 | 16 |
| c005 | argos_early_stop | argos_fixed_budget | True | True | 0 | 16 |
| c006 | argos_early_stop | argos_fixed_budget | False | False | None | 0 |
| c007 | argos_early_stop | argos_fixed_budget | True | True | 0 | 16 |
| c008 | argos_early_stop | argos_fixed_budget | False | False | None | 0 |

## Selected candidate parameters

| case | method | result_status | qualified_bid | candidate | Pbar | R | weights |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c001 | v3_only | DONE | True | v3-1500-0206 | 0.3664 | 0.2197 | [0.44967254996299744, 0.16022250056266785, 0.16323883831501007, 0.22686611115932465] |
| c001 | v3_fixed_probing | DONE | True | v3-1500-0206 | 0.3664 | 0.2197 | [0.44967254996299744, 0.16022250056266785, 0.16323883831501007, 0.22686611115932465] |
| c001 | simulator_only_adaptive | DONE | True | b003-independent-0006 | 0.5403 | 0.1496 | [0.322505763127408, 0.2713446694419377, 0.2246919532930569, 0.18145761413759742] |
| c001 | argos_fixed_budget | DONE | True | v3-1500-0206 | 0.3664 | 0.2197 | [0.44967254996299744, 0.16022250056266785, 0.16323883831501007, 0.22686611115932465] |
| c001 | argos_early_stop | DONE | True | v3-1500-0206 | 0.3664 | 0.2197 | [0.44967254996299744, 0.16022250056266785, 0.16323883831501007, 0.22686611115932465] |
| c002 | v3_fixed_probing | DONE | True | fixed-b003-independent-0007 | 0.4905 | 0.1864 | [0.3684401600357865, 0.23768461069184732, 0.16747258826248163, 0.22640264100988455] |
| c002 | simulator_only_adaptive | DONE | True | b004-local-0000 | 0.4341 | 0.1604 | [0.42496280885544646, 0.22428427107212323, 0.15, 0.20075292007243045] |
| c002 | argos_fixed_budget | DONE | True | b002-local-0003 | 0.5113 | 0.2785 | [0.45, 0.17672775642998445, 0.22327224357001568, 0.15] |
| c002 | argos_early_stop | DONE | True | b002-local-0003 | 0.5113 | 0.2785 | [0.45, 0.17672775642998445, 0.22327224357001568, 0.15] |
| c003 | v3_only | DONE | True | v3-1500-0383 | 0.3352 | 0.201 | [0.44960519671440125, 0.1697465032339096, 0.18469057977199554, 0.1959577351808548] |
| c003 | v3_fixed_probing | DONE | True | v3-1500-0383 | 0.3352 | 0.201 | [0.44960519671440125, 0.1697465032339096, 0.18469057977199554, 0.1959577351808548] |
| c003 | simulator_only_adaptive | DONE | True | b004-local-0000 | 0.3313 | 0.04176 | [0.38902548465566733, 0.20597480498111215, 0.18297723956916362, 0.22202247079405701] |
| c003 | argos_fixed_budget | DONE | True | v3-1500-0383 | 0.3352 | 0.201 | [0.44960519671440125, 0.1697465032339096, 0.18469057977199554, 0.1959577351808548] |
| c003 | argos_early_stop | DONE | True | v3-1500-0383 | 0.3352 | 0.201 | [0.44960519671440125, 0.1697465032339096, 0.18469057977199554, 0.1959577351808548] |
| c004 | v3_only | NO_BID | False | v3-1500-0275 | 0.3835 | 0.2299 | [0.44805729389190674, 0.2322375327348709, 0.15970204770565033, 0.16000311076641083] |
| c004 | v3_fixed_probing | DONE | True | fixed-b004-local-0000 | 0.4401 | 0.2606 | [0.45, 0.21000219222135136, 0.18471882269225776, 0.15527898508639104] |
| c004 | simulator_only_adaptive | DONE | True | b001-independent-0005 | 0.3831 | 0.04691 | [0.42405619337892786, 0.21571194249512232, 0.1679484498813003, 0.1922834142446495] |
| c004 | argos_fixed_budget | DONE | True | b003-local-0004 | 0.4117 | 0.177 | [0.42018931768411494, 0.27981068231588513, 0.15, 0.15] |
| c004 | argos_early_stop | DONE | True | v3-0000-0152 | 0.4167 | 0.1618 | [0.3846343457698822, 0.18412812054157257, 0.2350703328847885, 0.1961672008037567] |
| c005 | v3_only | DONE | True | v3-1500-0027 | 0.4738 | 0.1008 | [0.26256445050239563, 0.2516682744026184, 0.24889235198497772, 0.23687492311000824] |
| c005 | v3_fixed_probing | DONE | True | v3-0150-0493 | 0.4751 | 0.1244 | [0.263502836227417, 0.25144970417022705, 0.24786745011806488, 0.23718000948429108] |
| c005 | argos_fixed_budget | DONE | True | v3-0150-0493 | 0.4751 | 0.1244 | [0.263502836227417, 0.25144970417022705, 0.24786745011806488, 0.23718000948429108] |
| c005 | argos_early_stop | DONE | True | v3-0150-0493 | 0.4751 | 0.1244 | [0.263502836227417, 0.25144970417022705, 0.24786745011806488, 0.23718000948429108] |
| c006 | v3_only | NO_BID | False | v3-1500-0070 | 0.5875 | 0.1329 | [0.25882488489151, 0.25588127970695496, 0.24318400025367737, 0.24210983514785767] |
| c007 | v3_only | NO_BID | False | v3-1500-0076 | 0.4704 | 0.1162 | [0.26825445890426636, 0.25292664766311646, 0.24729259312152863, 0.23152630031108856] |
| c007 | v3_fixed_probing | DONE | True | v3-0100-0424 | 0.4751 | 0.04684 | [0.2608281075954437, 0.25420162081718445, 0.24530282616615295, 0.23966743052005768] |
| c007 | argos_fixed_budget | DONE | True | v3-0100-0424 | 0.4751 | 0.04684 | [0.2608281075954437, 0.25420162081718445, 0.24530282616615295, 0.23966743052005768] |
| c007 | argos_early_stop | DONE | True | v3-0100-0424 | 0.4751 | 0.04684 | [0.2608281075954437, 0.25420162081718445, 0.24530282616615295, 0.23966743052005768] |
| c008 | v3_only | DONE | True | v3-1500-0030 | 0.5826 | 0.1344 | [0.2637091279029846, 0.2574663758277893, 0.24094831943511963, 0.23787617683410645] |

## Per-job selected-point evidence

| case | method | result_status | job | Pj | n | unfinished | horizon_flag |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c001 | v3_only | DONE | Resnet.train.4 | 0.07004 | 1443 | 294 | False |
| c001 | v3_only | DONE | GPT2.train.4 | 0 | 280 | 250 | True |
| c001 | v3_only | DONE | Llama.train.4 | 0 | 297 | 297 | True |
| c001 | v3_only | DONE | Bloom.train.4 | 0 | 360 | 293 | True |
| c001 | v3_fixed_probing | DONE | Resnet.train.4 | 0.07004 | 1443 | 294 | False |
| c001 | v3_fixed_probing | DONE | GPT2.train.4 | 0 | 280 | 250 | True |
| c001 | v3_fixed_probing | DONE | Llama.train.4 | 0 | 297 | 297 | True |
| c001 | v3_fixed_probing | DONE | Bloom.train.4 | 0 | 360 | 293 | True |
| c001 | simulator_only_adaptive | DONE | Resnet.train.4 | 0 | 1443 | 114 | False |
| c001 | simulator_only_adaptive | DONE | GPT2.train.4 | 0 | 280 | 74 | True |
| c001 | simulator_only_adaptive | DONE | Llama.train.4 | 0 | 297 | 109 | True |
| c001 | simulator_only_adaptive | DONE | Bloom.train.4 | 0 | 360 | 208 | True |
| c001 | argos_fixed_budget | DONE | Resnet.train.4 | 0.07004 | 1443 | 294 | False |
| c001 | argos_fixed_budget | DONE | GPT2.train.4 | 0 | 280 | 250 | True |
| c001 | argos_fixed_budget | DONE | Llama.train.4 | 0 | 297 | 297 | True |
| c001 | argos_fixed_budget | DONE | Bloom.train.4 | 0 | 360 | 293 | True |
| c001 | argos_early_stop | DONE | Resnet.train.4 | 0.07004 | 1443 | 294 | False |
| c001 | argos_early_stop | DONE | GPT2.train.4 | 0 | 280 | 250 | True |
| c001 | argos_early_stop | DONE | Llama.train.4 | 0 | 297 | 297 | True |
| c001 | argos_early_stop | DONE | Bloom.train.4 | 0 | 360 | 293 | True |
| c002 | v3_fixed_probing | DONE | Resnet.train.4 | 0 | 1899 | 376 | False |
| c002 | v3_fixed_probing | DONE | GPT2.train.4 | 0 | 396 | 237 | True |
| c002 | v3_fixed_probing | DONE | Llama.train.4 | 0 | 413 | 395 | True |
| c002 | v3_fixed_probing | DONE | Bloom.train.4 | 0 | 474 | 297 | True |
| c002 | simulator_only_adaptive | DONE | Resnet.train.4 | 0 | 1899 | 346 | False |
| c002 | simulator_only_adaptive | DONE | GPT2.train.4 | 0 | 396 | 316 | True |
| c002 | simulator_only_adaptive | DONE | Llama.train.4 | 0 | 413 | 413 | True |
| c002 | simulator_only_adaptive | DONE | Bloom.train.4 | 0 | 474 | 395 | True |
| c002 | argos_fixed_budget | DONE | Resnet.train.4 | 0.06955 | 1899 | 188 | False |
| c002 | argos_fixed_budget | DONE | GPT2.train.4 | 0 | 396 | 240 | True |
| c002 | argos_fixed_budget | DONE | Llama.train.4 | 0 | 413 | 247 | True |
| c002 | argos_fixed_budget | DONE | Bloom.train.4 | 0 | 474 | 324 | True |
| c002 | argos_early_stop | DONE | Resnet.train.4 | 0.06955 | 1899 | 188 | False |
| c002 | argos_early_stop | DONE | GPT2.train.4 | 0 | 396 | 240 | True |
| c002 | argos_early_stop | DONE | Llama.train.4 | 0 | 413 | 247 | True |
| c002 | argos_early_stop | DONE | Bloom.train.4 | 0 | 474 | 324 | True |
| c003 | v3_only | DONE | Resnet.train.4 | 0 | 1461 | 401 | False |
| c003 | v3_only | DONE | GPT2.train.4 | 0 | 299 | 299 | True |
| c003 | v3_only | DONE | Llama.train.4 | 0 | 252 | 252 | True |
| c003 | v3_only | DONE | Bloom.train.4 | 0 | 323 | 323 | True |
| c003 | v3_fixed_probing | DONE | Resnet.train.4 | 0 | 1461 | 401 | False |
| c003 | v3_fixed_probing | DONE | GPT2.train.4 | 0 | 299 | 299 | True |
| c003 | v3_fixed_probing | DONE | Llama.train.4 | 0 | 252 | 252 | True |
| c003 | v3_fixed_probing | DONE | Bloom.train.4 | 0 | 323 | 323 | True |
| c003 | simulator_only_adaptive | DONE | Resnet.train.4 | 0 | 1461 | 514 | False |
| c003 | simulator_only_adaptive | DONE | GPT2.train.4 | 0 | 299 | 299 | True |
| c003 | simulator_only_adaptive | DONE | Llama.train.4 | 0 | 252 | 252 | True |
| c003 | simulator_only_adaptive | DONE | Bloom.train.4 | 0 | 323 | 323 | True |
| c003 | argos_fixed_budget | DONE | Resnet.train.4 | 0 | 1461 | 401 | False |
| c003 | argos_fixed_budget | DONE | GPT2.train.4 | 0 | 299 | 299 | True |
| c003 | argos_fixed_budget | DONE | Llama.train.4 | 0 | 252 | 252 | True |
| c003 | argos_fixed_budget | DONE | Bloom.train.4 | 0 | 323 | 323 | True |
| c003 | argos_early_stop | DONE | Resnet.train.4 | 0 | 1461 | 401 | False |
| c003 | argos_early_stop | DONE | GPT2.train.4 | 0 | 299 | 299 | True |
| c003 | argos_early_stop | DONE | Llama.train.4 | 0 | 252 | 252 | True |
| c003 | argos_early_stop | DONE | Bloom.train.4 | 0 | 323 | 323 | True |
| c004 | v3_only | NO_BID | Resnet.train.4 | 0.101 | 1912 | 669 | False |
| c004 | v3_only | NO_BID | GPT2.train.4 | 0 | 390 | 319 | True |
| c004 | v3_only | NO_BID | Llama.train.4 | 0 | 375 | 354 | True |
| c004 | v3_only | NO_BID | Bloom.train.4 | 0 | 462 | 458 | True |
| c004 | v3_fixed_probing | DONE | Resnet.train.4 | 0 | 1912 | 508 | False |
| c004 | v3_fixed_probing | DONE | GPT2.train.4 | 0 | 390 | 296 | True |
| c004 | v3_fixed_probing | DONE | Llama.train.4 | 0 | 375 | 212 | True |
| c004 | v3_fixed_probing | DONE | Bloom.train.4 | 0 | 462 | 424 | True |
| c004 | simulator_only_adaptive | DONE | Resnet.train.4 | 0 | 1912 | 450 | False |
| c004 | simulator_only_adaptive | DONE | GPT2.train.4 | 0 | 390 | 390 | True |
| c004 | simulator_only_adaptive | DONE | Llama.train.4 | 0 | 375 | 375 | True |
| c004 | simulator_only_adaptive | DONE | Bloom.train.4 | 0 | 462 | 433 | True |
| c004 | argos_fixed_budget | DONE | Resnet.train.4 | 0 | 1912 | 575 | False |
| c004 | argos_fixed_budget | DONE | GPT2.train.4 | 0 | 390 | 265 | True |
| c004 | argos_fixed_budget | DONE | Llama.train.4 | 0 | 375 | 375 | True |
| c004 | argos_fixed_budget | DONE | Bloom.train.4 | 0 | 462 | 462 | True |
| c004 | argos_early_stop | DONE | Resnet.train.4 | 0 | 1912 | 603 | False |
| c004 | argos_early_stop | DONE | GPT2.train.4 | 0 | 390 | 390 | True |
| c004 | argos_early_stop | DONE | Llama.train.4 | 0 | 375 | 310 | True |
| c004 | argos_early_stop | DONE | Bloom.train.4 | 0 | 462 | 418 | True |
| c005 | v3_only | DONE | Resnet.infer.4 | 0 | 21374 | 8 | False |
| c005 | v3_only | DONE | GPT2.infer.4 | 0.02412 | 19280 | 246 | False |
| c005 | v3_only | DONE | Llama.infer.4 | 0 | 14846 | 112 | False |
| c005 | v3_only | DONE | Bloom.infer.4 | 0.05805 | 12093 | 286 | False |
| c005 | v3_fixed_probing | DONE | Resnet.infer.4 | 0 | 21374 | 8 | False |
| c005 | v3_fixed_probing | DONE | GPT2.infer.4 | 0.08087 | 19280 | 206 | False |
| c005 | v3_fixed_probing | DONE | Llama.infer.4 | 0 | 14846 | 108 | False |
| c005 | v3_fixed_probing | DONE | Bloom.infer.4 | 0.07459 | 12093 | 251 | False |
| c005 | argos_fixed_budget | DONE | Resnet.infer.4 | 0 | 21374 | 8 | False |
| c005 | argos_fixed_budget | DONE | GPT2.infer.4 | 0.08087 | 19280 | 206 | False |
| c005 | argos_fixed_budget | DONE | Llama.infer.4 | 0 | 14846 | 108 | False |
| c005 | argos_fixed_budget | DONE | Bloom.infer.4 | 0.07459 | 12093 | 251 | False |
| c005 | argos_early_stop | DONE | Resnet.infer.4 | 0 | 21374 | 8 | False |
| c005 | argos_early_stop | DONE | GPT2.infer.4 | 0.08087 | 19280 | 206 | False |
| c005 | argos_early_stop | DONE | Llama.infer.4 | 0 | 14846 | 108 | False |
| c005 | argos_early_stop | DONE | Bloom.infer.4 | 0.07459 | 12093 | 251 | False |
| c006 | v3_only | NO_BID | Resnet.infer.4 | 0 | 28597 | 340 | False |
| c006 | v3_only | NO_BID | GPT2.infer.4 | 0 | 25354 | 41 | False |
| c006 | v3_only | NO_BID | Llama.infer.4 | 0.09279 | 19852 | 413 | False |
| c006 | v3_only | NO_BID | Bloom.infer.4 | 0.01014 | 16181 | 355 | False |
| c007 | v3_only | NO_BID | Resnet.infer.4 | 0 | 21453 | 0 | False |
| c007 | v3_only | NO_BID | GPT2.infer.4 | 0.0003652 | 19170 | 134 | False |
| c007 | v3_only | NO_BID | Llama.infer.4 | 0 | 15029 | 247 | False |
| c007 | v3_only | NO_BID | Bloom.infer.4 | 0.2135 | 12225 | 702 | False |
| c007 | v3_fixed_probing | DONE | Resnet.infer.4 | 0 | 21453 | 25 | False |
| c007 | v3_fixed_probing | DONE | GPT2.infer.4 | 0 | 19170 | 30 | False |
| c007 | v3_fixed_probing | DONE | Llama.infer.4 | 0 | 15029 | 405 | False |
| c007 | v3_fixed_probing | DONE | Bloom.infer.4 | 0 | 12225 | 540 | False |
| c007 | argos_fixed_budget | DONE | Resnet.infer.4 | 0 | 21453 | 25 | False |
| c007 | argos_fixed_budget | DONE | GPT2.infer.4 | 0 | 19170 | 30 | False |
| c007 | argos_fixed_budget | DONE | Llama.infer.4 | 0 | 15029 | 405 | False |
| c007 | argos_fixed_budget | DONE | Bloom.infer.4 | 0 | 12225 | 540 | False |
| c007 | argos_early_stop | DONE | Resnet.infer.4 | 0 | 21453 | 25 | False |
| c007 | argos_early_stop | DONE | GPT2.infer.4 | 0 | 19170 | 30 | False |
| c007 | argos_early_stop | DONE | Llama.infer.4 | 0 | 15029 | 405 | False |
| c007 | argos_early_stop | DONE | Bloom.infer.4 | 0 | 12225 | 540 | False |
| c008 | v3_only | DONE | Resnet.infer.4 | 0 | 28511 | 23 | False |
| c008 | v3_only | DONE | GPT2.infer.4 | 0 | 25486 | 148 | False |
| c008 | v3_only | DONE | Llama.infer.4 | 0.06828 | 19891 | 801 | False |
| c008 | v3_only | DONE | Bloom.infer.4 | 0 | 16066 | 650 | False |

## Prediction errors (actual minus predicted)

| tier | category | method | source_class | J | metric | logical_observations | unique_executions | mean | median | mean_absolute | p10 | p90 | min | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | independent_exploration | 4 | max_pj | 18 | 18 | -0.009558 | -0.01629 | 0.04702 | -0.05021 | 0.04983 | -0.1807 | 0.1885 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | independent_exploration | 4 | objective | 18 | 18 | -0.2459 | -0.5503 | 1.18 | -1.216 | 1.419 | -3.553 | 3.895 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | independent_exploration | 4 | p90 | 18 | 18 | -0.001403 | -0.001134 | 0.01179 | -0.02133 | 0.007332 | -0.04254 | 0.06904 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | independent_exploration | 4 | pj_0 | 18 | 18 | -0.009558 | -0.01629 | 0.04702 | -0.05021 | 0.04983 | -0.1807 | 0.1885 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | independent_exploration | 4 | pj_1 | 18 | 18 | -4.119e-05 | -4.456e-06 | 4.119e-05 | -0.0001309 | -3.845e-15 | -0.0002558 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | independent_exploration | 4 | pj_2 | 18 | 18 | -0.000392 | -6.797e-06 | 0.000392 | -0.001488 | -1.656e-12 | -0.002784 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | independent_exploration | 4 | pj_3 | 18 | 18 | -0.0001124 | -1.078e-08 | 0.0001124 | -6.352e-06 | -6.931e-13 | -0.002002 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | initial_v3_region_representative | 4 | max_pj | 30 | 30 | -0.007519 | -0.009711 | 0.02037 | -0.04016 | 0.03107 | -0.05736 | 0.06699 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | initial_v3_region_representative | 4 | objective | 30 | 30 | -0.4352 | -0.1936 | 0.7291 | -1.065 | 0.8057 | -6.263 | 1.275 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | initial_v3_region_representative | 4 | p90 | 30 | 30 | -0.0264 | -0.0003124 | 0.02896 | -0.001887 | 0.002793 | -0.5962 | 0.0186 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | initial_v3_region_representative | 4 | pj_0 | 30 | 30 | -0.007519 | -0.009711 | 0.02037 | -0.04016 | 0.03107 | -0.05736 | 0.06699 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | initial_v3_region_representative | 4 | pj_1 | 30 | 30 | -1.706e-05 | -8.437e-07 | 1.706e-05 | -2.116e-05 | -8.969e-23 | -0.0002847 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | initial_v3_region_representative | 4 | pj_2 | 30 | 30 | -4.895e-05 | -2.898e-06 | 4.895e-05 | -9.772e-05 | -1.947e-22 | -0.0005291 | -1.151e-34 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | initial_v3_region_representative | 4 | pj_3 | 30 | 30 | -9.206e-06 | -1.413e-08 | 9.206e-06 | -8.69e-07 | -6.074e-26 | -0.0002702 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | local_refinement | 4 | max_pj | 32 | 32 | -0.007688 | -0.002134 | 0.03142 | -0.06358 | 0.03655 | -0.166 | 0.1044 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | local_refinement | 4 | objective | 32 | 32 | -0.7616 | -0.1866 | 1.335 | -1.865 | 0.944 | -17.65 | 2.312 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | local_refinement | 4 | p90 | 32 | 32 | -0.04854 | 0.000748 | 0.05719 | -0.001181 | 0.003405 | -1.637 | 0.1042 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | local_refinement | 4 | pj_0 | 32 | 32 | -0.007688 | -0.002134 | 0.03142 | -0.06358 | 0.03655 | -0.166 | 0.1044 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | local_refinement | 4 | pj_1 | 32 | 32 | -1.586e-05 | -1.972e-07 | 1.586e-05 | -1.748e-05 | -1.71e-20 | -0.0002887 | -1.741e-28 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | local_refinement | 4 | pj_2 | 32 | 32 | -9.113e-05 | -6.447e-06 | 9.113e-05 | -0.0001401 | -3.236e-22 | -0.001132 | -1.207e-32 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_early_stop | local_refinement | 4 | pj_3 | 32 | 32 | -7.938e-07 | -5.712e-08 | 7.938e-07 | -3.761e-07 | -5.361e-24 | -1.915e-05 | -4.225e-31 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | independent_exploration | 4 | max_pj | 32 | 32 | -0.01251 | -0.01127 | 0.04535 | -0.0607 | 0.05924 | -0.207 | 0.1885 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | independent_exploration | 4 | objective | 32 | 32 | -0.3502 | -0.3927 | 1.227 | -1.304 | 1.227 | -5.886 | 3.895 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | independent_exploration | 4 | p90 | 32 | 32 | -0.00798 | -0.001134 | 0.02217 | -0.04148 | 0.01088 | -0.1641 | 0.08872 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | independent_exploration | 4 | pj_0 | 32 | 32 | -0.01251 | -0.01127 | 0.04535 | -0.0607 | 0.05924 | -0.207 | 0.1885 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | independent_exploration | 4 | pj_1 | 32 | 32 | -2.78e-05 | -3.309e-08 | 2.78e-05 | -0.0001144 | -1.741e-25 | -0.0002558 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | independent_exploration | 4 | pj_2 | 32 | 32 | -0.0002268 | -3.686e-07 | 0.0002268 | -0.0003051 | -3.024e-26 | -0.002784 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | independent_exploration | 4 | pj_3 | 32 | 32 | -6.348e-05 | -4.215e-10 | 6.348e-05 | -3.584e-06 | -3.056e-26 | -0.002002 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | initial_v3_region_representative | 4 | max_pj | 28 | 28 | -0.007329 | -0.00843 | 0.02109 | -0.04148 | 0.03108 | -0.05736 | 0.06699 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | initial_v3_region_representative | 4 | objective | 28 | 28 | -0.4525 | -0.1914 | 0.7673 | -1.083 | 0.8382 | -6.263 | 1.275 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | initial_v3_region_representative | 4 | p90 | 28 | 28 | -0.02824 | -0.0003124 | 0.03098 | -0.003057 | 0.002986 | -0.5962 | 0.0186 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | initial_v3_region_representative | 4 | pj_0 | 28 | 28 | -0.007329 | -0.00843 | 0.02109 | -0.04148 | 0.03108 | -0.05736 | 0.06699 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | initial_v3_region_representative | 4 | pj_1 | 28 | 28 | -1.826e-05 | -1.205e-06 | 1.826e-05 | -2.731e-05 | -6.976e-23 | -0.0002847 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | initial_v3_region_representative | 4 | pj_2 | 28 | 28 | -5.223e-05 | -2.642e-06 | 5.223e-05 | -0.0001377 | -1.556e-22 | -0.0005291 | -1.151e-34 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | initial_v3_region_representative | 4 | pj_3 | 28 | 28 | -9.862e-06 | -2.104e-08 | 9.862e-06 | -8.859e-07 | -4.734e-26 | -0.0002702 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | local_refinement | 4 | max_pj | 76 | 76 | -0.0193 | -0.002134 | 0.03791 | -0.08205 | 0.0361 | -0.3276 | 0.1044 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | local_refinement | 4 | objective | 76 | 76 | -0.733 | -0.1358 | 1.226 | -2.394 | 0.9502 | -17.65 | 2.312 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | local_refinement | 4 | p90 | 76 | 76 | -0.02505 | 0.0005393 | 0.04058 | -0.01575 | 0.00337 | -1.637 | 0.3601 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | local_refinement | 4 | pj_0 | 76 | 76 | -0.0193 | -0.002134 | 0.03791 | -0.08205 | 0.0361 | -0.3276 | 0.1044 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | local_refinement | 4 | pj_1 | 76 | 76 | -9.546e-06 | -6.246e-08 | 9.546e-06 | -1.481e-05 | -5.378e-23 | -0.0002887 | -8.274e-29 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | local_refinement | 4 | pj_2 | 76 | 76 | -4.208e-05 | -9.377e-07 | 4.208e-05 | -4.818e-05 | -1.711e-21 | -0.001132 | -1.207e-32 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | argos_fixed_budget | local_refinement | 4 | pj_3 | 76 | 76 | -4.123e-07 | -1.985e-09 | 4.123e-07 | -4.215e-07 | -1.126e-28 | -1.915e-05 | -4.996e-38 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | independent_exploration | 4 | max_pj | 34 | 34 | -0.01494 | -0.01549 | 0.04585 | -0.0612 | 0.05881 | -0.207 | 0.1885 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | independent_exploration | 4 | objective | 34 | 34 | -0.3894 | -0.5027 | 1.214 | -1.275 | 1.225 | -5.886 | 3.895 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | independent_exploration | 4 | p90 | 34 | 34 | -0.00745 | -0.0008731 | 0.02093 | -0.03935 | 0.009695 | -0.1641 | 0.08872 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | independent_exploration | 4 | pj_0 | 34 | 34 | -0.01494 | -0.01549 | 0.04585 | -0.0612 | 0.05881 | -0.207 | 0.1885 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | independent_exploration | 4 | pj_1 | 34 | 34 | -2.635e-05 | -1.668e-06 | 2.635e-05 | -0.0001123 | -5.224e-25 | -0.0002558 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | independent_exploration | 4 | pj_2 | 34 | 34 | -0.0002135 | -8.262e-07 | 0.0002135 | -0.0002764 | -8.968e-26 | -0.002784 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | independent_exploration | 4 | pj_3 | 34 | 34 | -5.975e-05 | -2.627e-09 | 5.975e-05 | -3.509e-06 | -9.167e-26 | -0.002002 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | initial_v3_region_representative | 4 | max_pj | 28 | 28 | -0.007329 | -0.00843 | 0.02109 | -0.04148 | 0.03108 | -0.05736 | 0.06699 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | initial_v3_region_representative | 4 | objective | 28 | 28 | -0.4525 | -0.1914 | 0.7673 | -1.083 | 0.8382 | -6.263 | 1.275 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | initial_v3_region_representative | 4 | p90 | 28 | 28 | -0.02824 | -0.0003124 | 0.03098 | -0.003057 | 0.002986 | -0.5962 | 0.0186 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | initial_v3_region_representative | 4 | pj_0 | 28 | 28 | -0.007329 | -0.00843 | 0.02109 | -0.04148 | 0.03108 | -0.05736 | 0.06699 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | initial_v3_region_representative | 4 | pj_1 | 28 | 28 | -1.826e-05 | -1.205e-06 | 1.826e-05 | -2.731e-05 | -6.976e-23 | -0.0002847 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | initial_v3_region_representative | 4 | pj_2 | 28 | 28 | -5.223e-05 | -2.642e-06 | 5.223e-05 | -0.0001377 | -1.556e-22 | -0.0005291 | -1.151e-34 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | initial_v3_region_representative | 4 | pj_3 | 28 | 28 | -9.862e-06 | -2.104e-08 | 9.862e-06 | -8.859e-07 | -4.734e-26 | -0.0002702 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | local_refinement | 4 | max_pj | 74 | 74 | -0.009757 | -0.006859 | 0.02396 | -0.03635 | 0.02937 | -0.166 | 0.08399 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | local_refinement | 4 | objective | 74 | 74 | -1.018 | -0.2467 | 1.461 | -1.922 | 0.9402 | -18.76 | 1.663 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | local_refinement | 4 | p90 | 74 | 74 | -0.07136 | -8.282e-05 | 0.08603 | -0.01615 | 0.004004 | -1.841 | 0.3613 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | local_refinement | 4 | pj_0 | 74 | 74 | -0.009757 | -0.006859 | 0.02396 | -0.03635 | 0.02937 | -0.166 | 0.08399 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | local_refinement | 4 | pj_1 | 74 | 74 | -2.219e-05 | -1.063e-06 | 2.219e-05 | -4.044e-05 | -4.974e-25 | -0.0003214 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | local_refinement | 4 | pj_2 | 74 | 74 | -9.183e-05 | -5.446e-06 | 9.183e-05 | -0.0001565 | -3.131e-23 | -0.001312 | -2.452e-36 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_fixed_probing | local_refinement | 4 | pj_3 | 74 | 74 | -1.679e-05 | -8.715e-08 | 1.679e-05 | -1.873e-06 | -8.58e-29 | -0.000804 | 0 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_only | v3_endpoint | 4 | max_pj | 7 | 7 | -0.006406 | -0.01454 | 0.03239 | -0.04609 | 0.04117 | -0.04609 | 0.06699 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_only | v3_endpoint | 4 | objective | 7 | 7 | -0.1098 | -0.1634 | 0.5921 | -0.8936 | 0.7576 | -0.8974 | 1.275 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_only | v3_endpoint | 4 | p90 | 7 | 7 | -0.0005888 | -0.0003023 | 0.0005888 | -0.001275 | -0.0002568 | -0.001302 | -0.0002568 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_only | v3_endpoint | 4 | pj_0 | 7 | 7 | -0.006406 | -0.01454 | 0.03239 | -0.04609 | 0.04117 | -0.04609 | 0.06699 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_only | v3_endpoint | 4 | pj_1 | 7 | 7 | -3.357e-06 | -1.452e-06 | 3.357e-06 | -8.107e-06 | -3.52e-07 | -1.809e-05 | -3.52e-07 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_only | v3_endpoint | 4 | pj_2 | 7 | 7 | -4.579e-06 | -2.386e-06 | 4.579e-06 | -9.377e-06 | -1.678e-06 | -1.986e-05 | -1.678e-06 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W1 | v3_only | v3_endpoint | 4 | pj_3 | 7 | 7 | -1.918e-07 | -1.465e-07 | 1.918e-07 | -4.321e-07 | -1.413e-08 | -8.605e-07 | -1.413e-08 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | independent_exploration | 4 | max_pj | 24 | 24 | -0.01998 | -4.186e-06 | 0.03439 | -0.01358 | 0.006364 | -0.5623 | 0.1176 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | independent_exploration | 4 | objective | 24 | 24 | -1.088 | -0.3258 | 1.981 | -2.061 | 1.204 | -16.69 | 4.396 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | independent_exploration | 4 | p90 | 24 | 24 | -0.01243 | -0.02509 | 0.0695 | -0.1235 | 0.06241 | -0.1557 | 0.3296 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | independent_exploration | 4 | pj_0 | 24 | 24 | -0.05022 | -0.003916 | 0.05043 | -0.02318 | 0 | -0.6205 | 0.002189 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | independent_exploration | 4 | pj_1 | 24 | 24 | -0.003661 | -7.84e-05 | 0.004739 | -0.01164 | -2.924e-25 | -0.03572 | 0.01293 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | independent_exploration | 4 | pj_2 | 24 | 24 | 0.005956 | -4.204e-24 | 0.006811 | -0.001311 | 0.008113 | -0.004939 | 0.1176 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | independent_exploration | 4 | pj_3 | 24 | 24 | 0.001248 | -2.397e-38 | 0.00333 | -0.0006976 | 0.00618 | -0.02243 | 0.02299 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | initial_v3_region_representative | 4 | max_pj | 28 | 28 | 0.02255 | -1.189e-33 | 0.02707 | -0.007161 | 0.08524 | -0.01398 | 0.2821 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | initial_v3_region_representative | 4 | objective | 28 | 28 | 0.66 | 0.4259 | 1.168 | -0.5843 | 2.183 | -3.582 | 6.286 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | initial_v3_region_representative | 4 | p90 | 28 | 28 | 0.06148 | 0.01225 | 0.06921 | -0.003842 | 0.1937 | -0.08778 | 0.2187 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | initial_v3_region_representative | 4 | pj_0 | 28 | 28 | -0.0177 | -0.007161 | 0.0177 | -0.02094 | -9.96e-16 | -0.1671 | -1.846e-34 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | initial_v3_region_representative | 4 | pj_1 | 28 | 28 | -0.009135 | -0.0004768 | 0.0167 | -0.02097 | 0.006572 | -0.2163 | 0.05997 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | initial_v3_region_representative | 4 | pj_2 | 28 | 28 | 0.01296 | -1.424e-19 | 0.02047 | -0.009163 | 0.02169 | -0.02826 | 0.3038 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | initial_v3_region_representative | 4 | pj_3 | 28 | 28 | 0.02475 | 0.0006899 | 0.03349 | -0.002165 | 0.09514 | -0.1082 | 0.2364 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | local_refinement | 4 | max_pj | 48 | 48 | 0.001777 | -0.002441 | 0.03706 | -0.02141 | 0.02101 | -0.269 | 0.4569 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | local_refinement | 4 | objective | 48 | 48 | 0.0254 | -0.1534 | 2.545 | -4.071 | 3.171 | -13.67 | 14.23 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | local_refinement | 4 | p90 | 48 | 48 | 0.006047 | 2.757e-05 | 0.05653 | -0.1065 | 0.1169 | -0.1764 | 0.258 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | local_refinement | 4 | pj_0 | 48 | 48 | -0.02088 | -3.37e-05 | 0.02293 | -0.01716 | -1.116e-24 | -0.505 | 0.0492 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | local_refinement | 4 | pj_1 | 48 | 48 | 0.004638 | -3.524e-06 | 0.022 | -0.01998 | 0.004042 | -0.1508 | 0.4981 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | local_refinement | 4 | pj_2 | 48 | 48 | 0.02276 | -2.456e-22 | 0.0331 | -0.001663 | 0.03587 | -0.1384 | 0.4569 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_early_stop | local_refinement | 4 | pj_3 | 48 | 48 | -0.0103 | -8.068e-26 | 0.02289 | -0.0339 | 0.01657 | -0.269 | 0.068 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | independent_exploration | 4 | max_pj | 32 | 32 | -0.03578 | -7.4e-05 | 0.04851 | -0.1315 | 0.008112 | -0.5623 | 0.1176 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | independent_exploration | 4 | objective | 32 | 32 | -1.467 | -0.3619 | 2.157 | -5.828 | 0.8089 | -16.69 | 4.396 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | independent_exploration | 4 | p90 | 32 | 32 | -0.01847 | -0.02509 | 0.06211 | -0.1188 | 0.03753 | -0.1557 | 0.3296 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | independent_exploration | 4 | pj_0 | 32 | 32 | -0.05254 | -0.006605 | 0.05304 | -0.1362 | 0 | -0.6205 | 0.00552 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | independent_exploration | 4 | pj_1 | 32 | 32 | -0.01138 | -4.546e-06 | 0.01493 | -0.02029 | 0.007893 | -0.2984 | 0.01802 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | independent_exploration | 4 | pj_2 | 32 | 32 | 0.003481 | -4.204e-24 | 0.006315 | -0.001781 | 0.006305 | -0.03219 | 0.1176 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | independent_exploration | 4 | pj_3 | 32 | 32 | 0.001633 | -2.248e-30 | 0.003197 | -0.0004005 | 0.007334 | -0.02243 | 0.02299 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | initial_v3_region_representative | 4 | max_pj | 28 | 28 | 0.02255 | -1.189e-33 | 0.02707 | -0.007161 | 0.08524 | -0.01398 | 0.2821 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | initial_v3_region_representative | 4 | objective | 28 | 28 | 0.66 | 0.4259 | 1.168 | -0.5843 | 2.183 | -3.582 | 6.286 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | initial_v3_region_representative | 4 | p90 | 28 | 28 | 0.06148 | 0.01225 | 0.06921 | -0.003842 | 0.1937 | -0.08778 | 0.2187 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | initial_v3_region_representative | 4 | pj_0 | 28 | 28 | -0.0177 | -0.007161 | 0.0177 | -0.02094 | -9.96e-16 | -0.1671 | -1.846e-34 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | initial_v3_region_representative | 4 | pj_1 | 28 | 28 | -0.009135 | -0.0004768 | 0.0167 | -0.02097 | 0.006572 | -0.2163 | 0.05997 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | initial_v3_region_representative | 4 | pj_2 | 28 | 28 | 0.01296 | -1.424e-19 | 0.02047 | -0.009163 | 0.02169 | -0.02826 | 0.3038 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | initial_v3_region_representative | 4 | pj_3 | 28 | 28 | 0.02475 | 0.0006899 | 0.03349 | -0.002165 | 0.09514 | -0.1082 | 0.2364 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | local_refinement | 4 | max_pj | 72 | 72 | 0.001104 | -4.714e-05 | 0.03398 | -0.02386 | 0.02144 | -0.269 | 0.4569 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | local_refinement | 4 | objective | 72 | 72 | -0.1406 | -0.4098 | 2.569 | -4.531 | 3.617 | -13.67 | 14.23 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | local_refinement | 4 | p90 | 72 | 72 | -0.01786 | -0.007113 | 0.07456 | -0.1373 | 0.1121 | -0.2082 | 0.258 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | local_refinement | 4 | pj_0 | 72 | 72 | -0.01968 | -1.042e-08 | 0.02224 | -0.0176 | -3.494e-30 | -0.505 | 0.0492 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | local_refinement | 4 | pj_1 | 72 | 72 | 0.004031 | -9.49e-10 | 0.01681 | -0.01462 | 0.003131 | -0.1508 | 0.4981 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | local_refinement | 4 | pj_2 | 72 | 72 | 0.01156 | -8.901e-19 | 0.0289 | -0.003029 | 0.02389 | -0.1623 | 0.4569 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | argos_fixed_budget | local_refinement | 4 | pj_3 | 72 | 72 | 0.003956 | -2.139e-23 | 0.0289 | -0.006262 | 0.02019 | -0.269 | 0.4147 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | independent_exploration | 4 | max_pj | 32 | 32 | -0.03578 | -7.4e-05 | 0.04851 | -0.1315 | 0.008112 | -0.5623 | 0.1176 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | independent_exploration | 4 | objective | 32 | 32 | -1.467 | -0.3619 | 2.157 | -5.828 | 0.8089 | -16.69 | 4.396 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | independent_exploration | 4 | p90 | 32 | 32 | -0.01847 | -0.02509 | 0.06211 | -0.1188 | 0.03753 | -0.1557 | 0.3296 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | independent_exploration | 4 | pj_0 | 32 | 32 | -0.05254 | -0.006605 | 0.05304 | -0.1362 | 0 | -0.6205 | 0.00552 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | independent_exploration | 4 | pj_1 | 32 | 32 | -0.01138 | -4.546e-06 | 0.01493 | -0.02029 | 0.007893 | -0.2984 | 0.01802 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | independent_exploration | 4 | pj_2 | 32 | 32 | 0.003481 | -4.204e-24 | 0.006315 | -0.001781 | 0.006305 | -0.03219 | 0.1176 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | independent_exploration | 4 | pj_3 | 32 | 32 | 0.001633 | -2.248e-30 | 0.003197 | -0.0004005 | 0.007334 | -0.02243 | 0.02299 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | initial_v3_region_representative | 4 | max_pj | 28 | 28 | 0.02255 | -1.189e-33 | 0.02707 | -0.007161 | 0.08524 | -0.01398 | 0.2821 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | initial_v3_region_representative | 4 | objective | 28 | 28 | 0.66 | 0.4259 | 1.168 | -0.5843 | 2.183 | -3.582 | 6.286 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | initial_v3_region_representative | 4 | p90 | 28 | 28 | 0.06148 | 0.01225 | 0.06921 | -0.003842 | 0.1937 | -0.08778 | 0.2187 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | initial_v3_region_representative | 4 | pj_0 | 28 | 28 | -0.0177 | -0.007161 | 0.0177 | -0.02094 | -9.96e-16 | -0.1671 | -1.846e-34 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | initial_v3_region_representative | 4 | pj_1 | 28 | 28 | -0.009135 | -0.0004768 | 0.0167 | -0.02097 | 0.006572 | -0.2163 | 0.05997 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | initial_v3_region_representative | 4 | pj_2 | 28 | 28 | 0.01296 | -1.424e-19 | 0.02047 | -0.009163 | 0.02169 | -0.02826 | 0.3038 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | initial_v3_region_representative | 4 | pj_3 | 28 | 28 | 0.02475 | 0.0006899 | 0.03349 | -0.002165 | 0.09514 | -0.1082 | 0.2364 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | local_refinement | 4 | max_pj | 72 | 72 | 0.0002339 | -9.944e-08 | 0.007859 | -0.009839 | 0.006061 | -0.06206 | 0.1708 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | local_refinement | 4 | objective | 72 | 72 | -0.3103 | -0.1779 | 1.667 | -3.274 | 1.644 | -12.14 | 13.2 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | local_refinement | 4 | p90 | 72 | 72 | -0.004934 | 9.035e-05 | 0.04095 | -0.06098 | 0.07404 | -0.399 | 0.2877 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | local_refinement | 4 | pj_0 | 72 | 72 | -0.005008 | -0.00389 | 0.01593 | -0.01646 | -2.695e-35 | -0.1702 | 0.2045 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | local_refinement | 4 | pj_1 | 72 | 72 | -0.003684 | -1.865e-13 | 0.01578 | -0.03544 | 0.004824 | -0.1508 | 0.1378 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | local_refinement | 4 | pj_2 | 72 | 72 | -0.003427 | -1.051e-24 | 0.02026 | -0.00504 | 0.007114 | -0.378 | 0.3399 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_fixed_probing | local_refinement | 4 | pj_3 | 72 | 72 | -0.0007527 | -3.836e-26 | 0.01881 | -0.01078 | 0.01374 | -0.2777 | 0.2237 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_only | v3_endpoint | 4 | max_pj | 8 | 8 | 0.04921 | 0.03413 | 0.05573 | -0.01298 | 0.1163 | -0.01325 | 0.2046 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_only | v3_endpoint | 4 | objective | 8 | 8 | 1.186 | 0.9812 | 1.292 | -0.0533 | 2.754 | -0.4244 | 4.207 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_only | v3_endpoint | 4 | p90 | 8 | 8 | 0.09246 | 0.09883 | 0.09246 | 0.05436 | 0.1273 | 0.02083 | 0.1281 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_only | v3_endpoint | 4 | pj_0 | 8 | 8 | -0.007485 | -0.007329 | 0.007485 | -0.007885 | -0.007148 | -0.008881 | -0.007025 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_only | v3_endpoint | 4 | pj_1 | 8 | 8 | -0.007315 | -0.01138 | 0.01087 | -0.01359 | 0.003733 | -0.0144 | 0.01423 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_only | v3_endpoint | 4 | pj_2 | 8 | 8 | 0.009561 | -0.008735 | 0.02585 | -0.0134 | 0.06631 | -0.0134 | 0.08211 |
| SERIOUS_DEVELOPMENT | ORIGINAL_W2 | v3_only | v3_endpoint | 4 | pj_3 | 8 | 8 | 0.03744 | 0.01225 | 0.04185 | -0.005884 | 0.0994 | -0.005884 | 0.2082 |

Error summaries retain logical-method grouping. Reused physical observations are not independent samples.

## Every recorded failure

| case_id | method | kind | details |
| --- | --- | --- | --- |
| c002 | v3_only | NO_BID | V3_NO_SAFE_ENDPOINT |
| c004 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c005 | v3_only | CONFIRMATION_FAILURE | CONFIRMATION_PARTIAL_PASS |
| c005 | v3_fixed_probing | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c005 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c005 | argos_fixed_budget | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c005 | argos_early_stop | CONFIRMATION_FAILURE | CONFIRMATION_NONE_PASS |
| c006 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c006 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c006 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c006 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c006 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |
| c007 | v3_only | NO_BID | V3_SELECTED_POINT_NOT_QUALIFIED |
| c007 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c008 | v3_only | CONFIRMATION_FAILURE | CONFIRMATION_PARTIAL_PASS |
| c008 | v3_fixed_probing | NO_BID | HARD_MAX_SEARCH_CALLS |
| c008 | simulator_only_adaptive | NO_BID | HARD_MAX_SEARCH_CALLS |
| c008 | argos_fixed_budget | NO_BID | HARD_MAX_SEARCH_CALLS |
| c008 | argos_early_stop | NO_BID | HARD_MAX_SEARCH_CALLS |

## Limitations

One search scenario and one initialization per context, two fresh confirmation scenarios, and a one-hour simulation horizon. Qualified evidence requires at least one observation per job; that is not proof of statistical reliability. Confirmation evidence is retained in campaign_confirmations.csv. Shared executions are not extra independent scenarios.
