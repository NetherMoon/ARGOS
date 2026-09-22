"""Run from the ARGOS root with the pinned paper Python environment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from argos.diagnostics.seed_factorization import main

if __name__ == "__main__":
    raise SystemExit(main())
