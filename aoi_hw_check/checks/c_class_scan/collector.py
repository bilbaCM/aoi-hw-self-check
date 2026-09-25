from __future__ import annotations

from abc import ABC, abstractmethod

from aoi_hw_check.checks.c_class_scan.models import (
    AFZMap,
    AFZSample,
    AFZTrack,
    CellCoordinateSample,
    PinHeightSample,
    ScanImageSet,
    ScanResult,
)

# Mock에서 흉내 낼 인스펙터 카메라 번호 — 실제 대수는 설비마다 다르며, 인스펙터
# PC 1대당 카메라 1대 기준이다. 여기서는 대표로 3대를 가정한다.
_INSPECTOR_IDS = ("INS1", "INS2", "INS3")


class ScanCollector(ABC):
    """실제 구현은 기준 시료 1회 Scan을 구동해 AF Z 추종 맵과 스캔 영상을 동시에 취득한다.

    영상은 설비를 구동해야만 취득되고(Scan 1회 = 셋업 시간), 단독 취득이
    불가능하므로 이 Scan 1회의 결과를 C분류 5개 항목이 함께 사용한다.
    """

    @abstractmethod
    def run_reference_scan(self) -> ScanResult: ...


class MockScanCollector(ScanCollector):
    """실제 설비/DAFM/영상 SDK 연동 전까지 사용하는 Mock — 정상(양품) 시료를 가정한다."""

    def __init__(self, scan_result: ScanResult | None = None):
        self._scan_result = scan_result or self._default_scan_result()

    def run_reference_scan(self) -> ScanResult:
        return self._scan_result

    @staticmethod
    def _default_scan_result() -> ScanResult:
        def flat_track(inspector_id: str) -> AFZTrack:
            # x/y 둘 다 변화하는 2D 그리드로 샘플링한다 — 한 방향으로만 샘플링하면
            # (x,y) 투영이 한 직선 위에 놓여 평면 피팅 연립방정식이 특이(singular)해진다.
            samples = [
                AFZSample(
                    x_mm=float(x),
                    y_mm=float(y),
                    z_um=50.0 + 0.01 * x + 0.005 * y,
                    beam_position_error_um=0.05,
                )
                for x in (0, 10, 20)
                for y in (0, 10)
            ]
            return AFZTrack(inspector_id=inspector_id, samples=samples)

        af_z_map = AFZMap(
            pin_heights=[
                PinHeightSample("PIN1", 100.0),
                PinHeightSample("PIN2", 100.3),
                PinHeightSample("PIN3", 99.8),
                PinHeightSample("PIN4", 100.1),
            ],
            tracks={inspector_id: flat_track(inspector_id) for inspector_id in _INSPECTOR_IDS},
        )

        def axis_line(dx: float, dy: float) -> list[CellCoordinateSample]:
            return [
                CellCoordinateSample(
                    stage_position_mm=i * 50.0,
                    x_um=i * dx,
                    y_um=i * dy,
                )
                for i in range(5)
            ]

        scan_images = ScanImageSet(
            focus_measures={"INS1": 980.0, "INS2": 875.0, "INS3": 910.0},
            gantry_x_axis_samples=axis_line(dx=50.0, dy=0.0),
            gantry_y_axis_samples=axis_line(dx=0.0, dy=50.0),
        )

        return ScanResult(af_z_map=af_z_map, scan_images=scan_images)
