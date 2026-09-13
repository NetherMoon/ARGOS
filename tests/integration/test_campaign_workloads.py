"""Real pinned parser and source-lineage tests; no simulator execution."""

from pathlib import Path

import pytest

from argos.campaign.workloads import generate, parser
from argos.provenance import read_json

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    not (ROOT / ".deps/FlexDC/src").is_dir(), reason="Pinned FlexDC required"
)


def test_all_declared_workloads_preserve_profiles_and_order(tmp_path):
    protocol = read_json(ROOT / "configs/campaigns/controlled_v1.json")
    generated = generate(ROOT, tmp_path, protocol)
    assert len(generated) == 32
    assert {v["J"] for v in generated.values()} == {3, 4, 5, 6, 8}
    for name, record in generated.items():
        for row in record["lineage"]:
            if name.startswith("V4-"):
                assert set(row["changed_behavior_fields"]) <= {"qos_constraint"}
            else:
                assert row["changed_behavior_fields"] == []
                assert (
                    dict(parser(Path(row["source"]))[row["source_section"]]) == row["copied_fields"]
                )
    assert generate(ROOT, tmp_path, protocol) == generated


def test_generated_workload_corruption_is_not_replaced(tmp_path):
    protocol = read_json(ROOT / "configs/campaigns/controlled_v1.json")
    records = generate(ROOT, tmp_path, protocol)
    path = Path(next(iter(records.values()))["path"])
    path.write_text(path.read_text().replace("qos_constraint", "invalid_qos"))
    with pytest.raises(ValueError, match="changed"):
        generate(ROOT, tmp_path, protocol)


def test_serious_subset_and_phase_counts_are_predeclared():
    protocol = read_json(ROOT / "configs/campaigns/controlled_v1.json")
    cases = protocol["cases"]
    assert len(cases) == 47
    assert sum(len(c["methods"]) for c in cases) == 227
    assert {
        c["workload"] for c in cases if c["phase"] == 2 and c["tier"] == "SERIOUS_DEVELOPMENT"
    } == {"MIX4-TTII", "MIX4-IITT", "MIX4-ITTT", "MIX4-TTTI", "MIX4-TIII", "MIX4-IIIT"}
    assert sum(c["phase"] == 2 and c["tier"] == "SCREENING" for c in cases) == 14
