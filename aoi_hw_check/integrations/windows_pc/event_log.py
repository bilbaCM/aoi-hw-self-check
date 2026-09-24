from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone

# Windows 이벤트 로그 레벨: 1=Critical, 2=Error, 3=Warning, 4=Information, 5=Verbose
_ERROR_LEVEL = 2


def build_event_log_query(lookback_hours: float, now: datetime | None = None) -> str:
    """최근 lookback_hours 시간 내 Error 레벨 이벤트 수를 세는 PowerShell 스크립트를 만든다.

    Win32_NTLogEvent(레거시 WMI 공급자)는 최신 Windows에서 비권장이므로,
    Windows Event Log(WinEvt) API 기반의 Get-WinEvent를 사용한다.
    """
    reference_time = now or datetime.now(timezone.utc)
    start_time = (reference_time - timedelta(hours=lookback_hours)).isoformat()
    return (
        "(Get-WinEvent -FilterHashtable @{LogName='Application','System'; "
        f"Level={_ERROR_LEVEL}; StartTime='{start_time}'}} "
        "-ErrorAction SilentlyContinue | Measure-Object).Count"
    )


def default_count_recent_errors(lookback_hours: float) -> int:
    """PowerShell Get-WinEvent로 최근 lookback_hours 시간 내 Error 레벨 이벤트 수를 센다.

    Windows 전용 — 이 함수를 직접 호출하는 대신, 테스트할 때는
    WindowsPCStateCollector에 대체 콜러블을 주입한다.
    """
    script = build_event_log_query(lookback_hours)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return int(result.stdout.strip() or "0")
