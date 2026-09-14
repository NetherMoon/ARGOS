"""Strict content identities and immutable campaign receipts."""

import hashlib
import json
from pathlib import Path

from argos.provenance import git, read_json, sha256, write_json

CORE = "425eec6b7fec1202bdc97b88f7b50c23ca575aa0"


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()
    ).hexdigest()


def immutable_json(path: Path, value) -> str:
    if path.exists():
        if digest(read_json(path)) != digest(value):
            raise ValueError(f"Immutable campaign record changed: {path.name}")
    else:
        write_json(path, value)
    return sha256(path)


def verify_files(base: Path, files: dict) -> None:
    for name, expected in files.items():
        p = (base / name).resolve()
        if not p.is_relative_to(base.resolve()) or sha256(p) != expected:
            raise ValueError(f"Campaign artifact integrity mismatch: {name}")


def file_manifest(base: Path) -> dict:
    return {
        p.relative_to(base).as_posix(): sha256(p)
        for p in sorted(base.rglob("*"))
        if p.is_file() and p.name != "manifest.json" and not p.name.startswith(".env")
    }


def frozen_core(root: Path, core: str = CORE, tag: str = "v0.2.0-pretest") -> dict:
    if git(root, "rev-parse", f"{tag}^{{commit}}") != core:
        raise ValueError("Frozen core tag mismatch")
    names = git(root, "ls-tree", "-r", "--name-only", core, "src/argos").splitlines()
    changed = []
    hashes = {}
    for name in names:
        original = git(root, "show", f"{core}:{name}")
        actual = (root / name).read_text(encoding="utf-8").strip()
        if core == CORE and name == "src/argos/cli.py":
            start = "    # CAMPAIGN ROUTING START"
            end = "    # CAMPAIGN ROUTING END"
            while start in actual:
                a = actual.index(start)
                b = actual.index(end, a) + len(end)
                actual = actual[:a] + actual[b:].lstrip("\n")
        if actual != original:
            changed.append(name)
        hashes[name] = sha256(root / name)
    if changed:
        raise ValueError(f"Frozen core changed: {changed}")
    return {"commit": core, "tag": tag, "files": hashes}
