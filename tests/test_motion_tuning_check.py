from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.motion_tuning_check.example_criteria import seed_example_criteria
from aoi_hw_check.checks.motion_tuning_check.judge import CHECK_ITEM, run_motion_tuning_check
from aoi_hw_check.checks.motion_tuning_check.models import MotionTuningState
from aoi_hw_check.checks.motion_tuning_check.runner import MotionTuningRunner
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore


class FixedRunner(MotionTuningRunner):
    def __init__(self, state: MotionTuningState):
        self._state = state

    def run_tuning_sequence(self) -> MotionTuningState:
        return self._state


def _state(position_deviation_um: float) -> MotionTuningState:
    return MotionTuningState(axes={"X": {"position_deviation_um": position_deviation_um}})


class MotionTuningCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")
        self.criteria_store = JSONCriteriaStore(Path(self._tmpdir.name) / "criteria.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_single_equipment_has_no_peers_yields_na(self) -> None:
        seed_example_criteria(self.criteria_store)

        result = run_motion_tuning_check(
            FixedRunner(_state(1.0)), self.criteria_store, self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.NA)

    def test_without_tolerance_criteria_yields_na_even_with_peers(self) -> None:
        run_motion_tuning_check(FixedRunner(_state(1.0)), self.criteria_store, self.store, "EQ01")

        result = run_motion_tuning_check(
            FixedRunner(_state(1.0)), self.criteria_store, self.store, "EQ02"
        )

        self.assertEqual(result.verdict, Verdict.NA)

    def test_value_near_best_among_peers_passes(self) -> None:
        seed_example_criteria(self.criteria_store)  # 허용 배수 1.5x
        run_motion_tuning_check(FixedRunner(_state(1.0)), self.criteria_store, self.store, "EQ01")

        # EQ02는 EQ01(최량값 1.0)의 1.5배 이내인 1.4 -> PASS
        result = run_motion_tuning_check(
            FixedRunner(_state(1.4)), self.criteria_store, self.store, "EQ02"
        )

        self.assertEqual(result.verdict, Verdict.PASS)

    def test_value_far_from_best_among_peers_fails(self) -> None:
        seed_example_criteria(self.criteria_store)  # 허용 배수 1.5x
        run_motion_tuning_check(FixedRunner(_state(1.0)), self.criteria_store, self.store, "EQ01")

        # EQ02는 EQ01(최량값 1.0)의 3배 -> 1.5x 허용 초과, FAIL
        result = run_motion_tuning_check(
            FixedRunner(_state(3.0)), self.criteria_store, self.store, "EQ02"
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(result.deviation[0].field_path, "X.position_deviation_um")
        self.assertEqual(result.deviation[0].current_value, 3.0)

    def test_equipment_that_is_itself_the_best_still_gets_compared(self) -> None:
        seed_example_criteria(self.criteria_store)
        run_motion_tuning_check(FixedRunner(_state(3.0)), self.criteria_store, self.store, "EQ01")

        # EQ02가 새 최량값(1.0)을 기록 -> 자기 자신 대비 판정하므로 PASS
        result = run_motion_tuning_check(
            FixedRunner(_state(1.0)), self.criteria_store, self.store, "EQ02"
        )

        self.assertEqual(result.verdict, Verdict.PASS)

    def test_measurement_is_recorded_into_cross_equipment_history(self) -> None:
        run_motion_tuning_check(FixedRunner(_state(1.0)), self.criteria_store, self.store, "EQ01")

        peers = self.store.list_latest_baselines_by_equipment(CHECK_ITEM)

        self.assertEqual(peers["EQ01"], {"X.position_deviation_um": 1.0})


if __name__ == "__main__":
    unittest.main()
