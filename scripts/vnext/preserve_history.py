"""Read-only content inventory of immutable H1 evidence; never open .env files."""

import argparse
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = [
    ROOT / "runs/campaigns/controlled_development_v2",
    ROOT / "docs/campaign_v2_results",
    ROOT / "docs/CONTROLLED_CAMPAIGN_V2_RESULTS.md",
]


def inventory():
    paths = []
    directories = []
    excluded = []
    for source in SOURCES:
        if not source.exists():
            raise FileNotFoundError(source)
        entries = [source] if source.is_file() else source.rglob("*")
        for p in entries:
            if any(part == ".env" or part.startswith(".env.") for part in p.parts):
                excluded.append(p.relative_to(ROOT).as_posix())
                continue
            if p.is_symlink():
                raise ValueError(f"Unexpected historical symlink: {p}")
            if p.is_file():
                paths.append(p)
            elif p.is_dir():
                directories.append(p.relative_to(ROOT).as_posix())
    records = {}
    start = time.monotonic()
    last = start
    total = 0
    for i, p in enumerate(sorted(paths), 1):
        stat = p.stat()
        h = hashlib.sha256()
        with p.open("rb") as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                h.update(block)
        after = p.stat()
        if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"Historical file changed during read: {p}")
        records[p.relative_to(ROOT).as_posix()] = {"sha256": h.hexdigest(), "bytes": stat.st_size}
        total += stat.st_size
        if time.monotonic() - last > 30:
            print(json.dumps({"hashed": i, "files": len(paths), "bytes": total}), flush=True)
            last = time.monotonic()
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema": 1,
        "files": records,
        "directories": sorted(directories),
        "excluded_env_metadata_only": excluded,
        "aggregate_sha256": hashlib.sha256(canonical).hexdigest(),
        "total_bytes": total,
        "hash_seconds": time.monotonic() - start,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    result = inventory()
    if args.compare:
        before = json.loads(args.compare.read_text(encoding="utf-8"))
        result["historical_files_unchanged"] = (
            before["files"] == result["files"] and before["directories"] == result["directories"]
        )
        if not result["historical_files_unchanged"]:
            raise RuntimeError("Historical evidence changed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "file_count": len(result["files"]),
                "aggregate_sha256": result["aggregate_sha256"],
                "bytes": result["total_bytes"],
                "seconds": result["hash_seconds"],
                "unchanged": result.get("historical_files_unchanged"),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
