"""Real FlexDC evaluator for shared three-scenario panels."""

from __future__ import annotations

from pathlib import Path

from argos.experimental_sa.phase3.evaluator import Phase3Evaluator
from argos.experimental_sa.phase3.scenarios import Scenario


class SharedPanelEvaluator:
    """Evaluate one candidate on three isolated generated job tables."""

    def __init__(self, root: Path, output: Path, specification: dict, case: dict, grid_hash: str):
        self.evaluators = [
            Phase3Evaluator(
                root,
                output / "panel_scenarios" / f"slot_{slot}",
                specification,
                case,
                grid_hash,
                "varying",
            )
            for slot in range(3)
        ]

    def evaluate_panel(self, *, params, evaluation_id: int, panel_index: int,
                       panel_seeds: list[int], runtime_seed: int) -> dict:
        if len(panel_seeds) != 3:
            raise ValueError("Shared panel must contain exactly three seeds")
        raw_results = []
        performed = 0
        for slot, (seed, evaluator) in enumerate(zip(panel_seeds, self.evaluators, strict=True)):
            scenario = Scenario(int(evaluation_id), int(seed), int(runtime_seed))
            response = evaluator(params, int(evaluation_id), scenario)
            raw_results.append(response["raw"])
            performed += int(response.get("simulator_call_performed", True))
            evaluator.finalize_iteration(int(evaluation_id), scenario, True)
        hashes = [x["grid_signal_hash"] for x in raw_results]
        if len(set(hashes)) != 1:
            raise ValueError("Grid hash differs inside shared panel")
        if {int(x["runtime_seed"]) for x in raw_results} != {int(runtime_seed)}:
            raise ValueError("Runtime seed differs inside shared panel")
        return {
            "panel_index": int(panel_index),
            "panel_seeds": [int(x) for x in panel_seeds],
            "raw_results": raw_results,
            "performed_calls": performed,
        }

