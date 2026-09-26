"""Synthetic breadth export tests, without FlexDC or V3 calls."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pandas as pd

from argos.oc_basic.breadth_plan import ORIGINAL_RUN, V3_RUN
from argos.oc_basic.breadth_runner import (
    _aggregate,
    _baseline_candidates,
    _configure_worker_import_root,
    _context_report,
    _package,
)
from argos.oc_basic.generic import PanelRule
from argos.search.candidates import Domain


class BreadthExportTest(unittest.TestCase):
    def test_child_imports_pinned_scientific_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source, root, extra = base / "oc", base / "science", base / "dependencies"
            with patch.dict(
                os.environ, {"PYTHONPATH": os.pathsep.join([str(source / "src"), str(extra)])}
            ):
                result = _configure_worker_import_root(root, source).split(os.pathsep)
                self.assertEqual(result[0], str((root / "src").resolve()))
                self.assertEqual(result[1], str(extra))
                self.assertNotIn(str(source / "src"), result)

    def test_synthetic_full_aggregate_with_absent_bids(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            output = Path(temporary) / "output"
            output.mkdir()
            contracts, results, old_v3, old_argos = [], [], [], []
            for workload in ("W1a", "W1b", "W2a", "W2b"):
                for n, u in ((250, 0.6), (250, 0.8), (1000, 0.6), (1000, 0.8)):
                    key = f"{workload}/N{n}_U{u:.1f}"
                    contracts.append(
                        {
                            "context": key,
                            "workload": workload,
                            "N": n,
                            "U": u,
                            "job_types": json.dumps(["A", "B"]),
                            "tracking_limit": 0.3,
                            "qos_limit": 0.1,
                        }
                    )
                    results.append(
                        {
                            "status": "COMPLETE",
                            "context": key,
                            "workload": workload,
                            "N": n,
                            "U": u,
                            "is_oc_development_context": False,
                            "search_status": "NO_ELIGIBLE_BID_WITHIN_BUDGET",
                            "search_calls": 100,
                            "search_wall_seconds": 1200,
                            "search_passes": None,
                            "first_eligible_call": None,
                            "first_eligible_seconds": None,
                            **{f"first_eligible_by_{m}min": False for m in (5, 10, 15, 20)},
                            "oc_assessment_passes": None,
                            "oc_assessment_total": 0,
                            "v3_assessment_passes": None,
                            "v3_assessment_total": 0,
                            "argos_assessment_passes": None,
                            "argos_assessment_total": 0,
                        }
                    )
                    old_v3.append({"context": key, "actual_feasible": False})
                    old_argos.append(
                        {"context": key, "search_status": "NO_BID", "runtime_checks_passed": 0}
                    )
                    target = output / key / "final"
                    target.mkdir(parents=True)
                    (target / "frozen_comparison_bids.json").write_text(
                        json.dumps({"pure_v3": None, "standard_argos": None, "argos_oc": None})
                    )
            for relative, rows, filename in (
                (V3_RUN, old_v3, "v3_only_context_summary.csv"),
                (ORIGINAL_RUN, old_argos, "context_summary.csv"),
            ):
                path = root / relative / filename
                path.parent.mkdir(parents=True)
                pd.DataFrame(rows).to_csv(path, index=False)
            _aggregate(
                root,
                output,
                results,
                contracts,
                {"version": "synthetic", "source_commit_before_freeze": "synthetic"},
                1,
            )
            self.assertEqual(len(list((output / "figures").glob("*.png"))), 10)
            self.assertEqual(
                len(pd.read_csv(output / "benchmark" / "argos_oc_16_context_summary.csv")), 16
            )
            self.assertIn("0/15", (output / "report.md").read_text())

    def test_missing_frozen_baseline_bid_stays_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / V3_RUN / "v3_only_context_summary.csv"
            path.parent.mkdir(parents=True)
            pd.DataFrame([{"context": "case", "Pbar": None, "R": None, "weights": None}]).to_csv(
                path, index=False
            )
            path = root / ORIGINAL_RUN / "selected_candidates.csv"
            path.parent.mkdir(parents=True)
            pd.DataFrame([{"context": "case", "candidate": ""}]).to_csv(path, index=False)
            domain = Domain(0.25, 0.75, 1, 0.01, 0.6, (0.05, 0.05), (0.9, 0.9))
            bids = _baseline_candidates(root, {"context": "case"}, domain)
            self.assertIsNone(bids["pure_v3"])
            self.assertIsNone(bids["standard_argos"])

    def test_report_figures_and_compact_zip(self):
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "run" / "case"
            (episode / "search").mkdir(parents=True)
            pd.DataFrame([{"candidate_id": "a", "passes": 9}]).to_csv(
                episode / "search" / "candidate_summary.csv", index=False
            )
            rows = [
                {
                    "candidate_id": "a",
                    "candidate_number": 1,
                    "arrival_seed": seed,
                    "p90": 0.2,
                    "Pj": [0, 0],
                    "Pbar": 0.4,
                    "R": 0.2,
                    "feasible": True,
                    "evidence_valid": True,
                    "execution_status": "COMPLETE",
                    "objective": 80,
                    "cumulative_search_wall_seconds": seed,
                }
                for seed in range(10, 20)
            ]
            arrivals = [
                {"arrival_seed": seed, "job_type": name, "later_arrival_count": 2}
                for seed in range(10, 20)
                for name in ("A", "B")
            ]
            search = {
                "search_status": "SEARCH_ELIGIBLE",
                "total_search_calls": 10,
                "search_wall_seconds": 19,
                "best_complete_passes": 10,
                "selected_candidate_id": "a",
                "selected_search_passes": 10,
                "selected_mean_objective": 80,
            }
            assessment = {"pure_v3_passes": None, "standard_argos_passes": 3, "argos_oc_passes": 4}
            _context_report(
                episode,
                {"context": "case"},
                rows,
                search,
                [],
                assessment,
                arrivals,
                PanelRule(("A", "B"), 10, 8),
                21,
            )
            self.assertEqual(len(list((episode / "figures").glob("*.png"))), 6)
            self.assertIn("SEARCH_ELIGIBLE", (episode / "report.md").read_text())
            (episode / "manifest.json").write_text(json.dumps({"case": 1}))
            (episode / "initial_jobs.csv.gz").write_bytes(b"not an archive source")
            (episode / "evaluations").mkdir()
            (episode / "evaluations" / "raw_result.json").write_text("{}")
            archive = _package(episode.parent)
            with ZipFile(archive) as zipped:
                names = zipped.namelist()
                self.assertTrue(any(name.endswith("report.md") for name in names))
                self.assertFalse(any("evaluations" in name for name in names))
                self.assertFalse(any("initial_jobs" in name for name in names))


if __name__ == "__main__":
    unittest.main()
