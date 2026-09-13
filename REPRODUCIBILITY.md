# Reproducibility

Development platform: Windows, Python 3.12.4, PyTorch 2.4.1+cpu. CPU-only operation.
The initial clones use current main, then dependency_lock.json pins their identities.
All generated data lives under ARGOS; the two user reference repositories are read-only.
Scikit-learn is needed by the immutable training utility imports, not region clustering.
The initial .venv uses system-site-packages; an exact installed-package report will
record the tested environment. A portable installation uses pyproject dependencies.
