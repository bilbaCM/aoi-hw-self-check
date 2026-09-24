from __future__ import annotations

import json
import socket
import threading
import uuid
from typing import Any

from aoi_hw_check.integrations.control_program.protocol import RESPONSE_ERROR


class ControlProgramError(RuntimeError):
    """제어 프로그램과의 통신 오류 또는 오류 응답."""


class ControlProgramConnection:
    """C# 제어 프로그램과의 TCP 연결 — NDJSON 요청/응답을 1건씩 주고받는다.

    연결은 최초 요청 시 지연 생성되고 이후 재사용된다. 여러 체크 모듈이
    같은 연결(같은 제어 프로그램)을 공유할 수 있도록 락으로 요청을
    직렬화한다.
    """

    def __init__(self, host: str, port: int, timeout_sec: float = 5.0):
        self._host = host
        self._port = port
        self._timeout_sec = timeout_sec
        self._sock: socket.socket | None = None
        self._reader: Any = None
        self._lock = threading.Lock()

    def _ensure_connected(self) -> None:
        if self._sock is not None:
            return
        sock = socket.create_connection((self._host, self._port), timeout=self._timeout_sec)
        sock.settimeout(self._timeout_sec)
        self._sock = sock
        self._reader = sock.makefile("r", encoding="utf-8", newline="\n")

    def close(self) -> None:
        with self._lock:
            if self._sock is not None:
                self._sock.close()
                self._sock = None
                self._reader = None

    def request(self, message: dict[str, Any]) -> dict[str, Any]:
        """요청 메시지를 보내고 응답 메시지를 반환한다. 오류 응답은 예외로 변환한다."""
        payload = dict(message)
        payload.setdefault("request_id", str(uuid.uuid4()))

        with self._lock:
            self._ensure_connected()
            assert self._sock is not None and self._reader is not None
            try:
                self._sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
                line = self._reader.readline()
            except OSError as exc:
                self.close()
                raise ControlProgramError(f"제어 프로그램 통신 오류: {exc}") from exc

            if not line:
                self.close()
                raise ControlProgramError("제어 프로그램과의 연결이 끊어졌습니다")

            response = json.loads(line)

        if response.get("request_id") != payload["request_id"]:
            raise ControlProgramError(
                "응답의 request_id가 요청과 일치하지 않습니다 (프로토콜 동기화 오류)"
            )
        if response.get("type") == RESPONSE_ERROR:
            raise ControlProgramError(response.get("message", "알 수 없는 오류"))
        return response
