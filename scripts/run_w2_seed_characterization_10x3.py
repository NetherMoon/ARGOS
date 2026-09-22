"""Thin entry point; use the existing paper Python from the ARGOS root."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from argos.diagnostics.seed_characterization import main

if __name__ == "__main__":
    raise SystemExit(main())
