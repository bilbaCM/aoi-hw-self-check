from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.c_class_scan.constants import DOF_CHECK_ITEM
from aoi_hw_check.checks.c_class_scan.models import (
    AFZMap,
    AFZSample,
    AFZTrack,
    ScanImageSet,
    ScanResult,
)
from aoi_hw_check.checks.optical_tilt_check.judge import run_optical_tilt_check
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore

# (x, y) 비직선 배치 — 평면 피팅 연립방정식이 특이(singular)해지지 않도록 함
_COORDS = [(0.0, 0.0), (5.0, 0.0), (0.0, 5.0)]


def _track(subsystem: str, z_values: list[float]) -> AFZTrack:
    samples = [
        AFZSample(x_mm=x, y_mm=y, z_um=z, beam_position_error_um=0.0)
        for (x, y), z in zip(_COORDS, z_values)
    ]
    return AFZTrack(subsystem=subsystem, samples=samples)


class OpticalTiltCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")
        self.dof_store = JSONCriteriaStore(Path(self._tmpdir.name) / "dof.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_no_dof_criteria_yields_na(self) -> None:
        scan_result = ScanResult(
            af_z_map=AFZMap(tracks={"Micro": _track("Micro", [50.0, 50.0, 50.0])}),
            scan_images=ScanImageSet(),
        )

        result = run_optical_tilt_check(scan_result, self.dof_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.NA)

    def test_flat_surface_within_dof_passes(self) -> None:
        self.dof_store.save_criteria(DOF_CHECK_ITEM, "Micro", 0.0, 5.0)
        scan_result = ScanResult(
            af_z_map=AFZMap(tracks={"Micro": _track("Micro", [50.0, 50.0, 50.0])}),
            scan_images=ScanImageSet(),
        )

        result = run_optical_tilt_check(scan_result, self.dof_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])

    def test_steep_tilt_exceeding_dof_fails(self) -> None:
        self.dof_store.save_criteria(DOF_CHECK_ITEM, "Micro", 0.0, 1.0)
        # (0,0)->50, (5,0)->60, (0,5)->50: z=50+2x 평면, 측정 영역 내 10um 변화
        scan_result = ScanResult(
            af_z_map=AFZMap(tracks={"Micro": _track("Micro", [50.0, 60.0, 50.0])}),
            scan_images=ScanImageSet(),
        )

        result = run_optical_tilt_check(scan_result, self.dof_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(result.deviation[0].field_path, "Micro")
        self.assertEqual(result.deviation[0].current_value, 10.0)

    def test_only_evaluated_subsystems_without_dof_are_skipped(self) -> None:
        self.dof_store.save_criteria(DOF_CHECK_ITEM, "Micro", 0.0, 5.0)
        scan_result = ScanResult(
            af_z_map=AFZMap(
                tracks={
                    "Micro": _track("Micro", [50.0, 50.0, 50.0]),
                    "Macro": _track("Macro", [50.0, 50.0, 50.0]),
                }
            ),
            scan_images=ScanImageSet(),
        )

        result = run_optical_tilt_check(scan_result, self.dof_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.PASS)


if __name__ == "__main__":
    unittest.main()
