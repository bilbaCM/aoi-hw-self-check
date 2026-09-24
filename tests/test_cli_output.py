from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.cli_output import (
    PROGRAM_NAME,
    enable_windows_ansi,
    format_verdict_badge,
    print_banner,
    print_result,
    save_run_report,
)
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict


class FormatVerdictBadgeTest(unittest.TestCase):
    def test_badges_are_plain_text_when_stdout_is_not_a_tty(self) -> None:
        # StringIO는 isatty()가 False이므로 색상 코드 없이 순수 텍스트만 나와야 한다
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            badge = format_verdict_badge(Verdict.PASS)

        self.assertEqual(badge, "[ PASS ]")
        self.assertNotIn("\x1b", badge)

    def test_each_verdict_has_a_distinct_badge_label(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            labels = {
                format_verdict_badge(Verdict.PASS),
                format_verdict_badge(Verdict.FAIL),
                format_verdict_badge(Verdict.NA),
            }

        self.assertEqual(len(labels), 3)


class PrintHelpersTest(unittest.TestCase):
    def test_print_banner_includes_program_name_and_equipment_id(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            print_banner("EQ01")

        output = stdout.getvalue()
        self.assertIn(PROGRAM_NAME, output)
        self.assertIn("EQ01", output)

    def test_print_result_includes_deviation_lines(self) -> None:
        result = CheckResult(
            equipment_id="EQ01",
            check_item="I/O Check",
            verdict=Verdict.FAIL,
            deviation=[FieldMismatch("io1", True, False)],
            detail="응답 불일치 1건",
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            print_result(result)

        output = stdout.getvalue()
        self.assertIn("I/O Check", output)
        self.assertIn("io1", output)
        self.assertIn("baseline=True", output)
        self.assertIn("current=False", output)


class SaveRunReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_creates_reports_directory_and_file(self) -> None:
        reports_dir = Path(self._tmpdir.name) / "reports"
        result = CheckResult(
            equipment_id="EQ01", check_item="PC 동작 Check", verdict=Verdict.PASS, detail="ok"
        )

        path = save_run_report("EQ01", [result], [], reports_dir=reports_dir)

        self.assertTrue(path.exists())
        self.assertTrue(path.parent.samefile(reports_dir))

    def test_report_contains_results_and_action_items(self) -> None:
        reports_dir = Path(self._tmpdir.name) / "reports"
        passing = CheckResult(
            equipment_id="EQ01", check_item="PC 동작 Check", verdict=Verdict.PASS, detail="ok"
        )
        failing = CheckResult(
            equipment_id="EQ01",
            check_item="I/O Check",
            verdict=Verdict.FAIL,
            deviation=[FieldMismatch("io1", True, False)],
            detail="응답 불일치 1건",
        )

        path = save_run_report("EQ01", [passing, failing], [failing], reports_dir=reports_dir)
        content = path.read_text(encoding="utf-8")

        self.assertIn(PROGRAM_NAME, content)
        self.assertIn("[PASS] PC 동작 Check", content)
        self.assertIn("[FAIL] I/O Check", content)
        self.assertIn("조치 대상 목록 (1건)", content)
        self.assertNotIn("\x1b", content)  # 색상 코드가 파일에는 섞이면 안 됨

    def test_report_states_no_action_items_when_clean(self) -> None:
        reports_dir = Path(self._tmpdir.name) / "reports"
        result = CheckResult(
            equipment_id="EQ01", check_item="PC 동작 Check", verdict=Verdict.PASS, detail="ok"
        )

        path = save_run_report("EQ01", [result], [], reports_dir=reports_dir)
        content = path.read_text(encoding="utf-8")

        self.assertIn("조치 대상 없음", content)


class EnableWindowsAnsiTest(unittest.TestCase):
    def test_is_a_no_op_off_windows(self) -> None:
        # 이 테스트 환경은 Windows가 아니므로 예외 없이 조용히 아무 것도 하지 않아야 한다
        enable_windows_ansi()


if __name__ == "__main__":
    unittest.main()
