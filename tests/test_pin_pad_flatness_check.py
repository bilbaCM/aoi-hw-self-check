from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.c_class_scan.models import AFZMap, PinHeightSample, ScanImageSet, ScanResult
from aoi_hw_check.checks.pin_pad_flatness_check.judge import CHECK_ITEM, run_pin_pad_flatness_check
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore


def _scan_result(heights: list[PinHeightSample]) -> ScanResult:
    return ScanResult(af_z_map=AFZMap(pin_heights=heights), scan_images=ScanImageSet())


class PinPadFlatnessCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")
        self.criteria_store = JSONCriteriaStore(Path(self._tmpdir.name) / "criteria.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_no_criteria_yields_na(self) -> None:
        scan_result = _scan_result([PinHeightSample("PIN1", 100.0), PinHeightSample("PIN2", 100.1)])

        result = run_pin_pad_flatness_check(scan_result, self.criteria_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.NA)

    def test_deviation_within_criteria_passes(self) -> None:
        self.criteria_store.save_criteria(CHECK_ITEM, "pin_height_deviation_um", 0.0, 5.0)
        scan_result = _scan_result([PinHeightSample("PIN1", 100.0), PinHeightSample("PIN2", 102.0)])

        result = run_pin_pad_flatness_check(scan_result, self.criteria_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.PASS)

    def test_deviation_exceeding_criteria_fails(self) -> None:
        self.criteria_store.save_criteria(CHECK_ITEM, "pin_height_deviation_um", 0.0, 5.0)
        scan_result = _scan_result([PinHeightSample("PIN1", 100.0), PinHeightSample("PIN2", 110.0)])

        result = run_pin_pad_flatness_check(scan_result, self.criteria_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(result.deviation[0].current_value, 10.0)

    def test_insufficient_data_is_na(self) -> None:
        scan_result = _scan_result([PinHeightSample("PIN1", 100.0)])

        result = run_pin_pad_flatness_check(scan_result, self.criteria_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.NA)


if __name__ == "__main__":
    unittest.main()
