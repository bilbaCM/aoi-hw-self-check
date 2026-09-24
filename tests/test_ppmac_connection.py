from __future__ import annotations

import socket
import threading
import unittest
from typing import Callable

from aoi_hw_check.integrations.ppmac.connection import PmacAsciiConnection, PmacError


class _MockPmacServer:
    """테스트용 최소 PMAC ASCII 서버 — "\\r"로 끝나는 명령을 받아
    handler(command) -> (body, ok)를 호출하고 ACK(0x06)/BELL(0x07)로 응답한다."""

    def __init__(
        self,
        handler: Callable[[str], tuple[str, bool]],
        ack_char: str = "\x06",
        error_char: str = "\x07",
    ):
        self._handler = handler
        self._ack_char = ack_char
        self._error_char = error_char
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.bind(("127.0.0.1", 0))
        self._server_sock.listen(1)
        self.port = self._server_sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        try:
            conn, _ = self._server_sock.accept()
        except OSError:
            return
        with conn:
            buffer = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\r" in buffer:
                    line, buffer = buffer.split(b"\r", 1)
                    command = line.decode("ascii")
                    body, ok = self._handler(command)
                    terminator = self._ack_char if ok else self._error_char
                    conn.sendall((body + terminator).encode("ascii"))

    def close(self) -> None:
        self._server_sock.close()


class PmacAsciiConnectionTest(unittest.TestCase):
    def test_query_parses_numeric_response(self) -> None:
        server = _MockPmacServer(lambda command: ("123.456", True))
        try:
            connection = PmacAsciiConnection("127.0.0.1", server.port, timeout_sec=2.0)
            self.assertEqual(connection.query("Motor[1].ActPos"), 123.456)
        finally:
            connection.close()
            server.close()

    def test_error_terminator_raises(self) -> None:
        server = _MockPmacServer(lambda command: ("ERR003", False))
        try:
            connection = PmacAsciiConnection("127.0.0.1", server.port, timeout_sec=2.0)
            with self.assertRaises(PmacError):
                connection.send_command("BadCommand")
        finally:
            connection.close()
            server.close()

    def test_non_numeric_query_response_raises(self) -> None:
        server = _MockPmacServer(lambda command: ("not-a-number", True))
        try:
            connection = PmacAsciiConnection("127.0.0.1", server.port, timeout_sec=2.0)
            with self.assertRaises(PmacError):
                connection.query("Motor[1].ActPos")
        finally:
            connection.close()
            server.close()

    def test_jog_to_position_sends_expected_command(self) -> None:
        received: list[str] = []

        def handler(command: str) -> tuple[str, bool]:
            received.append(command)
            return ("", True)

        server = _MockPmacServer(handler)
        try:
            connection = PmacAsciiConnection("127.0.0.1", server.port, timeout_sec=2.0)
            connection.jog_to_position(1, 250.0)
            self.assertEqual(received, ["#1J=250.0"])
        finally:
            connection.close()
            server.close()

    def test_custom_terminators_are_respected(self) -> None:
        server = _MockPmacServer(lambda command: ("42", True), ack_char="A", error_char="E")
        try:
            connection = PmacAsciiConnection(
                "127.0.0.1",
                server.port,
                timeout_sec=2.0,
                ack_char="A",
                error_char="E",
            )
            self.assertEqual(connection.query("Motor[1].ActPos"), 42.0)
        finally:
            connection.close()
            server.close()


if __name__ == "__main__":
    unittest.main()
