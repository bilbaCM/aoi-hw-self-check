from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.pc_check.collector import PCStateCollector
from aoi_hw_check.checks.pc_check.example_criteria import seed_example_criteria
from aoi_hw_check.checks.pc_check.judge import CHECK_ITEM, run_pc_check
from aoi_hw_check.checks.pc_check.models import PCState
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore


class FixedCollector(PCStateCollector):
    def __init__(self, state: PCState):
        self._state = state

    def collect(self) -> PCState:
        return self._state


class PCCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "test.sqlite3")
        self.criteria_store = JSONCriteriaStore(Path(self._tmpdir.name) / "criteria.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_first_run_creates_baseline_and_passes(self) -> None:
        state = PCState(os={"version": "Win10"})

        result = run_pc_check(FixedCollector(state), self.criteria_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])
        self.assertIsNotNone(self.store.get_baseline("EQ01", CHECK_ITEM))

    def test_matching_state_passes(self) -> None:
        state = PCState(os={"version": "Win10"})
        run_pc_check(FixedCollector(state), self.criteria_store, self.store, "EQ01")

        result = run_pc_check(FixedCollector(state), self.criteria_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])

    def test_mismatched_state_fails_with_field_level_deviation(self) -> None:
        baseline_state = PCState(
            os={"version": "Win10"},
            services={"AOI_VisionService": "Running"},
        )
        run_pc_check(FixedCollector(baseline_state), self.criteria_store, self.store, "EQ01")

        drifted_state = PCState(
            os={"version": "Win10"},
            services={"AOI_VisionService": "Stopped"},
        )
        result = run_pc_check(FixedCollector(drifted_state), self.criteria_store, self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(len(result.deviation), 1)
        self.assertEqual(result.deviation[0].field_path, "services.AOI_VisionService")
        self.assertEqual(result.deviation[0].baseline_value, "Running")
        self.assertEqual(result.deviation[0].current_value, "Stopped")

    def test_only_mismatched_fields_are_reported(self) -> None:
        baseline_state = PCState(
            os={"version": "Win10"},
            services={"AOI_VisionService": "Running"},
        )
        run_pc_check(FixedCollector(baseline_state), self.criteria_store, self.store, "EQ01")

        drifted_state = PCState(
            os={"version": "Win11"},
            services={"AOI_VisionService": "Running"},
        )
        result = run_pc_check(FixedCollector(drifted_state), self.criteria_store, self.store, "EQ01")

        self.assertEqual([m.field_path for m in result.deviation], ["os.version"])

    def test_results_are_persisted_per_equipment(self) -> None:
        state = PCState(os={"version": "Win10"})
        run_pc_check(FixedCollector(state), self.criteria_store, self.store, "EQ01")
        run_pc_check(FixedCollector(state), self.criteria_store, self.store, "EQ01")

        results = self.store.list_results(equipment_id="EQ01", check_item=CHECK_ITEM)

        self.assertEqual(len(results), 2)

    def test_field_with_registered_range_is_judged_by_range_not_exact_match(self) -> None:
        # CPU 사용률처럼 계속 변하는 값은, 기준 범위만 등록해 두면 baseline과
        # 값이 달라도(=계속 변해도) 범위 안이면 PASS해야 한다.
        self.criteria_store.save_criteria(CHECK_ITEM, "cpu.usage_percent", 0, 80)
        run_pc_check(
            FixedCollector(PCState(cpu={"usage_percent": 10})),
            self.criteria_store,
            self.store,
            "EQ01",
        )

        result = run_pc_check(
            FixedCollector(PCState(cpu={"usage_percent": 70})),
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])

    def test_field_with_registered_range_fails_when_out_of_range_even_on_first_run(self) -> None:
        # 등록된 기준 범위는 "처음 관측된 값"이 아니라 정해진 스펙이므로,
        # baseline이 아예 없는 최초 실행이라도 범위를 벗어나면 FAIL이어야 한다.
        self.criteria_store.save_criteria(CHECK_ITEM, "cpu.usage_percent", 0, 80)

        result = run_pc_check(
            FixedCollector(PCState(cpu={"usage_percent": 95})),
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(len(result.deviation), 1)
        self.assertEqual(result.deviation[0].field_path, "cpu.usage_percent")
        self.assertEqual(result.deviation[0].baseline_value, "[0, 80]")
        self.assertEqual(result.deviation[0].current_value, 95)

    def test_field_with_registered_range_fails_when_out_of_range_on_later_run(self) -> None:
        self.criteria_store.save_criteria(CHECK_ITEM, "memory.used_gb", 0, 28)
        run_pc_check(
            FixedCollector(PCState(memory={"used_gb": 9})),
            self.criteria_store,
            self.store,
            "EQ01",
        )

        result = run_pc_check(
            FixedCollector(PCState(memory={"used_gb": 30})),
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual([m.field_path for m in result.deviation], ["memory.used_gb"])

    def test_seed_example_criteria_enables_range_judgement_for_mock_defaults(self) -> None:
        from aoi_hw_check.checks.pc_check.collector import MockPCStateCollector

        seed_example_criteria(self.criteria_store)

        result = run_pc_check(
            MockPCStateCollector(), self.criteria_store, self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.PASS)


if __name__ == "__main__":
    unittest.main()
