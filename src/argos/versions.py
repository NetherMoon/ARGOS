"""Central persisted-contract versions: increment when semantics change."""

SOFTWARE_VERSION = "0.3.0"
OBSERVATION_SCHEMA = 3
AUDIT_SCHEMA = 3
REPORT_SCHEMA = 3
QOS_ESTIMATOR = "flexdc_rank_cdf_v1"
SEARCH_SCHEMA = 2
RETENTION_POLICY = "tradeoff_round_robin_all_and_infeasible_diversity_v2"
REGION_POLICY = "greedy_normalized_geometry_v1"
SNAPSHOT_POLICY = "preupdate_and_endpoint_v1"
EARLY_STOP_POLICY = "qualified_local_patience_v1"

QOS_PARITY_RTOL = 1e-10
QOS_PARITY_ATOL = 1e-12
