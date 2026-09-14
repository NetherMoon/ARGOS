"""Run and preserve the mandatory pre-execution gate against a clean campaign commit."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from argos.campaign.config import load_config, plan
from argos.campaign.identity import digest
from argos.campaign.runner import audit_plan
from argos.episode import doctor
from argos.provenance import git, sha256, write_json


def main():
    root = Path(__file__).resolve().parents[1]
    if git(root, "status", "--porcelain"):
        raise ValueError("Commit campaign infrastructure before gate")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    config = parser.parse_args().config.resolve()
    directory = plan(root, config)
    receipts = []
    for label, arguments in [
        ("pytest", ["-m", "pytest", "-q"]),
        ("ruff", ["-m", "ruff", "check", "src", "tests", "scripts"]),
        ("format", ["-m", "ruff", "format", "--check", "src", "tests", "scripts"]),
    ]:
        log = directory / "gate" / (label + ".log")
        log.parent.mkdir(parents=True, exist_ok=True)
        print(f"GATE {label}", flush=True)
        with log.open("w", encoding="utf-8") as out:
            result = subprocess.run(
                [sys.executable, "-B", *arguments],
                cwd=root,
                stdout=out,
                stderr=subprocess.STDOUT,
                check=False,
            )
        receipts.append(
            {
                "check": label,
                "returncode": result.returncode,
                "log": str(log),
                "sha256": sha256(log),
            }
        )
        if result.returncode:
            write_json(directory / "gate/failure.json", receipts)
            raise RuntimeError(f"Gate failed: {label}; see {log}")
    manifest = audit_plan(root, directory)
    result = doctor(root, load_config(manifest["cases"][0]["settings"]))
    write_json(directory / "gate/doctor.json", result)
    receipts.append(
        {
            "check": "doctor",
            "status": result["status"],
            "sha256": sha256(directory / "gate/doctor.json"),
        }
    )
    write_json(
        directory / "execution_gate.json",
        {
            "status": "PASS",
            "source_identity_digest": digest(manifest["identity"]),
            "campaign_head": git(root, "rev-parse", "HEAD"),
            "checks": receipts,
            "expanded_plan_sha256": sha256(directory / "campaign_cases.csv"),
            "campaign_manifest_sha256": sha256(directory / "campaign_manifest.json"),
        },
    )
    print(
        json.dumps(
            {"status": "PASS", "directory": str(directory), "head": git(root, "rev-parse", "HEAD")}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
