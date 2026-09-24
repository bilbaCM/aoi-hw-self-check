from __future__ import annotations

import json
import socket
import threading
import uuid
from typing import Any


class NDJSONConnection:
    """줄바꿈 구분 JSON(NDJSON) 기반 TCP 요청/응답 연결의 공통 구현.

    요청 1건 = 응답 1건을 동기로 주고받는 외부 프로그램 연동(C# 제어
    프로그램, C++ 검사 프로그램 등)이 공유하는 저수준 로직이다. 연결은
    최초 요청 시 지연 생성되고, 여러 요청이 겹치지 않도록 락으로 직렬화한다.

    error_type/error_cls로 "오류 응답"을 나타내는 type 값과, 발생시킬
    예외 클래스를 대상 시스템별로 다르게 지정한다.
    """

    def __init__(
        self,
        host: str,
        port: int,
        timeout_sec: float = 5.0,
        error_type: str = "error",
        error_cls: type[Exception] = RuntimeError,
    ):
        self._host = host
        self._port = port
        self._timeout_sec = timeout_sec
        self._error_type = error_type
        self._error_cls = error_cls
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
                raise self._error_cls(f"통신 오류: {exc}") from exc

            if not line:
                self.close()
                raise self._error_cls("연결이 끊어졌습니다")

            response = json.loads(line)

        if response.get("request_id") != payload["request_id"]:
            raise self._error_cls(
                "응답의 request_id가 요청과 일치하지 않습니다 (프로토콜 동기화 오류)"
            )
        if response.get("type") == self._error_type:
            raise self._error_cls(response.get("message", "알 수 없는 오류"))
        return response
