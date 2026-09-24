from __future__ import annotations

from typing import Any

from aoi_hw_check.checks.interlock_check.models import InterlockSignalEvent
from aoi_hw_check.checks.interlock_check.runner import InterlockTestRunner
from aoi_hw_check.checks.io_check.client import PLCTestModeClient
from aoi_hw_check.checks.single_unit_check.models import SequenceStepResult
from aoi_hw_check.checks.single_unit_check.runner import SingleUnitSequenceRunner
from aoi_hw_check.integrations.control_program.connection import ControlProgramConnection
from aoi_hw_check.integrations.control_program.protocol import (
    REQUEST_FORCE_IO,
    REQUEST_GET_INTERLOCK_STATUS,
    REQUEST_RUN_TEST_SEQUENCE,
)


class TCPPLCTestModeClient(PLCTestModeClient):
    """C# 제어 프로그램(CC-Link 마스터 보유)에 TCP로 I/O 강제 구동을 요청한다."""

    def __init__(self, connection: ControlProgramConnection):
        self._connection = connection

    def test_io_point(self, io_id: str, forced_input_value: Any) -> Any:
        response = self._connection.request(
            {
                "type": REQUEST_FORCE_IO,
                "io_id": io_id,
                "forced_input_value": forced_input_value,
            }
        )
        return response["observed_output_value"]


class TCPSingleUnitSequenceRunner(SingleUnitSequenceRunner):
    """C# 제어 프로그램에 TCP로 안전 인터락 시험 시퀀스 실행을 요청한다."""

    def __init__(self, connection: ControlProgramConnection):
        self._connection = connection

    def run_sequence(self) -> list[SequenceStepResult]:
        response = self._connection.request({"type": REQUEST_RUN_TEST_SEQUENCE})
        return [
            SequenceStepResult(
                step_id=step["step_id"],
                completed=step["completed"],
                abnormal_stop=step["abnormal_stop"],
                detail=step.get("detail", ""),
            )
            for step in response["steps"]
        ]


class TCPInterlockTestRunner(InterlockTestRunner):
    """C# 제어 프로그램에 TCP로 연동 신호 상태(수신·순서·지연)를 요청한다."""

    def __init__(self, connection: ControlProgramConnection):
        self._connection = connection

    def run_interlock_test(self) -> list[InterlockSignalEvent]:
        response = self._connection.request({"type": REQUEST_GET_INTERLOCK_STATUS})
        return [
            InterlockSignalEvent(
                signal_id=event["signal_id"],
                sequence_order=event["sequence_order"],
                response_delay_ms=event["response_delay_ms"],
                received=event["received"],
            )
            for event in response["events"]
        ]
