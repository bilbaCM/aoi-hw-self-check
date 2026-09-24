from __future__ import annotations

import json
import socket
import threading
import unittest
from typing import Callable

from aoi_hw_check.integrations.control_program.clients import (
    TCPInterlockTestRunner,
    TCPPLCTestModeClient,
    TCPSingleUnitSequenceRunner,
)
from aoi_hw_check.integrations.control_program.connection import (
    ControlProgramConnection,
    ControlProgramError,
)


class _MockControlProgramServer:
    """테스트용 최소 TCP 서버 — 요청 1건마다 handler를 호출해 응답을 만든다."""

    def __init__(self, handler: Callable[[dict], dict]):
        self._handler = handler
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
            reader = conn.makefile("r", encoding="utf-8", newline="\n")
            while True:
                line = reader.readline()
                if not line:
                    break
                request = json.loads(line)
                response = self._handler(request)
                conn.sendall((json.dumps(response) + "\n").encode("utf-8"))

    def close(self) -> None:
        self._server_sock.close()


class ControlProgramConnectionTest(unittest.TestCase):
    def test_request_response_round_trip(self) -> None:
        def handler(request: dict) -> dict:
            return {
                "type": "force_io_result",
                "request_id": request["request_id"],
                "observed_output_value": True,
            }

        server = _MockControlProgramServer(handler)
        try:
            connection = ControlProgramConnection("127.0.0.1", server.port, timeout_sec=2.0)
            response = connection.request(
                {"type": "force_io", "io_id": "x", "forced_input_value": True}
            )
            self.assertEqual(response["observed_output_value"], True)
        finally:
            connection.close()
            server.close()

    def test_error_response_raises(self) -> None:
        def handler(request: dict) -> dict:
            return {"type": "error", "request_id": request["request_id"], "message": "장치 없음"}

        server = _MockControlProgramServer(handler)
        try:
            connection = ControlProgramConnection("127.0.0.1", server.port, timeout_sec=2.0)
            with self.assertRaises(ControlProgramError):
                connection.request({"type": "force_io", "io_id": "x", "forced_input_value": True})
        finally:
            connection.close()
            server.close()

    def test_mismatched_request_id_raises(self) -> None:
        def handler(request: dict) -> dict:
            return {
                "type": "force_io_result",
                "request_id": "wrong-id",
                "observed_output_value": True,
            }

        server = _MockControlProgramServer(handler)
        try:
            connection = ControlProgramConnection("127.0.0.1", server.port, timeout_sec=2.0)
            with self.assertRaises(ControlProgramError):
                connection.request({"type": "force_io"})
        finally:
            connection.close()
            server.close()

    def test_connection_closed_by_server_raises(self) -> None:
        server = _MockControlProgramServer(lambda request: {})
        try:
            connection = ControlProgramConnection("127.0.0.1", server.port, timeout_sec=2.0)
            server.close()
            with self.assertRaises(ControlProgramError):
                connection.request({"type": "force_io"})
        finally:
            connection.close()
            server.close()


class TCPClientAdapterTest(unittest.TestCase):
    def test_plc_test_mode_client_returns_observed_value(self) -> None:
        def handler(request: dict) -> dict:
            return {
                "type": "force_io_result",
                "request_id": request["request_id"],
                "observed_output_value": request["forced_input_value"],
            }

        server = _MockControlProgramServer(handler)
        try:
            connection = ControlProgramConnection("127.0.0.1", server.port, timeout_sec=2.0)
            client = TCPPLCTestModeClient(connection)
            self.assertEqual(client.test_io_point("io1", True), True)
        finally:
            connection.close()
            server.close()

    def test_single_unit_sequence_runner_parses_steps(self) -> None:
        def handler(request: dict) -> dict:
            return {
                "type": "run_test_sequence_result",
                "request_id": request["request_id"],
                "steps": [
                    {
                        "step_id": "원점 복귀",
                        "completed": True,
                        "abnormal_stop": False,
                        "detail": "",
                    }
                ],
            }

        server = _MockControlProgramServer(handler)
        try:
            connection = ControlProgramConnection("127.0.0.1", server.port, timeout_sec=2.0)
            runner = TCPSingleUnitSequenceRunner(connection)
            steps = runner.run_sequence()

            self.assertEqual(steps[0].step_id, "원점 복귀")
            self.assertTrue(steps[0].completed)
            self.assertFalse(steps[0].abnormal_stop)
        finally:
            connection.close()
            server.close()

    def test_interlock_runner_parses_events(self) -> None:
        def handler(request: dict) -> dict:
            return {
                "type": "get_interlock_status_result",
                "request_id": request["request_id"],
                "events": [
                    {
                        "signal_id": "upstream_ready",
                        "sequence_order": 1,
                        "response_delay_ms": 120.0,
                        "received": True,
                    }
                ],
            }

        server = _MockControlProgramServer(handler)
        try:
            connection = ControlProgramConnection("127.0.0.1", server.port, timeout_sec=2.0)
            runner = TCPInterlockTestRunner(connection)
            events = runner.run_interlock_test()

            self.assertEqual(events[0].signal_id, "upstream_ready")
            self.assertEqual(events[0].response_delay_ms, 120.0)
        finally:
            connection.close()
            server.close()


if __name__ == "__main__":
    unittest.main()
