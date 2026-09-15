# RX 7700S investigation

The local HIP 6.2 utility enumerated AMD Radeon RX 7700S (gfx1102, discrete, approximately 8 GB) and Radeon 780M (gfx1103, integrated). Windows driver metadata reports 32.0.31007.5012. HIP enumeration alone does not establish a usable PyTorch backend.

The canonical paper environment is Python 3.12.4, torch 2.4.1+cpu. torch.cuda.is_available() is false; torch.version.cuda and torch.version.hip are null. Ubuntu is Python 3.12.3, has no torch installed, and no rocminfo. No existing ROCm/PyTorch environment was found in the inspected Ubuntu home directories. No system drivers, architecture overrides, or paper dependencies were changed.

AMD's versioned [Windows PyTorch 7.2.1 matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityrad/windows/windows_compatibility.html), read 2026-09-14, lists gfx1100/gfx1101/gfx1200/gfx1201, not the observed gfx1102 device. This version-specific evidence is not a claim about every newer/community build. A bounded investigation did not establish a supported, already-functional local PyTorch/HIP path.

Decision: use the unchanged CPU paper environment. Gates A-F (GPU tensors, checkpoint, forward parity, input gradients, small optimizer, larger optimizer) are NOT RUN, because no working PyTorch/HIP environment was established. CPU/HIP 128-start and 512x1500 timing comparison is NOT RUN; no GPU speedup is claimed. A driver or unsupported-wheel migration is outside this bounded development check. New backend metadata and tests distinguish CPU, NVIDIA CUDA, and HIP, and use the current device rather than assuming device 0 is the dGPU. H1 source remains byte-for-byte unchanged.
