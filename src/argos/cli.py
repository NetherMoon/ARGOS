"""ARGOS command line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from argos.provenance import bootstrap, inventory_artifact, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive Region-Guided Optimization Search")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    boot = commands.add_parser("bootstrap")
    boot.add_argument("--refresh-lock", action="store_true")
    commands.add_parser("inspect-artifact")
    args = parser.parse_args()
    if args.command == "bootstrap":
        result = bootstrap(args.root, args.refresh_lock)
    else:
        result = inventory_artifact(args.root)
        write_json(args.root / "artifact_manifest.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
