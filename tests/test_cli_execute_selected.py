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


if __name__ == "__main__":
    unittest.main()
