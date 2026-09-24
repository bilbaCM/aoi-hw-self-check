from __future__ import annotations

from abc import ABC, abstractmethod

from aoi_hw_check.checks.pc_check.models import PCState


class PCStateCollector(ABC):
    """실제 구현은 OS/장치 API를 호출해 PC 상태를 수집한다 (추후 교체 대상)."""

    @abstractmethod
    def collect(self) -> PCState: ...


class MockPCStateCollector(PCStateCollector):
    """실제 OS/장치 API 연동 전까지 사용하는 고정 샘플 Mock 구현체."""

    def __init__(self, state: PCState | None = None):
        self._state = state or self._default_state()

    def collect(self) -> PCState:
        return self._state

    @staticmethod
    def _default_state() -> PCState:
        return PCState(
            os={"version": "Windows 10 Enterprise", "build": "19045"},
            cpu={"model": "Intel i7-9700", "usage_percent": 12},
            memory={"total_gb": 32, "used_gb": 9},
            disk={"c_free_gb": 210, "d_free_gb": 480},
            services={"AOI_VisionService": "Running", "AOI_MotionService": "Running"},
            devices={"frame_grabber": "OK", "io_board": "OK"},
            communication={"plc_link": "Connected", "dafm_link": "Connected"},
            errors={"event_log_errors_24h": 0},
        )
