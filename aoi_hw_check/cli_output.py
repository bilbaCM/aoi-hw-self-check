from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from aoi_hw_check import __version__
from aoi_hw_check.core.models import CheckResult, Verdict

PROGRAM_NAME = "AOI H/W Self-Check 자동화 프로그램"

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_GREEN = "\x1b[32m"
_RED = "\x1b[31m"
_YELLOW = "\x1b[33m"

_VERDICT_LABEL = {
    Verdict.PASS: " PASS ",
    Verdict.FAIL: " FAIL ",
    Verdict.NA: "  NA  ",
}
_VERDICT_COLOR = {
    Verdict.PASS: _GREEN,
    Verdict.FAIL: _RED,
    Verdict.NA: _YELLOW,
}


def enable_windows_ansi() -> None:
    """Windows 콘솔에서 ANSI 색상 코드를 해석하도록 가상 터미널 모드를 켠다.

    Windows 10 1511 이상에서만 동작하며, 실패해도(구버전 등) 프로그램
    동작에는 영향이 없다 — 색상 없이 표시될 뿐이다.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    stream = sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def colorize(text: str, color: str) -> str:
    if not _supports_color():
        return text
    return f"{color}{text}{_RESET}"


def format_verdict_badge(verdict: Verdict) -> str:
    badge = f"[{_VERDICT_LABEL[verdict]}]"
    return colorize(badge, _BOLD + _VERDICT_COLOR[verdict])


def print_banner(equipment_id: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "=" * 60
    print(line)
    print(f" {PROGRAM_NAME}  (v{__version__})")
    print(f" 설비 ID: {equipment_id}    실행 시각: {now}")
    print(line)


def print_result(result: CheckResult) -> None:
    print(f"{format_verdict_badge(result.verdict)} {result.check_item} - {result.detail}")
    for mismatch in result.deviation:
        print(
            f"       - {mismatch.field_path}: "
            f"baseline={mismatch.baseline_value} current={mismatch.current_value}"
        )


def _plain_result_lines(result: CheckResult) -> list[str]:
    lines = [f"[{result.verdict.value}] {result.check_item} - {result.detail}"]
    for mismatch in result.deviation:
        lines.append(
            f"    - {mismatch.field_path}: "
            f"baseline={mismatch.baseline_value} current={mismatch.current_value}"
        )
    return lines


def save_run_report(
    equipment_id: str,
    results: list[CheckResult],
    action_items: list[CheckResult],
    reports_dir: str | Path = "reports",
) -> Path:
    """실행 결과를 색상 코드 없는 평문 리포트 파일로 저장한다 (감사 이력용).

    파일명은 "<설비ID>_<YYYYMMDD_HHMMSS>.log"이며, reports_dir가 없으면 만든다.
    """
    directory = Path(reports_dir)
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now()
    file_path = directory / f"{equipment_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.log"

    lines = [
        "=" * 60,
        f" {PROGRAM_NAME}  (v{__version__})",
        f" 설비 ID: {equipment_id}    실행 시각: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
    ]
    for result in results:
        lines.extend(_plain_result_lines(result))
    lines.append("")
    if action_items:
        lines.append(f"{equipment_id} 조치 대상 목록 ({len(action_items)}건)")
        for item in action_items:
            lines.append(f"  [{item.verdict.value}] {item.check_item}: {item.detail}")
    else:
        lines.append(f"{equipment_id}: 조치 대상 없음 — 셋업 착수 가능")

    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return file_path
