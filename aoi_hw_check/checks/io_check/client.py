from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from aoi_hw_check.checks.io_check.models import IOPoint


class PLCTestModeClient(ABC):
    """실제 구현은 PLC Test Mode를 통해 지정 I/O에 입력을 강제 구동하고 출력을 읽는다."""

    @abstractmethod
    def test_io_point(self, io_id: str, forced_input_value: Any) -> Any:
        """io_id에 forced_input_value를 강제 구동하고, 관측된 출력 값을 반환한다."""


class MockPLCTestModeClient(PLCTestModeClient):
    """실제 PLC 연동 전까지 사용하는 Mock — 정상 포인트는 입력값을 그대로 반사한다."""

    def __init__(self, faulty_io_ids: set[str] | None = None):
        self._faulty_io_ids = faulty_io_ids or set()

    def test_io_point(self, io_id: str, forced_input_value: Any) -> Any:
        if io_id in self._faulty_io_ids:
            return None
        return forced_input_value


# 개발/테스트용 예시 I/O Map — 실제 목록은 설비 I/O Map 문서 기준으로 정의 필요 (TBD).
DEFAULT_IO_MAP: list[IOPoint] = [
    IOPoint("cylinder_1_advance", True, True, "실린더1 전진 센서"),
    IOPoint("cylinder_1_retract", False, False, "실린더1 후진 센서"),
    IOPoint("safety_door_lock", True, True, "안전도어 잠금 상태"),
    IOPoint("vacuum_sensor_1", True, True, "진공 흡착 센서1"),
    IOPoint("high_voltage_output_1", True, True, "고전압 구동 출력 (위험 출력 예시)"),
]
