"""Auditable, source-preserving workload construction outside dependency trees."""

import configparser
import csv
import io
import sys
from dataclasses import asdict
from pathlib import Path

from argos.campaign.identity import immutable_json
from argos.provenance import sha256
from argos.simulator.evidence import FIELDS, ordered_jobs

FAMILIES = ["Resnet", "GPT2", "Llama", "Bloom"]
SOURCES = {"T": "W1-train-qos4444.ini", "I": "W2-short-qos5555.ini"}


def parser(path):
    value = configparser.ConfigParser(interpolation=None, strict=True)
    with path.open(encoding="utf-8") as f:
        value.read_file(f)
    return value


def immutable_bytes(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Generated workload changed: {path}")
    else:
        path.write_bytes(content)


def verify_parser(root: Path, path: Path) -> list:
    sys.path.insert(0, str(root / ".deps/FlexDC/src"))
    try:
        from peacsim.parsing.job_profile_reader import JobProfileReader

        reader = JobProfileReader(str(path))
    finally:
        sys.path.pop(0)
    jobs = ordered_jobs(path)
    properties = [
        reader.all_min_job_power,
        reader.all_max_job_power,
        reader.all_min_execution_time,
        reader.all_max_execution_time,
        reader.all_job_qos_constraints,
        reader.all_job_size,
    ]
    if reader.job_type_count != len(jobs):
        raise ValueError("FlexDC job count mismatch")
    for job in jobs:
        if (
            reader.all_jobs[job.index] != job.section
            or tuple(p[job.index] for p in properties) != job.descriptors
        ):
            raise ValueError("Pinned FlexDC workload parser mismatch")
    return [asdict(j) for j in jobs]


def generate(root: Path, directory: Path, protocol: dict) -> dict:
    source = root / ".deps/FlexDC/configs/workload"
    records = {}
    names = sorted({c["workload"] for c in protocol["cases"]})
    for name in names:
        target = directory / (name + ".ini")
        lineage = []
        authority = {}
        if name in protocol["original_workloads"]:
            original = source / (name + ".ini")
            content = original.read_bytes()
            for i, section in enumerate(parser(original).sections()):
                lineage.append(
                    {
                        "ordered_job_index": i,
                        "output_section": section,
                        "source": str(original),
                        "source_sha256": sha256(original),
                        "source_section": section,
                        "copied_fields": dict(parser(original)[section]),
                        "changed_behavior_fields": [],
                    }
                )
        elif name.startswith("V4-"):
            original = source / "v4_mixed" / (name + ".ini")
            manifest = source / "v4_mixed/v4_custom_workloads_manifest.csv"
            with manifest.open(newline="", encoding="utf-8") as f:
                rows = [r for r in csv.DictReader(f) if r["workload_id"] == name]
            rows.sort(key=lambda r: int(r["job_index"]))
            out = parser(original)
            if list(out.sections()) != [r["output_section"] for r in rows]:
                raise ValueError("Historical V4 ordered manifest mismatch")
            for row in rows:
                profile = source / Path(row["source_file"]).name
                before = dict(parser(profile)[row["source_section"]])
                after = dict(out[row["output_section"]])
                if set(before) != set(after):
                    raise ValueError("Historical V4 field set mismatch")
                changed = [k for k in before if float(before[k]) != float(after[k])]
                if set(changed) - {"qos_constraint"}:
                    raise ValueError("Historical V4 changes non-QoS fields")
                if float(before["qos_constraint"]) != float(
                    row["original_qos_constraint"]
                ) or float(after["qos_constraint"]) != float(row["generated_qos_constraint"]):
                    raise ValueError("Historical V4 QoS manifest mismatch")
                lineage.append(
                    {
                        **row,
                        "source": str(profile),
                        "source_sha256": sha256(profile),
                        "ordered_job_index": int(row["job_index"]),
                        "copied_fields": after,
                        "source_fields": before,
                        "changed_behavior_fields": changed,
                    }
                )
            content = original.read_bytes()
            authority = {
                "historical_ini_sha256": sha256(original),
                "historical_manifest_sha256": sha256(manifest),
                "generator_status": "UNAVAILABLE",
                "authority": "Pinned outputs and manifest authorized by user",
            }
        else:
            if name.startswith("MIX4-"):
                profiles = list(enumerate(name.removeprefix("MIX4-")))
            else:
                profiles = protocol["structural_workloads"][name]
            out = configparser.ConfigParser(interpolation=None)
            for i, (family, role) in enumerate(profiles):
                profile = source / SOURCES[role]
                before = parser(profile)
                section = before.sections()[family]
                output = section if section not in out else f"{section}.repeat{i}"
                out[output] = dict(before[section])
                lineage.append(
                    {
                        "source": str(profile),
                        "source_sha256": sha256(profile),
                        "source_section": section,
                        "role": "train" if role == "T" else "infer",
                        "family": FAMILIES[family],
                        "output_section": output,
                        "ordered_job_index": i,
                        "copied_fields": dict(before[section]),
                        "changed_behavior_fields": [],
                    }
                )
            stream = io.StringIO()
            out.write(stream)
            content = stream.getvalue().encode()
        immutable_bytes(target, content)
        jobs = verify_parser(root, target)
        for job, row in zip(jobs, lineage):
            if job["index"] != row["ordered_job_index"] or job["section"] != row["output_section"]:
                raise ValueError("Generated lineage order mismatch")
            if list(job["descriptors"]) != [float(row["copied_fields"].get(k, 1)) for k in FIELDS]:
                raise ValueError("Generated descriptor mismatch")
        record = {
            "name": name,
            "path": str(target.resolve()),
            "sha256": sha256(target),
            "ordered_jobs": jobs,
            "J": len(jobs),
            "lineage": lineage,
            **authority,
        }
        immutable_json(target.with_suffix(".manifest.json"), record)
        records[name] = record
    immutable_json(directory / "workload_manifest.json", records)
    return records
