"""Deterministic capacity-aware OC scenario dispatch planning.

This pure module does not execute FlexDC. The caller commits an entire planned
wave before reading any of its results, so worker completion order cannot affect
which candidate/table pairs are dispatched in the wave.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from argos.oc_basic.v1_1 import signed_scenario_violation
from argos.types import Candidate


@dataclass(frozen=True)
class PlannedCell:
    candidate_id: str
    arrival_seed: int


def plan_wave(batch: list[Candidate], rows: list[dict], seed_order: tuple[int, ...],
              workers: int, max_fanout: int = 4) -> list[PlannedCell]:
    """Prefer least-measured active bids, then fill spare workers by fanout.

    Three observed failures permanently inactivate a bid. Already launched
    cells may complete after a third failure, and are retained by the caller.
    """
    if workers < 1 or workers > 10 or max_fanout < 1:
        raise ValueError("Invalid OC worker or fanout limit")
    panel = tuple(int(s) for s in seed_order)
    if len(panel) != 10 or len(set(panel)) != 10:
        raise ValueError("OC scheduling requires ten frozen arrival seeds")
    by_id: dict[str, list[dict]] = defaultdict(list)
    ids = {c.candidate_id for c in batch}
    for row in rows:
        if row["candidate_id"] in ids:
            by_id[row["candidate_id"]].append(row)
    active = []
    for i, candidate in enumerate(batch):
        observed = by_id[candidate.candidate_id]
        measured = {int(r["arrival_seed"]) for r in observed}
        if len(measured) != len(observed):
            raise ValueError("Duplicate measured candidate/table cell")
        failures = sum(signed_scenario_violation(r) is None or signed_scenario_violation(r) > 0 for r in observed)
        if failures >= 3:
            continue
        pending = [s for s in panel if s not in measured]
        if pending:
            active.append((len(observed), i, candidate.candidate_id, pending))
    active.sort()
    if not active:
        return []
    cohort = active[:workers]
    fanout = min(max_fanout, max(1, (workers + len(cohort) - 1) // len(cohort)))
    planned = []
    for depth in range(fanout):
        for _, _, candidate_id, pending in cohort:
            if depth < len(pending):
                planned.append(PlannedCell(candidate_id, pending[depth]))
                if len(planned) == workers:
                    return planned
    return planned


def execute_fanout_batch(*, batch: list[Candidate], rows: list[dict], seed_order: tuple[int, ...],
                         workers: int, call_room: Callable[[], int],
                         deadline_reached: Callable[[], bool],
                         evaluate: Callable[[Candidate, int], dict],
                         record: Callable[[dict], None]) -> dict:
    """Execute deterministic planned waves in one bounded pool.

    Every wave is frozen before dispatch, and all results are recorded before
    planning another wave. A failure in one worker aborts instead of silently
    treating an execution error as infeasibility.
    """
    lookup = {candidate.candidate_id: candidate for candidate in batch}
    waves = launches = peak = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            if waves and deadline_reached():
                break
            available = call_room()
            if available <= 0:
                break
            planned = plan_wave(batch, rows, seed_order, workers)[:available]
            if not planned:
                break
            waves += 1
            launches += len(planned)
            peak = max(peak, len(planned))
            futures = {pool.submit(evaluate, lookup[cell.candidate_id], cell.arrival_seed): cell for cell in planned}
            for future in as_completed(futures):
                row = future.result()
                expected = futures[future]
                if row["candidate_id"] != expected.candidate_id or int(row["arrival_seed"]) != expected.arrival_seed:
                    raise ValueError("OC fanout worker returned a crossed candidate/table identity")
                record(row)
    return {"waves": waves, "launches": launches, "peak_workers": peak}
