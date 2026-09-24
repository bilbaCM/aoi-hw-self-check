from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.c_class_scan.collector import MockScanCollector
from aoi_hw_check.checks.c_class_scan.example_criteria import (
    seed_example_dof_criteria,
    seed_example_flatness_criteria,
    seed_example_focus_criteria,
    seed_example_gantry_criteria,
)
from aoi_hw_check.checks.c_class_scan.pipeline import run_c_class_pipeline
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore


class CClassPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")
        self.dof_store = JSONCriteriaStore(Path(self._tmpdir.name) / "dof.json")
        self.focus_store = JSONCriteriaStore(Path(self._tmpdir.name) / "focus.json")
        self.flatness_store = JSONCriteriaStore(Path(self._tmpdir.name) / "flatness.json")
        self.gantry_store = JSONCriteriaStore(Path(self._tmpdir.name) / "gantry.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _run(self, max_scan_attempts: int = 3):
        return run_c_class_pipeline(
            MockScanCollector(),
            self.dof_store,
            self.focus_store,
            self.flatness_store,
            self.gantry_store,
            self.store,
            "EQ01",
            max_scan_attempts=max_scan_attempts,
        )

    def test_single_scan_produces_six_results(self) -> None:
        outcome = self._run()

        self.assertEqual(len(outcome.results), 6)
        self.assertFalse(outcome.escalated)

    def test_without_any_criteria_focus_baseline_saves_and_rest_are_na(self) -> None:
        # criteria 미등록 상태에서는 Focus는 최초 baseline 저장으로 PASS,
        # 나머지(Flatness/Tilt/AFM/Gantry)는 기준 없어 NA -> all_passed는 False
        outcome = self._run()

        self.assertFalse(outcome.all_passed)

    def test_with_seeded_criteria_all_items_pass_on_healthy_mock_data(self) -> None:
        seed_example_dof_criteria(self.dof_store)
        seed_example_flatness_criteria(self.flatness_store)
        seed_example_gantry_criteria(self.gantry_store)
        seed_example_focus_criteria(self.focus_store)

        outcome = self._run()

        self.assertTrue(outcome.all_passed, outcome.results)

    def test_scan_attempt_limit_blocks_further_auto_scans(self) -> None:
        # criteria 미등록 상태 -> all_passed는 항상 False (기준 미등록으로 NA)
        for _ in range(3):
            outcome = self._run(max_scan_attempts=3)
            self.assertFalse(outcome.escalated)

        escalated_outcome = self._run(max_scan_attempts=3)

        self.assertTrue(escalated_outcome.escalated)
        self.assertEqual(escalated_outcome.results, [])

    def test_a_full_pass_resets_the_attempt_counter(self) -> None:
        seed_example_dof_criteria(self.dof_store)
        seed_example_flatness_criteria(self.flatness_store)
        seed_example_gantry_criteria(self.gantry_store)
        seed_example_focus_criteria(self.focus_store)

        first_outcome = self._run(max_scan_attempts=1)
        self.assertTrue(first_outcome.all_passed)

        # 직전 시도가 PASS였으므로 카운트가 리셋되어 다시 상한만큼 시도할 수 있어야 한다
        second_outcome = self._run(max_scan_attempts=1)
        self.assertFalse(second_outcome.escalated)


if __name__ == "__main__":
    unittest.main()
