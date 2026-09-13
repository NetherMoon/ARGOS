"""Create and test a genuinely clean checkout and new isolated environment."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import venv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    gate = root / "runs/release_gate" / (head[:12] + "_" + str(time.time_ns()))
    checkout = gate / "checkout"
    gate.mkdir(parents=True)
    subprocess.run(
        ["git", "clone", "--no-hardlinks", "--no-checkout", str(root), str(checkout)], check=True
    )
    subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", head], check=True)
    absent = [
        ".venv",
        ".deps",
        "runs",
        ".pytest_cache",
        ".pytest_tmp",
        "condor_set_transformer_sweep_v3_behavior_v3_best_feasibility_artifacts",
    ]
    assert all(not (checkout / name).exists() for name in absent)
    environment = gate / "fresh_venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment)
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    commands = [
        [str(python), "-m", "pip", "install", "-e", ".[dev]"],
        [str(python), "-B", "-m", "pytest", "-q"],
        [str(python), "-B", "-m", "ruff", "check", "."],
        [str(python), "-B", "-m", "ruff", "format", "--check", "."],
        [str(python), "-B", "-m", "argos.cli", "--help"],
    ]
    results = []
    for i, command in enumerate(commands):
        print(f"Release gate {i + 1}/{len(commands)}: {' '.join(command[1:])}", flush=True)
        start = time.perf_counter()
        with (gate / f"step_{i + 1}.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(
                command, cwd=checkout, stdout=log, stderr=subprocess.STDOUT, check=False
            )
        results.append(
            {
                "step": i + 1,
                "arguments": command[1:],
                "exit_code": result.returncode,
                "seconds": time.perf_counter() - start,
            }
        )
        (gate / "result.json").write_text(
            json.dumps(
                {
                    "head": head,
                    "clean_initial_absence": absent,
                    "isolated_venv": True,
                    "steps": results,
                    "runs_created": (checkout / "runs").exists(),
                },
                indent=2,
            )
        )
        if result.returncode:
            print((gate / f"step_{i + 1}.log").read_text(encoding="utf-8")[-6000:])
            raise SystemExit(result.returncode)
    assert not (checkout / "runs").exists()
    print(f"PASS: {gate.relative_to(root)}", flush=True)


if __name__ == "__main__":
    main()
