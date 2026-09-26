"""Deterministic capacity-aware OC scenario dispatch planning.

This pure module does not execute FlexDC. The caller commits an entire planned
wave before reading any of its results, so worker completion order cannot affect
which candidate/table pairs are dispatched in the wave.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from argos.oc_basic.core import SEARCH_TARGET
from argos.oc_basic.generic import PanelRule, signed_violation
from argos.types import Candidate


@dataclass(frozen=True)
class PlannedCell:
    candidate_id: str
    arrival_seed: int


def plan_wave(
    batch: list[Candidate],
    rows: list[dict],
    seed_order: tuple[int, ...],
    workers: int,
    max_fanout: int = 4,
    rule: PanelRule | None = None,
) -> list[PlannedCell]:
    """Prefer least-measured active bids, then fill spare workers by fanout.

    An impossible maximum pass count permanently inactivates a bid. Already launched
    cells may complete after a third failure, and are retained by the caller.
    """
    if workers < 1 or workers > 10 or max_fanout < 1:
        raise ValueError("Invalid OC worker or fanout limit")
    panel = tuple(int(s) for s in seed_order)
    if rule is None:
        # Historical OC1.3 callers retain their frozen 10/8 semantics. Job
        # labels are irrelevant to scenario pass counting.
        example = rows[0].get("Pj") if rows else [0] * len(batch[0].weights)
        if isinstance(example, str):
            example = json.loads(example)
        rule = PanelRule(tuple(f"job_{i}" for i in range(len(example))), len(panel), SEARCH_TARGET)
    if len(panel) != rule.panel_size or len(set(panel)) != len(panel):
        raise ValueError("OC scheduling panel differs from the frozen rule")
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
        passes = sum((g := signed_violation(r, rule)) is not None and g <= 0 for r in observed)
        if passes + rule.panel_size - len(observed) < rule.required_passes:
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


def execute_fanout_batch(
    *,
    batch: list[Candidate],
    rows: list[dict],
    seed_order: tuple[int, ...],
    workers: int,
    call_room: Callable[[], int],
    deadline_reached: Callable[[], bool],
    evaluate: Callable[[Candidate, int], dict],
    record: Callable[[dict], None],
    on_wave_planned: Callable[[list[PlannedCell]], None] | None = None,
    rule: PanelRule | None = None,
    allow_first_wave_past_deadline: bool = True,
) -> dict:
    """Execute deterministic planned waves in one bounded pool.

    Every wave is frozen before dispatch, and all results are recorded before
    planning another wave. A failure in one worker aborts instead of silently
    treating an execution error as infeasibility.
    """
    lookup = {candidate.candidate_id: candidate for candidate in batch}
    waves = launches = peak = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            if deadline_reached() and (waves or not allow_first_wave_past_deadline):
                break
            available = call_room()
            if available <= 0:
                break
            planned = plan_wave(batch, rows, seed_order, workers, rule=rule)[:available]
            if not planned:
                break
            waves += 1
            launches += len(planned)
            peak = max(peak, len(planned))
            if on_wave_planned is not None:
                on_wave_planned(planned)
            futures = {
                pool.submit(evaluate, lookup[cell.candidate_id], cell.arrival_seed): cell
                for cell in planned
            }
            for future in as_completed(futures):
                row = future.result()
                expected = futures[future]
                if (
                    row["candidate_id"] != expected.candidate_id
                    or int(row["arrival_seed"]) != expected.arrival_seed
                ):
                    raise ValueError("OC fanout worker returned a crossed candidate/table identity")
                record(row)
    return {"waves": waves, "launches": launches, "peak_workers": peak}
