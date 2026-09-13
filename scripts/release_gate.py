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
    parser.add_argument("--environment", choices=("portable", "paper-cpu"), default="portable")
    args = parser.parse_args()
    if args.environment == "paper-cpu" and sys.version_info[:3] != (3, 12, 4):
        raise RuntimeError("Paper CPU gate requires the declared Python 3.12.4 interpreter")
    root = args.root.resolve()
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    gate = (
        root
        / "runs/release_gate"
        / (head[:12] + "_" + args.environment + "_" + str(time.time_ns()))
    )
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
    install = [[str(python), "-m", "pip", "install", "--no-compile", "-e", ".[dev]"]]
    if args.environment == "paper-cpu":
        install = [
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-compile",
                "-c",
                "constraints-paper-cpu.txt",
                "setuptools",
                "wheel",
            ],
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-compile",
                "--no-build-isolation",
                "-c",
                "constraints-paper-cpu.txt",
                "--extra-index-url",
                "https://download.pytorch.org/whl/cpu",
                "-e",
                ".[dev]",
            ],
        ]
    commands = install + [
        [str(python), "-m", "pip", "check"],
        [str(python), "-B", "-m", "pytest", "-q"],
        [str(python), "-B", "-m", "ruff", "check", "."],
        [str(python), "-B", "-m", "ruff", "format", "--check", "."],
        [
            str(environment / ("Scripts/argos.exe" if sys.platform == "win32" else "bin/argos")),
            "--help",
        ],
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
                    "status": "FAIL" if result.returncode else "RUNNING",
                    "environment": args.environment,
                    "python": sys.version,
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
    with (gate / "installed_packages.json").open("w", encoding="utf-8") as log:
        subprocess.run([str(python), "-m", "pip", "list", "--format=json"], stdout=log, check=True)
    if args.environment == "paper-cpu":
        subprocess.run(
            [
                str(python),
                "-c",
                "import torch; assert torch.__version__ == '2.4.1+cpu'; assert torch.version.cuda is None",
            ],
            check=True,
        )
    receipt = json.loads((gate / "result.json").read_text())
    receipt["status"] = "PASS"
    (gate / "result.json").write_text(json.dumps(receipt, indent=2))
    print(f"PASS: {gate.relative_to(root)}", flush=True)


if __name__ == "__main__":
    main()
