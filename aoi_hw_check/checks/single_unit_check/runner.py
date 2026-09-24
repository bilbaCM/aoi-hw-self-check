from __future__ import annotations

from abc import ABC, abstractmethod

from aoi_hw_check.checks.single_unit_check.models import SequenceStepResult


class SingleUnitSequenceRunner(ABC):
    """실제 구현은 안전 인터락이 걸린 PLC 시험 시퀀스를 구동하고 스텝별 결과를 기록한다."""

    @abstractmethod
    def run_sequence(self) -> list[SequenceStepResult]: ...


class MockSingleUnitSequenceRunner(SingleUnitSequenceRunner):
    """실제 PLC 시퀀스 연동 전까지 사용하는 Mock 구현체."""

    def __init__(self, steps: list[SequenceStepResult] | None = None):
        self._steps = steps or self._default_steps()

    def run_sequence(self) -> list[SequenceStepResult]:
        return self._steps

    @staticmethod
    def _default_steps() -> list[SequenceStepResult]:
        return [
            SequenceStepResult(step_id="원점 복귀", completed=True, abnormal_stop=False),
            SequenceStepResult(step_id="Stage 이동", completed=True, abnormal_stop=False),
            SequenceStepResult(step_id="카메라 촬영 시퀀스", completed=True, abnormal_stop=False),
            SequenceStepResult(step_id="복귀·정지", completed=True, abnormal_stop=False),
        ]
