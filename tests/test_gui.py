from __future__ import annotations

import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from aoi_hw_check.cli import C_CLASS_SCAN_KEY, CRITERIA_STORE_FILES
from aoi_hw_check.core.models import CheckResult, FieldMismatch, GateStatus, Verdict
from aoi_hw_check.core.thresholds import Criteria, JSONCriteriaStore
from aoi_hw_check.gui_support import (
    DANGER_LIST_PATH,
    SELECTABLE_ITEMS,
    ConnectionInputs,
    advance_criteria_gate,
    build_connected_run_all_args,
    build_run_all_args,
    describe_connection_inputs,
    format_action_items,
    format_criteria_row,
    format_detail_cell,
    format_report_row,
    list_criteria_rows,
    list_dangerous_io_points,
    list_report_files,
    parse_min_max,
    read_report_text,
    save_criteria_value,
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

    def test_uses_real_control_program_when_host_and_port_given(self) -> None:
        args = build_run_all_args(
            "EQ01", control_program_host="10.0.0.5", control_program_port=9000
        )

        self.assertEqual(args.control_program_host, "10.0.0.5")
        self.assertEqual(args.control_program_port, 9000)
        # 다른 연동은 지정하지 않았으니 그대로 Mock
        self.assertIsNone(args.ppmac_host)
        self.assertIsNone(args.inspection_program_host)

    def test_control_program_stays_mock_if_only_host_given_without_port(self) -> None:
        args = build_run_all_args("EQ01", control_program_host="10.0.0.5")

        self.assertIsNone(args.control_program_host)

    def test_ppmac_only_needs_a_host_port_defaults_to_1025(self) -> None:
        args = build_run_all_args("EQ01", ppmac_host="10.0.0.6")

        self.assertEqual(args.ppmac_host, "10.0.0.6")
        self.assertEqual(args.ppmac_port, 1025)

    def test_use_wmi_flag_passes_through(self) -> None:
        args = build_run_all_args("EQ01", use_wmi=True)

        self.assertTrue(args.use_wmi)

    def test_approve_dangerous_defaults_to_empty(self) -> None:
        args = build_run_all_args("EQ01")

        self.assertEqual(args.approve_dangerous, "")

    def test_approve_dangerous_passes_through(self) -> None:
        args = build_run_all_args("EQ01", approve_dangerous="high_voltage_output_1,other_id")

        self.assertEqual(args.approve_dangerous, "high_voltage_output_1,other_id")


class BuildConnectedRunAllArgsTest(unittest.TestCase):
    def test_all_blank_inputs_produce_all_mock_args(self) -> None:
        args = build_connected_run_all_args("EQ01", ConnectionInputs())

        self.assertIsNone(args.control_program_host)
        self.assertIsNone(args.ppmac_host)
        self.assertIsNone(args.inspection_program_host)
        self.assertFalse(args.use_wmi)

    def test_filled_inputs_produce_real_connection_args(self) -> None:
        inputs = ConnectionInputs(
            control_program_host="10.0.0.5",
            control_program_port="9000",
            ppmac_host="10.0.0.6",
            ppmac_port="1025",
            inspection_program_host="10.0.0.7",
            inspection_program_port="9100",
            use_wmi=True,
        )

        args = build_connected_run_all_args("EQ01", inputs)

        self.assertEqual(args.control_program_host, "10.0.0.5")
        self.assertEqual(args.control_program_port, 9000)
        self.assertEqual(args.ppmac_host, "10.0.0.6")
        self.assertEqual(args.ppmac_port, 1025)
        self.assertEqual(args.inspection_program_host, "10.0.0.7")
        self.assertEqual(args.inspection_program_port, 9100)
        self.assertTrue(args.use_wmi)

    def test_host_without_port_raises_a_korean_error(self) -> None:
        inputs = ConnectionInputs(control_program_host="10.0.0.5", control_program_port="")

        with self.assertRaises(ValueError) as ctx:
            build_connected_run_all_args("EQ01", inputs)
        self.assertIn("제어 프로그램", str(ctx.exception))

    def test_non_numeric_port_raises_a_korean_error(self) -> None:
        inputs = ConnectionInputs(inspection_program_host="10.0.0.7", inspection_program_port="abc")

        with self.assertRaises(ValueError) as ctx:
            build_connected_run_all_args("EQ01", inputs)
        self.assertIn("검사 프로그램", str(ctx.exception))

    def test_out_of_range_port_is_rejected(self) -> None:
        inputs = ConnectionInputs(ppmac_host="10.0.0.6", ppmac_port="70000")

        with self.assertRaises(ValueError):
            build_connected_run_all_args("EQ01", inputs)

    def test_no_approved_ids_means_no_approve_dangerous_flag(self) -> None:
        args = build_connected_run_all_args("EQ01", ConnectionInputs())

        self.assertEqual(args.approve_dangerous, "")

    def test_approved_ids_are_joined_and_sorted(self) -> None:
        args = build_connected_run_all_args(
            "EQ01", ConnectionInputs(), approved_dangerous_io_ids=["b_id", "a_id"]
        )

        self.assertEqual(args.approve_dangerous, "a_id,b_id")

    def test_blank_approved_ids_are_ignored(self) -> None:
        args = build_connected_run_all_args(
            "EQ01", ConnectionInputs(), approved_dangerous_io_ids=["  ", "real_id"]
        )

        self.assertEqual(args.approve_dangerous, "real_id")


class DescribeConnectionInputsTest(unittest.TestCase):
    def test_all_blank_describes_mock(self) -> None:
        self.assertEqual(describe_connection_inputs(ConnectionInputs()), "연동: 전부 Mock")

    def test_lists_which_integrations_are_real(self) -> None:
        inputs = ConnectionInputs(ppmac_host="10.0.0.6", use_wmi=True)

        summary = describe_connection_inputs(inputs)

        self.assertIn("PPMAC", summary)
        self.assertIn("PC WMI", summary)
        self.assertNotIn("제어 프로그램", summary)


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

    def test_save_criteria_value_registers_a_new_version_reset_to_generated(self) -> None:
        store_path = CRITERIA_STORE_FILES[0]
        store = JSONCriteriaStore(store_path)
        store.save_criteria("모션 H/W Check", "X.encoder_count", 90000, 110000)
        store.advance_criteria_gate("모션 H/W Check", "X.encoder_count", GateStatus.TRIAL)

        updated = save_criteria_value(store_path, "모션 H/W Check", "X.encoder_count", 95000, 105000)

        self.assertEqual((updated.min_value, updated.max_value), (95000, 105000))
        self.assertEqual(updated.version, 2)
        self.assertEqual(updated.gate_status, GateStatus.GENERATED)
        reloaded = JSONCriteriaStore(store_path).get_criteria("모션 H/W Check", "X.encoder_count")
        self.assertEqual((reloaded.min_value, reloaded.max_value), (95000, 105000))
        self.assertEqual(reloaded.gate_status, GateStatus.GENERATED)


class ListDangerousIoPointsTest(unittest.TestCase):
    """list_dangerous_io_points는 DANGER_LIST_PATH를 현재 작업 디렉터리 기준
    상대경로로 읽으므로 임시 디렉터리로 옮겨서 테스트한다."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_cwd = os.getcwd()
        os.chdir(self._tmpdir.name)

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)
        self._tmpdir.cleanup()

    def test_empty_when_danger_list_file_is_missing(self) -> None:
        self.assertEqual(list_dangerous_io_points(), [])

    def test_lists_ids_from_the_danger_list_with_known_description(self) -> None:
        os.makedirs(os.path.dirname(DANGER_LIST_PATH), exist_ok=True)
        with open(DANGER_LIST_PATH, "w", encoding="utf-8") as f:
            f.write('["high_voltage_output_1"]')

        points = list_dangerous_io_points()

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].io_id, "high_voltage_output_1")
        self.assertIn("위험 출력", points[0].description)

    def test_unknown_id_still_listed_with_blank_description(self) -> None:
        os.makedirs(os.path.dirname(DANGER_LIST_PATH), exist_ok=True)
        with open(DANGER_LIST_PATH, "w", encoding="utf-8") as f:
            f.write('["some_new_output_not_in_default_map"]')

        points = list_dangerous_io_points()

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].io_id, "some_new_output_not_in_default_map")
        self.assertEqual(points[0].description, "")


class ListReportFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.reports_dir = Path(self._tmpdir.name) / "reports"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _write_report(self, equipment_id: str, timestamp: str, content: str = "content") -> None:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        (self.reports_dir / f"{equipment_id}_{timestamp}.log").write_text(content, encoding="utf-8")

    def test_empty_when_reports_dir_is_missing(self) -> None:
        self.assertEqual(list_report_files(self.reports_dir), [])

    def test_lists_reports_newest_first(self) -> None:
        self._write_report("EQ01", "20260101_090000")
        self._write_report("EQ01", "20260102_090000")

        infos = list_report_files(self.reports_dir)

        self.assertEqual([info.measured_at.day for info in infos], [2, 1])

    def test_ignores_files_not_matching_the_report_filename_format(self) -> None:
        self._write_report("EQ01", "20260101_090000")
        (self.reports_dir / "not_a_report.txt").write_text("junk", encoding="utf-8")

        infos = list_report_files(self.reports_dir)

        self.assertEqual(len(infos), 1)

    def test_equipment_id_with_underscore_is_parsed_correctly(self) -> None:
        self._write_report("EQ_01", "20260101_090000")

        infos = list_report_files(self.reports_dir)

        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].equipment_id, "EQ_01")

    def test_equipment_id_filter_keeps_only_exact_matches(self) -> None:
        self._write_report("EQ01", "20260101_090000")
        self._write_report("EQ02", "20260101_090000")

        infos = list_report_files(self.reports_dir, equipment_id_filter="EQ02")

        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].equipment_id, "EQ02")

    def test_format_report_row(self) -> None:
        self._write_report("EQ01", "20260101_090000")
        info = list_report_files(self.reports_dir)[0]

        row = format_report_row(info)

        self.assertEqual(row, ("EQ01", "2026-01-01 09:00:00", "EQ01_20260101_090000.log"))

    def test_read_report_text_returns_file_contents(self) -> None:
        self._write_report("EQ01", "20260101_090000", content="hello report")
        info = list_report_files(self.reports_dir)[0]

        self.assertEqual(read_report_text(info), "hello report")


class ParseMinMaxTest(unittest.TestCase):
    def test_parses_valid_numbers(self) -> None:
        self.assertEqual(parse_min_max("90000", "110000"), (90000.0, 110000.0))
        self.assertEqual(parse_min_max("-0.05", "0.05"), (-0.05, 0.05))

    def test_rejects_non_numeric_input(self) -> None:
        with self.assertRaises(ValueError):
            parse_min_max("abc", "110000")

    def test_rejects_min_greater_than_or_equal_to_max(self) -> None:
        with self.assertRaises(ValueError):
            parse_min_max("110000", "90000")
        with self.assertRaises(ValueError):
            parse_min_max("100", "100")


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

    def test_connection_summary_starts_as_mock(self) -> None:
        self.assertEqual(self.app._connection_summary_var.get(), "연동: 전부 Mock")

    def test_applying_connection_inputs_updates_summary_and_stored_inputs(self) -> None:
        inputs = ConnectionInputs(ppmac_host="10.0.0.6")

        self.app._apply_connection_inputs(inputs)

        self.assertEqual(self.app._connection_inputs, inputs)
        self.assertIn("PPMAC", self.app._connection_summary_var.get())

    def test_dangerous_io_checkboxes_default_unapproved(self) -> None:
        # 이 테스트는 chdir 없이 저장소 루트에서 실행되므로 실제
        # config/io_check_danger_list.example.json(high_voltage_output_1)을 읽는다.
        self.assertIn("high_voltage_output_1", self.app._danger_vars)
        self.assertEqual(self.app._approved_dangerous_ids(), set())

    def test_checking_a_danger_checkbox_approves_it(self) -> None:
        self.app._danger_vars["high_voltage_output_1"].set(True)

        self.assertEqual(self.app._approved_dangerous_ids(), {"high_voltage_output_1"})

    def test_render_outcome_shows_cancelled_status(self) -> None:
        from aoi_hw_check.cli import RunAllOutcome

        passing = CheckResult(
            equipment_id="EQ01", check_item="PC 동작 Check", verdict=Verdict.PASS, detail="정상"
        )
        outcome = RunAllOutcome(
            results=[passing],
            c_class_detail="",
            c_class_results=[],
            action_items=[],
            escalated=False,
            report_path=Path("reports/EQ01_20260101_000000.log"),
            cancelled=True,
        )

        self.app._render_outcome("EQ01", outcome)

        self.assertIn("취소됨", self.app._status_var.get())

    def test_run_with_approved_danger_ids_asks_for_confirmation(self) -> None:
        from unittest import mock

        self.app._danger_vars["high_voltage_output_1"].set(True)

        with mock.patch("aoi_hw_check.gui.messagebox.askyesno", return_value=False) as mock_ask:
            self.app._on_run_clicked()

        mock_ask.assert_called_once()
        # 확인 대화상자에서 "아니오"를 선택했으니 실행 버튼은 그대로 활성 상태여야 한다
        self.assertNotIn("disabled", self.app._run_button.state())


@unittest.skipUnless(_TK_APP_AVAILABLE, "tkinter 또는 디스플레이를 사용할 수 없는 환경")
class ConnectionSettingsDialogTest(unittest.TestCase):
    def setUp(self) -> None:
        from aoi_hw_check.gui import HWSelfCheckApp

        self.app = HWSelfCheckApp()

    def tearDown(self) -> None:
        self.app.destroy()

    def _open_dialog(self, current: ConnectionInputs | None = None):
        from aoi_hw_check.gui import ConnectionSettingsDialog

        captured = {}
        dialog = ConnectionSettingsDialog(
            self.app, current or ConnectionInputs(), on_saved=lambda inputs: captured.update(saved=inputs)
        )
        return dialog, captured

    def test_prefills_fields_from_current_inputs(self) -> None:
        current = ConnectionInputs(ppmac_host="10.0.0.6", ppmac_port="1025", use_wmi=True)
        dialog, _captured = self._open_dialog(current)

        self.assertEqual(dialog._ppmac_host_var.get(), "10.0.0.6")
        self.assertEqual(dialog._ppmac_port_var.get(), "1025")
        self.assertTrue(dialog._use_wmi_var.get())
        dialog.destroy()

    def test_saving_valid_input_calls_on_saved_and_closes(self) -> None:
        dialog, captured = self._open_dialog()

        dialog._control_host_var.set("10.0.0.5")
        dialog._control_port_var.set("9000")
        dialog._on_save_clicked()

        self.assertFalse(dialog.winfo_exists())
        saved: ConnectionInputs = captured["saved"]
        self.assertEqual(saved.control_program_host, "10.0.0.5")
        self.assertEqual(saved.control_program_port, "9000")

    def test_saving_invalid_port_shows_error_and_keeps_dialog_open(self) -> None:
        from unittest import mock

        dialog, captured = self._open_dialog()
        dialog._control_host_var.set("10.0.0.5")
        dialog._control_port_var.set("not-a-number")

        with mock.patch("aoi_hw_check.gui.messagebox.showerror") as mock_showerror:
            dialog._on_save_clicked()

        mock_showerror.assert_called_once()
        self.assertTrue(dialog.winfo_exists())
        self.assertNotIn("saved", captured)
        dialog.destroy()

    def test_main_window_can_open_connection_settings(self) -> None:
        self.app._open_connection_settings()


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

    def _run_via_button_and_wait(self, timeout_sec: float = 30.0) -> None:
        # Mock 실행 자체는 보통 1초 안에 끝나지만, 공유 샌드박스에서 다른
        # 프로세스와 자원을 다툴 때는 스레드 스케줄링이 밀려 훨씬 오래 걸릴 수
        # 있어(직접 측정: 정상 시 <1초, 부하 시 10초 넘게 걸리는 경우 관찰)
        # 넉넉하게 잡는다 — 실제 동작이 아니라 폴링 루프의 여유 시간 문제다.
        self.app._on_run_clicked()
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            self.app.update()
            if self.app._tree.get_children() or self.app._status_var.get() == "오류 발생":
                return
            time.sleep(0.02)
        self.fail("실행이 제한 시간 내에 끝나지 않았습니다")

    def test_running_via_button_click_skips_confirmation_without_approved_danger_ids(self) -> None:
        from unittest import mock

        # 이 테스트의 목적은 승인된 위험 출력이 없을 때 확인 대화상자가 뜨지
        # 않는지 확인하는 것뿐이라, 굳이 13개 항목을 전부 돌릴 필요는 없다 —
        # 항목 1개로 좁혀서 빠르고 안정적으로 검증한다.
        self.app._set_all_items(False)
        self.app._item_vars["pc_check"].set(True)

        with mock.patch("aoi_hw_check.gui.messagebox.askyesno") as mock_ask:
            self._run_via_button_and_wait()

        mock_ask.assert_not_called()

    def test_running_via_button_click_advances_progress_to_completion(self) -> None:
        self.app._set_all_items(False)
        self.app._item_vars["pc_check"].set(True)
        self.app._item_vars["motion_hw_check"].set(True)

        self._run_via_button_and_wait()

        self.assertEqual(len(self.app._tree.get_children()), 2)
        self.assertEqual(int(self.app._progress["value"]), 2)
        self.assertEqual(int(self.app._progress["maximum"]), 2)
        self.assertIn("완료", self.app._status_var.get())
        self.assertIn("disabled", self.app._cancel_button.state())

    def test_approving_a_danger_id_via_button_runs_it_after_confirmation(self) -> None:
        from unittest import mock

        self.app._set_all_items(False)
        self.app._item_vars["io_check"].set(True)
        self.app._danger_vars["high_voltage_output_1"].set(True)

        with mock.patch("aoi_hw_check.gui.messagebox.askyesno", return_value=True):
            self._run_via_button_and_wait()

        rows = self.app._tree.get_children()
        self.assertEqual(len(rows), 1)
        values = self.app._tree.item(rows[0], "values")
        self.assertEqual(values[1], "I/O Check")
        # 위험 출력을 승인했으니 더 이상 "작업자 확인 대기"로 NA 처리되지 않아야 한다
        self.assertNotIn("작업자 확인 대기", values[2])


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
        window._update_buttons()

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
        window._update_buttons()

        self.assertIn("disabled", window._advance_button.state())
        self.assertIn("APPLIED", window._advance_button.cget("text"))

    def test_edit_button_enabled_for_any_selected_row_including_applied(self) -> None:
        store = JSONCriteriaStore(CRITERIA_STORE_FILES[0])
        store.save_criteria("모션 H/W Check", "X.encoder_count", 90000, 110000)
        for target in (GateStatus.TRIAL, GateStatus.OPTIMIZED, GateStatus.VALIDATED, GateStatus.APPLIED):
            store.advance_criteria_gate("모션 H/W Check", "X.encoder_count", target)

        window = self._open_window()
        row_id = window._tree.get_children()[0]
        window._tree.selection_set(row_id)
        window._update_buttons()

        # 값 수정은 Gate 단계와 무관하게 항상 가능해야 한다 (APPLIED라도 재조정할 수 있음)
        self.assertNotIn("disabled", window._edit_button.state())

    def test_confirmed_advance_updates_the_underlying_file_and_refreshes_the_table(self) -> None:
        from unittest import mock

        JSONCriteriaStore(CRITERIA_STORE_FILES[0]).save_criteria(
            "모션 H/W Check", "X.encoder_count", 90000, 110000
        )
        window = self._open_window()
        row_id = window._tree.get_children()[0]
        window._tree.selection_set(row_id)
        window._update_buttons()

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
        window._update_buttons()

        with mock.patch("aoi_hw_check.gui.messagebox.askyesno", return_value=False):
            window._on_advance_clicked()

        reloaded = JSONCriteriaStore(CRITERIA_STORE_FILES[0]).get_criteria(
            "모션 H/W Check", "X.encoder_count"
        )
        self.assertEqual(reloaded.gate_status, GateStatus.GENERATED)

    def test_main_window_can_open_the_gate_management_window(self) -> None:
        self.app._open_gate_window()

    def test_edit_button_opens_a_dialog_prefilled_with_current_values(self) -> None:
        JSONCriteriaStore(CRITERIA_STORE_FILES[0]).save_criteria(
            "모션 H/W Check", "X.encoder_count", 90000, 110000
        )
        window = self._open_window()
        row_id = window._tree.get_children()[0]
        window._tree.selection_set(row_id)
        window._update_buttons()

        window._on_edit_clicked()

        from aoi_hw_check.gui import EditCriteriaDialog

        dialogs = [c for c in window.winfo_children() if isinstance(c, EditCriteriaDialog)]
        self.assertEqual(len(dialogs), 1)
        dialog = dialogs[0]
        self.assertEqual(dialog._min_var.get(), "90000")
        self.assertEqual(dialog._max_var.get(), "110000")
        dialog.destroy()

    def test_tree_has_a_double_click_binding_wired_to_edit(self) -> None:
        # Tk은 "Double-1" 같은 합성(synthetic) 이벤트는 event_generate로 직접
        # 재현할 수 없어(TclError: Double modifier not allowed) 실제 더블클릭
        # 타이밍을 흉내낼 수 없다 — 여기서는 바인딩 자체가 등록됐는지만
        # 확인하고, 열리는 동작 자체는 버튼 클릭 경로(_on_edit_clicked)로
        # 이미 검증한다.
        window = self._open_window()
        self.assertTrue(window._tree.bind("<Double-1>"))

    def test_saving_valid_values_registers_a_new_version_and_refreshes_the_table(self) -> None:
        JSONCriteriaStore(CRITERIA_STORE_FILES[0]).save_criteria(
            "모션 H/W Check", "X.encoder_count", 90000, 110000
        )
        window = self._open_window()
        row_id = window._tree.get_children()[0]
        window._tree.selection_set(row_id)
        window._on_edit_clicked()

        from aoi_hw_check.gui import EditCriteriaDialog

        dialog = [c for c in window.winfo_children() if isinstance(c, EditCriteriaDialog)][0]
        dialog._min_var.set("95000")
        dialog._max_var.set("105000")
        dialog._on_save_clicked()

        reloaded = JSONCriteriaStore(CRITERIA_STORE_FILES[0]).get_criteria(
            "모션 H/W Check", "X.encoder_count"
        )
        self.assertEqual((reloaded.min_value, reloaded.max_value), (95000, 105000))
        self.assertEqual(reloaded.version, 2)
        self.assertEqual(reloaded.gate_status, GateStatus.GENERATED)
        # 저장 후 대화상자는 닫히고, 뒤에 있던 표는 새로고침되어야 한다
        self.assertFalse(dialog.winfo_exists())
        row_values = window._tree.item(window._tree.get_children()[0], "values")
        self.assertEqual(row_values[3], "2")
        self.assertEqual(row_values[5], "GENERATED")

    def test_saving_invalid_values_shows_an_error_and_keeps_the_dialog_open(self) -> None:
        from unittest import mock

        JSONCriteriaStore(CRITERIA_STORE_FILES[0]).save_criteria(
            "모션 H/W Check", "X.encoder_count", 90000, 110000
        )
        window = self._open_window()
        row_id = window._tree.get_children()[0]
        window._tree.selection_set(row_id)
        window._on_edit_clicked()

        from aoi_hw_check.gui import EditCriteriaDialog

        dialog = [c for c in window.winfo_children() if isinstance(c, EditCriteriaDialog)][0]
        dialog._min_var.set("110000")
        dialog._max_var.set("90000")  # 최소값이 최대값보다 커서 거부되어야 함

        with mock.patch("aoi_hw_check.gui.messagebox.showerror") as mock_showerror:
            dialog._on_save_clicked()

        mock_showerror.assert_called_once()
        self.assertTrue(dialog.winfo_exists())
        reloaded = JSONCriteriaStore(CRITERIA_STORE_FILES[0]).get_criteria(
            "모션 H/W Check", "X.encoder_count"
        )
        self.assertEqual(reloaded.version, 1)
        dialog.destroy()


@unittest.skipUnless(_TK_APP_AVAILABLE, "tkinter 또는 디스플레이를 사용할 수 없는 환경")
class ReportHistoryWindowTest(unittest.TestCase):
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

    def _write_report(self, equipment_id: str, timestamp: str, content: str) -> None:
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        (reports_dir / f"{equipment_id}_{timestamp}.log").write_text(content, encoding="utf-8")

    def _open_window(self):
        from aoi_hw_check.gui import ReportHistoryWindow

        return ReportHistoryWindow(self.app)

    def test_shows_no_rows_and_a_placeholder_when_nothing_saved(self) -> None:
        window = self._open_window()

        self.assertEqual(len(window._tree.get_children()), 0)
        self.assertIn(
            "저장된 리포트가 없습니다", window._content_text.get("1.0", "end").strip()
        )
        window.destroy()

    def test_lists_reports_newest_first_and_shows_content_on_select(self) -> None:
        self._write_report("EQ01", "20260101_090000", "첫 실행 리포트")
        self._write_report("EQ01", "20260102_090000", "둘째 실행 리포트")

        window = self._open_window()

        rows = window._tree.get_children()
        self.assertEqual(len(rows), 2)
        self.assertEqual(window._tree.item(rows[0], "values")[2], "EQ01_20260102_090000.log")

        window._tree.selection_set(rows[1])
        window._show_selected()

        self.assertEqual(window._content_text.get("1.0", "end").strip(), "첫 실행 리포트")
        window.destroy()

    def test_filter_keeps_only_matching_equipment_id(self) -> None:
        self._write_report("EQ01", "20260101_090000", "EQ01 리포트")
        self._write_report("EQ02", "20260101_090000", "EQ02 리포트")

        window = self._open_window()
        window._filter_var.set("EQ02")
        window._reload()

        rows = window._tree.get_children()
        self.assertEqual(len(rows), 1)
        self.assertEqual(window._tree.item(rows[0], "values")[0], "EQ02")
        window.destroy()

    def test_main_window_can_open_report_history(self) -> None:
        self.app._open_report_history()


if __name__ == "__main__":
    unittest.main()
