from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.cli import (
    C_CLASS_SCAN_KEY,
    CHECK_ITEM_SPECS,
    build_parser,
    execute_run_all,
    execute_selected,
)

_EXAMPLE_CONFIG_FILES = (
    "io_check_danger_list.example.json",
    "ppmac_axis_map.example.json",
    "ppmac_tuning_moves.example.json",
    "windows_pc_check.example.json",
)


def _run_all_args(equipment_id: str = "EQ01", db: str = "test.sqlite3"):
    return build_parser().parse_args(
        [
            "run-all",
            "--equipment-id",
            equipment_id,
            "--db",
            db,
            "--seed-example-criteria",
            "--supervised",
        ]
    )


class ExecuteSelectedTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_cwd = os.getcwd()
        os.chdir(self._tmpdir.name)

        repo_root = Path(__file__).resolve().parent.parent
        Path("config").mkdir()
        for name in _EXAMPLE_CONFIG_FILES:
            (Path("config") / name).write_text(
                (repo_root / "config" / name).read_text(encoding="utf-8"), encoding="utf-8"
            )

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)
        self._tmpdir.cleanup()

    def test_selecting_a_single_item_runs_only_that_item(self) -> None:
        outcome = execute_selected(_run_all_args(), {"pc_check"})

        self.assertEqual(len(outcome.results), 1)
        self.assertEqual(outcome.results[0].check_item, "PC 동작 Check")
        self.assertEqual(outcome.c_class_results, [])
        self.assertEqual(outcome.c_class_detail, "")
        self.assertTrue(outcome.report_path.exists())

    def test_selecting_c_class_scan_runs_all_six_shared_scan_items(self) -> None:
        outcome = execute_selected(_run_all_args(), {C_CLASS_SCAN_KEY})

        self.assertEqual(outcome.results, [])
        self.assertEqual(len(outcome.c_class_results), 6)
        self.assertNotEqual(outcome.c_class_detail, "")

    def test_selecting_nothing_runs_no_checks_but_still_saves_a_report(self) -> None:
        outcome = execute_selected(_run_all_args(), set())

        self.assertEqual(outcome.results, [])
        self.assertEqual(outcome.c_class_results, [])
        self.assertTrue(outcome.report_path.exists())

    def test_action_items_reflect_db_history_even_for_items_not_selected_this_run(self) -> None:
        # 1차: 전체 실행해서 I/O Check가 NA로 DB에 남게 한다
        execute_run_all(_run_all_args())

        # 2차: PC 동작 Check 하나만 선택 실행해도, I/O Check의 과거 NA가
        # 조치 대상 목록에는 여전히 남아야 한다 (build_action_item_list와 동일한 원칙)
        outcome = execute_selected(_run_all_args(), {"pc_check"})

        self.assertEqual(len(outcome.results), 1)
        action_check_items = {item.check_item for item in outcome.action_items}
        self.assertIn("I/O Check", action_check_items)

    def test_execute_run_all_matches_selecting_every_item(self) -> None:
        all_keys = {key for key, _label, _fn in CHECK_ITEM_SPECS} | {C_CLASS_SCAN_KEY}

        outcome = execute_selected(_run_all_args(equipment_id="EQ02"), all_keys)

        self.assertEqual(len(outcome.results), 7)
        self.assertEqual(len(outcome.c_class_results), 6)
        self.assertEqual(len(outcome.all_results), 13)

    def test_on_progress_fires_once_per_selected_item_in_order(self) -> None:
        seen: list[tuple[str, str]] = []

        outcome = execute_selected(
            _run_all_args(),
            {"pc_check", "motion_hw_check", C_CLASS_SCAN_KEY},
            on_progress=lambda key, label: seen.append((key, label)),
        )

        self.assertEqual(
            seen,
            [
                ("pc_check", "PC 동작 Check"),
                ("motion_hw_check", "모션 H/W Check"),
                (C_CLASS_SCAN_KEY, "C분류 6항목 (Stage 평탄도·광학계·AFM·Gantry — 기준 시료 1회 Scan 공유)"),
            ],
        )
        self.assertFalse(outcome.cancelled)

    def test_should_continue_false_before_an_item_stops_remaining_items(self) -> None:
        seen: list[str] = []

        def should_continue() -> bool:
            return len(seen) < 1  # 2번째 항목을 시작하기 전에 중단

        outcome = execute_selected(
            _run_all_args(),
            {"pc_check", "motion_hw_check", C_CLASS_SCAN_KEY},
            on_progress=lambda key, _label: seen.append(key),
            should_continue=should_continue,
        )

        self.assertEqual(seen, ["pc_check"])
        self.assertEqual(len(outcome.results), 1)
        self.assertEqual(outcome.c_class_results, [])
        self.assertTrue(outcome.cancelled)

    def test_should_continue_false_before_c_class_skips_only_c_class(self) -> None:
        def should_continue() -> bool:
            return False

        outcome = execute_selected(
            _run_all_args(),
            {C_CLASS_SCAN_KEY},
            should_continue=should_continue,
        )

        self.assertEqual(outcome.results, [])
        self.assertEqual(outcome.c_class_results, [])
        self.assertTrue(outcome.cancelled)

    def test_an_already_started_item_always_finishes_even_if_cancelled_after(self) -> None:
        # should_continue는 각 항목을 "시작하기 전"에만 확인한다 — 이미 시작한
        # 항목(여기서는 pc_check 자체)은 중간에 끊기지 않고 끝까지 실행된다.
        outcome = execute_selected(_run_all_args(), {"pc_check"}, should_continue=lambda: True)

        self.assertEqual(len(outcome.results), 1)
        self.assertFalse(outcome.cancelled)


if __name__ == "__main__":
    unittest.main()
