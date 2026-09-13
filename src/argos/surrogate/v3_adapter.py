"""Read-only V3 source adapter; no architecture or optimizer-loop duplication."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from types import FunctionType
from typing import Any

import pandas as pd
import torch

from argos.provenance import ARTIFACT, CHECKPOINT, import_file


class V3Adapter:
    """Use exact bundled model/features and pinned generic inference machinery.

    Temporary import aliases bind the generic inference imports to artifact code.
    A private function-global namespace supplies observation hooks during search;
    the dependency module and optimizer bytecode remain unmodified.
    """

    def __init__(self, root: Path, threads: int = 4, device: str = "cpu"):
        torch.set_num_threads(threads)
        resolved, self.device_metadata = resolve_device(device, threads)
        artifact = root / ARTIFACT
        self.training = import_file(
            "_argos_v3_training", artifact / "am_flexdc_behavior_training_utilities_v3.py"
        )
        self.architecture = import_file(
            "_argos_v3_architecture", artifact / "data_center_model_flexdc_behavior_v3.py"
        )
        source = (
            root
            / ".deps/CONDOR-FLEXDC/am_flexdc/flexdc_generic_sources/flexdc_generic_sources/flexdc_behavior_inference_utilities.py"
        )
        aliases = {
            "flexdc_behavior_training_utilities": self.training,
            "data_center_model_flexdc_behavior": self.architecture,
        }
        previous = {name: sys.modules.get(name) for name in aliases}
        try:
            sys.modules.update(aliases)
            self.api = import_file("_argos_v3_inference", source)
        finally:
            for name, module in previous.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module
        self.loaded = self.api.load_behavior_model(artifact / CHECKPOINT, device_name=resolved)
        c = self.loaded.checkpoint
        if c.get("format_version") != 3 or c["epoch"] != c["best_epochs"]["best_feasibility"]:
            raise ValueError("Selected artifact is not the recorded V3 best-feasibility checkpoint")
        if any(p.requires_grad for p in self.loaded.model.parameters()):
            raise ValueError("V3 parameters must be frozen")

    def context(
        self, workload: Path, experiment: Path, server_count: int, utilization: float, seed: int
    ) -> tuple[Any, Any]:
        w = self.api.read_workload_config(workload)
        e = self.api.read_experiment_config(experiment)
        from argos.simulator.evidence import ordered_jobs

        jobs = ordered_jobs(workload)
        if w.job_names != [j.section for j in jobs] or w.mix.tolist() != [
            list(j.descriptors) for j in jobs
        ]:
            raise ValueError("V3 token/workload identity order mismatch")
        return w, replace(e, server_count=server_count, utilization=utilization, random_seed=seed)

    def predict(
        self, workload: Any, experiment: Any, pbar: float, reserve: float, weights: list[float]
    ) -> dict:
        result, _ = self.api.predict_configuration(
            self.loaded,
            workload=workload,
            experiment=experiment,
            pbar_kw_per_server=pbar,
            r_kw_per_server=reserve,
            weights=weights,
            safety=self.api.resolve_safety_limits(self.loaded.constants),
        )
        return result

    def optimize(
        self,
        *,
        workload: Any,
        experiment: Any,
        settings: Any,
        snapshot_every: int,
        capture: bool = True,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if snapshot_every < 1:
            raise ValueError("snapshot_every must be positive")
        original = self.api.optimize_candidates
        kwargs = {
            "workload": workload,
            "experiment": experiment,
            "settings": settings,
            "bounds": self.api.calculate_pr_bounds(workload),
            "safety": self.api.resolve_safety_limits(self.loaded.constants),
        }
        if not capture:
            endpoints, _, trajectory = original(self.loaded, **kwargs)
            return endpoints, pd.DataFrame(), trajectory
        namespace = dict(original.__globals__)
        latest_weights = None
        iteration = 0
        rows = []

        def weights_hook(*args: Any, **kw: Any) -> torch.Tensor:
            nonlocal latest_weights
            latest_weights = self.api.parameterize_weights(*args, **kw)
            return latest_weights

        def output_hook(**kw: Any) -> dict:
            nonlocal iteration
            outputs = self.api.reconstruct_differentiable_outputs(**kw)
            if iteration % snapshot_every == 0 or iteration == settings.iterations:
                arrays = {k: v.detach().cpu().numpy() for k, v in outputs.items()}
                ps = kw["pbar"].detach().cpu().numpy()
                rs = kw["reserve"].detach().cpu().numpy()
                ws = latest_weights.detach().cpu().numpy()
                for i in range(settings.starts):
                    rows.append(
                        {
                            "Start_Index": i,
                            "Iteration": iteration,
                            "Pbar_kw_per_server": float(ps[i]),
                            "R_kw_per_server": float(rs[i]),
                            "weights": ws[i].astype(float).tolist(),
                            "Predicted_Mean_Tracking": float(arrays["mean_tracking"][i]),
                            "Predicted_P90_Tracking": float(arrays["p90_tracking"][i]),
                            "Predicted_QoS_Probabilities": arrays["qos_probabilities"][i]
                            .astype(float)
                            .tolist(),
                            "Predicted_Full_Objective": float(arrays["objective"][i]),
                        }
                    )
            iteration += 1
            return outputs

        namespace.update(
            parameterize_weights=weights_hook, reconstruct_differentiable_outputs=output_hook
        )
        wrapped = FunctionType(
            original.__code__,
            namespace,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        wrapped.__kwdefaults__ = original.__kwdefaults__
        endpoints, _, trajectory = wrapped(self.loaded, **kwargs)
        if iteration != settings.iterations + 1:
            raise ValueError("Upstream optimizer call sequence changed; snapshot contract failed")
        return endpoints, pd.DataFrame(rows), trajectory


def resolve_device(requested: str, threads: int) -> tuple[str, dict]:
    if requested not in {"cpu", "cuda", "auto"}:
        raise ValueError("Device must be cpu, cuda, or auto")
    available = torch.cuda.is_available()
    if requested == "cuda" and not available:
        raise RuntimeError("CUDA explicitly requested but unavailable")
    resolved = "cuda" if available and requested != "cpu" else "cpu"
    return resolved, {
        "requested": requested,
        "resolved": resolved,
        "torch_version": str(torch.__version__),
        "cuda_available": available,
        "cuda_runtime": torch.version.cuda,
        "gpu_name": torch.cuda.get_device_name(0) if resolved == "cuda" else None,
        "dtype": "float32",
        "torch_threads": threads,
    }
