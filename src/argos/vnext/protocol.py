"""Original-only frozen protocol and disjoint new seed pools."""

import random
from pathlib import Path

from argos.campaign.config import load_config
from argos.campaign.identity import immutable_json
from argos.context import check_context
from argos.provenance import read_json, sha256

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "runs/vnext_originals"
ALLOWED = {"W1-train-qos3333", "W1-train-qos4444", "W2-short-qos5_4.5_4_3.5", "W2-short-qos5555"}


def validate_case(case):
    c = load_config(case["settings"])
    if (
        case["workload"] not in ALLOWED
        or case["J"] != 4
        or c.server_count != 1000
        or c.utilization not in {0.6, 0.8}
        or c.policy != "AQA"
        or c.allow_context_ood
    ):
        raise ValueError("vNext is restricted to the eight original contexts")
    if (
        c.starts,
        c.iterations,
        c.max_search_calls,
        c.batch_size,
        c.max_search_batches,
        c.independent_per_batch,
    ) != (512, 1500, 32, 8, 4, 2):
        raise ValueError("Frozen effort allocation changed")
    if (
        len(c.confirmation_seeds) != 3
        or len(case["repeat_seeds"]) != 3
        or len({c.search_seed, *c.confirmation_seeds, *case["repeat_seeds"]}) != 7
    ):
        raise ValueError("Invalid scenario allocation")
    if sha256(Path(c.workload)) != case["workload_sha256"]:
        raise ValueError("Workload changed")
    actual_context = check_context(ROOT, c)
    if case.get("context") is not None and case["context"] != actual_context:
        raise ValueError("Original context inputs changed")
    return c


def prepare():
    path = ROOT / "configs/vnext/protocol.json"
    if path.exists():
        raise ValueError("Protocol already prepared; do not overwrite")
    old = read_json(ROOT / "runs/campaigns/controlled_development_v2/campaign_manifest.json")
    # Read membership only; never expose old reserved seed values.
    oldledger = read_json(ROOT / "configs/campaigns/seed_ledger_v1.json")
    excluded = {v for values in oldledger["groups"].values() for v in values}
    excluded.update(c["settings"]["candidate_seed"] for c in old["cases"])
    excluded.update({20, 21, 22})
    rng = random.Random(20260914)
    used = set(excluded)

    def fresh():
        while True:
            v = rng.randrange(1, 2**32)
            if v not in used:
                used.add(v)
                return v

    cases = []
    ledger = {
        "schema": 1,
        "exclusion_ledger_sha256": sha256(ROOT / "configs/campaigns/seed_ledger_v1.json"),
        "excluded_count": len(excluded),
        "overlap_with_all_old_groups": False,
        "groups": {},
    }
    for stage in ["development", "verification"]:
        prefixes = ["primary", "repeat", "confirmation", "candidate"]
        for name in prefixes:
            ledger["groups"][f"vnext_{stage}_{name}"] = []
        originals = [
            c
            for c in old["cases"]
            if c["case_id"] in [f"c{i:03d}" for i in range(1, 9)]
            and (stage == "verification" or c["case_id"] in ["c005", "c006", "c007", "c008"])
        ]
        for oldcase in originals:
            settings = dict(oldcase["settings"])
            workload = BASE / "workloads" / f"{oldcase['workload']}.ini"
            source = Path(settings["workload"])
            workload.parent.mkdir(parents=True, exist_ok=True)
            if workload.exists() and sha256(workload) != sha256(source):
                raise ValueError("New workload copy mismatch")
            if not workload.exists():
                workload.write_bytes(source.read_bytes())
            settings["workload"] = str(workload)
            settings["search_seed"] = fresh()
            settings["confirmation_seeds"] = [fresh() for _ in range(3)]
            settings["candidate_seed"] = fresh()
            repeats = [fresh() for _ in range(3)]
            values = {
                "primary": [settings["search_seed"]],
                "repeat": repeats,
                "confirmation": settings["confirmation_seeds"],
                "candidate": [settings["candidate_seed"]],
            }
            for key, vals in values.items():
                ledger["groups"][f"vnext_{stage}_{key}"].extend(vals)
            case = {
                "case_id": oldcase["case_id"],
                "stage": stage,
                "workload": oldcase["workload"],
                "J": 4,
                "settings": settings,
                "repeat_seeds": repeats,
                "workload_sha256": sha256(workload),
                "methods": ["H1", "E", "ER", "ERT"] if stage == "development" else ["SELECTED"],
            }
            config = validate_case(case)
            case["context"] = check_context(ROOT, config)
            cases.append(case)
    flat = [v for values in ledger["groups"].values() for v in values]
    if len(set(flat)) != len(flat) or excluded.intersection(flat):
        raise ValueError("New seed leakage")
    ledger_path = ROOT / "configs/vnext/seed_ledger.json"
    immutable_json(ledger_path, ledger)
    protocol = {
        "schema": 1,
        "version": "vnext-originals-1",
        "cases": cases,
        "ledger_sha256": sha256(ledger_path),
        "device": "cpu",
        "correction": {
            "selected": "C0",
            "reason": "No candidate correction met prequential W2 improvement requirements; no ERTC duplicate",
        },
        "controller": {
            "elite_count": 2,
            "elite_distance": 0.02,
            "repeat_capacity_by_batch": [0, 2, 3, 3],
            "minimum_search_scenarios": 2,
            "required_screen_failures_allowed": 0,
            "independent_per_batch": 2,
            "target_step": 0.02,
            "weight_transfer": 0.01,
            "trust_radius": 0.06,
            "trust_min": 0.0075,
            "trust_max": 0.12,
            "trust_shrink_after": 2,
            "trust_expand_after": 2,
            "trust_shrink_factor": 0.5,
            "trust_expand_factor": 1.5,
            "local_pool_per_anchor": 32,
            "anchors": 4,
            "repeat_boundary_violation": 0.15,
        },
        "selection_rule": "Lexicographically maximize W2 contexts with >=2/3 confirmation passes, total confirmation passes, robust-search contexts, contexts with any search-qualified point; then minimize sum of first-qualified call indices (33 for none), sum of per-context selected-objective ranks (missing last), then mechanism count H1<E<ER<ERT. Confirmation labels select the method only, never an episode incumbent. No retuning after development.",
        "verification_launch": "User runs locally after selected.json is frozen; no automatic verification",
        "mixed_allowed": False,
        "historical_warmstarts_allowed": False,
    }
    immutable_json(path, protocol)
    print(
        "Prepared 4 W2 development contexts x 4 ablations and 8 user-run verification contexts; new seed pools are disjoint.",
        flush=True,
    )
    return path
