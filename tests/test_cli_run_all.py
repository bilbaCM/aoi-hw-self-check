from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.cli import main

_EXAMPLE_CONFIG_FILES = (
    "io_check_danger_list.example.json",
    "ppmac_axis_map.example.json",
    "ppmac_tuning_moves.example.json",
    "windows_pc_check.example.json",
)


class RunAllCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_cwd = os.getcwd()
        os.chdir(self._tmpdir.name)

        # run-all의 설정 파일 기본값은 "config/..." 상대경로이므로,
        # 리포지토리의 example 설정을 임시 작업 디렉터리에 복사해 둔다.
        repo_root = Path(__file__).resolve().parent.parent
        Path("config").mkdir()
        for name in _EXAMPLE_CONFIG_FILES:
            (Path("config") / name).write_text(
                (repo_root / "config" / name).read_text(encoding="utf-8"), encoding="utf-8"
            )

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)
        self._tmpdir.cleanup()

    def test_run_all_executes_all_items_and_reports_action_items(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "run-all",
                    "--equipment-id",
                    "EQ01",
                    "--db",
                    "test.sqlite3",
                    "--seed-example-criteria",
                    "--supervised",
                ]
            )

        output = stdout.getvalue()
        # 모션 Tuning 상태 확인은 동종 설비가 1대뿐이라 NA -> 조치 대상 목록에 남아 exit 1
        self.assertEqual(exit_code, 1)
        self.assertIn("PC 동작 Check", output)
        self.assertIn("모션 H/W Check", output)
        self.assertIn("광학 부품 동작·통신 확인", output)
        self.assertIn("I/O Check", output)
        self.assertIn("설비 단동 동작 확인", output)
        self.assertIn("모션 Tuning 상태 확인", output)
        self.assertIn("설비 연동 동작 Test", output)
        self.assertIn("Stage PIN·PAD·Sensor 평탄도", output)
        self.assertIn("Micro 광학계 상태 확인", output)
        self.assertIn("Macro 광학계 상태 확인", output)
        self.assertIn("계측 광학계 상태 확인", output)
        self.assertIn("AFM Setting 상태 확인", output)
        self.assertIn("계측 Y축 Gantry 직각도", output)
        self.assertIn("조치 대상 목록", output)

    def test_run_all_is_clean_on_second_run_with_a_peer(self) -> None:
        # danger-list의 위험 출력(high_voltage_output_1)을 매 실행 승인해야
        # I/O Check가 NA로 남지 않는다 — 작업자 승인 없이는 시험하지 않는다는
        # 안전 설계가 의도한 그대로다.
        common_args = [
            "--seed-example-criteria",
            "--supervised",
            "--approve-dangerous",
            "high_voltage_output_1",
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            main(["run-all", "--equipment-id", "EQ01", "--db", "test.sqlite3", *common_args])

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                ["run-all", "--equipment-id", "EQ02", "--db", "test.sqlite3", *common_args]
            )

        # EQ02는 EQ01이라는 동종 설비 비교 대상이 있어 모션 Tuning도 판정 가능해져야 함
        self.assertEqual(exit_code, 0)
        self.assertIn("조치 대상 없음", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
