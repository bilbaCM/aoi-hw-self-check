from __future__ import annotations

from abc import ABC, abstractmethod

from aoi_hw_check.checks.motion_tuning_check.models import MotionTuningState


class MotionTuningRunner(ABC):
    """실제 구현은 축을 반복 이동시켜 위치편차·오버슈트·정착시간을 측정한다."""

    @abstractmethod
    def run_tuning_sequence(self) -> MotionTuningState: ...


class MockMotionTuningRunner(MotionTuningRunner):
    """실제 모션 컨트롤러 연동 전까지 사용하는 Mock 구현체."""

    def __init__(self, state: MotionTuningState | None = None):
        self._state = state or self._default_state()

    def run_tuning_sequence(self) -> MotionTuningState:
        return self._state

    @staticmethod
    def _default_state() -> MotionTuningState:
        return MotionTuningState(
            axes={
                "X": {
                    "position_deviation_um": 1.2,
                    "overshoot_percent": 3.5,
                    "settling_time_ms": 85.0,
                },
                "Y": {
                    "position_deviation_um": 1.4,
                    "overshoot_percent": 4.0,
                    "settling_time_ms": 90.0,
                },
                "Z": {
                    "position_deviation_um": 0.8,
                    "overshoot_percent": 2.1,
                    "settling_time_ms": 60.0,
                },
            }
        )
