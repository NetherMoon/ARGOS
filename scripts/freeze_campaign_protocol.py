"""One-time deterministic protocol genesis; reserved values are never printed."""

import hashlib
import itertools
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from argos.config import Config
from argos.provenance import ARTIFACT, git, sha256

ROOT = Path(__file__).resolve().parents[1]
CORE = "425eec6b7fec1202bdc97b88f7b50c23ca575aa0"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def main():
    target = ROOT / "configs/campaigns"
    if (target / "seed_ledger_v1.json").exists():
        raise ValueError("Genesis cannot replace an existing ledger")
    if git(ROOT, "rev-parse", "v0.2.0-pretest^{commit}") != CORE:
        raise ValueError("Frozen tag mismatch")
    sources = []
    historical = {20, 100020, 100021, 2026091301}
    for split in ["train", "validation", "test"]:
        matches = list((ROOT / ARTIFACT).glob(f"*{split}*predictions.csv"))
        if len(matches) != 1:
            raise ValueError(f"Expected one saved {split} predictions file: {matches}")
        p = matches[0]
        d = pd.read_csv(p)
        seeds = d.Plan_Row_ID.str.extract(r"__seed(\d+)$")[0]
        if seeds.isna().any():
            raise ValueError("Unknown V3 simulator seed")
        counts = seeds.astype(int).value_counts().sort_index()
        historical.update(counts.index.tolist())
        sources.append(
            {
                "split": split,
                "path": str(p.relative_to(ROOT)),
                "sha256": sha256(p),
                "rows": len(d),
                "seed_counts": {str(k): int(v) for k, v in counts.items()},
                "contexts": d[["Workload_Name", "server_count", "utilization"]]
                .drop_duplicates()
                .sort_values(["Workload_Name", "server_count", "utilization"])
                .to_dict("records"),
            }
        )
    executions = []
    for p in sorted((ROOT / "runs").glob("*/flexdc_raw/*/attempt-*/execution.json")):
        d = json.loads(p.read_text())
        historical.add(d["identity"]["seed"])
        executions.append(
            {
                "path": str(p.relative_to(ROOT)),
                "sha256": sha256(p),
                "seed": d["identity"]["seed"],
                "phase": d["identity"]["phase"],
            }
        )
    generator = ROOT / ".deps/FlexDC/am_generate_flexdc_sweep_plan_v3.py"
    provenance = {
        "v3_splits": sources,
        "historical_executions": executions,
        "generator_sha256": sha256(generator),
        "training_server_counts": [250, 1000],
        "training_utilizations": [0.6, 0.8],
        "historical_v4_authority": "User authorized pinned V4 INIs and manifest; original generator unavailable",
        "unseen_profile_status": "No provenance-supported unseen-profile experiment declared",
    }
    write_json(target / "provenance_v1.json", provenance)
    used = set(historical)
    groups = {"historical_or_training": sorted(historical)}
    counts = {
        "engineering_smoke": 3,
        "campaign_development_search": 96,
        "campaign_development_confirmation": 192,
        "reserved_final_benchmark_search": 100,
        "reserved_final_benchmark_confirmation": 200,
    }
    for name, count in counts.items():
        values = []
        counter = 0
        while len(values) < count:
            value = int.from_bytes(
                hashlib.sha256(f"ARGOS-controlled-v1/{name}/{counter}".encode()).digest()[:4], "big"
            )
            counter += 1
            if value not in used:
                used.add(value)
                values.append(value)
        groups[name] = values
    ledger = {
        "schema": 1,
        "generation": "SHA256 ARGOS-controlled-v1/group/counter, first 32 bits, collision rejection",
        "provenance_sha256": sha256(target / "provenance_v1.json"),
        "groups": groups,
        "reserved_policy": "Never supply reserved groups to campaign planning, search, confirmation, or reporting",
    }
    write_json(target / "seed_ledger_v1.json", ledger)
    methods = [
        "v3_only",
        "v3_fixed_probing",
        "simulator_only_adaptive",
        "argos_fixed_budget",
        "argos_early_stop",
    ]
    cases = []

    def add(phase, workload, category, tier="SERIOUS_DEVELOPMENT", n=1000, u=0.6, method_list=None):
        i = len(cases)
        settings = asdict(Config())
        settings.update(
            run_mode="paper",
            server_count=n,
            utilization=u,
            candidate_seed=300000 + i,
            search_seed=groups["campaign_development_search"][i],
            confirmation_seeds=groups["campaign_development_confirmation"][2 * i : 2 * i + 2],
        )
        if tier == "SCREENING":
            settings.update(starts=128, iterations=500, max_search_batches=2, max_search_calls=16)
        if tier == "ENGINEERING_SMOKE":
            settings.update(
                starts=4,
                iterations=4,
                snapshot_every=2,
                batch_size=2,
                independent_per_batch=1,
                max_search_batches=2,
                max_search_calls=4,
                search_seed=groups["engineering_smoke"][0],
                confirmation_seeds=groups["engineering_smoke"][1:],
            )
        cases.append(
            {
                "case_id": f"c{i:03d}",
                "phase": phase,
                "workload": workload,
                "category": category,
                "tier": tier,
                "methods": method_list or methods,
                "settings": settings,
            }
        )

    original = [
        "W1-train-qos3333",
        "W1-train-qos4444",
        "W2-short-qos5_4.5_4_3.5",
        "W2-short-qos5555",
    ]
    add(0, original[0], "ORIGINAL_W1", "ENGINEERING_SMOKE")
    for workload in original:
        for u in [0.6, 0.8]:
            add(1, workload, "ORIGINAL_W1" if workload.startswith("W1") else "ORIGINAL_W2", u=u)
    mixed = ["".join(x) for x in itertools.product("TI", repeat=4) if len(set(x)) > 1]
    for name in mixed:
        add(2, "MIX4-" + name, "CLEAN_J4_COMPOSITION", "SCREENING")
    serious = ["TTII", "IITT", "ITTT", "TTTI", "TIII", "IIIT"]
    for name in serious:
        add(2, "MIX4-" + name, "CLEAN_J4_COMPOSITION")
    for name in ["H4-RG", "H4-GL", "H4-LB", "H4-BR", "J5-GPT2", "J5-Bloom", "J6-RGL", "J8-ALL"]:
        add(3, "V4-" + name, "HISTORICAL_V4_COMPOSITION_PLUS_QOS_STRESS")
    structural = {
        "J3-TRAIN": [[0, "T"], [1, "T"], [2, "T"]],
        "J3-INFER": [[0, "I"], [1, "I"], [2, "I"]],
        "J5-TRAIN4-GPT2I": [[0, "T"], [1, "T"], [2, "T"], [3, "T"], [1, "I"]],
        "J5-GPT2T-INFER4": [[1, "T"], [0, "I"], [1, "I"], [2, "I"], [3, "I"]],
        "J6-RGL": [[f, r] for f in range(3) for r in "TI"],
        "J8-ALL": [[f, r] for f in range(4) for r in "TI"],
    }
    for name in structural:
        add(4, name, "CLEAN_STRUCTURAL_" + name.split("-")[0])
    for workload in [original[1], original[3]]:
        for n, u, label in [(500, 0.7, "INTERPOLATION_LIKE"), (1500, 0.9, "EXTRAPOLATION_LIKE")]:
            add(
                5,
                workload,
                "OPERATING_" + label,
                n=n,
                u=u,
                method_list=["v3_only", "simulator_only_adaptive", "argos_fixed_budget"],
            )
    protocol = {
        "schema": 1,
        "campaign_id": "controlled_development_v1",
        "frozen_core": CORE,
        "core_tag": "v0.2.0-pretest",
        "output": "runs/campaigns/controlled_development_v1",
        "ledger": "configs/campaigns/seed_ledger_v1.json",
        "ledger_sha256": sha256(target / "seed_ledger_v1.json"),
        "provenance": "configs/campaigns/provenance_v1.json",
        "provenance_sha256": sha256(target / "provenance_v1.json"),
        "original_workloads": original,
        "structural_workloads": structural,
        "serious_compositions": serious,
        "cases": cases,
        "fixed_probe_policy": "First core initial batch; remaining guided slots cycle local perturbations of original region representatives; same independent slots per batch; whole set frozen before simulator feedback",
        "v3_selection": "Pinned select_distinct_top_k Safety_Both_Pass; first original rank; no accepted endpoint means zero-query NO_BID",
        "sa_representatives": ["W1-train-qos4444", "W2-short-qos5555", "MIX4-TTII", "J3-TRAIN"],
        "sa_gate": "Run only if unchanged upstream supports controlled canonical-objective/evidence protocol; otherwise report source incompatibility without modifying SA",
        "optional_repeated_profiles": False,
        "timing": "Logical V3 full measured bank runtime; simulator batch estimate by deterministic FIFO list scheduling of physical execution durations on at most four workers; physical time and reuse separate",
        "scientific_limits": [
            "One search scenario and one bank initialization per case",
            "Two fresh confirmation scenarios are descriptive only",
            "One-hour horizon and per-job evidence counts retained",
            "No locked benchmark seeds used",
        ],
    }
    write_json(target / "controlled_v1.json", protocol)
    print(
        json.dumps(
            {
                "cases": len(cases),
                "method_cases": sum(len(c["methods"]) for c in cases),
                "historical_seeds": groups["historical_or_training"],
                "group_counts": {k: len(v) for k, v in groups.items()},
                "ledger_sha256": sha256(target / "seed_ledger_v1.json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
