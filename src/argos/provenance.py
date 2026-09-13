"""Immutable input identities and explicit dependency bootstrapping."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

ARTIFACT = "condor_set_transformer_sweep_v3_behavior_v3_best_feasibility_artifacts"
CHECKPOINT = "condor_set_transformer_sweep_v3_behavior_v3_best_feasibility.pt"
REPOSITORIES = {
    "FlexDC": "https://github.com/amenon871/FlexDC",
    "CONDOR-FLEXDC": "https://github.com/NetherMoon/CONDOR-FLEXDC",
}


def sha256(path: Path) -> str:
    if path.name == ".env" or path.name.startswith(".env."):
        raise ValueError("Environment files are excluded from ARGOS input processing")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def import_file(name: str, path: Path) -> ModuleType:
    """Import source without writing bytecode into immutable reference trees."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old
    return module


def git(path: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={path.resolve().as_posix()}", "-C", str(path), *args],
        text=True,
    ).strip()


def dependency_status(root: Path) -> dict:
    result = {}
    for name, url in REPOSITORIES.items():
        path = root / ".deps" / name
        result[name] = {
            "url": url,
            "commit": git(path, "rev-parse", "HEAD"),
            "branch": git(path, "branch", "--show-current"),
            "dirty": bool(git(path, "status", "--porcelain")),
        }
    return result


def verify_dependencies(root: Path) -> dict:
    expected = read_json(root / "dependency_lock.json")
    actual = dependency_status(root)
    for name, record in actual.items():
        if record["dirty"] or record["commit"] != expected["repositories"][name]["commit"]:
            raise ValueError(f"Dependency lock mismatch: {name}")
        if (
            git(root / ".deps" / name, "remote", "get-url", "origin").removesuffix(".git")
            != record["url"]
        ):
            raise ValueError(f"Dependency URL mismatch: {name}")
    return actual


def bootstrap(root: Path, refresh_lock: bool = False) -> dict:
    lock_path = root / "dependency_lock.json"
    lock = read_json(lock_path) if lock_path.exists() else None
    for name, url in REPOSITORIES.items():
        path = root / ".deps" / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "--branch", "main", url, str(path)], check=True)
            if lock and not refresh_lock:
                git(path, "checkout", "--detach", lock["repositories"][name]["commit"])
        if git(path, "status", "--porcelain"):
            raise ValueError(f"Refusing dirty dependency: {name}")
        if refresh_lock:
            git(path, "fetch", "origin", "main")
            git(path, "checkout", "--detach", "origin/main")
    if lock is None or refresh_lock:
        lock = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "repositories": dependency_status(root),
        }
        write_json(lock_path, lock)
    verify_dependencies(root)
    return lock


def inventory_artifact(root: Path) -> dict:
    directory = root / ARTIFACT
    files = {
        p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)}
        for p in sorted(directory.iterdir())
        if p.is_file() and not p.name.startswith(".env")
    }
    if CHECKPOINT not in files:
        raise FileNotFoundError(CHECKPOINT)
    return {"directory": ARTIFACT, "selected_checkpoint": CHECKPOINT, "files": files}
