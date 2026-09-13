"""Campaign command routing."""

import json
from pathlib import Path


def add_parser(commands):
    parser = commands.add_parser("campaign", help="Controlled frozen-core experiments")
    sub = parser.add_subparsers(dest="campaign_command", required=True)
    for name in ["plan", "run"]:
        p = sub.add_parser(name)
        p.add_argument("--config", type=Path, required=True)
        if name == "run":
            p.add_argument("--phases", type=int, nargs="+")
    for name in ["resume", "audit", "report"]:
        p = sub.add_parser(name)
        p.add_argument("campaign_dir", type=Path)
        if name == "resume":
            p.add_argument("--phases", type=int, nargs="+")


def dispatch(args):
    from argos.campaign.config import plan
    from argos.campaign.reporting import campaign_report
    from argos.campaign.runner import audit, run

    root = args.root.resolve()
    command = args.campaign_command
    if command in {"plan", "run"}:
        directory = plan(root, args.config.resolve())
        result = {"campaign_dir": str(directory)}
        if command == "run":
            result = run(root, directory, args.phases)
    else:
        directory = args.campaign_dir.resolve()
        if command == "resume":
            result = run(root, directory, args.phases)
        elif command == "audit":
            result = audit(root, directory)
        else:
            result = campaign_report(directory)
    print(json.dumps(result, indent=2))
