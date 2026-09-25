from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.afm_setting_check.judge import run_afm_setting_check
from aoi_hw_check.checks.c_class_scan.constants import DOF_CHECK_ITEM
from aoi_hw_check.checks.c_class_scan.models import (
    AFZMap,
    AFZSample,
    AFZTrack,
    ScanImageSet,
    ScanResult,
)
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore


def _track(inspector_id: str, errors: list[float]) -> AFZTrack:
    samples = [
        AFZSample(x_mm=float(i), y_mm=0.0, z_um=50.0, beam_position_error_um=e)
        for i, e in enumerate(errors)
    ]
    return AFZTrack(inspector_id=inspector_id, samples=samples)


class AFMSettingCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")
        self.dof_store = JSONCriteriaStore(Path(self._tmpdir.name) / "dof.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_no_dof_criteria_yields_na(self) -> None:
        scan_result = ScanResult(
            af_z_map=AFZMap(tracks={"INS1": _track("INS1", [0.1, 0.2])}),
            scan_images=ScanImageSet(),
        )

        result = run_afm_setting_check(scan_result, self.dof_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.NA)

    def test_error_within_dof_third_passes(self) -> None:
        self.dof_store.save_criteria(DOF_CHECK_ITEM, "INS1", 0.0, 3.0)  # 허용 1.0
        scan_result = ScanResult(
            af_z_map=AFZMap(tracks={"INS1": _track("INS1", [0.5, 0.9])}),
            scan_images=ScanImageSet(),
        )

        result = run_afm_setting_check(scan_result, self.dof_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.PASS)

    def test_error_exceeding_dof_third_fails(self) -> None:
        self.dof_store.save_criteria(DOF_CHECK_ITEM, "INS1", 0.0, 3.0)  # 허용 1.0
        scan_result = ScanResult(
            af_z_map=AFZMap(tracks={"INS1": _track("INS1", [0.5, 1.5])}),
            scan_images=ScanImageSet(),
        )

        result = run_afm_setting_check(scan_result, self.dof_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(result.deviation[0].field_path, "INS1")
        self.assertEqual(result.deviation[0].current_value, 1.5)


if __name__ == "__main__":
    unittest.main()
