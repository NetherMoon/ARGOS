"""Phase 3 scenario evaluator that delegates simulation to the audited Phase 2C worker."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from argos.experimental_sa.paper_consistent.evaluator import prepare


class Phase3Evaluator:
    """Materialize a real generated job table, then invoke the unchanged Phase 2C worker."""

    def __init__(
        self,
        root: Path,
        trajectory_dir: Path,
        specification: dict,
        case: dict,
        expected_grid_hash: str,
        method: str,
    ):
        if method not in {"fixed", "varying"}:
            raise ValueError("Unknown arrival policy")
        self.root = root.resolve()
        self.output = trajectory_dir.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.spec = specification
        self.case = case
        self.expected_grid_hash = expected_grid_hash
        self.method = method
        self.fixed_context_dir = self.output / "fixed_initial_state"

    def _context_dir(self, iteration: int) -> Path:
        return (
            self.fixed_context_dir
            if self.method == "fixed"
            else self.output / "initial_states" / f"{iteration:06d}"
        )

    def _ensure_context(self, iteration: int, arrival_seed: int) -> tuple[Path, dict]:
        context_dir = self._context_dir(iteration)
        context_path = context_dir / "fixed_context.json"
        if context_path.exists():
            context = json.loads(context_path.read_text())
            if context["arrival_seed"] != arrival_seed:
                raise ValueError("Existing initial state has the wrong arrival seed")
            initial = context_dir / "initial_jobs.csv.gz"
            if not initial.exists():
                raise ValueError("Incomplete initial-state context")
            return context_dir, context
        if context_dir.exists():
            if any(context_dir.iterdir()):
                raise ValueError("Partial initial-state context requires inspection")
            context_dir.rmdir()
        context, _experiment, _jobs = prepare(
            self.root,
            context_dir,
            self.spec,
            self.case,
            arrival_seed,
            self.expected_grid_hash,
        )
        return context_dir, context

    def __call__(self, params, iteration, scenario) -> dict:
        context_dir = self._context_dir(iteration)
        cell_number = iteration if self.method == "fixed" else 0
        cell = context_dir / "evaluations" / f"{cell_number:06d}"
        raw_path = cell / "raw_result.json"
        request_path = cell / "request.json"
        if raw_path.exists() and request_path.exists():
            request = json.loads(request_path.read_text())
            if (
                request["params"] != list(params)
                or request["runtime_seed"] != scenario.runtime_seed
            ):
                raise ValueError("Completed evaluation does not match planned candidate/scenario")
            raw = json.loads(raw_path.read_text())
            if raw["arrival_seed"] != scenario.arrival_seed:
                raise ValueError("Completed evaluation has the wrong arrival seed")
            if raw.get("phase3_enriched"):
                return {"raw": raw, "simulator_call_performed": False}
            initial_path = context_dir / "initial_jobs.csv.gz"
            if not initial_path.exists():
                raise ValueError("Completed worker output lacks Phase 3 arrival evidence")
            raw = self._enrich(
                raw, initial_path, json.loads((context_dir / "fixed_context.json").read_text())
            )
            raw_path.write_text(json.dumps(raw, indent=2, allow_nan=False), encoding="utf8")
            return {
                "raw": raw,
                "simulator_call_performed": (cell / "flexdc_call_completed").exists(),
            }

        context_dir, context = self._ensure_context(iteration, scenario.arrival_seed)
        cell.mkdir(parents=True, exist_ok=True)
        scratch = cell / "scratch"
        if scratch.exists():
            if scratch.resolve().parent != cell.resolve():
                raise ValueError("Unsafe scratch cleanup")
            shutil.rmtree(scratch)
        request = {
            "context": str(context_dir / "fixed_context.json"),
            "params": list(params),
            "runtime_seed": scenario.runtime_seed,
            "cell": str(cell),
        }
        request_path.write_text(json.dumps(request), encoding="utf8")
        environment = os.environ.copy()
        for name in ["OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"]:
            environment[name] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        with (cell / "worker.log").open("w", encoding="utf8") as log:
            run = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(self.root / "scripts/run_experimental_sa.py"),
                    "--worker",
                    str(request_path),
                ],
                cwd=self.root,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=1800,
                check=False,
            )
        log_path = cell / "worker.log"
        log_path.write_bytes(log_path.read_bytes()[-16384:])
        if run.returncode or not raw_path.exists():
            raise RuntimeError("Isolated FlexDC execution failed; inspect " + str(log_path))
        (cell / "flexdc_call_completed").write_text("1\n", encoding="ascii")
        raw = json.loads(raw_path.read_text())
        initial_path = context_dir / "initial_jobs.csv.gz"
        raw = self._enrich(raw, initial_path, context)
        raw_path.write_text(json.dumps(raw, indent=2, allow_nan=False), encoding="utf8")
        return {"raw": raw, "simulator_call_performed": True}

    def _enrich(self, raw: dict, initial_path: Path, context: dict) -> dict:
        table = pd.read_csv(initial_path, float_precision="round_trip")
        summaries = []
        prefill = int(context["prefill"])
        job_ids = list(range(len(self.case["weights"])))
        for job_id in job_ids:
            arrivals = table.loc[table["job_type_id"] == job_id, "arrival_time"]
            prefill_jobs = int((table.iloc[:prefill]["job_type_id"] == job_id).sum())
            later = table.iloc[prefill:]
            later = later.loc[later["job_type_id"] == job_id, "arrival_time"]
            summaries.append(
                {
                    "job_type_id": job_id,
                    "total_jobs": len(arrivals),
                    "prefill_jobs": prefill_jobs,
                    "later_arrivals": len(later),
                    "min_later_arrival": None if later.empty else float(later.min()),
                    "max_later_arrival": None if later.empty else float(later.max()),
                    "mean_later_arrival": None if later.empty else float(later.mean()),
                }
            )
        if sum(x["prefill_jobs"] for x in summaries) != prefill:
            raise ValueError("Prefill accounting changed")
        raw["arrival_summary"] = summaries
        raw["simulator_policy_contract"] = "normal_v3_argos_aqa"
        raw["phase3_enriched"] = True
        return raw

    def finalize_iteration(self, iteration, scenario, valid: bool) -> None:
        if self.method != "varying" or not valid:
            return
        context_dir = self._context_dir(iteration)
        initial_path = context_dir / "initial_jobs.csv.gz"
        raw_path = context_dir / "evaluations" / "000000" / "raw_result.json"
        if raw_path.exists() and initial_path.exists():
            initial_path.unlink()
            context = json.loads((context_dir / "fixed_context.json").read_text())
            context["initial_file_retained"] = False
            context["initial_file_retention_reason"] = "seed, hash and compact summary retained"
            (context_dir / "fixed_context.json").write_text(
                json.dumps(context, indent=2), encoding="utf8"
            )
