"""Deterministic stopping shared by live control and observation-stream replay."""

from argos.contracts import qualified


def early_stop_details(observations, config) -> dict:
    searches = [o for o in observations if o.phase == "search"]
    eligible = [o for o in searches if qualified(o, config.min_qos_observations_per_type)]
    if not eligible:
        return {"stop": False, "first_eligible_call": None}
    first = eligible[0]
    first_batch = first.batch
    best = float("inf")
    stale = 0
    refined = False
    winning_batch = None
    threshold_best = float("inf")
    for batch in sorted({o.batch for o in searches}):
        rows = [o for o in eligible if o.batch == batch]
        value = min((o.metrics.objective for o in rows), default=float("inf"))
        if value < best:
            best, winning_batch = value, batch
        improved = value < threshold_best - config.objective_improvement_epsilon
        if improved:
            threshold_best = value
            stale = 0
        elif batch > first_batch:
            stale += 1
        if batch > first_batch and any(
            o.batch == batch and o.candidate.source == "local" for o in searches
        ):
            refined = True
    last_batch = max(o.batch for o in searches)
    return {
        "stop": refined
        and last_batch >= config.early_stop_min_batches
        and stale >= config.early_stop_patience,
        "first_eligible_call": searches.index(first) + 1,
        "first_eligible_batch": first_batch,
        "winning_batch": winning_batch,
        "stale_batches": stale,
        "subsequent_local_refinement": refined,
        "best_objective": best,
    }


def replay(observations, config) -> dict:
    searches = [o for o in observations if o.phase == "search"]
    stop_at = len(searches)
    reason = "HARD_BUDGET_OR_END_OF_RECORDED_STREAM"
    details = early_stop_details(searches, config)
    for batch in sorted({o.batch for o in searches}):
        prefix = [o for o in searches if o.batch <= batch]
        current = early_stop_details(prefix, config)
        if current["stop"]:
            stop_at, reason, details = len(prefix), "EARLY_STOP_QUALIFIED_LOCAL_PATIENCE", current
            break
    return {
        "mode": "offline_replay_no_simulator_calls",
        "would_have_search_calls": stop_at,
        "recorded_search_calls": len(searches),
        "avoidable_extra_calls": len(searches) - stop_at,
        "reason": reason,
        **details,
    }
