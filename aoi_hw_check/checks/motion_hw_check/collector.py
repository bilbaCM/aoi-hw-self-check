from __future__ import annotations

from abc import ABC, abstractmethod

from aoi_hw_check.checks.motion_hw_check.models import MotionHWState


class MotionHWCollector(ABC):
    """실제 구현은 제어기(PLC/모션 컨트롤러)에서 축별 Encoder/PWM/I/O 값을 판독한다."""

    @abstractmethod
    def collect(self) -> MotionHWState: ...


class MockMotionHWCollector(MotionHWCollector):
    """실제 제어기 연동 전까지 사용하는 고정 샘플 Mock 구현체."""

    def __init__(self, state: MotionHWState | None = None):
        self._state = state or self._default_state()

    def collect(self) -> MotionHWState:
        return self._state

    @staticmethod
    def _default_state() -> MotionHWState:
        return MotionHWState(
            axes={
                "X": {"encoder_count": 102345, "pwm_duty_percent": 42.5, "io_home_sensor": 1},
                "Y": {"encoder_count": 98765, "pwm_duty_percent": 39.8, "io_home_sensor": 1},
                "Z": {"encoder_count": 5120, "pwm_duty_percent": 15.2, "io_home_sensor": 0},
            }
        )
