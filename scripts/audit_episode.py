"""Compatibility entry point; use argos audit for the supported audit CLI."""

import argparse
import json
from pathlib import Path

from argos.audit import audit_episode

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("episode", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = audit_episode(args.root, args.episode, allow_legacy=True)
    print(json.dumps(result, indent=2))
    raise SystemExit(result["status"] != "PASS")
