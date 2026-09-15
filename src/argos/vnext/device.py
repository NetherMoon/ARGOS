"""Backend metadata for new research runs, preserving frozen H1 source bytes."""

import torch

from argos.surrogate.v3_adapter import V3Adapter as H1Adapter


def resolve_device(requested, threads):
    if requested not in {"cpu", "cuda", "auto"}:
        raise ValueError("Device must be cpu, cuda, or auto")
    available = torch.cuda.is_available()
    if requested == "cuda" and not available:
        raise RuntimeError("GPU explicitly requested but unavailable")
    resolved = "cuda" if available and requested != "cpu" else "cpu"
    hip = getattr(torch.version, "hip", None)
    return resolved, {
        "requested": requested,
        "resolved": resolved,
        "backend": ("HIP" if hip else "CUDA") if resolved == "cuda" else "CPU",
        "torch_version": str(torch.__version__),
        "cuda_available": available,
        "cuda_runtime": torch.version.cuda,
        "hip_runtime": hip,
        "device_index": torch.cuda.current_device() if resolved == "cuda" else None,
        "gpu_name": torch.cuda.get_device_name(torch.cuda.current_device())
        if resolved == "cuda"
        else None,
        "dtype": "float32",
        "torch_threads": threads,
    }


class V3Adapter(H1Adapter):
    def __init__(self, root, threads=4, device="cpu"):
        super().__init__(root, threads, device)
        _, self.device_metadata = resolve_device(device, threads)
