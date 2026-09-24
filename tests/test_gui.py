from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.gui_support import build_run_all_args, format_action_items, format_detail_cell


class BuildRunAllArgsTest(unittest.TestCase):
    def test_uses_mock_everything_with_seed_criteria_and_supervised(self) -> None:
        args = build_run_all_args("EQ01")

        self.assertEqual(args.command, "run-all")
        self.assertEqual(args.equipment_id, "EQ01")
        self.assertTrue(args.seed_example_criteria)
        self.assertTrue(args.supervised)
        # 연동 호스트를 주지 않았으므로 전부 Mock으로 실행되어야 한다
        self.assertIsNone(args.control_program_host)
        self.assertIsNone(args.ppmac_host)
        self.assertIsNone(args.inspection_program_host)
        self.assertFalse(args.use_wmi)


class FormatDetailCellTest(unittest.TestCase):
    def test_returns_plain_detail_when_no_deviation(self) -> None:
        result = CheckResult(
            equipment_id="EQ01", check_item="PC 동작 Check", verdict=Verdict.PASS, detail="정상"
        )
        self.assertEqual(format_detail_cell(result), "정상")

    def test_appends_mismatches_when_deviation_present(self) -> None:
        result = CheckResult(
            equipment_id="EQ01",
            check_item="I/O Check",
            verdict=Verdict.FAIL,
            deviation=[FieldMismatch("io1", True, False)],
            detail="응답 불일치 1건",
        )
        cell = format_detail_cell(result)
        self.assertIn("응답 불일치 1건", cell)
        self.assertIn("io1", cell)
        self.assertIn("baseline=True", cell)
        self.assertIn("current=False", cell)


class FormatActionItemsTest(unittest.TestCase):
    def test_states_no_action_items_when_clean(self) -> None:
        text = format_action_items("EQ01", [])
        self.assertIn("조치 대상 없음", text)

    def test_lists_action_items_when_present(self) -> None:
        failing = CheckResult(
            equipment_id="EQ01", check_item="I/O Check", verdict=Verdict.FAIL, detail="불일치 1건"
        )
        text = format_action_items("EQ01", [failing])
        self.assertIn("조치 대상 목록 (1건)", text)
        self.assertIn("I/O Check", text)
        self.assertIn("불일치 1건", text)


def _tk_app_available() -> bool:
    """이 실행 환경에서 실제 Tk 위젯을 만들 수 있는지 확인한다.

    설비 PC(Windows, 항상 GUI 세션)에서는 항상 True지만, tkinter가 설치되어
    있지 않거나(이 저장소의 기본 개발 컨테이너) 디스플레이가 없는 헤드리스
    환경에서는 위젯을 실제로 그려보는 테스트를 건너뛴다. 순수 로직
    (gui_support 모듈)은 이 확인과 무관하게 항상 테스트된다.
    """
    try:
        import tkinter as tk
    except ImportError:
        return False
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    root.destroy()
    return True


_TK_APP_AVAILABLE = _tk_app_available()


@unittest.skipUnless(_TK_APP_AVAILABLE, "tkinter 또는 디스플레이를 사용할 수 없는 환경")
class HWSelfCheckAppRenderTest(unittest.TestCase):
    def setUp(self) -> None:
        from aoi_hw_check.gui import HWSelfCheckApp

        self.app = HWSelfCheckApp()

    def tearDown(self) -> None:
        self.app.destroy()

    def test_render_outcome_populates_tree_and_action_text(self) -> None:
        from aoi_hw_check.cli import RunAllOutcome

        passing = CheckResult(
            equipment_id="EQ01", check_item="PC 동작 Check", verdict=Verdict.PASS, detail="정상"
        )
        failing = CheckResult(
            equipment_id="EQ01",
            check_item="I/O Check",
            verdict=Verdict.FAIL,
            deviation=[FieldMismatch("io1", True, False)],
            detail="응답 불일치 1건",
        )
        outcome = RunAllOutcome(
            results=[passing, failing],
            c_class_detail="Scan 1회 완료",
            c_class_results=[],
            action_items=[failing],
            escalated=False,
            report_path=Path("reports/EQ01_20260101_000000.log"),
        )

        self.app._render_outcome("EQ01", outcome)

        rows = self.app._tree.get_children()
        self.assertEqual(len(rows), 2)
        action_text = self.app._action_text.get("1.0", "end").strip()
        self.assertIn("조치 대상 목록 (1건)", action_text)
        self.assertIn("결과 저장 위치", self.app._report_var.get())


@unittest.skipUnless(_TK_APP_AVAILABLE, "tkinter 또는 디스플레이를 사용할 수 없는 환경")
class HWSelfCheckAppIntegrationTest(unittest.TestCase):
    """build_run_all_args -> execute_run_all -> _render_outcome을 실제로 이어서 실행한다."""

    _EXAMPLE_CONFIG_FILES = (
        "io_check_danger_list.example.json",
        "ppmac_axis_map.example.json",
        "ppmac_tuning_moves.example.json",
        "windows_pc_check.example.json",
    )

    def setUp(self) -> None:
        from aoi_hw_check.gui import HWSelfCheckApp

        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_cwd = os.getcwd()
        os.chdir(self._tmpdir.name)

        repo_root = Path(__file__).resolve().parent.parent
        Path("config").mkdir()
        for name in self._EXAMPLE_CONFIG_FILES:
            (Path("config") / name).write_text(
                (repo_root / "config" / name).read_text(encoding="utf-8"), encoding="utf-8"
            )

        self.app = HWSelfCheckApp()

    def tearDown(self) -> None:
        self.app.destroy()
        os.chdir(self._old_cwd)
        self._tmpdir.cleanup()

    def test_full_run_all_renders_thirteen_rows(self) -> None:
        from aoi_hw_check.cli import execute_run_all

        outcome = execute_run_all(build_run_all_args("EQ01"))
        self.app._render_outcome("EQ01", outcome)

        rows = self.app._tree.get_children()
        self.assertEqual(len(rows), 13)
        self.assertTrue(outcome.report_path.exists())


if __name__ == "__main__":
    unittest.main()
