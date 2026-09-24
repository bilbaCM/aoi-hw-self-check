from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from aoi_hw_check.cli import C_CLASS_SCAN_KEY, CRITERIA_STORE_FILES
from aoi_hw_check.core.models import CheckResult, FieldMismatch, GateStatus, Verdict
from aoi_hw_check.core.thresholds import Criteria, JSONCriteriaStore
from aoi_hw_check.gui_support import (
    SELECTABLE_ITEMS,
    advance_criteria_gate,
    build_run_all_args,
    format_action_items,
    format_criteria_row,
    format_detail_cell,
    list_criteria_rows,
)


class SelectableItemsTest(unittest.TestCase):
    def test_lists_seven_individual_items_plus_one_c_class_group(self) -> None:
        keys = [key for key, _label in SELECTABLE_ITEMS]

        self.assertEqual(len(keys), 8)
        self.assertEqual(len(set(keys)), 8)  # 중복 key 없음
        self.assertEqual(keys[-1], C_CLASS_SCAN_KEY)


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


class FormatCriteriaRowTest(unittest.TestCase):
    def test_formats_expected_columns(self) -> None:
        criteria = Criteria(
            check_item="모션 H/W Check",
            key="X.encoder_count",
            version=1,
            min_value=90000,
            max_value=110000,
            updated_at=datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
            gate_status=GateStatus.GENERATED,
        )

        row = format_criteria_row("motion_hw_check_criteria.json", criteria)

        self.assertEqual(
            row,
            (
                "motion_hw_check_criteria.json",
                "모션 H/W Check",
                "X.encoder_count",
                "1",
                "90000 ~ 110000",
                "GENERATED",
                "2026-01-01 09:30:00",
            ),
        )


class GateManagementFileIOTest(unittest.TestCase):
    """list_criteria_rows/advance_criteria_gate는 CRITERIA_STORE_FILES를 현재
    작업 디렉터리 기준 상대경로로 읽으므로, 실행 파일들과 마찬가지로 임시
    디렉터리로 옮겨서 테스트한다."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_cwd = os.getcwd()
        os.chdir(self._tmpdir.name)

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)
        self._tmpdir.cleanup()

    def test_list_criteria_rows_is_empty_when_nothing_registered(self) -> None:
        self.assertEqual(list_criteria_rows(), [])

    def test_list_criteria_rows_sorts_by_check_item_then_key(self) -> None:
        store = JSONCriteriaStore(CRITERIA_STORE_FILES[0])
        store.save_criteria("모션 H/W Check", "Y.pwm_duty_percent", 30, 60)
        store.save_criteria("모션 H/W Check", "X.encoder_count", 90000, 110000)

        rows = list_criteria_rows()

        self.assertEqual([criteria.key for _path, criteria in rows], ["X.encoder_count", "Y.pwm_duty_percent"])

    def test_advance_criteria_gate_advances_and_persists(self) -> None:
        store_path = CRITERIA_STORE_FILES[0]
        JSONCriteriaStore(store_path).save_criteria("모션 H/W Check", "X.encoder_count", 90000, 110000)

        advanced = advance_criteria_gate(store_path, "모션 H/W Check", "X.encoder_count", GateStatus.TRIAL)

        self.assertEqual(advanced.gate_status, GateStatus.TRIAL)
        reloaded = JSONCriteriaStore(store_path).get_criteria("모션 H/W Check", "X.encoder_count")
        self.assertEqual(reloaded.gate_status, GateStatus.TRIAL)


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

    def test_all_items_are_selected_by_default(self) -> None:
        self.assertEqual(len(self.app._item_vars), 8)
        self.assertEqual(self.app._selected_item_keys(), set(self.app._item_vars))

    def test_set_all_items_toggles_every_checkbox(self) -> None:
        self.app._set_all_items(False)
        self.assertEqual(self.app._selected_item_keys(), set())

        self.app._set_all_items(True)
        self.assertEqual(self.app._selected_item_keys(), set(self.app._item_vars))

    def test_unchecking_one_item_excludes_it_from_selection(self) -> None:
        self.app._item_vars["pc_check"].set(False)

        selected = self.app._selected_item_keys()
        self.assertNotIn("pc_check", selected)
        self.assertEqual(len(selected), 7)


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

    def test_unchecking_all_but_pc_check_runs_and_renders_only_that_item(self) -> None:
        from aoi_hw_check.cli import execute_selected

        self.app._set_all_items(False)
        self.app._item_vars["pc_check"].set(True)

        outcome = execute_selected(build_run_all_args("EQ01"), self.app._selected_item_keys())
        self.app._render_outcome("EQ01", outcome)

        rows = self.app._tree.get_children()
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.app._tree.item(rows[0], "values")[1], "PC 동작 Check")


@unittest.skipUnless(_TK_APP_AVAILABLE, "tkinter 또는 디스플레이를 사용할 수 없는 환경")
class CriteriaGateWindowTest(unittest.TestCase):
    def setUp(self) -> None:
        from aoi_hw_check.gui import HWSelfCheckApp

        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_cwd = os.getcwd()
        os.chdir(self._tmpdir.name)

        self.app = HWSelfCheckApp()

    def tearDown(self) -> None:
        self.app.destroy()
        os.chdir(self._old_cwd)
        self._tmpdir.cleanup()

    def _open_window(self):
        from aoi_hw_check.gui import CriteriaGateWindow

        # self.app.destroy()가 tearDown에서 이 Toplevel도 같이 정리하므로 별도
        # cleanup을 등록하지 않는다 (등록하면 이중 destroy로 TclError가 난다).
        return CriteriaGateWindow(self.app)

    def test_shows_no_rows_when_nothing_registered(self) -> None:
        window = self._open_window()
        self.assertEqual(len(window._tree.get_children()), 0)

    def test_lists_registered_criteria(self) -> None:
        JSONCriteriaStore(CRITERIA_STORE_FILES[0]).save_criteria(
            "모션 H/W Check", "X.encoder_count", 90000, 110000
        )

        window = self._open_window()

        rows = window._tree.get_children()
        self.assertEqual(len(rows), 1)
        values = window._tree.item(rows[0], "values")
        self.assertEqual(values[1], "모션 H/W Check")
        self.assertEqual(values[2], "X.encoder_count")
        self.assertEqual(values[5], "GENERATED")

    def test_selecting_a_row_enables_advance_button_with_target_stage(self) -> None:
        JSONCriteriaStore(CRITERIA_STORE_FILES[0]).save_criteria(
            "모션 H/W Check", "X.encoder_count", 90000, 110000
        )
        window = self._open_window()
        row_id = window._tree.get_children()[0]

        window._tree.selection_set(row_id)
        window._update_advance_button()

        self.assertNotIn("disabled", window._advance_button.state())
        self.assertIn("TRIAL", window._advance_button.cget("text"))

    def test_item_already_applied_disables_advance_button(self) -> None:
        store = JSONCriteriaStore(CRITERIA_STORE_FILES[0])
        store.save_criteria("모션 H/W Check", "X.encoder_count", 90000, 110000)
        for target in (GateStatus.TRIAL, GateStatus.OPTIMIZED, GateStatus.VALIDATED, GateStatus.APPLIED):
            store.advance_criteria_gate("모션 H/W Check", "X.encoder_count", target)

        window = self._open_window()
        row_id = window._tree.get_children()[0]
        window._tree.selection_set(row_id)
        window._update_advance_button()

        self.assertIn("disabled", window._advance_button.state())
        self.assertIn("APPLIED", window._advance_button.cget("text"))

    def test_confirmed_advance_updates_the_underlying_file_and_refreshes_the_table(self) -> None:
        from unittest import mock

        JSONCriteriaStore(CRITERIA_STORE_FILES[0]).save_criteria(
            "모션 H/W Check", "X.encoder_count", 90000, 110000
        )
        window = self._open_window()
        row_id = window._tree.get_children()[0]
        window._tree.selection_set(row_id)
        window._update_advance_button()

        with mock.patch("aoi_hw_check.gui.messagebox.askyesno", return_value=True):
            window._on_advance_clicked()

        reloaded = JSONCriteriaStore(CRITERIA_STORE_FILES[0]).get_criteria(
            "모션 H/W Check", "X.encoder_count"
        )
        self.assertEqual(reloaded.gate_status, GateStatus.TRIAL)
        values = window._tree.item(window._tree.get_children()[0], "values")
        self.assertEqual(values[5], "TRIAL")

    def test_declining_the_confirmation_leaves_the_gate_unchanged(self) -> None:
        from unittest import mock

        JSONCriteriaStore(CRITERIA_STORE_FILES[0]).save_criteria(
            "모션 H/W Check", "X.encoder_count", 90000, 110000
        )
        window = self._open_window()
        row_id = window._tree.get_children()[0]
        window._tree.selection_set(row_id)
        window._update_advance_button()

        with mock.patch("aoi_hw_check.gui.messagebox.askyesno", return_value=False):
            window._on_advance_clicked()

        reloaded = JSONCriteriaStore(CRITERIA_STORE_FILES[0]).get_criteria(
            "모션 H/W Check", "X.encoder_count"
        )
        self.assertEqual(reloaded.gate_status, GateStatus.GENERATED)

    def test_main_window_can_open_the_gate_management_window(self) -> None:
        self.app._open_gate_window()


if __name__ == "__main__":
    unittest.main()
