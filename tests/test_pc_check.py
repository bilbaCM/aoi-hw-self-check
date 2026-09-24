from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.pc_check.collector import PCStateCollector
from aoi_hw_check.checks.pc_check.judge import CHECK_ITEM, run_pc_check
from aoi_hw_check.checks.pc_check.models import PCState
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore


class FixedCollector(PCStateCollector):
    def __init__(self, state: PCState):
        self._state = state

    def collect(self) -> PCState:
        return self._state


class PCCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "test.sqlite3")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_first_run_creates_baseline_and_passes(self) -> None:
        state = PCState(os={"version": "Win10"})

        result = run_pc_check(FixedCollector(state), self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])
        self.assertIsNotNone(self.store.get_baseline("EQ01", CHECK_ITEM))

    def test_matching_state_passes(self) -> None:
        state = PCState(os={"version": "Win10"})
        run_pc_check(FixedCollector(state), self.store, "EQ01")

        result = run_pc_check(FixedCollector(state), self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])

    def test_mismatched_state_fails_with_field_level_deviation(self) -> None:
        baseline_state = PCState(
            os={"version": "Win10"},
            services={"AOI_VisionService": "Running"},
        )
        run_pc_check(FixedCollector(baseline_state), self.store, "EQ01")

        drifted_state = PCState(
            os={"version": "Win10"},
            services={"AOI_VisionService": "Stopped"},
        )
        result = run_pc_check(FixedCollector(drifted_state), self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(len(result.deviation), 1)
        self.assertEqual(result.deviation[0].field_path, "services.AOI_VisionService")
        self.assertEqual(result.deviation[0].baseline_value, "Running")
        self.assertEqual(result.deviation[0].current_value, "Stopped")

    def test_only_mismatched_fields_are_reported(self) -> None:
        baseline_state = PCState(
            os={"version": "Win10"},
            cpu={"usage_percent": 10},
            memory={"used_gb": 8},
        )
        run_pc_check(FixedCollector(baseline_state), self.store, "EQ01")

        drifted_state = PCState(
            os={"version": "Win10"},
            cpu={"usage_percent": 95},
            memory={"used_gb": 8},
        )
        result = run_pc_check(FixedCollector(drifted_state), self.store, "EQ01")

        self.assertEqual([m.field_path for m in result.deviation], ["cpu.usage_percent"])

    def test_results_are_persisted_per_equipment(self) -> None:
        state = PCState(os={"version": "Win10"})
        run_pc_check(FixedCollector(state), self.store, "EQ01")
        run_pc_check(FixedCollector(state), self.store, "EQ01")

        results = self.store.list_results(equipment_id="EQ01", check_item=CHECK_ITEM)

        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
