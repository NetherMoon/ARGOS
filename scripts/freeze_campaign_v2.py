"""Derive corrected campaign v2 without changing any predeclared case or seed."""

import argparse
import copy
import json
from pathlib import Path

from argos.provenance import git, read_json, sha256
from argos.surrogate.weights import WEIGHT_PARAMETERIZATION


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-tag", required=True)
    args = parser.parse_args()
    original = root / "configs/campaigns/controlled_v1.json"
    target = root / "configs/campaigns/controlled_v2.json"
    if target.exists():
        raise ValueError("Cannot overwrite a frozen v2 protocol")
    core = git(root, "rev-parse", args.core_tag + "^{commit}")
    protocol = copy.deepcopy(read_json(original))
    protocol.update(
        campaign_id="controlled_development_v2",
        frozen_core=core,
        core_tag=args.core_tag,
        output="runs/campaigns/controlled_development_v2",
        weight_parameterization=WEIGHT_PARAMETERIZATION,
        supersedes={
            "campaign_id": "controlled_development_v1",
            "protocol_sha256": sha256(original),
            "reason": "User-authorized v0.3.0 bounded-weight correctness fix after stopped c001 bank",
            "prior_results": "Preserve as original-version engineering evidence; do not reuse as v2 results",
        },
        v3_selection=(
            "Corrected bounded-logistic weight transform for every V3-based method; "
            "unchanged pinned select_distinct_top_k Safety_Both_Pass; first original rank; "
            "no accepted endpoint means zero-query NO_BID"
        ),
    )
    assert protocol["cases"] == read_json(original)["cases"]
    target.write_bytes((json.dumps(protocol, indent=2, allow_nan=False) + "\n").encode())
    print(
        json.dumps(
            {
                "path": str(target),
                "core": core,
                "tag": args.core_tag,
                "protocol_sha256": sha256(target),
                "ledger_sha256": protocol["ledger_sha256"],
                "contexts": len(protocol["cases"]),
                "method_cases": sum(len(c["methods"]) for c in protocol["cases"]),
                "all_case_settings_and_seeds_unchanged": True,
                "old_results_reused": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
