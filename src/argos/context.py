"""Compare requested simulator behavior with the explicit frozen V3 contract."""

from pathlib import Path

from argos.provenance import read_json, sha256
from argos.simulator.configuration import read_ini


def check_context(root: Path, config) -> dict:
    contract_path = root / "configs/v3_context_contract.json"
    contract = read_json(contract_path)
    flex = root / ".deps/FlexDC"
    experiment = read_ini(flex / config.experiment)
    if experiment.getint("system", "simulation_duration") != 3600:
        raise ValueError(
            "Exact simulator objective supports only simulation_duration=3600, even in OOD mode"
        )
    excluded = {
        ("system", "server_count"),
        ("system", "utilization"),
        ("system", "random_seed"),
        ("iso", "iso_file_path"),
    }
    actual = {
        f"{sec}.{key}": value
        for sec in experiment.sections()
        for key, value in experiment.items(sec)
        if (sec, key) not in excluded
    }
    mismatches = {
        key: {"expected": contract["locked_experiment"].get(key), "actual": actual.get(key)}
        for key in set(actual) | set(contract["locked_experiment"])
        if actual.get(key) != contract["locked_experiment"].get(key)
    }
    signal = (flex / "src/peacsim" / experiment["iso"]["iso_file_path"]).resolve()
    values = {
        "policy": config.policy,
        "node_count_control": True,
        "iso_sha256": sha256(signal),
        "cluster_sha256": sha256(flex / config.cluster),
    }
    for key, value in values.items():
        if value != contract[key]:
            mismatches[key] = {"expected": contract[key], "actual": value}
    if mismatches and not config.allow_context_ood:
        raise ValueError(f"Unconditioned V3 context mismatch: {mismatches}")
    return {
        "contract_sha256": sha256(contract_path),
        "context_ood": bool(mismatches),
        "label": "CONTEXT_OOD_OVERRIDE" if mismatches else "REVIEWED_V3_CONTEXT",
        "allow_context_ood": config.allow_context_ood,
        "mismatches": mismatches,
        "actual_locked_experiment": actual,
        **values,
    }
