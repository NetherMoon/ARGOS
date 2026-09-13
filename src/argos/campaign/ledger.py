"""Validate disjoint seed groups; expose development allocations only."""

from pathlib import Path

from argos.provenance import read_json, sha256

GROUPS = (
    "historical_or_training",
    "engineering_smoke",
    "campaign_development_search",
    "campaign_development_confirmation",
    "reserved_final_benchmark_search",
    "reserved_final_benchmark_confirmation",
)


def validate_ledger(path: Path, expected: str) -> dict:
    if sha256(path) != expected:
        raise ValueError("Seed ledger digest mismatch")
    ledger = read_json(path)
    groups = ledger["groups"]
    if set(groups) != set(GROUPS):
        raise ValueError("Unexpected seed groups")
    seen = set()
    for name in GROUPS:
        values = groups[name]
        if any(type(v) is not int or not 0 <= v < 2**32 for v in values):
            raise ValueError("Invalid seed")
        if len(set(values)) != len(values) or seen.intersection(values):
            raise ValueError("Seed leakage/overlap")
        seen.update(values)
    return {
        "sha256": expected,
        "counts": {k: len(v) for k, v in groups.items()},
        "development": {k: groups[k] for k in GROUPS[:4]},
    }


def validate_case_seeds(case: dict, ledger: dict) -> None:
    groups = ledger["development"]
    config = case["settings"]
    search = config["search_seed"]
    confirmations = config["confirmation_seeds"]
    if case["tier"] == "ENGINEERING_SMOKE":
        allowed_search = groups["engineering_smoke"][:1]
        allowed_confirmation = groups["engineering_smoke"][1:]
    else:
        allowed_search = groups["campaign_development_search"]
        allowed_confirmation = groups["campaign_development_confirmation"]
    if search not in allowed_search or len(confirmations) != 2:
        raise ValueError("Unallocated search/confirmation seed")
    if len(set(confirmations)) != 2 or search in confirmations:
        raise ValueError("Confirmation overlap")
    if not set(confirmations) <= set(allowed_confirmation):
        raise ValueError("Unallocated confirmation seed")
