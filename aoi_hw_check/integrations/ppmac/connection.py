from __future__ import annotations

import socket
import threading


class PmacError(RuntimeError):
    """PPMAC과의 통신 오류 또는 오류 응답."""


class PmacAsciiConnection:
    """Power PMAC Ethernet ASCII 명령 채널(관례상 기본 포트 1025) 클라이언트.

    명령을 캐리지리턴("\\r")으로 종료해 보내고, 응답은 종료 문자가 나올
    때까지 읽는다. PMAC ASCII 프로토콜은 정상 응답 종료를 ACK(0x06),
    오류를 BELL(0x07)로 표시하는 것이 일반적 관례이나, 실제 펌웨어/설정에
    따라 다를 수 있어 실기 연결 전 검증이 필요하다 (TBD) — 이 클래스는
    그 값들을 생성자 인자로 바꿀 수 있게 해 둔다.
    """

    DEFAULT_ACK_CHAR = "\x06"
    DEFAULT_ERROR_CHAR = "\x07"

    def __init__(
        self,
        host: str,
        port: int = 1025,
        timeout_sec: float = 5.0,
        ack_char: str = DEFAULT_ACK_CHAR,
        error_char: str = DEFAULT_ERROR_CHAR,
    ):
        self._host = host
        self._port = port
        self._timeout_sec = timeout_sec
        self._ack_char = ack_char
        self._error_char = error_char
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

    def _ensure_connected(self) -> None:
        if self._sock is not None:
            return
        sock = socket.create_connection((self._host, self._port), timeout=self._timeout_sec)
        sock.settimeout(self._timeout_sec)
        self._sock = sock

    def close(self) -> None:
        with self._lock:
            if self._sock is not None:
                self._sock.close()
                self._sock = None

    def send_command(self, command: str) -> str:
        """PMAC ASCII 명령 1건을 보내고 응답 본문(ACK/BELL 제외)을 반환한다."""
        with self._lock:
            self._ensure_connected()
            assert self._sock is not None
            try:
                self._sock.sendall((command + "\r").encode("ascii"))
                raw = self._read_until_terminator()
            except OSError as exc:
                self.close()
                raise PmacError(f"PPMAC 통신 오류: {exc}") from exc

        is_error = raw.endswith(self._error_char)
        body = raw.rstrip(self._ack_char).rstrip(self._error_char).strip()
        if is_error:
            raise PmacError(f"PPMAC 명령 오류: {command!r} -> {body!r}")
        return body

    def _read_until_terminator(self) -> str:
        assert self._sock is not None
        ack = self._ack_char.encode("ascii")
        err = self._error_char.encode("ascii")
        buffer = b""
        while True:
            chunk = self._sock.recv(4096)
            if not chunk:
                self.close()
                raise PmacError("PPMAC과의 연결이 끊어졌습니다")
            buffer += chunk
            if buffer.endswith(ack) or buffer.endswith(err):
                break
        return buffer.decode("ascii", errors="replace")

    def query(self, variable: str) -> float:
        """PMAC 글로벌 변수(예: "Motor[1].ActPos") 값을 조회해 float로 반환한다."""
        response = self.send_command(variable)
        try:
            return float(response)
        except ValueError as exc:
            raise PmacError(f"숫자로 해석할 수 없는 응답: {variable!r} -> {response!r}") from exc

    def jog_to_position(self, motor: int, position: float) -> None:
        """모터를 절대 위치로 조그 이동시킨다 (PMAC 표준 조그 명령 "#nJ=pos").

        실제 좌표 단위(카운트 vs 엔지니어링 단위)와 속도/가속도는 PPMAC
        쪽 설정에 따라 다르므로 실기 검증이 필요하다 (TBD).
        """
        self.send_command(f"#{motor}J={position}")
