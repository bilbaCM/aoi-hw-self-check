from __future__ import annotations

import json
import socket
import threading
import unittest
from typing import Callable

from aoi_hw_check.integrations.inspection_program.clients import (
    TCPOpticalCommCollector,
    TCPScanCollector,
)
from aoi_hw_check.integrations.inspection_program.connection import (
    InspectionProgramConnection,
    InspectionProgramError,
)


class _MockInspectionProgramServer:
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


class TCPScanCollectorTest(unittest.TestCase):
    def test_parses_full_scan_result(self) -> None:
        def handler(request: dict) -> dict:
            return {
                "type": "run_reference_scan_result",
                "request_id": request["request_id"],
                "af_z_map": {
                    "pin_heights": [{"pin_id": "PIN1", "z_um": 100.0}],
                    "tracks": {
                        "Micro": {
                            "samples": [
                                {
                                    "x_mm": 0.0,
                                    "y_mm": 0.0,
                                    "z_um": 50.0,
                                    "beam_position_error_um": 0.05,
                                }
                            ]
                        }
                    },
                },
                "scan_images": {
                    "focus_measures": {"Micro": 980.0},
                    "gantry_x_axis_samples": [
                        {"stage_position_mm": 0.0, "x_um": 0.0, "y_um": 0.0}
                    ],
                    "gantry_y_axis_samples": [
                        {"stage_position_mm": 0.0, "x_um": 0.0, "y_um": 0.0}
                    ],
                },
            }

        server = _MockInspectionProgramServer(handler)
        try:
            connection = InspectionProgramConnection("127.0.0.1", server.port, timeout_sec=2.0)
            collector = TCPScanCollector(connection)
            scan_result = collector.run_reference_scan()

            self.assertEqual(scan_result.af_z_map.pin_heights[0].pin_id, "PIN1")
            self.assertEqual(scan_result.af_z_map.tracks["Micro"].samples[0].z_um, 50.0)
            self.assertEqual(scan_result.scan_images.focus_measures["Micro"], 980.0)
            self.assertEqual(len(scan_result.scan_images.gantry_x_axis_samples), 1)
        finally:
            connection.close()
            server.close()

    def test_error_response_raises(self) -> None:
        def handler(request: dict) -> dict:
            return {"type": "error", "request_id": request["request_id"], "message": "카메라 오류"}

        server = _MockInspectionProgramServer(handler)
        try:
            connection = InspectionProgramConnection("127.0.0.1", server.port, timeout_sec=2.0)
            collector = TCPScanCollector(connection)
            with self.assertRaises(InspectionProgramError):
                collector.run_reference_scan()
        finally:
            connection.close()
            server.close()


class TCPOpticalCommCollectorTest(unittest.TestCase):
    def test_parses_channel_responses(self) -> None:
        def handler(request: dict) -> dict:
            return {
                "type": "run_optical_comm_test_result",
                "request_id": request["request_id"],
                "channels": {
                    "Micro_CH1": {
                        "communication_ok": True,
                        "samples": [
                            {"light_level": 0.0, "gray_value": 10.0},
                            {"light_level": 100.0, "gray_value": 240.0},
                        ],
                    }
                },
            }

        server = _MockInspectionProgramServer(handler)
        try:
            connection = InspectionProgramConnection("127.0.0.1", server.port, timeout_sec=2.0)
            collector = TCPOpticalCommCollector(connection)
            state = collector.collect()

            channel = state.channels["Micro_CH1"]
            self.assertTrue(channel.communication_ok)
            self.assertEqual(len(channel.samples), 2)
            self.assertEqual(channel.samples[1].gray_value, 240.0)
        finally:
            connection.close()
            server.close()


if __name__ == "__main__":
    unittest.main()
