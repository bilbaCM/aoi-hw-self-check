from __future__ import annotations

from typing import Any

from aoi_hw_check.checks.c_class_scan.collector import ScanCollector
from aoi_hw_check.checks.c_class_scan.models import (
    AFZMap,
    AFZSample,
    AFZTrack,
    CellCoordinateSample,
    PinHeightSample,
    ScanImageSet,
    ScanResult,
)
from aoi_hw_check.checks.optical_comm_check.collector import OpticalCommCollector
from aoi_hw_check.checks.optical_comm_check.models import (
    ChannelResponse,
    GrayResponseSample,
    OpticalCommState,
)
from aoi_hw_check.integrations.inspection_program.connection import InspectionProgramConnection
from aoi_hw_check.integrations.inspection_program.protocol import (
    REQUEST_RUN_OPTICAL_COMM_TEST,
    REQUEST_RUN_REFERENCE_SCAN,
)


class TCPScanCollector(ScanCollector):
    """C++ 검사 프로그램에 TCP로 기준 시료 1회 Scan을 요청한다."""

    def __init__(self, connection: InspectionProgramConnection):
        self._connection = connection

    def run_reference_scan(self) -> ScanResult:
        response = self._connection.request({"type": REQUEST_RUN_REFERENCE_SCAN})
        return _parse_scan_result(response)


class TCPOpticalCommCollector(OpticalCommCollector):
    """C++ 검사 프로그램에 TCP로 광량 단계별 채널 응답을 요청한다."""

    def __init__(self, connection: InspectionProgramConnection):
        self._connection = connection

    def collect(self) -> OpticalCommState:
        response = self._connection.request({"type": REQUEST_RUN_OPTICAL_COMM_TEST})
        return _parse_optical_comm_state(response)


def _parse_scan_result(response: dict[str, Any]) -> ScanResult:
    af_z_map_data = response["af_z_map"]
    pin_heights = [
        PinHeightSample(pin_id=p["pin_id"], z_um=p["z_um"])
        for p in af_z_map_data.get("pin_heights", [])
    ]
    tracks = {
        inspector_id: AFZTrack(
            inspector_id=inspector_id,
            samples=[
                AFZSample(
                    x_mm=s["x_mm"],
                    y_mm=s["y_mm"],
                    z_um=s["z_um"],
                    beam_position_error_um=s["beam_position_error_um"],
                )
                for s in track["samples"]
            ],
        )
        for inspector_id, track in af_z_map_data.get("tracks", {}).items()
    }
    af_z_map = AFZMap(pin_heights=pin_heights, tracks=tracks)

    scan_images_data = response["scan_images"]
    scan_images = ScanImageSet(
        focus_measures=dict(scan_images_data.get("focus_measures", {})),
        gantry_x_axis_samples=[
            _parse_cell_coordinate_sample(s)
            for s in scan_images_data.get("gantry_x_axis_samples", [])
        ],
        gantry_y_axis_samples=[
            _parse_cell_coordinate_sample(s)
            for s in scan_images_data.get("gantry_y_axis_samples", [])
        ],
    )

    return ScanResult(af_z_map=af_z_map, scan_images=scan_images)


def _parse_cell_coordinate_sample(data: dict[str, Any]) -> CellCoordinateSample:
    return CellCoordinateSample(
        stage_position_mm=data["stage_position_mm"], x_um=data["x_um"], y_um=data["y_um"]
    )


def _parse_optical_comm_state(response: dict[str, Any]) -> OpticalCommState:
    channels = {
        channel_id: ChannelResponse(
            channel_id=channel_id,
            communication_ok=data["communication_ok"],
            samples=[
                GrayResponseSample(light_level=s["light_level"], gray_value=s["gray_value"])
                for s in data.get("samples", [])
            ],
        )
        for channel_id, data in response.get("channels", {}).items()
    }
    return OpticalCommState(channels=channels)
