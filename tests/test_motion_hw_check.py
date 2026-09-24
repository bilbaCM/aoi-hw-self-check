from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.motion_hw_check.collector import MotionHWCollector
from aoi_hw_check.checks.motion_hw_check.example_criteria import seed_example_criteria
from aoi_hw_check.checks.motion_hw_check.judge import CHECK_ITEM, run_motion_hw_check
from aoi_hw_check.checks.motion_hw_check.models import MotionHWState
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore


class FixedCollector(MotionHWCollector):
    def __init__(self, state: MotionHWState):
        self._state = state

    def collect(self) -> MotionHWState:
        return self._state


class MotionHWCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")
        self.criteria_store = JSONCriteriaStore(Path(self._tmpdir.name) / "criteria.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_no_registered_criteria_yields_na(self) -> None:
        state = MotionHWState(axes={"X": {"encoder_count": 100000}})

        result = run_motion_hw_check(
            FixedCollector(state), self.criteria_store, self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.NA)

    def test_value_within_range_passes(self) -> None:
        self.criteria_store.save_criteria(CHECK_ITEM, "X.encoder_count", 90000, 110000)
        state = MotionHWState(axes={"X": {"encoder_count": 100000}})

        result = run_motion_hw_check(
            FixedCollector(state), self.criteria_store, self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])

    def test_value_out_of_range_fails_with_deviation(self) -> None:
        self.criteria_store.save_criteria(CHECK_ITEM, "X.encoder_count", 90000, 110000)
        state = MotionHWState(axes={"X": {"encoder_count": 150000}})

        result = run_motion_hw_check(
            FixedCollector(state), self.criteria_store, self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(len(result.deviation), 1)
        self.assertEqual(result.deviation[0].field_path, "X.encoder_count")
        self.assertEqual(result.deviation[0].current_value, 150000)

    def test_only_out_of_range_axes_are_reported(self) -> None:
        self.criteria_store.save_criteria(CHECK_ITEM, "X.encoder_count", 90000, 110000)
        self.criteria_store.save_criteria(CHECK_ITEM, "Y.encoder_count", 90000, 110000)
        state = MotionHWState(
            axes={
                "X": {"encoder_count": 100000},
                "Y": {"encoder_count": 5000},
            }
        )

        result = run_motion_hw_check(
            FixedCollector(state), self.criteria_store, self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual([m.field_path for m in result.deviation], ["Y.encoder_count"])

    def test_seed_example_criteria_enables_judgement(self) -> None:
        seed_example_criteria(self.criteria_store)
        state = MotionHWState(
            axes={
                "X": {"encoder_count": 102345, "pwm_duty_percent": 42.5, "io_home_sensor": 1},
            }
        )

        result = run_motion_hw_check(
            FixedCollector(state), self.criteria_store, self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.PASS)


if __name__ == "__main__":
    unittest.main()
