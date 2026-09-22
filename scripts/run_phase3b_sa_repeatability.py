"""Thin Phase 3B entry point; no ARGOS controller or FlexDC source is modified."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from argos.experimental_sa.phase3b.runner import main

if __name__ == "__main__":
    main()
