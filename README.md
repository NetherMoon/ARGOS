# ARGOS

Adaptive Region-Guided Optimization Search. Frozen CONDOR V3 proposes candidate
regions; FlexDC supplies simulator evidence; ARGOS will control bounded adaptive
search and independent confirmation. This repository is under implementation.

Install with `python -m pip install -e ".[dev]"`, then `argos bootstrap`.
Place the immutable V3 bundle in the directory named in `artifact_manifest.json`.
Dependency versions are pinned in `dependency_lock.json`; refresh is explicit.

References: https://github.com/amenon871/FlexDC and
https://github.com/NetherMoon/CONDOR-FLEXDC.

Numerical feasibility requires p90 <= 0.30 and every job Pj <= 0.10. Evidence
validity is separate. No universal feasibility or reliability guarantee is claimed.
