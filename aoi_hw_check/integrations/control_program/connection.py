from __future__ import annotations

from aoi_hw_check.integrations.control_program.protocol import RESPONSE_ERROR
from aoi_hw_check.integrations.ndjson_connection import NDJSONConnection


class ControlProgramError(RuntimeError):
    """제어 프로그램과의 통신 오류 또는 오류 응답."""


class ControlProgramConnection(NDJSONConnection):
    """C# 제어 프로그램과의 TCP 연결 — NDJSON 요청/응답을 1건씩 주고받는다."""

    def __init__(self, host: str, port: int, timeout_sec: float = 5.0):
        super().__init__(
            host,
            port,
            timeout_sec=timeout_sec,
            error_type=RESPONSE_ERROR,
            error_cls=ControlProgramError,
        )
