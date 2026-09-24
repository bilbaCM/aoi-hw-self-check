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
from aoi_hw_check.checks.optical_subsystem_check.judge import (
    check_item_name,
    run_optical_subsystem_check,
)
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


def _scan_result(z_values: list[float], focus_measure: float) -> ScanResult:
    return ScanResult(
        af_z_map=AFZMap(tracks={"Micro": _track("Micro", z_values)}),
        scan_images=ScanImageSet(focus_measures={"Micro": focus_measure}),
    )


class OpticalSubsystemCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")
        self.dof_store = JSONCriteriaStore(Path(self._tmpdir.name) / "dof.json")
        self.focus_store = JSONCriteriaStore(Path(self._tmpdir.name) / "focus.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_check_item_name_is_per_subsystem(self) -> None:
        self.assertEqual(check_item_name("Micro"), "Micro 광학계 상태 확인")

    def test_first_run_without_any_criteria_is_na(self) -> None:
        # Tilt: DOF 미등록 -> NA / Focus: 최초 실행 -> PASS(baseline 저장) => 종합 NA
        result = run_optical_subsystem_check(
            "Micro",
            _scan_result([50.0, 50.0, 50.0], 1000.0),
            self.dof_store,
            self.focus_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.NA)

    def test_all_sub_judgements_pass(self) -> None:
        self.dof_store.save_criteria(DOF_CHECK_ITEM, "Micro", 0.0, 5.0)
        # 최초 실행으로 baseline 저장
        run_optical_subsystem_check(
            "Micro",
            _scan_result([50.0, 50.0, 50.0], 1000.0),
            self.dof_store,
            self.focus_store,
            self.store,
            "EQ01",
        )
        self.focus_store.save_criteria(check_item_name("Micro"), "focus_ratio", 0.85, 1.15)

        result = run_optical_subsystem_check(
            "Micro",
            _scan_result([50.0, 50.0, 50.0], 980.0),
            self.dof_store,
            self.focus_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])

    def test_tilt_failure_dominates_even_if_focus_passes(self) -> None:
        self.dof_store.save_criteria(DOF_CHECK_ITEM, "Micro", 0.0, 1.0)
        run_optical_subsystem_check(
            "Micro",
            _scan_result([50.0, 50.0, 50.0], 1000.0),
            self.dof_store,
            self.focus_store,
            self.store,
            "EQ01",
        )
        self.focus_store.save_criteria(check_item_name("Micro"), "focus_ratio", 0.85, 1.15)

        # (0,0)->50, (5,0)->60, (0,5)->50: 10um 변화, DOF(1um) 초과
        result = run_optical_subsystem_check(
            "Micro",
            _scan_result([50.0, 60.0, 50.0], 1000.0),
            self.dof_store,
            self.focus_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(
            [m.field_path for m in result.deviation], ["tilt_focus_deviation_um"]
        )

    def test_focus_failure_fails_even_if_tilt_passes(self) -> None:
        self.dof_store.save_criteria(DOF_CHECK_ITEM, "Micro", 0.0, 5.0)
        run_optical_subsystem_check(
            "Micro",
            _scan_result([50.0, 50.0, 50.0], 1000.0),
            self.dof_store,
            self.focus_store,
            self.store,
            "EQ01",
        )
        self.focus_store.save_criteria(check_item_name("Micro"), "focus_ratio", 0.85, 1.15)

        result = run_optical_subsystem_check(
            "Micro",
            _scan_result([50.0, 50.0, 50.0], 400.0),
            self.dof_store,
            self.focus_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual([m.field_path for m in result.deviation], ["focus_ratio"])


if __name__ == "__main__":
    unittest.main()
