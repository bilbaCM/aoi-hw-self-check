from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.c_class_scan.models import AFZMap, ScanImageSet, ScanResult
from aoi_hw_check.checks.optical_focus_check.judge import CHECK_ITEM, run_optical_focus_check
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore


def _scan_result(focus_measures: dict[str, float]) -> ScanResult:
    return ScanResult(af_z_map=AFZMap(), scan_images=ScanImageSet(focus_measures=focus_measures))


class OpticalFocusCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")
        self.criteria_store = JSONCriteriaStore(Path(self._tmpdir.name) / "criteria.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_first_run_saves_baseline_and_passes(self) -> None:
        result = run_optical_focus_check(
            _scan_result({"Micro": 1000.0}), self.criteria_store, self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(self.store.get_baseline("EQ01", CHECK_ITEM), {"Micro": 1000.0})

    def test_ratio_within_criteria_passes(self) -> None:
        run_optical_focus_check(_scan_result({"Micro": 1000.0}), self.criteria_store, self.store, "EQ01")
        self.criteria_store.save_criteria(CHECK_ITEM, "Micro", 0.85, 1.15)

        result = run_optical_focus_check(
            _scan_result({"Micro": 950.0}), self.criteria_store, self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.PASS)

    def test_ratio_outside_criteria_fails(self) -> None:
        run_optical_focus_check(_scan_result({"Micro": 1000.0}), self.criteria_store, self.store, "EQ01")
        self.criteria_store.save_criteria(CHECK_ITEM, "Micro", 0.85, 1.15)

        result = run_optical_focus_check(
            _scan_result({"Micro": 500.0}), self.criteria_store, self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(result.deviation[0].field_path, "Micro")
        self.assertEqual(result.deviation[0].current_value, 0.5)

    def test_no_criteria_registered_yields_na(self) -> None:
        run_optical_focus_check(_scan_result({"Micro": 1000.0}), self.criteria_store, self.store, "EQ01")

        result = run_optical_focus_check(
            _scan_result({"Micro": 500.0}), self.criteria_store, self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.NA)


if __name__ == "__main__":
    unittest.main()
