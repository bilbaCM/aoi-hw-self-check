from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.c_class_scan.models import (
    AFZMap,
    CellCoordinateSample,
    ScanImageSet,
    ScanResult,
)
from aoi_hw_check.checks.gantry_squareness_check.judge import CHECK_ITEM, run_gantry_squareness_check
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore


def _line(dx: float, dy: float, count: int = 4) -> list[CellCoordinateSample]:
    return [
        CellCoordinateSample(stage_position_mm=i * 10.0, x_um=i * dx, y_um=i * dy)
        for i in range(count)
    ]


def _scan_result(
    x_samples: list[CellCoordinateSample], y_samples: list[CellCoordinateSample]
) -> ScanResult:
    return ScanResult(
        af_z_map=AFZMap(),
        scan_images=ScanImageSet(gantry_x_axis_samples=x_samples, gantry_y_axis_samples=y_samples),
    )


class GantrySquarenessCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")
        self.criteria_store = JSONCriteriaStore(Path(self._tmpdir.name) / "criteria.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_too_few_points_is_na(self) -> None:
        result = run_gantry_squareness_check(
            _scan_result(_line(50, 0, count=2), _line(0, 50, count=2)),
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.NA)
        self.assertIn("2점 측정 금지", result.detail)

    def test_perfectly_perpendicular_axes_pass(self) -> None:
        self.criteria_store.save_criteria(
            CHECK_ITEM, "perpendicularity_deviation_deg", 0.0, 0.1
        )

        result = run_gantry_squareness_check(
            _scan_result(_line(50, 0), _line(0, 50)),
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])

    def test_skewed_y_axis_fails(self) -> None:
        self.criteria_store.save_criteria(
            CHECK_ITEM, "perpendicularity_deviation_deg", 0.0, 0.1
        )
        # Y축 구동에 X 방향 드리프트가 섞여 직각에서 벗어남
        result = run_gantry_squareness_check(
            _scan_result(_line(50, 0), _line(10, 50)),
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(result.deviation[0].field_path, "perpendicularity_deviation_deg")

    def test_no_criteria_registered_yields_na(self) -> None:
        result = run_gantry_squareness_check(
            _scan_result(_line(50, 0), _line(0, 50)),
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.NA)


if __name__ == "__main__":
    unittest.main()
