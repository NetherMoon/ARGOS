"""Thin Phase 3 entry point; no ARGOS controller behavior is modified."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argos.experimental_sa.phase3.runner import main

if __name__ == "__main__":
    main()
