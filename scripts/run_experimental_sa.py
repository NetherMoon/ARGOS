"""Thin entry point; all experimental behavior lives outside ARGOS search."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from argos.experimental_sa.paper_consistent.runner import main

if __name__ == "__main__":
    main()
