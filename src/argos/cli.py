"""ARGOS command line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from argos.config import Config
from argos.provenance import bootstrap, inventory_artifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive Region-Guided Optimization Search")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    boot = commands.add_parser("bootstrap")
    boot.add_argument("--refresh-lock", action="store_true")
    commands.add_parser("inspect-artifact")
    doctor_parser = commands.add_parser("doctor")
    doctor_parser.add_argument("--config", type=Path)
    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    resume = commands.add_parser("resume")
    resume.add_argument("episode_dir", type=Path)
    audit = commands.add_parser(
        "audit", help="Validate reported Pj, raw evidence and provenance without simulator calls"
    )
    audit.add_argument("episode_dir", type=Path)
    audit.add_argument(
        "--allow-legacy-audit",
        "--allow-historical-audit",
        action="store_true",
        help="Allow raw historical audit with separately reported environment mismatches; never grants resume trust",
    )
    audit.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "audit":
        from argos.audit import audit_episode
        from argos.provenance import write_json

        result = audit_episode(args.root, args.episode_dir, args.allow_legacy_audit)
        if args.output:
            # Avoid silently replacing historical episode records.
            if args.output.exists() or args.output.resolve().is_relative_to(
                args.episode_dir.resolve()
            ):
                raise ValueError("Audit output must be a new file outside the historical episode")
            write_json(args.output, result)
        print(json.dumps(result, indent=2))
        if result["status"] != "PASS":
            raise SystemExit(1)
        return
    if args.command == "bootstrap":
        result = bootstrap(args.root, args.refresh_lock)
    elif args.command == "inspect-artifact":
        result = inventory_artifact(args.root)
        # Inspection is read-only once the selected artifact identity has been established.
        print(json.dumps(result, indent=2))
        return
    else:
        from argos.episode import doctor, run_episode

        if args.command == "doctor":
            result = doctor(args.root, Config.load(args.config) if args.config else Config())
        elif args.command == "run":
            run_episode(args.root, args.config)
            return
        else:
            run_episode(args.root, resume=args.episode_dir)
            return
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
